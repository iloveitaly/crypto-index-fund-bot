#!/usr/bin/env bash

cd "${0%/*}/.."

source "$HOME/.asdf/asdf.sh"

/bin/find $CODESPACE_VSCODE_FOLDER -name ".tool-versions" | while read filePath; do
  echo "asdf setup for $filePath"

  # install all required plugins
  cat $filePath | cut -d' ' -f1 | grep "^[^\#]" | xargs -i asdf plugin add {}

  # install all required versions
  (cd $(dirname $filePath) && asdf install)
done

if test -f $CODESPACE_VSCODE_FOLDER/.devcontainer/docker-compose.yml; then
  docker compose up -d
fi