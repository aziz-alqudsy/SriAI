@echo off
echo Sri - AI Little Sister for YouTube Streaming
echo =====================================================

:: Check if .env exists
if not exist .env (
    echo Error: .env file not found
    echo Please run: python setup.py
    echo Then edit .env with your API keys
    pause
    exit /b 1
)

:: Check if virtual environment should be activated
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

:: Run the bot
echo Starting SriAI bot...
python main.py

:: Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo Bot stopped with an error
    pause
)