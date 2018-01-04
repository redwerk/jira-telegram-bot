import pytest

from bot.app import JTBApp
from bot.parsers import command_parser, cron_parser, TYPES, WEEKDAYS, DAYS
from bot.exceptions import ContextValidationError, ScheduleValidationError
import bot.commands as commands


NOT_ALLOWED_TEST_COMMANDS = (
    "/help",
    "/schedule",
    "/unschedule",
    "/connect",
    "/oauth",
    "/disconnect",
    "/start"
)


class TestCommandParser:
    """Test cases for 'command_parser' function"""
    def setup(self):
        self.app = JTBApp()
        self.commands = self.app.commands

    @pytest.mark.parametrize("callback", NOT_ALLOWED_TEST_COMMANDS)
    def test_parse_not_allowed_command(self, callback):
        with pytest.raises(ScheduleValidationError):
            command_parser(callback, self.commands)

    def test_parse_listunresolved_without_context(self):
        callback = "/listunresolved"
        with pytest.raises(ContextValidationError):
            command_parser(callback, self.commands)

    def test_parse_listunresolved_me(self):
        callback = "/listunresolved my"
        command, context = command_parser(callback, self.commands)
        assert issubclass(command, commands.ListUnresolvedIssuesCommand)

    def test_parse_listunresolved_user(self):
        callback = "/listunresolved user"
        with pytest.raises(ContextValidationError):
            command_parser(callback, self.commands)

        callback = "/listunresolved user test_username"
        command, context = command_parser(callback, self.commands)
        assert issubclass(command, commands.ListUnresolvedIssuesCommand)

    def test_parse_listunresolved_project(self):
        callback = "/listunresolved project"
        with pytest.raises(ContextValidationError):
            command_parser(callback, self.commands)

        callback = "/listunresolved project test_project"
        command, context = command_parser(callback, self.commands)
        assert issubclass(command, commands.ListUnresolvedIssuesCommand)

    def test_parse_liststatus_without_context(self):
        callback = "/liststatus"
        with pytest.raises(ContextValidationError):
            command_parser(callback, self.commands)

    def test_parse_liststatus_me(self):
        callback = "/liststatus my"
        command, context = command_parser(callback, self.commands)
        assert issubclass(command, commands.ListStatusIssuesCommand)

    def test_parse_liststatus_user(self):
        callback = "/liststatus user"
        with pytest.raises(ContextValidationError):
            command_parser(callback, self.commands)

        callback = "/liststatus user test_username"
        command, context = command_parser(callback, self.commands)
        assert issubclass(command, commands.ListStatusIssuesCommand)

    def test_parse_liststatus_project(self):
        callback = "/liststatus project"
        with pytest.raises(ContextValidationError):
            command_parser(callback, self.commands)

        callback = "/liststatus project test_project"
        command, context = command_parser(callback, self.commands)
        assert issubclass(command, commands.ListStatusIssuesCommand)

    def test_parse_filter_without_context(self):
        callback = "/filter"
        with pytest.raises(ContextValidationError):
            command_parser(callback, self.commands)

    def test_parse_filter_with_context(self):
        callback = "/filter Test Filter"
        command, context = command_parser(callback, self.commands)
        assert issubclass(command, commands.FilterIssuesCommand)

    def test_parse_time_without_context(self):
        callback = "/time"
        with pytest.raises(ContextValidationError):
            command_parser(callback, self.commands)

    def test_parse_time_issue(self):
        callback = "/time issue"
        with pytest.raises(ContextValidationError):
            command_parser(callback, self.commands)

        callback = "/time issue test_issue today"
        command, context = command_parser(callback, self.commands)
        assert issubclass(command, commands.TimeTrackingDispatcher)

    def test_parse_time_user(self):
        callback = "/time user"
        with pytest.raises(ContextValidationError):
            command_parser(callback, self.commands)

        callback = "/time user test_user 28/Dec/2017"
        command, context = command_parser(callback, self.commands)
        assert issubclass(command, commands.TimeTrackingDispatcher)

    def test_parse_time_project(self):
        callback = "/time project"
        with pytest.raises(ContextValidationError):
            command_parser(callback, self.commands)

        callback = "/time project test_project yesterday"
        command, context = command_parser(callback, self.commands)
        assert issubclass(command, commands.TimeTrackingDispatcher)


class TestSimpleCronParser:
    """Test cases for 'SimpleCronParser' class"""
    @pytest.mark.parametrize("name", TYPES)
    def test_parser_method(self, name):
        with pytest.raises(ScheduleValidationError):
            cron_parser(name, "test_options")

    def test_parser_method_exception(self):
        with pytest.raises(AttributeError):
            cron_parser("not_implemented", "test_options")

    def test_parser_incorect_options(self):
        with pytest.raises(ScheduleValidationError):
            cron_parser(TYPES[0], "test_options")

    @pytest.mark.parametrize("day_name", WEEKDAYS)
    def test_parser_weekly_success(self, day_name):
        day_name, day = day_name, WEEKDAYS[day_name]
        opt = f"{day_name} 12:30"
        cron = cron_parser("weekly", opt)
        expected_cron = f"30 12 * * {day}"
        assert cron == expected_cron

    @pytest.mark.parametrize("day_name", WEEKDAYS)
    def test_parser_weekly_failed(self, day_name):
        day_name = day_name + "test"
        opt = f"{day_name} 12:30"
        with pytest.raises(ScheduleValidationError):
            cron_parser("weekly", opt)

    @pytest.mark.parametrize("day", DAYS)
    def test_parser_monthly_success(self, day):
        opt = f"{day} 12:30"
        cron = cron_parser("monthly", opt)
        expected_cron = f"30 12 {day} * *"
        assert cron == expected_cron

    @pytest.mark.parametrize("day", [33, 100, "abc", "+", None])
    def test_parser_monthly_failed(self, day):
        opt = f"{day} 12:30"
        with pytest.raises(ScheduleValidationError):
            cron_parser("monthly", opt)

    @pytest.mark.parametrize("opt", ["00:05", "1:20, 15:40", "05:25", "23:59"])
    def test_parser_daily_success(self, opt):
        cron = cron_parser("daily", opt)
        hour, minute = cron_parser.match_time(opt)
        expected_cron = f"{minute} {hour} * * *"
        assert cron == expected_cron

    @pytest.mark.parametrize("opt", ["25:00", "10:86", "231:1", "10:200", "abc"])
    def test_parser_daily_failed(self, opt):
        with pytest.raises(ScheduleValidationError):
            cron_parser("daily", opt)

    @pytest.mark.parametrize("opt", ["12:30", "12.30", "12 30", "12-30", "12 - 30"])
    def test_parser_match_time_success(self, opt):
        assert cron_parser.match_time(opt) == (12, 30)

    def test_parser_match_time_none(self):
        assert cron_parser.match_time(None) == (0, 0)

    def test_parser_match_time_only_hour(self):
        assert cron_parser.match_time("12:") == (12, 0)

    def test_parser_match_time_only_minute(self):
        assert cron_parser.match_time(":30") == (0, 30)

    @pytest.mark.parametrize("opt", ["25:00", "10:86", "231:1", "10:200", "abc"])
    def test_parser_match_time_failed(self, opt):
        with pytest.raises(ScheduleValidationError):
            cron_parser.match_time(opt)
