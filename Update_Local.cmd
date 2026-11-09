@echo off
setlocal DisableDelayedExpansion
call "%~dp0LocalEnv.cmd"
call "%~dp0update.cmd" %*
exit /b %errorlevel%
