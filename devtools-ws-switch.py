#!/usr/bin/env python3

import asyncio
import json
import sys
import aiohttp
from aiohttp.web import Application, MsgType, Response, WebSocketResponse

PROXY_DEBUGGING_PORT = int(sys.argv[1]) if len(sys.argv) >= 2 else 12222
CHROME_DEBUGGING_PORT = int(sys.argv[2]) if len(sys.argv) >= 3 else 9222


def port_juggling(tabs):
    new_tabs = tabs[:]
    for tab in new_tabs:
        #
        # if tab.get('webSocketDebuggerUrl'):
        #     tab['webSocketDebuggerUrl'] = tab['webSocketDebuggerUrl'].replace(
        #         "ws://localhost:%d/" % CHROME_DEBUGGING_PORT,
        #         "ws://localhost:%d/" % PROXY_DEBUGGING_PORT
        #     )
        #
        for k, v in tab.items():
            if ":%d/" % CHROME_DEBUGGING_PORT in v:
                tab[k] = v.replace("localhost:%d/" % CHROME_DEBUGGING_PORT,
                                   "localhost:%d/" % PROXY_DEBUGGING_PORT)
    return new_tabs


async def http_handler(request):
    response = None
    path = request.path

    session = aiohttp.ClientSession(loop=request.app.loop)
    url = "http://localhost:%s%s" % (CHROME_DEBUGGING_PORT, path)
    try:
        if path == '/json':
            response = await session.get(url)
            data = await response.json()
            new_data = port_juggling(data)
            return Response(body=json.dumps(new_data).encode('utf-8'))
        elif path == '/json/version':
            try:
                response = await session.get(url)
                data = await response.read()
                return Response(body=data)
            except (aiohttp.errors.ClientOSError, OSError):
                print("%s is unavailable" % url)
        else:
            msg = "Don not know how to handle request to '%s'" % path
            print(msg)
            return Response(text=msg, status=444)
    finally:
        if response:
            await response.release()
        await session.close()


async def redirect_handler(request):
    path_qs = request.path_qs
    return aiohttp.web.HTTPMovedPermanently("http://localhost:%s%s" % (CHROME_DEBUGGING_PORT, path_qs))


async def from_browser_to_client(ws_client, ws_browser):
    # https://github.com/KeepSafe/aiohttp/commit/8d9ee8b77820a2af11d7c1716f793a610afe306f
    while True:
        msg = await ws_browser.receive()
        if msg.tp != MsgType.text:
            break
        print('<<', msg.data)
        ws_client.send_str(msg.data)


async def ws_handler(request):
    ws_client = WebSocketResponse()
    await ws_client.prepare(request)

    request.app['sockets'].append(ws_client)

    session = aiohttp.ClientSession(loop=request.app.loop)
    url = "ws://localhost:%s%s" % (CHROME_DEBUGGING_PORT, request.path)
    task = None
    try:
        ws_browser = await session.ws_connect(url, autoclose=False, autoping=False)
        request.app['sockets'].append(ws_browser)

        task = request.app.loop.create_task(from_browser_to_client(ws_client, ws_browser))

        while True:
            msg = await ws_client.receive()
            if msg.tp != MsgType.text:
                break
            data = msg.data
            print('>>', data)
            ws_browser.send_str(data)
    finally:
        if task is not None:
            task.cancel()
        session.close()

    return ws_client


async def init(loop):
    app = Application(loop=loop)
    app['sockets'] = []
    app.router.add_route('GET', '/{path:(?!devtools).*}', http_handler)
    app.router.add_route('GET', '/{path:devtools(?!/inspector.html).*}', ws_handler)
    app.router.add_route('GET', '/devtools/inspector.html', redirect_handler)

    handler = app.make_handler()
    srv = await loop.create_server(handler, 'localhost', PROXY_DEBUGGING_PORT)
    print("Server started at localhost:%d.\n"
          "Launch Chrome with parameter --remote-debugging-port=%d" % (PROXY_DEBUGGING_PORT, CHROME_DEBUGGING_PORT))
    return app, srv, handler


async def finish(app, srv, handler):
    for ws in app['sockets']:
        ws.close()
    app['sockets'].clear()
    await asyncio.sleep(0.1)
    srv.close()
    await handler.finish_connections()
    await srv.wait_closed()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    app, srv, handler = loop.run_until_complete(init(loop))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(finish(app, srv, handler))
