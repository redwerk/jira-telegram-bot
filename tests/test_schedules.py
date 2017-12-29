import copy
from collections.abc import Iterable
import pytest

from decouple import config
from telegram import (
    Bot, Message, User, Update, Chat, CallbackQuery, InlineQuery,
    ChosenInlineResult, ShippingQuery, PreCheckoutQuery
)

from bot.app import JTBApp
import bot.commands as commands
from bot.schedules import ScheduleTask, ScheduleCommands, schedule_commands

from .base import JTBTest


message = Message(1, User(1, '', False), None, Chat(1, ''), text='Text')

params = {
    'message': message,
    'edited_message': message,
    'callback_query': CallbackQuery(1, User(1, '', False), 'chat', message=message),
    'channel_post': message,
    'edited_channel_post': message,
    'inline_query': InlineQuery(1, User(1, '', False), '', ''),
    'chosen_inline_result': ChosenInlineResult('id', User(1, '', False), ''),
    'shipping_query': ShippingQuery('id', User(1, '', False), '', None),
    'pre_checkout_query': PreCheckoutQuery('id', User(1, '', False), '', 0, ''),
}


class TestScheduleCommands:
    """Test cases for 'ScheduleCommands' class"""

    def prepare_schedule_commands(self):
        instance = copy.deepcopy(schedule_commands)
        instance._ScheduleCommands__commands = dict()
        return instance

    def setup_method(self, method):
        self.schedule_commands = self.prepare_schedule_commands()

    def teardown_method(self, method):
        del self.schedule_commands

    def test_register_command(self):
        self.schedule_commands.register('listunresolved', commands.ListUnresolvedIssuesCommand)
        self.schedule_commands.register('/liststatus', commands.ListStatusIssuesCommand)
        assert '/listunresolved' in self.schedule_commands
        assert '/liststatus' in self.schedule_commands
        assert '/test' not in self.schedule_commands

    def test_register_exist_command(self):
        self.schedule_commands.register('/liststatus', commands.ListStatusIssuesCommand)
        with pytest.raises(ValueError):
            self.schedule_commands.register('/liststatus', commands.ListStatusIssuesCommand)

    @pytest.mark.parametrize('instance', [dict, list, None, str, ScheduleCommands])
    def test_register_other_type_command(self, instance):
        with pytest.raises(TypeError):
            self.schedule_commands.register('/liststatus', instance)

    def test_command_name_validation(self):
        with pytest.raises(TypeError):
            self.schedule_commands.register(list, commands.ListStatusIssuesCommand)

    def test_items_method(self):
        with pytest.raises(AttributeError):
            self.schedule_commands.items()

    def test_get_method(self):
        self.schedule_commands.register('/liststatus', commands.ListStatusIssuesCommand)
        assert self.schedule_commands.get('/liststatus') == commands.ListStatusIssuesCommand
        assert self.schedule_commands.get('/test') is None

    def test_keys_method(self):
        self.schedule_commands.register('/liststatus', commands.ListStatusIssuesCommand)
        self.schedule_commands.register('/listunresolved', commands.ListUnresolvedIssuesCommand)
        assert '/liststatus' in self.schedule_commands.keys()
        assert '/listunresolved' in self.schedule_commands.keys()
        assert '/test' not in self.schedule_commands.keys()

    def test_values_method(self):
        self.schedule_commands.register('/liststatus', commands.ListStatusIssuesCommand)
        self.schedule_commands.register('/listunresolved', commands.ListUnresolvedIssuesCommand)
        assert commands.ListStatusIssuesCommand in self.schedule_commands.values()
        assert commands.ListUnresolvedIssuesCommand in self.schedule_commands.values()
        assert commands.HelpCommand not in self.schedule_commands.values()

    def test_getitem(self):
        self.schedule_commands.register('/liststatus', commands.ListStatusIssuesCommand)
        assert self.schedule_commands['/liststatus'] == commands.ListStatusIssuesCommand
        with pytest.raises(KeyError):
            self.schedule_commands['/test']

    def test_setitem(self):
        with pytest.raises(AttributeError):
            self.schedule_commands['/liststatus'] = commands.ListStatusIssuesCommand

    def test_contains(self):
        self.schedule_commands.register('/liststatus', commands.ListStatusIssuesCommand)
        assert '/liststatus' in self.schedule_commands
        assert '/test' not in self.schedule_commands

    def test_len(self):
        self.schedule_commands.register('/listunresolved', commands.ListUnresolvedIssuesCommand)
        self.schedule_commands.register('/liststatus', commands.ListStatusIssuesCommand)
        assert len(self.schedule_commands) == 2

    def test_iter(self):
        self.schedule_commands.register('/listunresolved', commands.ListUnresolvedIssuesCommand)
        self.schedule_commands.register('/liststatus', commands.ListStatusIssuesCommand)
        assert isinstance(self.schedule_commands, Iterable)

        count = 0
        for i in self.schedule_commands:
            count += 1
        assert count == 2


class TestScheduleTask(JTBTest):
    """Test cases for 'ScheduleTask' class"""

    def setup_class(cls):
        super().setup_class(cls)
        cls._ScheduleTask = ScheduleTask
        cls._ScheduleTask._ScheduleTask__collection = cls.db.conn["schedules"]
        cls.collection = cls._ScheduleTask._ScheduleTask__collection

    def setup(self):
        self.app = JTBApp()
        self.bot = Bot(config("BOT_TOKEN"))

    def get_update(self, update_id=1):
        return Update(update_id=update_id, **params)

    def create_task(self):
        update = self.get_update()
        interval = "30 * * * *"
        result = self._ScheduleTask.create(update, "/test", "UTC", interval, "/test")
        return result

    def load_task(self, task_id):
        return self._ScheduleTask.load(self.collection.find_one({'_id': task_id}), self.bot)

    def test_create_and_load(self):
        result = self.create_task()
        task = self.load_task(result.inserted_id)
        assert self.collection.count() == 1
        assert result.inserted_id == task.id

    def test_delete(self):
        result = self.create_task()
        task = self.load_task(result.inserted_id)
        assert self.collection.count({'_id': task.id}) == 1
        task.delete()
        assert self.collection.count({'_id': task.id}) == 0

    def test_save(self):
        result = self.create_task()
        task = self.load_task(result.inserted_id)
        task.total_run_count = 10
        task.save()
        _task = self.load_task(result.inserted_id)
        assert task.total_run_count == _task.total_run_count

    def test_done(self):
        result = self.create_task()
        task = self.load_task(result.inserted_id)
        current_last_run = task.last_run
        current_next_run = task.next_run
        current_total_run_count = task.total_run_count

        task.done()

        assert task.last_run.timestamp() > current_last_run.timestamp()
        assert task.next_run.timestamp() > current_next_run.timestamp()
        assert task.total_run_count == current_total_run_count + 1

    @pytest.mark.parametrize('interval', ["30 minutes", "3000", "test" "2 *** #", "*"])
    def test_interval_validation(self, interval):
        with pytest.raises(ValueError):
            update = self.get_update()
            self._ScheduleTask.create(update, "/test", "UTC", interval, "/test")
