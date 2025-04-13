#!/bin/bash

IMAGE="lgxz/aipy:latest"
DOCKER="docker run -v $(pwd)/aipython.toml:/app/aipy.toml -v $(pwd)/work:/app/work"

if [ "$1" = "--ttyd" ]; then
    ${DOCKER} -d --name aipy-ttyd -p 8080:80 $IMAGE --ttyd
else
    ${DOCKER} -it --rm --name aipy $IMAGE
fi
