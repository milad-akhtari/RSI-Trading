@echo off
setlocal
set "RSI_RELEASE_DIR=%~dp0"
set "RSI_SETTINGS_DIR=%~dp0"
if exist "%RSI_SETTINGS_DIR%.venv\Scripts\python.exe" goto run_check
set "RSI_SETTINGS_DIR=%USERPROFILE%\Downloads\RSI-Trading\"
if exist "%RSI_SETTINGS_DIR%.venv\Scripts\python.exe" goto run_check
echo Existing Python environment was not found in this folder or Downloads\RSI-Trading.
echo Place this release's files inside your existing RSI-Trading folder and retry.
pause
exit /b 1
:run_check
cd /d "%RSI_RELEASE_DIR%"
if errorlevel 1 exit /b 1
echo US30 READ-ONLY CHECK - all broker writes blocked.
echo Keep MT5 open on MetaQuotes-Demo with Algo Trading OFF.
"%RSI_SETTINGS_DIR%.venv\Scripts\python.exe" "%RSI_RELEASE_DIR%windows_readonly.py" --settings-directory "%RSI_SETTINGS_DIR%."
set "RSI_CHECK_EXIT=%ERRORLEVEL%"
echo.
if "%RSI_CHECK_EXIT%"=="0" echo PASS: isolated US30 gateway check completed without orders.
if not "%RSI_CHECK_EXIT%"=="0" echo CHECK STOPPED: see the reason above. No safety gate was bypassed.
pause
exit /b %RSI_CHECK_EXIT%
