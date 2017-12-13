import datetime
from functools import partial, wraps
from importlib import import_module
import time
import logging

from croniter import croniter
from decouple import config
from telegram import Update
from telegram.ext import Job
from pytz import timezone

from lib.db import create_connection
from .commands.base import AbstractCommand


conn = create_connection()


def adjust(func):
    """This decorator execute accepted function
    and return elapsed time.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        func(*args, **kwargs)
        return time.time() - start
    return wrapper


class ScheduleTaskSerializer:
    """Serializer class for schedule tesk object.

    This serializer class can serialize and deserialize
    telegram and some specific python objects.
    """
    @staticmethod
    def serialize(data):
        if "update" in data:
            data["update"] = data["update"].to_dict()

        if "callback" in data:
            cb = data["callback"]
            data["callback"] = f"{cb.__module__}:{cb.__name__}"

        if "id" in data:
            _id = data.pop("id")
            if _id is not None:
                data["_id"] = _id

        return data

    @staticmethod
    def deserialize(data, bot):
        if "update" in data:
            data["update"] = Update.de_json(data["update"], bot)

        if "callback" in data:
            cb_module, cb_cls = data["callback"].split(":")
            data["callback"] = getattr(import_module(cb_module), cb_cls, None)

        if "_id" in data:
            data["id"] = data.pop("_id")

        return data


class ScheduleTask:
    """This class allows you to periodically perform tasks with the bot.

    Attributes:
        __collection (pymongo.MongoClient): db collection for schedule tasks

    Args:
        id (int): Task object id
        update (telegram.Update): Update instance
        name (str): command display name
        user_id (int): telegram user id
        tz (str): timezone name
        interval (str): schedule time interval in cron style
        callback (commands.AbstractCommand): The callback function that should be
                                             executed by the new job.
        context (list): Additional data needed for the callback function.
        last_run (datetime.datetime): task last time run
        next_run (datetime.datetime): task next time run
        total_run_count (int): task total runs
    """
    __collection = conn[config("SCHEDULE_COLLECTION", "schedules")]

    def __init__(
            self,
            id,
            update,
            interval,
            name,
            user_id,
            tz,
            callback,
            context=[],
            last_run=None,
            next_run=None,
            total_run_count=0,
            *args,
            **kwargs):

        self._id = id
        self._update = update
        self._name = name
        self._user_id = user_id
        self._tz = tz
        # validate cron interval
        if not croniter.is_valid(interval):
            raise ValueError("The 'interval' value is not valid")
        self._interval = interval
        self._callback = callback
        self._context = context
        self._last_run = last_run
        self._next_run = next_run
        self._total_run_count = total_run_count

    def get_job(self, app, bot):
        """Create and return future job.

        Arguments:
            app (app.JTBApp): bot app
            bot (telegram.Bot): telegram bot instance
        Returns:
            telegram.ext.Job
        """
        handler = self.callback(app).handler
        callback = partial(handler, bot, self.update, args=self.context)
        return Job(callback, repeat=False, name=self.id)

    def get_cron(self):
        """Return new cron from current datetime."""
        return croniter(self.interval, self.now)

    @property
    def now(self):
        """Return current system time."""
        tz = timezone(self.tz)
        return datetime.datetime.now(tz=tz)

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def user_id(self):
        return self._user_id

    @property
    def tz(self):
        return self._tz

    @property
    def callback(self):
        return self._callback

    @property
    def context(self):
        return self._context

    @property
    def update(self):
        return self._update

    @callback.setter
    def callback(self, value):
        if not issubclass(value, AbstractCommand):
            raise TypeError(
                "The 'callback' must be of type 'AbstractCommand'"
            )
        self._callback = value

    @property
    def interval(self):
        return self._interval

    @interval.setter
    def interval(self, value):
        if value is None:
            raise ValueError("The 'interval' can not be None")

        if not croniter.is_valid(value):
            raise ValueError("The 'interval' value is not valid")

        self._interval = value

    @property
    def last_run(self):
        return self._last_run or self.now

    @last_run.setter
    def last_run(self, value):
        if value is None:
            raise ValueError("The 'last_run' can not be None")

        if not isinstance(value, datetime.datetime):
            raise TypeError(
                "The 'last_run' must be of type 'datetime.datetime'"
            )

        self._last_run = value

    def __increase_last_run(self):
        """Increase lat_run time to current system time."""
        self.last_run = self.now

    @property
    def next_run(self):
        return self._next_run

    @next_run.setter
    def next_run(self, value):
        if value is None:
            raise ValueError("The 'next_run' can not be None")

        if not isinstance(value, datetime.datetime):
            raise TypeError("The 'next_run' must be of type 'datetime.datetime'")

        self._next_run = value

    def __increase_next_run(self):
        """Сalculate new next_run time."""
        self.next_run = self.get_cron().get_next(datetime.datetime)

    @property
    def total_run_count(self):
        return self._total_run_count

    @total_run_count.setter
    def total_run_count(self, value):
        if not isinstance(value, int):
            raise ValueError("The 'total_run_count' must be of type 'int'")
        self._total_run_count = value

    def __increase_total_run_count(self):
        """Increase total_run_count."""
        self.total_run_count += 1

    def done(self):
        """Schedule new task processing."""
        self.__increase_last_run()
        self.__increase_next_run()
        self.__increase_total_run_count()
        self.save()

    def save(self):
        """Save task in mongodb.

        Returns:
            bson.objectid.ObjectId
        """
        serialized_data = ScheduleTaskSerializer.serialize(self.to_dict())
        return self.__collection.save(serialized_data)

    def delete(self):
        """Remove task from schedule collection.

        Returns:
            pymongo.results.DeleteResult
        """
        return self.__collection.delete_one(dict(_id=self.id))

    def to_dict(self):
        """
        Returns:
            dict: allowed attributes
        """
        data = dict(
            id=self.id,
            update=self.update,
            name=self.name,
            user_id=self.user_id,
            tz=self.tz,
            callback=self.callback,
            context=self.context,
            interval=self.interval,
            last_run=self.last_run,
            next_run=self.next_run,
            total_run_count=self.total_run_count
        )
        return data

    @classmethod
    def load(cls, data, bot):
        """Restore periodic task from mongodb.

        Args:
            data (dict): mongo results item
            bot (telegram.Bot): The bot instance that should be passed to deserialization
        Returns:
            ScheduleTask: new instance
        """
        data = ScheduleTaskSerializer.deserialize(data, bot)
        return cls(**data)

    @classmethod
    def create(cls, update, name, tz, interval, callback, context=[]):
        """Create new periodic task.

        Args:
            update (telegram.Update): Update instance
            name (str): command display name
            tz (str): timezone name
            interval (datetime.timedelta): interval time
            callback (commands.AbstractCommand): the callback hendler
            context (list): callback params
        Returns:
            pymongo.results.InsertOneResult
        """
        user_id = update.effective_user.id
        if user_id is None:
            raise ValueError("User id is required")

        instance = cls(
            id=None,
            update=update,
            interval=interval,
            name=name,
            user_id=user_id,
            tz=tz,
            callback=callback,
            context=context
        )
        instance.__increase_next_run()
        # prepare task to save in MongoDB
        serialized_data = ScheduleTaskSerializer.serialize(instance.to_dict())
        # save task and return result
        return cls.__collection.insert_one(serialized_data)


class Scheduler:
    """Scheduler for periodic tasks.

    Attributes:
        __collection (pymongo.MongoClient): db collection for schedule tasks

    Args:
        app (app.JTBApp): bot app
        bot (telegram.Bot): telegram bot instance
        queue (telegram.ext.JobQueue): bot job queue
        sync_every (int): time to sleep between re-checking the schedule
    """
    __collection = conn[config("SCHEDULE_COLLECTION", "schedules")]

    def __init__(self, app, bot, queue, sync_every=10):
        self._app = app
        self._bot = bot
        if not isinstance(sync_every, int) or sync_every < 0:
            raise ValueError(f"Sync value {sync_every} is incorect.")
        self._sync_every = sync_every
        self.queue = queue

    def get_due_entries(self):
        return self.__collection.find({"next_run": {"$lte": datetime.datetime.utcnow()}})

    def run(self):
        logging.debug("Scheduler thread started")
        # Executing scheduler thread while JobQueue is running.
        while self.queue._running:
            adjust = self.processing()
            # sleep between re-checking
            time.sleep(self._when(adjust))

        logging.debug("Scheduler thread stopped")

    @adjust
    def processing(self):
        for entry in self.get_due_entries():
            try:
                task = ScheduleTask.load(entry, self._bot)
                job = task.get_job(self._app, self._bot)
                self.queue.put(job, task.next_run)
            except Exception as err:
                logging.exception(str(err))
            else:
                task.done()

    def _when(self, drift=0):
        """Return adjusted time sleep."""
        tick = self._sync_every - drift
        return tick if tick > 0 else 0
