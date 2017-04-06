#!/usr/bin/env python3

import argparse
import asyncio
import math
import os
import sys
import traceback
import warnings
from pathlib import Path

import aiohttp
from aiohttp.web import Application, HTTPBadGateway, Response, WebSocketResponse, WSMsgType, hdrs, json_response

from devtools import VERSION

with_ujson = os.environ.get('DTP_UJSON', '').lower() == 'true'
if with_ujson:
    import ujson as json
else:
    import json

with_uvloop = os.environ.get('DTP_UVLOOP', '').lower() == 'true'
if with_uvloop:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# https://pythonhosted.org/PyInstaller/runtime-information.html
if not getattr(sys, 'frozen', False):
    CHROME_WRAPPER_PATH = str(Path(__file__, '../chrome-wrapper.sh').resolve())


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
    url = 'ws://{}:{}{}'.format(app['chrome_host'], app['chrome_port'], path_qs)
    encode_id = app['f']['encode_id']
    client_id = len(app['clients'])
    log_prefix = '[CLIENT {}]'.format(client_id)
    log_msg = app['f']['print']

    ws_client = WebSocketResponse()
    await ws_client.prepare(request)

    if client_id >= app['max_clients']:
        log_msg(log_prefix, 'CONNECTION FAILED')
        return ws_client

    app['clients'][ws_client] = {
        'id': client_id,
        'tab_id': tab_id,
        'subscriptions': set(),  # TODO: Move subscriptions to separate entity
    }

    log_msg(log_prefix, 'CONNECTED')

    if app['tabs'][tab_id].get('ws') is None or app['tabs'][tab_id]['ws'].closed:
        session = aiohttp.ClientSession(loop=app.loop)
        app['sessions'].append(session)
        try:
            app['tabs'][tab_id]['ws'] = await session.ws_connect(url)
        except aiohttp.WSServerHandshakeError:
            log_msg(log_prefix, 'CONNECTION ERROR: {}'.format(tab_id))
            return ws_client

    async for msg in ws_client:
        if msg.type == WSMsgType.TEXT:
            if app['tabs'][tab_id]['ws'].closed:
                log_msg(log_prefix, 'RECONNECTED')
                break
            data = msg.json(loads=json.loads)

            data['id'] = encode_id(client_id, data['id'])
            log_msg(log_prefix, '>>', data)

            if data.get('method', '').endswith('.enable'):
                domain = data['method'].split('.')[0]
                app['clients'][ws_client]['subscriptions'].add(domain)
            elif data.get('method', '').endswith('.disable'):
                domain = data['method'].split('.')[0]
                if domain in app['clients'][ws_client]['subscriptions']:
                    app['clients'][ws_client]['subscriptions'].remove(domain)

            app['tabs'][tab_id]['ws'].send_json(data, dumps=json.dumps)
    else:
        log_msg(log_prefix, 'DISCONNECTED')
        return ws_client


async def ws_browser_handler(request):
    log_prefix = '<<'
    app = request.app
    tab_id = request.path_qs.split('/')[-1]
    decode_id = app['f']['decode_id']
    log_msg = app['f']['print']

    timeout = 10
    interval = 0.1

    for i in range(math.ceil(timeout / interval)):
        if app['tabs'][tab_id].get('ws') is not None and not app['tabs'][tab_id]['ws'].closed:
            log_msg('[BROWSER {}]'.format(tab_id), 'CONNECTED')
            break
        await asyncio.sleep(interval)
    else:
        log_msg('[BROWSER {}]'.format(tab_id), 'DISCONNECTED')
        return

    async for msg in app['tabs'][tab_id]['ws']:
        if msg.type == WSMsgType.TEXT:
            data = msg.json(loads=json.loads)
            if data.get('id') is None:
                clients = {
                    k: v for k, v in app['clients'].items()
                    if v.get('tab_id') == tab_id and data.get('method', '').split('.')[0] in v['subscriptions']
                }
                for client in clients.keys():
                    if not client.closed:
                        client_id = app['clients'][client]['id']
                        log_msg('[CLIENT {}]'.format(client_id), log_prefix, msg.data)
                        client.send_str(msg.data)
            else:
                client_id, request_id = decode_id(data['id'])
                log_msg('[CLIENT {}]'.format(client_id), log_prefix, data)
                data['id'] = request_id
                ws = next(ws for ws, client in app['clients'].items() if client['id'] == client_id)
                ws.send_json(data, dumps=json.dumps)
    else:
        log_msg('[BROWSER {}]'.format(tab_id), 'DISCONNECTED')
        return


def update_tab(tab, host, port, log_msg):
    result = dict(tab)  # It is safe enough — all values are strings

    if result.get('id') is None:
        log_msg('[ERROR]', 'Got a tab without id (which is improbable): {}'.format(result))
        return result  # Maybe it should raise an error?

    devtools_url = '{}:{}/devtools/page/{}'.format(host, port, result['id'])
    result['webSocketDebuggerUrl'] = 'ws://{}'.format(devtools_url)
    result['devtoolsFrontendUrl'] = '/devtools/inspector.html?ws={}'.format(devtools_url)

    return result


