#!/usr/bin/env bash

poetry config virtualenvs.in-project true
poetry install

npm install -g pyright@latest