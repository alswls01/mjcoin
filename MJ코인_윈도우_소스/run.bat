@echo off
rem exe 없이 바로 실행 (테스트용)
cd /d "%~dp0"
python -m pip install -r requirements.txt >nul
python mj_coin_win.py
