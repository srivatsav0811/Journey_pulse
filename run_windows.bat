@echo off
REM JourneyPulse: install packages (first time only) and start the server.
REM The browser opens by itself once the data is ready.
cd /d "%~dp0"
python -m pip install -r requirements.txt --quiet
if exist .env (
  for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
)
python -m backend.server --open
pause
