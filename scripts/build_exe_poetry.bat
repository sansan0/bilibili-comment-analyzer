@echo off
chcp 65001 > nul
color 0A
echo ===================================
echo   哔哩哔哩评论观察者 - 打包工具 (pipx+Poetry版)
echo ===================================
echo.
REM 检查 pipx 是否已安装
where pipx >nul 2>nul
if %errorlevel% neq 0 (
    echo 错误: 找不到pipx，请先安装pipx。
    echo 可以通过以下命令安装: python -m pip install --user pipx
    echo 然后运行: python -m pipx ensurepath
    pause
    exit /b 1
)
REM 检查 Poetry 是否已安装
pipx list | findstr poetry >nul
if %errorlevel% neq 0 (
    echo 警告: 未找到通过pipx安装的Poetry。
    echo 正在尝试安装Poetry...
    pipx install poetry
    
    if %errorlevel% neq 0 (
        echo 错误: 安装Poetry失败！
        pause
        exit /b 1
    )
)
REM 安装项目依赖
echo 安装项目依赖...
cd ..
poetry install
if %errorlevel% neq 0 (
    echo.
    echo 错误: 安装依赖失败！请检查以上错误信息。
    pause
    exit /b 1
)
echo 清理旧的构建文件...
if exist build rmdir /s /q build
echo.
echo 正在使用cx_Freeze打包应用程序...
poetry run cxfreeze build
if %errorlevel% neq 0 (
    echo.
    echo 错误: 打包失败！请检查以上错误信息。
    pause
    exit /b 1
)
echo.
echo ===================================
echo  打包完成！
echo  "%cd%\build\exe.win-amd64-3.x\哔哩哔哩评论观察者.exe"
echo ===================================
echo.
pause