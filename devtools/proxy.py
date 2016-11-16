#!/usr/bin/env python3

import argparse
import asyncio
import math
import os
import re
import sys
from functools import partial
from pathlib import Path

import aiohttp
from aiohttp.web import Application, HTTPBadGateway, Response, WebSocketResponse, WSMsgType, json_response

from devtools import __version__

py_installer = getattr(sys, 'frozen', False)  # https://pythonhosted.org/PyInstaller/runtime-information.html

with_ujson = os.environ.get('DTP_UJSON', '').lower() == 'true'
if with_ujson:
    import ujson as json
else:
    import json

with_uvloop = os.environ.get('DTP_UVLOOP', '').lower() == 'true'
if with_uvloop:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

if not py_installer:
    DEVTOOLS_PROXY_PATH = str(Path(__file__).resolve())
    CHROME_WRAPPER_PATH = str(Path(__file__, '../chrome-wrapper.sh').resolve())

_BITS = 31


def encode_id_raw(client_id, request_id, max_request_id, bits_for_client_id):
    if request_id > max_request_id:
        raise OverflowError

    res = (client_id << _BITS - bits_for_client_id) | request_id

    return res


def decode_id_raw(encoded_id, max_request_id, bits_for_client_id):
    client_id = encoded_id >> (_BITS - bits_for_client_id)
    request_id = encoded_id & max_request_id

    return client_id, request_id


async def the_handler(request):
    response = WebSocketResponse()

    handler = ws_handler if response.can_prepare(request) else proxy_handler
    return await handler(request)


async def ws_handler(request):
    app = request.app
    tab_id = request.path_qs.split('/')[-1]
    tabs = app['tabs']

    if tabs.get(tab_id) is None:
        app['tabs'][tab_id] = {}
        # https://aiohttp.readthedocs.io/en/v1.0.0/faq.html#how-to-receive-an-incoming-events-from-different-sources-in-parallel
        task = app.loop.create_task(ws_browser_handler(request))
        app['tasks'].append(task)

    return await ws_client_handler(request)


async def ws_client_handler(request):
    app = request.app
    path_qs = request.path_qs
    tab_id = path_qs.split('/')[-1]
    url = "ws://%s:%d%s" % (app['chrome_host'], app['chrome_port'], path_qs)
    encode_id = app['f']['encode_id']
    client_id = len(app['clients'])
    log_prefix = "[CLIENT %d]" % client_id

    ws_client = WebSocketResponse()
    await ws_client.prepare(request)

    if client_id >= app['max_clients']:
        print(log_prefix, 'CONNECTION FAILED')
        return ws_client

    app['clients'][ws_client] = {
        'id': client_id,
        'tab_id': tab_id
    }

    print(log_prefix, 'CONNECTED')

    if app['tabs'][tab_id].get('ws') is None or app['tabs'][tab_id]['ws'].closed:
        session = aiohttp.ClientSession(loop=app.loop)
        app['sessions'].append(session)
        try:
            app['tabs'][tab_id]['ws'] = await session.ws_connect(url)
        except aiohttp.WSServerHandshakeError:
            print(log_prefix, 'CONNECTION ERROR: %s' % tab_id)
            return ws_client

    async for msg in ws_client:
        if msg.type == WSMsgType.TEXT:
            if app['tabs'][tab_id]['ws'].closed:
                print(log_prefix, 'RECONNECTED')
                break
            data = msg.json(loads=json.loads)

            data['id'] = encode_id(client_id, data['id'])
            print(log_prefix, '>>', data)

            app['tabs'][tab_id]['ws'].send_json(data, dumps=json.dumps)
    else:
        print(log_prefix, 'DISCONNECTED')
        return ws_client


async def ws_browser_handler(request):
    log_prefix = '<<'
    app = request.app
    tab_id = request.path_qs.split('/')[-1]
    decode_id = app['f']['decode_id']

    timeout = 10
    interval = 0.1

    for i in range(math.ceil(timeout / interval)):
        if app['tabs'][tab_id].get('ws') is not None and not app['tabs'][tab_id]['ws'].closed:
            print("[BROWSER %s]" % tab_id, 'CONNECTED')
            break
        await asyncio.sleep(interval)
    else:
        print("[BROWSER %s]" % tab_id, 'DISCONNECTED')
        return

    async for msg in app['tabs'][tab_id]['ws']:
        if msg.type == WSMsgType.TEXT:
            data = msg.json(loads=json.loads)
            if data.get('id') is None:
                clients = {k: v for k, v in app['clients'].items() if v.get('tab_id') == tab_id}
                for client in clients.keys():
                    if not client.closed:
                        client_id = app['clients'][client]['id']
                        print('[CLIENT %d]' % client_id, log_prefix, msg.data)
                        client.send_str(msg.data)
            else:
                client_id, request_id = decode_id(data['id'])
                print('[CLIENT %d]' % client_id, log_prefix, data)
                data['id'] = request_id
                ws = next(ws for ws, client in app['clients'].items() if client['id'] == client_id)
                ws.send_json(data, dumps=json.dumps)
    else:
        print("[BROWSER %s]" % tab_id, 'DISCONNECTED')
        return


