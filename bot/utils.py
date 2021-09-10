from rich.traceback import install as install_rich_tracebacks

# install_rich_tracebacks(show_locals=True, width=200)
install_rich_tracebacks(width=200)

import structlog
import logging
from decouple import config
import typing as t

from structlog.threadlocal import wrap_dict


def setLevel(level):
    level = logging.__getattribute__(level.upper())
    structlog.configure(
        # context_class enables thread-local logging to avoid passing a log instance around
        # https://www.structlog.org/en/21.1.0/thread-local.html
        context_class=wrap_dict(dict),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


log_level = config("LOG_LEVEL", default="WARN")
setLevel(log_level)

log = structlog.get_logger()

_cached_result = {}
def cached_result(key: str, func: t.Callable):
    if in_django_environment():
        from django.core.cache import cache

        if cached_value := cache.get(key):
            return cached_value

        value = func()
        cache.set(key, value)
        return value
    else:
        # if no django, then setup a simple dict-based cache to avoid
        # hitting the APIs too many times within a single process
        global _cached_result
        if key in _cached_result:
            return _cached_result[key]

        value = func()
        _cached_result[key] = value
        return value

def in_django_environment():
    return config("DJANGO_SETTINGS_MODULE", default=None) != None

def table_output_with_format(array_of_dicts, format):
    if not array_of_dicts:
        return None

    if format == "md":
        return markdown_table_output(array_of_dicts)
    else:
        return csv_table_output(array_of_dicts)


def markdown_table_output(array_of_dicts):
    # TODO would be nice to add comma separators to money values
    # note all table formats allow float formatting
    from tabulate import tabulate

    return tabulate(array_of_dicts, headers="keys", tablefmt="github", floatfmt=".2f")


def csv_table_output(array_of_dicts):
    import sys
    import csv

    # TODO return CSV as a string
    writer = csv.writer(sys.stdout)
    writer.writerow(array_of_dicts[0].keys())
    writer.writerows([row.values() for row in array_of_dicts])