async def proxy_handler(request):
    app = request.app
    method = request.method
    path_qs = request.path_qs
    session = aiohttp.ClientSession(loop=request.app.loop)
    url = 'http://{}:{}{}'.format(app['chrome_host'], app['chrome_port'], path_qs)
    log_msg = app['f']['print']

    log_msg('[HTTP {}] {}'.format(method, path_qs))
    try:
        response = await session.request(method, url)
        headers = response.headers.copy()
        if request.path in ('/json', '/json/list', '/json/new'):
            data = await response.json(loads=json.loads)

            proxy_host = request.url.host
            proxy_port = request.url.port
            if isinstance(data, list):
                data = [update_tab(tab, proxy_host, proxy_port, log_msg) for tab in data]
            elif isinstance(data, dict):
                data = update_tab(data, proxy_host, proxy_port, log_msg)
            else:
                log_msg('[WARN]', 'JSON data neither list nor dict: {}'.format(data))
            body, text = None, json.dumps(data)
            headers[hdrs.CONTENT_LENGTH] = str(len(text))
        else:
            body, text = await response.read(), None

        return Response(
            body=body,
            text=text,
            status=response.status,
            reason=response.reason,
            headers=headers,
        )
    except aiohttp.ClientError as exc:
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
    app = Application(debug=args['debug'])
    app.update(args)
    log_msg = app['f']['print']

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

    log_msg(
        'DevTools Proxy started at {}:{}\n'
        'Use --remote-debugging-port={} --remote-debugging-address={} for Chrome'.format(
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

    app['f']['close_log']()


def encode_decode_id(max_clients):
    bits_available = 31

    bits_for_client_id = math.ceil(math.log2(max_clients))
    _max_clients = 2 ** bits_for_client_id
    max_request_id = 2 ** (bits_available - bits_for_client_id) - 1

    def encode_id(client_id, request_id):
        if request_id > max_request_id:
            raise OverflowError
        return (client_id << bits_available - bits_for_client_id) | request_id

    def decode_id(encoded_id):
        client_id = encoded_id >> (bits_available - bits_for_client_id)
        request_id = encoded_id & max_request_id
        return client_id, request_id

    return encode_id, decode_id, _max_clients


def default_or_flatten_and_uniq(arg, default):
    # Simple helper for parsing arguments with action='append' and default value
    if arg is None:
        return default
    else:
        return list(set(e for ee in arg for e in ee))


def main():
    parser = argparse.ArgumentParser(
        prog='devtools-proxy',
        description='DevTools Proxy'
    )
    default_host = ['127.0.0.1']
    parser.add_argument(
        '--host',
        type=str, nargs='+', action='append',
        help='Hosts to serve on (default: {})'.format(default_host),
    )
    default_port = [9222]
    parser.add_argument(
        '--port',
        type=int, nargs='+', action='append',
        help='Ports to serve on (default: {})'.format(default_port),
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
        type=int, default=8,
        help='Number of clients which proxy can handle during life cycle (default: %(default)r)',
    )
    parser.add_argument(
        '--log',
        default=sys.stdout, type=argparse.FileType('w'),
        help='Write logs to file',
    )
    parser.add_argument(
        '--version',
        action='version',
        version=VERSION,
        help='Print DevTools Proxy version',
    )
    parser.add_argument(
        '--debug',
        action='store_true', default=False,
        help='Turn on debug mode (default: %(default)r)',
    )
    args = parser.parse_args()

    encode_id, decode_id, max_clients = encode_decode_id(args.max_clients)

    args.port = default_or_flatten_and_uniq(args.port, default_port)
    args.host = default_or_flatten_and_uniq(args.host, default_host)

    arguments = {
        'f': {
            'encode_id': encode_id,
            'decode_id': decode_id,
            'print': lambda *a: args.log.write(' '.join(str(v) for v in a) + '\n'),
            'close_log': lambda: args.log.close(),
        },
        'max_clients': max_clients,
        'debug': args.debug,
        'proxy_hosts': args.host,
        'proxy_ports': args.port,
        'chrome_host': args.chrome_host,
        'chrome_port': args.chrome_port,
        'internal': {
            'ujson': with_ujson,
            'uvloop': with_uvloop,
        },
        'version': VERSION,
    }

    def _excepthook(exctype, value, traceback):
        return arguments['f']['print'](*traceback.format_exception(exctype, value, traceback))

    sys.excepthook = _excepthook

    loop = asyncio.get_event_loop()
    if args.debug:
        def _showwarning(message, category, filename, lineno, file=None, line=None):
            return arguments['f']['print'](warnings.formatwarning(message, category, filename, lineno, line))

        warnings.showwarning = _showwarning
        warnings.simplefilter("always")
        loop.set_debug(True)

    application, srvs, handler = loop.run_until_complete(init(loop, arguments))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(finish(application, srvs, handler))


if __name__ == '__main__':
    main()
