import inspect
import json
import sys
from datetime import datetime
from enum import Enum

import colorful

_colorize = colorful.Colorful()
_colorize.use_style("solarized")

_serializable_types = (dict, list, tuple, int, float, bool, type(None))


def _time():
    # ISO-8601 time with timezone parameter.
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_time(time):
    return datetime.fromisoformat(time.replace("Z", "+00:00"))


def _no_color(x):
    return x


def _get_caller_context():
    try:
        frame = inspect.stack()[2]
        filename = frame[0].f_code.co_filename
        # TODO: Maybe use the full filename if it is generally useful.
        return "{}:{}".format(filename.split("/")[-1], frame[0].f_lineno)
    except KeyError:
        return "unknown"


class Log:
    """Static methods for logging to stderr and parsing log streams.

    Prefer using `info` or `warn` directly over `_log`. This is an opinionated logger; all log
    entries are separated by newlines (so log messages are newline-escaped), and each log entry
    has four tab-separated columns (level, time, context, and message).

    NOTE: ERROR, FATAL, and other similar log levels are not included since typically the program
    should crash when one of these scenarios occurs.

    """

    class Level(Enum):
        INFO = "INFO"
        WARN = "WARN"
        DATA = "DATA"

    @staticmethod
    def _log(
        log_level,
        message,
        context=_get_caller_context(),
        color_level=_no_color,
        color_time=_no_color,
        color_message=_no_color,
        color_context=_no_color,
    ):
        log_message = [color_level(log_level.value), color_time(_time())]
        log_message.append(color_context(context))
        log_message.append(color_message(str(message).replace("\n", "\\n").replace("\t", "\\t")))
        print("\t".join(str(x) for x in log_message), file=sys.stderr)

    @staticmethod
    def info(message):
        """Logs messages that are part of normal program operation."""
        Log._log(
            Log.Level.INFO,
            message,
            context=_get_caller_context(),
            color_level=_colorize.green,
            color_time=_colorize.cyan,
            color_context=_colorize.violet,
        )

    @staticmethod
    def warn(message):
        """Logs messages that indicate potential (non-fatal) issues."""
        Log._log(
            Log.Level.WARN,
            message,
            context=_get_caller_context(),
            color_level=_colorize.orange,
            color_time=_colorize.cyan,
            color_context=_colorize.violet,
        )

    @staticmethod
    def data(key, value):
        """Logs values that comprise a data stream."""
        warning = None
        if isinstance(value, _serializable_types):
            json_value = value
        else:
            try:
                json_value = value.json_value()
                if not isinstance(json_value, _serializable_types):
                    warning = "json_value for type {} returned a JSON-incompatible object"
            except (AttributeError, TypeError) as e:
                if isinstance(e, TypeError):
                    warning = "json_value for type {} has a bad signature"
                else:
                    warning = "object of type {} has no json_value method"
        try:
            json_message = json.dumps({"key": key, "value": json_value})
        except TypeError:
            # Unfortunately the `json_value` hack is not recursive by default.
            warning = "inner fields of this object are JSON-incompatible"
        if warning is not None:
            json_value = repr(value)
            Log.warn(warning.format(type(value).__name__) + " (falling back to repr)")
        Log._log(
            Log.Level.DATA,
            json_message,
            context=_get_caller_context(),
            color_level=_colorize.blue,
            color_time=_colorize.cyan,
            color_context=_colorize.violet,
        )

    class Entry:
        """A parsed log entry."""

        # Hacky solution to prevent manual construction.
        __private = object()

        class Error(Exception):
            pass

        def __init__(self, private, level, timestamp, context, message):
            if private != Log.Entry.__private:
                raise Log.Entry.Error("constructor is private")
            self.__level = level
            self.__timestamp = timestamp
            self.__context = context
            self.__message = message

        @property
        def level(self):
            return self.__level

        @property
        def timestamp(self):
            return self.__timestamp

        @property
        def context(self):
            return self.__context

        @property
        def message(self):
            return self.__message

        @staticmethod
        def parse(line):
            """Parses a log line into a log entry."""
            lines = line.split("\n")
            if len(lines) != 2 or lines[1] != "":
                raise Log.Entry.Error("expected a single log line")
            line = lines[0]

            fields = line.split("\t")
            if len(fields) != 4:
                # TODO: Remove print.
                print(fields)
                raise Log.Entry.Error("malformed log entry")

            try:
                level = Log.Level(fields[0])
            except ValueError:
                raise Log.Entry.Error("malformed log level")

            try:
                timestamp = _parse_time(fields[1])
                if timestamp.tzinfo is None:
                    raise Log.Entry.Error("timestamp has no timezone")
            except ValueError:
                raise Log.Entry.Error("malformed timestamp")

            context_fields = fields[2].split(":")
            if len(context_fields) != 2:
                raise Log.Entry.Error("malformed context")
            context_file = context_fields[0]
            try:
                context_line = int(context_fields[1])
            except ValueError:
                raise Log.Entry.Error("malformed line number for context")
            context = (context_file, context_line)

            if level == Log.Level.DATA:
                try:
                    message = json.loads(fields[3])
                except json.decoder.JSONDecodeError:
                    raise Log.Entry.Error("could not JSON-decode data message")
            else:
                message = fields[3]

            return Log.Entry(Log.Entry.__private, level, timestamp, context, message)

    @staticmethod
    def stream(file, levels=None):
        """Returns an generator of log entries from a stream of log lines.

        Args:
            file (File): A handle to an input stream. The file should be open when the generator
                gets run.
            levels (set): A set of log levels to filter by. The default is None, which includes
                entries from all levels.

        """
        for line in file:
            entry = Log.Entry.parse(line)
            if levels is None or entry.level in levels:
                yield entry
