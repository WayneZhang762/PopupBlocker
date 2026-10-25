@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo === 静窗 · 环境重建 ===
echo.

set "PY=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if exist "%PY%" goto found

set "PY=python"
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 找不到可用的 Python。
    echo 请安装 Python 3.11 以上版本后重试，或联系开发同学。
    pause
    exit /b 1
)

:found
echo 使用解释器: %PY%
"%PY%" --version

if exist ".venv" (
    echo 清理旧环境...
    rmdir /s /q ".venv"
)

echo 创建虚拟环境...
"%PY%" -m venv .venv
if errorlevel 1 goto fail

echo 安装依赖（首次会比较慢，PySide6 约 80MB）...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail

echo.
echo === 完成，可以双击「启动.bat」了 ===
pause
exit /b 0

:fail
echo.
echo [失败] 依赖安装没成功。若卡在下载，可先配置国内镜像后重试：
echo   .venv\Scripts\python.exe -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
pause
exit /b 1
