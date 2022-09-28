FROM mcr.microsoft.com/vscode/devcontainers/base:ubuntu-22.04

# docker & docker compose installation
RUN curl -fsSL https://download.docker.com/linux/$(lsb_release -is | tr '[:upper:]' '[:lower:]')/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/$(lsb_release -is | tr '[:upper:]' '[:lower:]') $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null \
 && apt-get update \
 && apt-get install -y docker-ce docker-compose-plugin

# additional packages required for many common python packages
RUN apt-get install -y libssl-dev \
    lbzip2 \
    libncursesw5 \
    libsqlite3-dev \
    libffi-dev \
    python3-dev \
    libreadline-dev \
    libpq-dev \
    zlib1g-dev \
    libncurses5-dev \
    lzma-dev

# https://github.com/erlang/erlang-org/blob/f5538eea5546884097ef66ef29a6ae7a8d874069/.devcontainer/Dockerfile#L18
RUN sudo su -l vscode -c 'git clone https://github.com/asdf-vm/asdf.git ~/.asdf --branch v0.10.2'
