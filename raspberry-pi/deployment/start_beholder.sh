#!/bin/bash

cd /home/bfalco/beholder

exec /home/bfalco/beholder/.venv/bin/python \
	-m uvicorn API.server:app \
	--host 0.0.0.0 \
	--port 8000
