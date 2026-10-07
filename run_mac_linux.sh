#!/usr/bin/env bash
# JourneyPulse: install packages (first time only) and start the server.
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt --quiet
if [ -f .env ]; then set -a; . ./.env; set +a; fi
python3 -m backend.server --open
