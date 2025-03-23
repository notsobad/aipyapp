#!/bin/bash

docker run -it --rm --env-file .env -v $(pwd)/work:/app/work aipython
