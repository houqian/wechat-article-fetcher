@echo off
REM 方案B: 指定公众号 + 关键词筛选, 自动下载并转 Markdown
REM 关键词从 keywords.txt 读取 (或在命令行传: search_to_md Agent 智能体)
REM 运行后按提示粘贴每个公众号的 Fiddler token 链接

chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0.venv\.playwright-browsers"

".venv\Scripts\python.exe" search_md.py %*
pause
