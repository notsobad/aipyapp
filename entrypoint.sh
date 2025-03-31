#!/bin/sh

if [ "$1" = "--ttyd" ]; then
    shift
    ttyd -p 80 -W uv run /app/aipython.py "$@"
else
    uv run /app/aipython.py "$@"
fi
