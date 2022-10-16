FROM mcr.microsoft.com/vscode/devcontainers/base:0-ubuntu-22.04

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    autoconf \
    build-essential \
    fop \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libncurses-dev \
    libncurses5-dev \
    libpng-dev \
    libssh-dev \
    libxml2-utils \
    m4 \
    openjdk-11-jdk \
    unixodbc-dev \
    xsltproc \
    lbzip2 \
    bzip2 \
    libncursesw5 \
    libsqlite3-dev \
    libffi-dev \
    python3-dev \
    libreadline-dev \
    libpq-dev \
    zlib1g-dev \
    postgresql-client \
    lzma-dev \
    liblzma-dev \
    automake

# https://github.com/erlang/erlang-org/blob/f5538eea5546884097ef66ef29a6ae7a8d874069/.devcontainer/Dockerfile#L18
USER vscode
RUN git clone https://github.com/asdf-vm/asdf.git ~/.asdf --branch v0.10.2