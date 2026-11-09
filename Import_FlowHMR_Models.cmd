@echo off
setlocal DisableDelayedExpansion
call "%~dp0LocalEnv.cmd"
"%~dp0runtime\python.exe" -I -X utf8 -B "%~dp0.setup\import_flow_manual.py" %*
set "import_exit=%errorlevel%"
if "%~1"=="" pause
exit /b %import_exit%
