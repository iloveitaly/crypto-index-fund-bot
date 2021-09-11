from .application import *

DATABASES = {"default": dj_database_url.parse(config("TEST_DATABASE_URL"))}

# https://stackoverflow.com/questions/19236771/add-method-imports-to-shell-plus
SHELL_PLUS_PRE_IMPORTS = [
    ("decimal", "Decimal"),
]

# TODO we should log SQL by default
# https://avilpage.com/2018/05/django-tips-tricks-log-sql-queries-to-console.html
# LOGGING = {
#   'loggers': {
#     'django.db.backends': {
#         'level': 'DEBUG',
#         'handlers': ['console', ],
#     },
#   }
# }
