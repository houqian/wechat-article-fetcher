@echo off
REM 启动微信公众号文章获取工具 (main.py)
REM 自动设置 UTF-8 控制台、Playwright 本地内核路径，并使用项目虚拟环境

chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0.venv\.playwright-browsers"

".venv\Scripts\python.exe" main.py
pause
