@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist .venv\Scripts\python.exe (echo 请先双击 install.bat 安装 & pause & exit /b 1)
echo 正在启动网页界面，浏览器会自动打开 http://127.0.0.1:7860
echo 关闭这个窗口即可退出。
.venv\Scripts\python.exe -m music_muse web
pause
