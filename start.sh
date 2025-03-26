#!/bin/bash

docker run -it --rm --name aipython -v $(pwd)/aipython.toml:/app/aipython.toml -v $(pwd)/work:/app/work lgxz/aipython
