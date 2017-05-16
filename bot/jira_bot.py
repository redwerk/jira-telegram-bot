from telegram.error import (BadRequest, ChatMigrated, NetworkError,
                            TelegramError, TimedOut, Unauthorized)
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater


class JiraBot(object):
    def __init__(self, logger, bot_token):
        self.logger = logger
        self.updater = Updater(bot_token)

        self.updater.dispatcher.add_handler(
            CommandHandler('start', self._start)
        )
        self.updater.dispatcher.add_handler(
            CommandHandler('caps', self._caps, pass_args=True)
        )
        self.updater.dispatcher.add_handler(
            MessageHandler(Filters.text, self._echo)
        )
        self.updater.dispatcher.add_error_handler(self._error_callback)

    def start(self):
        self.updater.start_polling()
        self.updater.idle()

    def stop(self):
        self.updater.stop()

    def _start(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id,
                         text="I'm a bot, please talk to me!")

    def _echo(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id,
                         text=update.message.text)

    def _caps(self, bot, update, args):
        text_caps = ' '.join(args).upper()
        bot.send_message(chat_id=update.message.chat_id, text=text_caps)

    def _error_callback(self, bot, update, error):
        try:
            raise error
        except Unauthorized:
            pass
        except BadRequest:
            pass
        except TimedOut:
            pass
        except NetworkError:
            pass
        except ChatMigrated as e:
            pass
        except TelegramError:
            pass
