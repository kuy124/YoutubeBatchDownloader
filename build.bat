@echo off
TITLE Building YouTube Batch Downloader release
setlocal EnableExtensions

pushd "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0packaging\build_release.ps1"
set "BUILD_EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %BUILD_EXIT_CODE%
