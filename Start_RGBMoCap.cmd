@echo off
setlocal DisableDelayedExpansion
call "%~dp0LocalEnv.cmd"
call "%~dp0RGBMoCap.cmd" %*
exit /b %errorlevel%
