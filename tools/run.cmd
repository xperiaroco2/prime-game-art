@echo off
rem prime-game-art task runner for PowerShell and cmd: tools\run.cmd <command> [args]
rem Finds Python as PYTHON_BIN, else the py launcher, else python on PATH.
rem No ( ) blocks around the call: inside a block %ERRORLEVEL% would be read before the call runs.
setlocal
set "PY="
if defined PYTHON_BIN set PY="%PYTHON_BIN%"
if not defined PY where py >nul 2>nul && set "PY=py -3"
if not defined PY set "PY=python"
%PY% "%~dp0run.py" %*
exit /b %ERRORLEVEL%
