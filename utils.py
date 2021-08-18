from dotenv import load_dotenv
load_dotenv()

from rich.traceback import install as install_rich_tracebacks
# install_rich_tracebacks(show_locals=True, width=200)
install_rich_tracebacks(width=200)

import structlog
import logging
import os

from structlog.stdlib import filter_by_level

def setLevel(level):
  level = logging.__getattribute__(level.upper())
  structlog.configure(
      wrapper_class=structlog.make_filtering_bound_logger(level),
  )

log_level = os.environ.get('LOG_LEVEL', 'WARN')
setLevel(log_level)

log = structlog.get_logger()

def table_output(array_of_dicts):
  # note all table formats allow float formatting
  from tabulate import tabulate
  return tabulate(array_of_dicts, headers="keys", tablefmt="github", floatfmt=".2f")

def csv_output(array_of_dicts):
  import sys
  import csv

  # TODO return CSV as a string
  writer = csv.writer(sys.stdout)
  writer.writerow(array_of_dicts[0].keys())
  writer.writerows([row.values() for row in array_of_dicts])
