# Load environment variables from .env file
#set dotenv-load := true
#set dotenv-path := ".env"

# show available commands
show-commands:
  just -l

# create python environment
[working-directory: '.']
create-python-env:
  uv venv --python 3.10
  uv sync

