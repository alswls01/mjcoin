; MJ코인 설치 파일 (NSIS 3). build_installer.bat 와 깃허브 빌드가 사용
Unicode true
!include "MUI2.nsh"
Name "MJ코인"
OutFile "dist\MJCoin_Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\MJCoin"
RequestExecutionLevel user
SetCompressor /SOLID lzma
!define MUI_ICON "mjcoin.ico"
!define MUI_UNICON "mjcoin.ico"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\MJCoin.exe"
!define MUI_FINISHPAGE_RUN_TEXT "MJ코인 실행"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Korean"

Section "MJ코인"
  SetOutPath "$INSTDIR"
  File /r "dist\MJCoin\*.*"
  File "mjcoin.ico"
  CreateShortcut "$SMPROGRAMS\MJ코인.lnk" "$INSTDIR\MJCoin.exe" "" "$INSTDIR\mjcoin.ico"
  CreateShortcut "$DESKTOP\MJ코인.lnk" "$INSTDIR\MJCoin.exe" "" "$INSTDIR\mjcoin.ico"
  WriteUninstaller "$INSTDIR\uninstall.exe"
  !define UK "Software\Microsoft\Windows\CurrentVersion\Uninstall\MJCoin"
  WriteRegStr HKCU "${UK}" "DisplayName" "MJ코인"
  WriteRegStr HKCU "${UK}" "DisplayIcon" "$INSTDIR\mjcoin.ico"
  WriteRegStr HKCU "${UK}" "Publisher" "kmj"
  WriteRegStr HKCU "${UK}" "DisplayVersion" "1.0"
  WriteRegStr HKCU "${UK}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKCU "${UK}" "NoModify" 1
  WriteRegDWORD HKCU "${UK}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\MJCoin.exe"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\mjcoin.ico"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\MJ코인.lnk"
  Delete "$DESKTOP\MJ코인.lnk"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MJCoin"
  DeleteRegKey HKCU "Software\Classes\AppUserModelId\kmj.MJCoin"
SectionEnd
