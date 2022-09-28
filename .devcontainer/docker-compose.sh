# TODO this still needs some work, doesn't work properly yet...

# since there are two docker-compose files, we need to make sure we run inside the `.devcontainer`
cd "$(dirname "$0")"

# using this hack, we need to run docker compose manually and cannot start it as a daemon service
sudo dockerd &

sudo docker compose up -d