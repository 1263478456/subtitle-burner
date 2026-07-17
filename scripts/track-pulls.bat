@echo off
REM Docker Hub Pull 数追踪脚本 (Windows)
REM 用法: track-pulls.bat [--history] [--csv]

python "%~dp0track-pulls.py" %*
