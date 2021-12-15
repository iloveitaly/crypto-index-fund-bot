from decimal import Decimal

from rich.traceback import install as install_rich_tracebacks

# install_rich_tracebacks(show_locals=True, width=200)
install_rich_tracebacks(width=200)

import logging
import typing as t
from typing import overload

import structlog
from decouple import config
from structlog.threadlocal import wrap_dict

from .data_types import CryptoBalance, CryptoData


def setLevel(level):
    level = getattr(logging, level.upper())
    structlog.configure(
        # context_class enables thread-local logging to avoid passing a log instance around
        # https://www.structlog.org/en/21.1.0/thread-local.html
        context_class=wrap_dict(dict),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

    # TODO maybe round floats automatically? https://github.com/kiwicom/kiwi-structlog-config/blob/dc6bba731de956e0a76f148d0c77bd419bd95283/kw/structlog_config/processors.py#L16


log_level = config("LOG_LEVEL", default="WARN")
setLevel(log_level)

log = structlog.get_logger()

_cached_result = {}


def cached_result(key: str, func: t.Callable):
    if in_django_environment():
        from django.core.cache import cache

        if cached_value := cache.get(key):
            return cached_value

        # use a 30m timeout by default for now
        value = func()
        cache.set(key, value, timeout=60 * 30)
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


# https://stackoverflow.com/questions/52445559/how-can-i-type-hint-a-function-where-the-return-type-depends-on-the-input-type-o
@overload
def entry_key_with_symbol(
    list_of_coins: t.Union[t.List[CryptoBalance], t.List[CryptoData]], symbol_or_dict: t.Union[CryptoBalance, CryptoData, str], key: str
) -> t.Optional[t.Union[str, Decimal]]:
    ...


@overload
def entry_key_with_symbol(list_of_coins: t.List[CryptoBalance], symbol_or_dict: t.Union[CryptoBalance, str], key: None) -> t.Optional[CryptoBalance]:
    ...


@overload
def entry_key_with_symbol(list_of_coins: t.List[CryptoData], symbol_or_dict: t.Union[CryptoData, str], key: None) -> t.Optional[CryptoData]:
    ...


def entry_key_with_symbol(
    list_of_coins: t.Union[t.List[CryptoBalance], t.List[CryptoData]], symbol_or_dict: t.Union[str, CryptoBalance, CryptoData], key: t.Optional[str]
) -> t.Optional[t.Union[CryptoBalance, CryptoData, str, Decimal]]:
    if isinstance(symbol_or_dict, str):
        symbol = symbol_or_dict
    else:
        symbol = symbol_or_dict["symbol"]

    match = next((target for target in list_of_coins if target["symbol"] == symbol), None)

    if not match:
        return None

    if not key:
        return match

    # optionally pluck a specific field from the match
    return match[key]


def currency_format(value):
    # https://stackoverflow.com/questions/320929/currency-formatting-in-python
    import locale

    locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
    return locale.currency(value, grouping=True)


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
    import csv
    import sys

    # TODO return CSV as a string
    writer = csv.writer(sys.stdout)
    writer.writerow(array_of_dicts[0].keys())
    writer.writerows([row.values() for row in array_of_dicts])
