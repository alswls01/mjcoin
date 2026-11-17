; MJ코인 설치 파일 (NSIS 3). build_installer.bat 와 깃허브 빌드가 사용
Unicode true
!ifndef VERSION
  !define VERSION "1.0.0"
!endif
!include "MUI2.nsh"
Name "MJ코인 ${VERSION}"
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
VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=${LANG_KOREAN} "ProductName" "MJ코인"
VIAddVersionKey /LANG=${LANG_KOREAN} "FileDescription" "MJ코인 설치 프로그램"
VIAddVersionKey /LANG=${LANG_KOREAN} "CompanyName" "alswls01"
VIAddVersionKey /LANG=${LANG_KOREAN} "LegalCopyright" "alswls01"
VIAddVersionKey /LANG=${LANG_KOREAN} "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=${LANG_KOREAN} "ProductVersion" "${VERSION}"

Section "MJ코인"
  ; 켜져 있는 MJ코인을 끔 (켜져 있으면 MJCoin.exe 를 덮어쓸 수 없어 "파일을 열 수 없습니다" 가 뜸)
  nsExec::Exec 'taskkill /F /IM MJCoin.exe'
  Sleep 1500
  ; 옛 버전 파일을 먼저 지움 (남은 옛 파일이 새 버전과 섞이지 않게). 설정은 %LOCALAPPDATA%\MJCoin 에 있어 그대로 남음
  Delete "$INSTDIR\MJCoin.exe"
  RMDir /r "$INSTDIR\_internal"
  SetOutPath "$INSTDIR"
  File /r "dist\MJCoin\*.*"
  File "mjcoin.ico"
  CreateShortcut "$SMPROGRAMS\MJ코인.lnk" "$INSTDIR\MJCoin.exe" "" "$INSTDIR\mjcoin.ico"
  CreateShortcut "$DESKTOP\MJ코인.lnk" "$INSTDIR\MJCoin.exe" "" "$INSTDIR\mjcoin.ico"
  WriteUninstaller "$INSTDIR\uninstall.exe"
  !define UK "Software\Microsoft\Windows\CurrentVersion\Uninstall\MJCoin"
  WriteRegStr HKCU "${UK}" "DisplayName" "MJ코인"
  WriteRegStr HKCU "${UK}" "DisplayIcon" "$INSTDIR\mjcoin.ico"
  WriteRegStr HKCU "${UK}" "Publisher" "alswls01"
  WriteRegStr HKCU "${UK}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UK}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKCU "${UK}" "NoModify" 1
  WriteRegDWORD HKCU "${UK}" "NoRepair" 1
  ; 프로그램 안 "새 버전 받기" 로 조용히(/S) 깔았으면 끝나고 바로 다시 켬
  IfSilent 0 +2
    Exec '"$INSTDIR\MJCoin.exe"'
SectionEnd

Section "Uninstall"
  nsExec::Exec 'taskkill /F /IM MJCoin.exe'
  Sleep 1000
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