async def proxy_handler(request):
    app = request.app
    method = request.method
    path_qs = request.path_qs
    session = aiohttp.ClientSession(loop=request.app.loop)
    url = "http://%s:%s%s" % (app['chrome_host'], app['chrome_port'], path_qs)

    print("[HTTP %s] %s" % (method, path_qs))
    try:
        response = await session.request(method, url)
        if request.path in ('/json', '/json/list'):
            data = await response.json(loads=json.loads)

            proxy_host = request.url.host
            proxy_port = request.url.port
            for tab in data:
                for k, v in tab.items():
                    if ":%d/" % app['chrome_port'] in v:
                        tab[k] = app['devtools_pattern'].sub("%s:%s/" % (proxy_host, proxy_port), tab[k])

                if tab.get('id') is None:
                    print('[WARN]', "Got a tab without id (which is improbable): %s" % tab)
                    continue

                devtools_url = "%s:%s/devtools/page/%s" % (proxy_host, proxy_port, tab['id'])
                if tab.get('webSocketDebuggerUrl') is None:
                    tab['webSocketDebuggerUrl'] = "ws://%s" % devtools_url
                if tab.get('devtoolsFrontendUrl') is None:
                    tab['devtoolsFrontendUrl'] = "/devtools/inspector.html?ws=%s" % devtools_url
            body, text = None, json.dumps(data)
        else:
            body, text = await response.read(), None

        return Response(
            body=body,
            text=text,
            status=response.status,
            reason=response.reason,
            headers=response.headers,
        )
    except (aiohttp.errors.ClientOSError, aiohttp.errors.ClientResponseError) as exc:
        return HTTPBadGateway(text=str(exc))
    finally:
        session.close()


async def status_handler(request):
    fields = (
        'chrome_host',
        'chrome_port',
        'debug',
        'internal',
        'max_clients',
        'proxy_hosts',
        'proxy_ports',
        'version',
    )
    data = {k: v for k, v in request.app.items() if k in fields}
    return json_response(data=data, dumps=json.dumps)


async def init(loop, args):
    app = Application(loop=loop)
    app.update(args)

    app['clients'] = {}
    app['tabs'] = {}
    # TODO: Move session and task handling to proper places
    app['sessions'] = []
    app['tasks'] = []

    app.router.add_route('*', '/{path:(?!status.json).*}', the_handler)
    app.router.add_route('*', '/status.json', status_handler)

    handler = app.make_handler()

    # Simplify after Python 3.6 release (with async comprehensions)
    # Simplify it even more when http://bugs.python.org/issue27665 will be ready :)
    srvs = []
    for proxy_port in app['proxy_ports']:
        srv = await loop.create_server(handler, app['proxy_hosts'], proxy_port)
        srvs.append(srv)

    print(
        "DevTools Proxy started at %s:%s\n"
        "Use --remote-debugging-port=%d --remote-debugging-address=%s for Chrome" % (
            app['proxy_hosts'], app['proxy_ports'], app['chrome_port'], app['chrome_host']
        )
    )
    return app, srvs, handler


async def finish(app, srvs, handler):
    for ws in list(app['clients'].keys()) + [tab['ws'] for tab in app['tabs'].values() if tab.get('ws') is not None]:
        if not ws.closed:
            await ws.close()

    for session in app['sessions']:
        if not session.closed:
            await session.close()

    for task in app['tasks']:
        task.cancel()

    await asyncio.sleep(0.1)
    for srv in srvs:
        srv.close()

    await handler.finish_connections()

    for srv in srvs:
        await srv.wait_closed()


def main():
    def bits(x):
        return math.ceil(math.log2(x))

    parser = argparse.ArgumentParser(
        prog='devtools-proxy',
        description='DevTools Proxy'
    )
    parser.add_argument(
        '--host',
        type=str, nargs='+', default=['127.0.0.1'],
        help='Hosts to serve on (default: %(default)r)',
    )
    parser.add_argument(
        '--port',
        type=int, nargs='+', default=[9222],
        help='Ports to serve on (default: %(default)r)',
    )
    parser.add_argument(
        '--chrome-host',
        type=str, default='127.0.0.1',
        help=('Host on which Chrome is running, '
              'it corresponds with --remote-debugging-address Chrome argument (default: %(default)r)'),
    )
    parser.add_argument(
        '--chrome-port',
        type=int, default=12222,
        help=('Port which Chrome remote debugger is listening, '
              'it corresponds with --remote-debugging-port Chrome argument (default: %(default)r)'),
    )
    parser.add_argument(
        '--max-clients',
        type=int, default=2,
        help='Number of clients which proxy can handle during life cycle (default: %(default)r)',
    )
    parser.add_argument(
        '--version',
        action='version',
        version=__version__,
        help='Print DevTools Proxy version',
    )
    parser.add_argument(
        '--debug',
        action='store_true', default=False,
        help='Turn on debug mode (default: %(default)r)',
    )
    args = parser.parse_args()

    bits_for_client_id = bits(args.max_clients)
    max_clients = 2 ** bits_for_client_id
    max_request_id = 2 ** (_BITS - bits_for_client_id) - 1

    arguments = {
        'f': {
            'encode_id': partial(encode_id_raw, max_request_id=max_request_id, bits_for_client_id=bits_for_client_id),
            'decode_id': partial(decode_id_raw, max_request_id=max_request_id, bits_for_client_id=bits_for_client_id),
        },
        'max_clients': max_clients,
        'debug': args.debug,
        'proxy_hosts': args.host,
        'proxy_ports': list(set(args.port)),
        'chrome_host': args.chrome_host,
        'chrome_port': args.chrome_port,
        'devtools_pattern': re.compile(r"(127\.0\.0\.1|localhost|%s):%d/" % (args.chrome_host, args.chrome_port)),
        'internal': {
            'ujson': with_ujson,
            'uvloop': with_uvloop,
        },
        'version': __version__,
    }

    loop = asyncio.get_event_loop()
    if args.debug:
        loop.set_debug(True)

    application, srvs, handler = loop.run_until_complete(init(loop, arguments))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(finish(application, srvs, handler))


if __name__ == '__main__':
    main()
