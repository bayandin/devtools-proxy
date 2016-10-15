#!/usr/bin/env python3

import argparse
import asyncio
import json
import re

import aiohttp
from aiohttp.web import Application, Response, WebSocketResponse, WSMsgType

from monkey_patch import patch_create_server


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
    unprocessed_msg = None
    app = request.app
    path_qs = request.path_qs
    tab_id = path_qs.split('/')[-1]
    url = "ws://%s:%d%s" % (app['chrome_host'], app['chrome_port'], path_qs)

    ws_client = WebSocketResponse()
    await ws_client.prepare(request)

    client_id = len(app['clients']) + 1
    app['clients'][ws_client] = {
        'id': client_id,
        'tab_id': tab_id
    }

    log_prefix = "[CLIENT %d]" % client_id

    print(log_prefix, 'CONNECTED')

    if app['tabs'][tab_id].get('ws') is None or app['tabs'][tab_id]['ws'].closed:
        session = aiohttp.ClientSession(loop=app.loop)
        app['sessions'].append(session)
        # TODO: handle connection to non-existing tab (in case of typo in tab_id, or try to connect to old one)
        app['tabs'][tab_id]['ws'] = await session.ws_connect(url, autoclose=False, autoping=False)

    while True:
        if unprocessed_msg:
            data = unprocessed_msg.data
            print(log_prefix, '>>', data)
            app['tabs'][tab_id]['ws'].send_str(data)
            unprocessed_msg = None

        async for msg in ws_client:
            if msg.type == WSMsgType.TEXT:
                app['tabs'][tab_id]['active_client'] = ws_client
                if app['tabs'][tab_id]['ws'].closed:
                    unprocessed_msg = msg
                    print(log_prefix, 'RECONNECTED')
                    break
                data = msg.data
                print(log_prefix, '>>', data)
                app['tabs'][tab_id]['ws'].send_str(data)
            else:
                print(log_prefix, 'DISCONNECTED')
                return ws_client


async def ws_browser_handler(request):
    log_prefix = '<<'
    app = request.app
    tab_id = request.path_qs.split('/')[-1]

    while True:
        while app['tabs'][tab_id].get('ws') is None or app['tabs'][tab_id]['ws'].closed:
            await asyncio.sleep(0.1)
            print("[BROWSER %s]" % tab_id, 'WAITED')
        else:
            print("[BROWSER %s]" % tab_id, 'CONNECTED')

        async for msg in app['tabs'][tab_id]['ws']:
            if msg.type == WSMsgType.TEXT:
                if msg.json().get('id') is None:
                    clients = {k: v for k, v in app['clients'].items() if v.get('tab_id') == tab_id}
                    for client in clients.keys():
                        if not client.closed:
                            client_id = app['clients'][client]['id']
                            print('[CLIENT %d]' % client_id, log_prefix, msg.data)
                            client.send_str(msg.data)
                else:
                    client_id = app['clients'][app['tabs'][tab_id]['active_client']]['id']
                    print('[CLIENT %d]' % client_id, log_prefix, msg.data)
                    app['tabs'][tab_id]['active_client'].send_str(msg.data)
            else:
                print("[BROWSER %s]" % tab_id, 'DISCONNECTED')
                break


async def proxy_handler(request):
    app = request.app
    path_qs = request.path_qs
    session = aiohttp.ClientSession(loop=request.app.loop)
    url = "http://%s:%s%s" % (app['chrome_host'], app['chrome_port'], path_qs)

    print("[HTTP %s] %s" % (request.method, path_qs))
    try:
        if request.path in ['/json', '/json/list']:
            response = await session.get(url)
            data = await response.json()

            proxy_host, proxy_port = request.host.split(':')
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

            return Response(status=response.status, body=json.dumps(data).encode('utf-8'))
        else:
            return await transparent_request(session, url)
    except (aiohttp.errors.ClientOSError, aiohttp.errors.ClientResponseError) as exc:
        return aiohttp.web.HTTPBadGateway(text=str(exc))
    finally:
        session.close()


async def transparent_request(session, url):
    response = await session.get(url)
    content_type = response.headers[aiohttp.hdrs.CONTENT_TYPE].split(';')[0]  # Could be 'text/html; charset=UTF-8'
    return Response(status=response.status, body=await response.read(), content_type=content_type)


async def init(loop, args):
    app = Application(loop=loop)
    app.update(args)

    app['clients'] = {}
    app['tabs'] = {}
    # TODO: Move session and task handling to proper places
    app['sessions'] = []
    app['tasks'] = []

    app.router.add_route('*', '/{path:.*}', the_handler)

    handler = app.make_handler()
    srv = await loop.create_server(handler, app['proxy_hosts'], app['proxy_ports'])
    print(
        "Server started at %s:%s\n"
        "Use --remote-debugging-port=%d --remote-debugging-address=%s for Chrome" % (
            app['proxy_hosts'], app['proxy_ports'], app['chrome_port'], app['chrome_host']
        )
    )
    return app, srv, handler


async def finish(app, srv, handler):
    for ws in list(app['clients'].keys()) + [tab['ws'] for tab in app['tabs'].values() if tab.get('ws') is not None]:
        if not ws.closed:
            await ws.close()

    for session in app['sessions']:
        if not session.closed:
            await session.close()

    for task in app['tasks']:
        task.cancel()

    await asyncio.sleep(0.1)
    srv.close()
    await handler.finish_connections()
    await srv.wait_closed()


def main():
    parser = argparse.ArgumentParser(description='DevTools proxy — …')
    parser.add_argument('--host', default=['127.0.0.1'], type=str, nargs='*', help='')
    parser.add_argument('--port', default=[9222], type=int, nargs='*', help='')
    parser.add_argument('--chrome-host', default='127.0.0.1', type=str, help='')
    parser.add_argument('--chrome-port', default=12222, type=int, help='')
    parser.add_argument('--debug', default=False, action='store_true', help='')
    args = parser.parse_args()

    arguments = {
        'debug': args.debug,
        'proxy_hosts': args.host,
        'proxy_ports': args.port,
        'chrome_host': args.chrome_host,
        'chrome_port': args.chrome_port,
        'devtools_pattern': re.compile(r"(127\.0\.0\.1|localhost|%s):%d/" % (args.chrome_host, args.chrome_port)),
    }

    loop = asyncio.get_event_loop()
    if args.debug:
        loop.set_debug(True)

    application, srv, handler = loop.run_until_complete(init(loop, arguments))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(finish(application, srv, handler))


if __name__ == '__main__':
    patch_create_server()
    main()
