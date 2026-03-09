@echo off
title AI Review Fix Daemon
echo ========================================
echo  AI Auto Review Fix Daemon
echo  Ctrl+C to stop
echo ========================================
echo.

cd /d "e:\work\auto-review-fix-vc"
pnpm daemon:loop

echo.
echo Daemon stopped.
pause
