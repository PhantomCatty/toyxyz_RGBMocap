@echo off
setlocal DisableDelayedExpansion
call "%~dp0LocalEnv.cmd"
call "%~dp0install.cmd" %*
exit /b %errorlevel%
