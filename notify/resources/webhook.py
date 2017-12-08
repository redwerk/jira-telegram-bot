import falcon
import json


class Updates:
    def on_get(self, req, resp, **kwargs):
        print(kwargs)
        resp.status = falcon.HTTP_200
        resp.body = 'Test endpoint is working!'

    def on_post(self, req, resp, **kwargs):
        if req.content_length:
            data = json.load(req.stream)
            print(data)
            print('#' * 200)
            resp.status = falcon.HTTP_200
