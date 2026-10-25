@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo.
    echo   运行环境还没准备好，正在自动安装，请稍等...
    echo.
    call "%~dp0重装环境.bat"
    if not exist ".venv\Scripts\pythonw.exe" (
        echo   安装失败，请把上面的报错发给开发同学。
        pause
        exit /b 1
    )
)

start "" ".venv\Scripts\pythonw.exe" "app\main.py"
exit /b 0
