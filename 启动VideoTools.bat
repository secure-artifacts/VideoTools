@echo off
:: 切换到脚本所在目录（项目根目录），无论从哪里启动都正确
cd /d "%~dp0"
python main\main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [错误] 启动失败，错误码: %ERRORLEVEL%
    echo 请确保已安装 Python 和所有依赖（pip install -r requirements.txt）
    pause
)
