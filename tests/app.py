from aiohttp import web


class TestApp:
    def __init__(self):
        self.counter = 0

        app = web.Application()
        app.router.add_get('/ping', self.ping_handler)
        app.router.add_get('/internal_error', self.internal_error_handler)
        app.router.add_get('/not_found_error', self.not_found_error_handler)
        app.router.add_get('/sometimes_error', self.sometimes_error)

        self.app = app

    async def ping_handler(self, request):
        self.counter += 1
        return web.Response(text='Ok!', status=200)

    async def internal_error_handler(self, request):
        self.counter += 1
        return web.HTTPInternalServerError()

    async def not_found_error_handler(self, request):
        self.counter += 1
        return web.HTTPNotFound()

    async def sometimes_error(self, request):
        self.counter += 1
        if self.counter == 3:
            return web.Response(text='Ok!', status=200)

        return web.HTTPInternalServerError()

    def get_app(self):
        return self.app
