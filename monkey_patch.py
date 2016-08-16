def patch_create_server():
    from asyncio import BaseEventLoop
    from issue27665 import create_server

    BaseEventLoop.create_server = create_server
