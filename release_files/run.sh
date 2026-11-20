#!/usr/bin/env sh
# Start the Chronic Care Loop on http://localhost:8000/ (Python 3.10 or later; nothing to install)
cd "$(dirname "$0")/server" || exit 1
export CCL_WEB=.. CCL_RULES=../4-data-model/rules
exec python3 -m backend.server "$@"
