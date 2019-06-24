from logging.handlers import SMTPHandler

from decouple import config


class MailAdminHandler(SMTPHandler):
    def getSubject(self, record):
        return "[{}] {} {}".format(config('ENV_PREFIX'), record.levelname, record.getMessage())
