@echo off
rem Start the Chronic Care Loop on http://localhost:8000/ (Python 3.10 or later; nothing to install)
cd /d "%~dp0server"
set CCL_WEB=..
set CCL_RULES=..\4-data-model\rules
python -m backend.server %*
