#!/bin/bash

DOCKER="docker run -v $(pwd)/aipython.toml:/app/aipython.toml -v $(pwd)/work:/app/work"

if [ "$1" = "--ttyd" ]; then
    ${DOCKER} -d --name aipython-ttyd -p 8080:80 lgxz/aipython:latest --ttyd
else
    ${DOCKER} -it --rm --name aipython lgxz/aipython:latest
fi
