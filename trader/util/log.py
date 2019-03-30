import inspect
import sys
from datetime import datetime

import colorful

_colorize = colorful.Colorful()
_colorize.use_style("solarized")


def _time():
    # ISO-8601 time with timezone parameter.
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _no_color(x):
    return x


def _get_caller_context():
    frame = inspect.stack()[2]
    filename = frame[0].f_code.co_filename
    # TODO: Maybe use the full filename if it is generally useful.
    return "{}:{}".format(filename.split("/")[-1], frame[0].f_lineno)


class Log:
    """Static methods for logging to stderr.

    Prefer using `info` or `warn` directly over `_log`. This is an opinionated logger; all log
    entries are separated by newlines (so log messages are newline-escaped), and each log entry
    has four tab-separated columns (level, time, context, and message).

    NOTE: ERROR, FATAL, and other similar log levels are not included since typically the program
    should crash when one of these scenarios occurs.

    """

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
        log_message = [color_level(log_level), color_time(_time())]
        log_message.append(color_context(context))
        log_message.append(color_message(str(message).replace("\n", "\\n")))
        print("\t".join(str(x) for x in log_message), file=sys.stderr)

    @staticmethod
    def info(message):
        Log._log(
            "INFO",
            message,
            context=_get_caller_context(),
            color_level=_colorize.blue,
            color_time=_colorize.cyan,
            color_context=_colorize.violet,
        )

    @staticmethod
    def warn(message):
        Log._log(
            "WARN",
            message,
            context=_get_caller_context(),
            color_level=_colorize.orange,
            color_time=_colorize.cyan,
            color_context=_colorize.violet,
        )
