#!/usr/bin/env bash
# Description: for moving local machine secrets to a codespace

targetMachine=$(gh codespace list --repo iloveitaly/$(gh repo view --json name | jq -r ".name") --json name | jq -r '.[0].name')

echo "Using codespace: $targetMachine"

gh codespace cp -e -c $targetMachine .env 'remote:/workspaces/$RepositoryName/.env'
