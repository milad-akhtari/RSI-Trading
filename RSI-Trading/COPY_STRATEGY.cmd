@echo off
setlocal
if not exist "%~dp0pine\rsi_trend_strategy.pine" goto missing
"%SystemRoot%\System32\clip.exe" < "%~dp0pine\rsi_trend_strategy.pine"
if errorlevel 1 goto missing
echo Strategy copied to the clipboard.
echo In TradingView: open Pine Editor, select all, paste, save and add to chart.
echo Keep standard candles on 5 minutes and RSI length 9, source Close.
pause
exit /b 0
:missing
echo Could not copy the strategy. Extract the complete ZIP first.
pause
exit /b 1
