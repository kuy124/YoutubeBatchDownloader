@echo off
TITLE YouTube Batch Downloader
:: Activate virtual environment and run the app
call venv\Scripts\activate.bat

:: Add root directory to python path
set PYTHONPATH=%cd%

echo Starting YouTube Batch Downloader...
python app/main.py