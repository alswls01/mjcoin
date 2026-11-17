@echo off
chcp 65001 >nul
rem MJ코인 윈도우 exe 만들기 (파이썬 3.10 이상이 설치되어 있어야 함: https://www.python.org)
cd /d "%~dp0"
python -m pip install --upgrade -r requirements.txt || goto err
python version_info.py || goto err
python -m PyInstaller --noconfirm --onedir --collect-submodules winrt --collect-submodules keyring.backends --windowed --name MJCoin --icon mjcoin.ico --version-file version_info.txt --add-data "web;web" --add-data "mjcoin.ico;." mj_coin_win.py || goto err
echo.
echo 완료: dist\MJCoin\MJCoin.exe
explorer dist
pause
exit /b 0
:err
echo 실패했어요. 위 오류 내용을 확인하세요.
pause
exit /b 1
