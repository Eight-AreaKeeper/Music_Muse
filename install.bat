@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set "PY=.venv\Scripts\python.exe"

echo ==== Music_Muse 安装（CPU 版） ====

where uv >nul 2>nul
if not errorlevel 1 goto :have_uv
echo [1/4] 安装 uv（Python 环境管理工具）...
powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul
if errorlevel 1 goto :fail
:have_uv

echo [2/4] 创建 Python 3.10 虚拟环境...
uv venv -p 3.10 .venv
if errorlevel 1 goto :fail

echo [3/4] 安装依赖（第一次较慢）...
uv pip install --python %PY% -r requirements\windows-lock.txt
if errorlevel 1 goto :fail
uv pip install --python %PY% --no-deps basic-pitch==0.4.0
if errorlevel 1 goto :fail

echo [4/4] 下载模型权重（约 1 GB）...
%PY% -m music_muse.download
if errorlevel 1 goto :fail

echo.
echo 安装完成。双击 start.bat 打开网页界面。
pause
exit /b 0

:fail
echo.
echo 安装失败，请把上面的报错截图发给 Claude。
pause
exit /b 1
