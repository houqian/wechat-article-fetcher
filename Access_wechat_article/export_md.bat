@echo off
REM 把 all_data 下散落的 article.md 汇总导出到 导出_md\<公众号>\<文章标题>.md
REM 图片统一放到各公众号的 assets\ 下, 链接自动重写

chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

".venv\Scripts\python.exe" export_md.py %*
pause
