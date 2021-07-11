from structlog import get_logger
log = get_logger()

def table_output(array_of_dicts):
  # note all table formats allow float formatting
  from tabulate import tabulate
  print(tabulate(array_of_dicts, headers="keys", tablefmt="github", floatfmt=".2f"))

def csv_output(array_of_dicts):
  import sys
  import csv

  writer = csv.writer(sys.stdout)
  writer.writerow(array_of_dicts[0].keys())
  writer.writerows([row.values() for row in array_of_dicts])
