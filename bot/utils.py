from rich.traceback import install as install_rich_tracebacks
# install_rich_tracebacks(show_locals=True, width=200)
install_rich_tracebacks(width=200)

import structlog
import logging
import os

from structlog.threadlocal import wrap_dict

def setLevel(level):
  level = logging.__getattribute__(level.upper())
  structlog.configure(
    # context_class enables thread-local logging to avoid passing a log instance around
    # https://www.structlog.org/en/21.1.0/thread-local.html
    context_class=wrap_dict(dict),

    wrapper_class=structlog.make_filtering_bound_logger(level),
  )

log_level = os.environ.get('LOG_LEVEL', 'WARN')
setLevel(log_level)

log = structlog.get_logger()

def table_output_with_format(array_of_dicts, format):
  if not array_of_dicts: return None

  if format == 'md':
    return csv_table_output(array_of_dicts)
  else:
    return markdown_table_output(array_of_dicts)

def markdown_table_output(array_of_dicts):
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
