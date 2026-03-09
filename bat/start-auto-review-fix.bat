@echo off
title AI Review Fix Daemon
echo ========================================
echo  AI Auto Review Fix Daemon
echo  Ctrl+C to stop
echo ========================================
echo.

pushd "%~dp0.." || exit /b 1
call pnpm daemon:loop
popd

echo.
echo Daemon stopped.
pause
