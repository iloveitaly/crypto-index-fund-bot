# install all required plugins
cat .tool-versions | cut -d' ' -f1 | grep "^[^\#]" | xargs -i asdf plugin add {}

# install all required versions
asdf install

poetry config virtualenvs.in-project true
poetry install

npm install -g pyright@latest