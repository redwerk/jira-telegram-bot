import pymongo
from pymongo.errors import ServerSelectionTimeoutError


class MongoBackend(object):
    def __init__(self, logger, server, port, db_name, collection):
        self.logger = logger

        try:
            client = pymongo.MongoClient(
                server,
                port,
                serverSelectionTimeoutMS=1
            )
            client.server_info()
        except ServerSelectionTimeoutError as error:
            self.logger.error("Can't connect to DB: {}".format(error))
        else:
            self.db = client[db_name][collection]

    def get_user_credential(self, user_id):
        user = self.db.find_one({'telegram_id': user_id})

        if user:
            return user

        return False
