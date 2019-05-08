import re

from croniter import croniter

from .exceptions import ScheduleValidationError


# Default periodicities
WEEKLY_DEFAULT = "0 0 * * 1"
MONTHLY_DEFAULT = "0 0 1 * *"
DAILY_DEFAULT = "0 0 * * *"


# allowed periodicity types
TYPES = ["weekly", "monthly", "daily"]
# allowed weekdays
WEEKDAYS = {'sun': 0, 'mon': 1, 'tue': 2, 'wed': 3, 'thu': 4, 'fri': 5, 'sat': 6}
# allowed days
DAYS = range(1, 32)
# allowed hours
HOURS = range(0, 24)
# allowed minutes
MINUTES = range(0, 60)


_or = lambda x: "|".join(x)


# match: callback <weekly_re>|<monthly_re>|<time_re>
command_re = r'(?P<callback>.*) (?P<type>%s)\s?(?P<opt>.*)?' % _or(TYPES)
# match: sun|mon|tue... <time_re>
weekly_re = r'(?P<day>%s)\s?(?P<opt>.*)?' % _or(WEEKDAYS.keys())
# match: 0-31 <time_re>
monthly_re = r'(?P<day>\d{1,2})\s?(?P<opt>.*)?'
# match: 10:20, 10-20, 10.20, 10 20
time_re = r'(?P<hour>\d{0,2})[:\-\\.\s]+(?P<minute>\d*)'


def command_parser(callback):
    """Parse and validate accepts command"""
    from .schedules import schedule_commands
    command, *context = callback.split()
    if command not in schedule_commands:
        raise ScheduleValidationError(f"Command '{command}' not registered")

    schedule_commands[command].validate_context(context[:])
    return command, context


class SimpleCronParser:
    """Custom and simple crontab parser."""

    @staticmethod
    def _match(pat, opt):
        """Match pattern on options and return groupdict
        with default values.
        """
        m = re.match(pat, opt)
        if not m:
            raise ScheduleValidationError(f"Incorrect periodicity value '{opt}'")
        return m.groupdict(None)

    @staticmethod
    def match_time(self, opt):
        """Parse time periodicity.

        Args:
            opt (str): periodicity options
        Returns:
            (int, int): hour and minute
        """
        if not opt:
            hour = minute = 0
        else:
            data = self._match(time_re, opt)
            hour = int(data.get("hour") or 0)
            minute = int(data.get("minute") or 0)

        if hour not in HOURS:
            raise ScheduleValidationError(f"Hour {hour} out of range")

        if minute not in MINUTES:
            raise ScheduleValidationError(f"Minute {minute} out of range")

        return hour, minute

    def parse(self, ptype, opt):
        """Get parser, validate and parse periodicity.

        Args:
            ptype (str): periodicity parser type
            opt (str): periodicity options
        Returns:
            Cron style periodicity value
        """
        parser = getattr(self, f"parse_{ptype}", None)
        if parser is None:
            raise AttributeError(
                f"Parser method parse_{ptype} not implemented."
            )

        crontab = parser(opt)
        if not croniter.is_valid(crontab):
            raise ScheduleValidationError(f"Incorrect schedule value '{opt}'")

        return crontab

    def parse_weekly(self, opt):
        """Parse weekly periodicity.

        Args:
            opt (str): periodicity options
        Returns:
            (str): Cron style periodicity value
        """
        if not opt:
            return WEEKLY_DEFAULT
        data = self._match(weekly_re, opt)
        day = WEEKDAYS.get(data.get("day", "").lower())
        hour, minute = self.match_time(data.get("opt"))
        return f"{minute} {hour} * * {day}"

    def parse_monthly(self, opt):
        """Parse monthly periodicity.

        Args:
            opt (str): periodicity options
        Returns:
            (str): Cron style periodicity value
        """
        if not opt:
            return MONTHLY_DEFAULT
        data = self._match(monthly_re, opt)
        day = int(data.get("day"))
        if day not in DAYS:
            raise ScheduleValidationError(f"Day {day} out of range")

        hour, minute = self.match_time(data.get("opt"))
        return f"{minute} {hour} {day} * *"

    def parse_daily(self, opt):
        """Parse daily periodicity.

        Args:
            opt (str): periodicity options
        Returns:
            (str): Cron style periodicity value
        """
        if not opt:
            return DAILY_DEFAULT
        hour, minute = self.match_time(opt)
        return f"{minute} {hour} * * *"

    def __call__(self, *args, **kwargs):
        return self.parse(*args, **kwargs)


cron_parser = SimpleCronParser()
