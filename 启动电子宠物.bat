@echo off
cd /d "%~dp0"

rem 检查 Python
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+（勾选 Add to PATH）。
    pause
    exit /b 1
)

rem 精灵帧不存在时先自动生成
if not exist "sprites_display\cockroach\default\walk_1.png" (
    echo 正在生成精灵帧（首次运行会自动完成）...
    python make_sprites.py
    if errorlevel 1 (
        echo [错误] 精灵帧生成失败，请手动运行 python make_sprites.py 查看报错。
        pause
        exit /b 1
    )
)

rem 用 pythonw 后台启动；重复启动由宠物程序自身的单实例保护拦截
start "" pythonw cockroach_pet.py
