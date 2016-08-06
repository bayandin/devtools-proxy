#!/usr/bin/env python3

import asyncio
import json
import re
import sys

import aiohttp
from aiohttp.web import Application, MsgType, Response, WebSocketResponse

PROXY_DEBUGGING_PORT = int(sys.argv[1]) if len(sys.argv) >= 2 else 12222
PROXY_DEBUGGING_HOST = '127.0.0.1'

CHROME_DEBUGGING_PORT = int(sys.argv[2]) if len(sys.argv) >= 3 else 9222
CHROME_DEBUGGING_HOST = '127.0.0.1'


async def the_handler(request):
    response = WebSocketResponse()

    ok, _protocol = response.can_prepare(request)
    return await (ws_handler(request) if ok else proxy_handler(request))


async def ws_handler(request):
    ws_client = WebSocketResponse()
    await ws_client.prepare(request)

    request.app['sockets'].append(ws_client)

    session = aiohttp.ClientSession(loop=request.app.loop)
    url = "ws://%s:%d%s" % (CHROME_DEBUGGING_HOST, CHROME_DEBUGGING_PORT, request.path)
    task = None
    try:
        ws_browser = await session.ws_connect(url, autoclose=False, autoping=False)
        request.app['sockets'].append(ws_browser)

        # https://github.com/KeepSafe/aiohttp/commit/8d9ee8b77820a2af11d7c1716f793a610afe306f
        task = request.app.loop.create_task(ws_from_to(ws_browser, ws_client, '<<'))
        await ws_from_to(ws_client, ws_browser, '>>')
    finally:
        if task is not None:
            task.cancel()
        session.close()

    return ws_client


async def ws_from_to(ws_from, ws_to, log_prefix=''):
    async for msg in ws_from:
        if msg.tp == MsgType.text:
            print(log_prefix, msg.data)
            ws_to.send_str(msg.data)
        # elif msg.tp == MsgType.error:
        #     break
        # elif msg.tp == MsgType.closed:
        #     break
        else:
            break


async def proxy_handler(request):
    session = aiohttp.ClientSession(loop=request.app.loop)
    path_qs = request.path_qs
    url = "http://%s:%s%s" % (CHROME_DEBUGGING_HOST, CHROME_DEBUGGING_PORT, path_qs)
    try:
        if request.path in ['/json', '/json/list']:
            response = await session.get(url)
            data = await response.json()
            pattern = re.compile(r"(127\.0\.0\.1|localhost|%s):%d/" % (CHROME_DEBUGGING_HOST, CHROME_DEBUGGING_PORT))
            for tab in data:
                for k, v in tab.items():
                    if ":%d/" % CHROME_DEBUGGING_PORT in v:
                        tab[k] = pattern.sub("%s:%d/" % (PROXY_DEBUGGING_HOST, PROXY_DEBUGGING_PORT), tab[k])
            return Response(status=response.status, body=json.dumps(data).encode('utf-8'))
        else:
            return await transparent_request(session, url)
    except (aiohttp.errors.ClientOSError, aiohttp.errors.ClientResponseError):
        return aiohttp.web.HTTPBadGateway()
    finally:
        session.close()


async def transparent_request(session, url):
    response = await session.get(url)
    content_type = response.headers[aiohttp.hdrs.CONTENT_TYPE].split(';')[0]  # Could be 'text/html; charset=UTF-8'
    return Response(status=response.status, body=await response.read(), content_type=content_type)


async def init(loop):
    app = Application(loop=loop)
    app['sockets'] = []
    app.router.add_route('*', '/{path:.*}', the_handler)

    handler = app.make_handler()
    srv = await loop.create_server(handler, PROXY_DEBUGGING_HOST, PROXY_DEBUGGING_PORT)
    print(
        "Server started at %s:%d\n"
        "Use --remote-debugging-port=%d for Chrome" % (
            PROXY_DEBUGGING_HOST, PROXY_DEBUGGING_PORT, CHROME_DEBUGGING_PORT
        )
    )
    return app, srv, handler


async def finish(app, srv, handler):
    for ws in app['sockets']:
        if not ws.closed:
            await ws.close()
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
