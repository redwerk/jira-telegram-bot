from common.db import MongoBackend


class DatabaseSessionManager:
    def __init__(self):
        self.db = MongoBackend()

    def process_resource(self, req, resp, resource, params):
        print(req, resp, resource, params)
