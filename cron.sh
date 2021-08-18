#!/bin/bash -l
set -eu

# export all env vars to a file which is automatically sourced inside the cron subshell
# https://gist.github.com/athlan/b6f09977e2f5cf20840ef61ca3cda932
printenv | awk -F= '{print "export " "\""$1"\"""=""\""$2"\"" }' >> /etc/profile

if [ "${SCHEDULE}" = "NONE" ]; then
  python main.py buy
else
  # `-l` ensures that /etc/profile is picked up by the sh subshell
  # stdout redirect ensures logs are redirected to the parent process https://snippets.aktagon.com/snippets/945-how-to-get-cron-to-log-to-stdout-under-docker-and-kubernetes
  echo "$SCHEDULE root sh -lc '/usr/local/bin/python $PWD/main.py buy' > /proc/1/fd/1 2>&1" >> /etc/crontab

  # debian slim does not include cron by default, this must be installed via Dockerfile
  # additionally, busybox does *not* add the cron process, so we must use the debian cron package
  cron -L 8 -f
fi