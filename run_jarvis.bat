@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo        Jarvis AI Voice Assistant
echo ========================================
echo.

REM --- 1. Python dhoondo (python / py) ---
set "PYCMD=python"
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python nahi mila! python.org se Python 3.10+ install karo.
        echo         Install me "Add python to PATH" tick karna.
        pause
        exit /b 1
    ) else (
        set "PYCMD=py"
    )
)
for /f "tokens=*" %%v in ('%PYCMD% --version 2^>^&1') do echo [OK] %%v

REM --- 2. main.py check ---
if not exist "main.py" (
    echo [ERROR] main.py nahi mila! Ye bat file project folder me honi chahiye.
    pause
    exit /b 1
)

REM --- 3. .env + API key check ---
if not exist ".env" (
    echo [ERROR] .env file nahi mila! .env me ye likho:
    echo         GOOGLE_API_KEY=your_api_key_here
    pause
    exit /b 1
)
%PYCMD% -c "import os; assert any(l.strip().startswith('GOOGLE_API_KEY=') and len(l.strip().split('=',1)[1].strip().strip('\"').strip(chr(39)))>10 for l in open('.env',encoding='utf-8',errors='ignore')), 'key missing'" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] .env me GOOGLE_API_KEY khali / galat hai. API key dalo.
    pause
    exit /b 1
)
echo [OK] .env me API key mili.

REM --- 4. Dependencies check + auto-install ---
%PYCMD% -c "import google.genai, pyaudio, dotenv" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Dependencies missing - install ho rahi hain...
    %PYCMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] pip install fail! Try karo:
        echo   %PYCMD% -m pip install -r requirements.txt
        pause
        exit /b 1
    )
) else (
    echo [OK] Dependencies installed hain.
)

echo.
echo [MIC]   Default microphone chalu - seedha boliye
echo [TEXT]  Ctrl+C = text mode, wapas Ctrl+C = mic mode
echo [EXIT]  'exit' likhein ya Ctrl+Break dabayein
echo [YOUTUBE] Maya se bolo: "youtube open kar" / "youtube pe koi gana chala de"
echo.
echo --- Jarvis start ho raha hai ---
echo.

%PYCMD% main.py
if errorlevel 1 (
    echo.
    echo [ERROR] Python run me error aaya. Upar wala message dekho:
    echo   - Mic error ho to Windows Settings - Sound - Input check karo
    echo   - API error ho to API key / internet check karo
    echo.
)
pause
