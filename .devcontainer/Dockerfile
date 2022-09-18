# [Choice] Python version (use -bullseye variants on local arm64/Apple Silicon): 3, 3.10, 3.9, 3.8, 3.7, 3.6, 3-bullseye, 3.10-bullseye, 3.9-bullseye, 3.8-bullseye, 3.7-bullseye, 3.6-bullseye, 3-buster, 3.10-buster, 3.9-buster, 3.8-buster, 3.7-buster, 3.6-buster
ARG VARIANT=3-bullseye
FROM mcr.microsoft.com/vscode/devcontainers/python:0-${VARIANT}

ENV PYTHONUNBUFFERED 1

# [Choice] Node.js version: none, lts/*, 16, 14, 12, 10
ARG NODE_VERSION="none"
RUN if [ "${NODE_VERSION}" != "none" ]; then su vscode -c "umask 0002 && . /usr/local/share/nvm/nvm.sh && nvm install ${NODE_VERSION} 2>&1"; fi

# https://stackoverflow.com/questions/53835198/integrating-python-poetry-with-docker
# https://gist.github.com/jthorniley/fba81c62a9d45c723777c7205ff96481
RUN curl -sSL https://install.python-poetry.org | python - --version=1.1.14
RUN .env* ./
ENV PATH "/home/vscode/.poetry/bin:$PATH"
RUN npm i -g pyright
