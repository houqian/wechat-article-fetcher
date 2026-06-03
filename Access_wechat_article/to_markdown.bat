@echo off
REM 将已下载的文章 (all_data 下的 index.html) 批量转换为 Markdown
REM 用法: 直接双击转换 all_data 下全部文章; 或把某个目录拖到本 bat 上只转换该目录

chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

".venv\Scripts\python.exe" html_to_md.py %*
pause
