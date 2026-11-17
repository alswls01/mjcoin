@echo off
chcp 65001 >nul
rem MJ코인 설치 파일(dist\MJCoin_Setup.exe) 만들기
rem 필요: 파이썬 3.10 이상 (python.org, 설치할 때 "Add python.exe to PATH" 체크)
rem NSIS 가 없으면 winget 으로 설치를 시도함
cd /d "%~dp0"
python -m pip install --upgrade -r requirements.txt || goto err
python version_info.py || goto err
python -m PyInstaller --noconfirm --onedir --collect-submodules winrt --collect-submodules keyring.backends --windowed --name MJCoin --icon mjcoin.ico --version-file version_info.txt --add-data "web;web" --add-data "mjcoin.ico;." mj_coin_win.py || goto err
set "MAKENSIS=%ProgramFiles(x86)%\NSIS\makensis.exe"
if not exist "%MAKENSIS%" (
  echo NSIS 설치 중...
  winget install --id NSIS.NSIS -e --accept-source-agreements --accept-package-agreements
)
if not exist "%MAKENSIS%" ( echo NSIS 를 찾을 수 없어요. https://nsis.sourceforge.io 에서 설치 후 다시 실행하세요. & goto err )
"%MAKENSIS%" mjcoin.nsi || goto err
echo.
echo 완료: dist\MJCoin_Setup.exe  (설치 파일)   dist\MJCoin\MJCoin.exe  (설치 없이 실행)
explorer dist
pause
exit /b 0
:err
echo 실패했어요. 위 오류 내용을 확인하세요.
pause
exit /b 1
