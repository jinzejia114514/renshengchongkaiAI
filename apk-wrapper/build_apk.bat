@echo off
chcp 65001 >nul
echo ============================================
echo    AI 人生重开手帐 - APK 一键构建
echo ============================================
echo.

set ANDROID_HOME=D:\Android
set ANDROID_SDK_ROOT=D:\Android
cd /d "%~dp0"

echo [1/3] 正在构建（首次构建需下载依赖，耗时较长）...
call "D:\Android\gradle\latest\bin\gradle.bat" assembleDebug --no-daemon
if errorlevel 1 (
    echo.
    echo [错误] 构建失败，请查看上方错误日志
    echo        常见原因：Gradle daemon 端口占用（重新运行本脚本即可）
    pause
    exit /b 1
)

echo.
echo [2/3] 构建成功，复制 APK 到桌面...
copy /y "app\build\outputs\apk\debug\app-debug.apk" "%USERPROFILE%\Desktop\AI人生重开手帐.apk" >nul
if errorlevel 1 (
    echo [错误] 复制到桌面失败，APK 在:
    echo        app\build\outputs\apk\debug\app-debug.apk
    pause
    exit /b 1
)

echo.
echo [3/3] 完成！
echo --------------------------------------------
echo  APK 位置: %USERPROFILE%\Desktop\AI人生重开手帐.apk
echo  传到手机覆盖安装即可
echo --------------------------------------------
pause
