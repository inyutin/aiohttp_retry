from aiohttp import web


class App:
    def __init__(self):
        self.counter = 0

        app = web.Application()
        app.router.add_get('/ping', self.ping_handler)
        app.router.add_get('/internal_error', self.internal_error_handler)
        app.router.add_get('/not_found_error', self.not_found_error_handler)
        app.router.add_get('/sometimes_error', self.sometimes_error)
        app.router.add_get('/sometimes_json', self.sometimes_json)
        app.router.add_get('/check_headers', self.check_headers)
        app.router.add_get('/with_auth', self.with_auth)

        app.router.add_options('/options_handler', self.ping_handler)
        app.router.add_head('/head_handler', self.ping_handler)
        app.router.add_post('/post_handler', self.ping_handler)
        app.router.add_put('/put_handler', self.ping_handler)
        app.router.add_patch('/patch_handler', self.ping_handler)
        app.router.add_delete('/delete_handler', self.ping_handler)

        app.router.add_post('/internal_error', self.internal_error_handler)

        self._web_app = app

    async def ping_handler(self, _: web.Request) -> web.Response:
        self.counter += 1
        return web.Response(text='Ok!', status=200)

    async def internal_error_handler(self, _: web.Request) -> web.Response:
        self.counter += 1
        raise web.HTTPInternalServerError()

    async def not_found_error_handler(self, _: web.Request) -> web.Response:
        self.counter += 1
        raise web.HTTPNotFound()

    async def sometimes_error(self, _: web.Request) -> web.Response:
        self.counter += 1
        if self.counter == 3:
            return web.Response(text='Ok!', status=200)

        raise web.HTTPInternalServerError()

    async def sometimes_json(self, _: web.Request) -> web.Response:
        self.counter += 1
        if self.counter == 3:
            return web.json_response(data={'status': 'Ok!'}, status=200)

        return web.Response(text='Ok!', status=200)

    async def check_headers(self, request: web.Request) -> web.Response:
        self.counter += 1
        if request.headers.get('correct_headers') != 'True':
            raise web.HTTPNotAcceptable()

        return web.Response(text='Ok!', status=200)

    async def with_auth(self, request: web.Request) -> web.Response:
        self.counter += 1

        # BasicAuth("username", "password")
        if request.headers.get('Authorization') != 'Basic dXNlcm5hbWU6cGFzc3dvcmQ=':
            return web.Response(text='incorrect auth', status=403)
        return web.Response(text='Ok!', status=200)

    @property
    def web_app(self) -> web.Application:
        return self._web_app
