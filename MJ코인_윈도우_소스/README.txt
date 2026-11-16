MJ코인 소스 (2026-11-16)
========================
업비트 실시간 코인 + 네이버 증권 주식 차트 프로그램.

기본 목록: 비트코인(원화), 비트코인(BTC/USDT), 이더리움, 리플, 비트코인캐시, 솔라나, SK하이닉스(주식)
- 맨 앞 + 버튼(엑셀 테마는 시트 탭 옆 ⊕): 업비트 원화 코인 아무거나 추가 / 카드에 마우스 올리면 × 로 빼기
- 카드(기본 테마)나 시트 탭(엑셀 테마)을 끌어서 순서 바꾸기, 목록·순서는 저장됨
- 비트코인 USDT: 업비트 USDT 마켓(USDT-BTC) 시세
- 주식(SK하이닉스): 네이버 증권, 장중 10초 / 장 마감 60초마다 자동 갱신 + "새로고침" 버튼(주식 볼 때만)
기능: 캔들, 추세선, 매물대, 볼린저 밴드(20,2), 거래량, RSI14, 스토캐스틱 슬로우(14,3,3),
      상승/하락 다이버전스 표시 + 새로 생기면 빨간 깜빡임 글자 + 바탕화면 알림,
      기본 테마 / 엑셀 테마 (Ctrl+Shift+X로도 전환), 엑셀 테마 Sheet1 = 빈 시트, Sheet2부터 종목

폴더 (각 zip에 하나씩)
----------------------
windows/  윈도우 판 (창: pywebview + Edge WebView2, 윈도우 10/11 기본 포함)
  - mj_coin_win.py : 창, 업비트·네이버 요청(urllib), 실시간 연결(websocket-client), 알림(windows-toasts 라이브러리, 오른쪽 아래. 예전 PowerShell 방식은 맥아피가 악성으로 오인해 바꿈)
  - run.bat : 바로 실행 (파이썬 3.10 이상 필요, 설치 시 "Add python.exe to PATH" 체크)
  - build.bat : dist\MJCoin\MJCoin.exe 만들기 (폴더형. 한 파일형은 백신에 더 잘 걸림)
  - build_installer.bat + mjcoin.nsi : exe + 설치 파일 dist\MJCoin_Setup.exe (NSIS 3, 없으면 winget으로 설치 시도)
  - 알림 이름: 프로그램이 HKCU\Software\Classes\AppUserModelId\kmj.MJCoin 에 "MJ코인" 등록 후 사용 (실패하면 명령 프롬프트 이름)
  - 오류 기록: %LOCALAPPDATA%\MJCoin\mjcoin.log
macos/    맥 판 (창: pywebview + 맥 기본 WebKit)
  - mj_coin_mac.py : 윈도우판과 같고 알림만 osascript(오른쪽 위)
  - run.sh : 바로 실행 (.venv 만들어 패키지 설치)
  - build_app.sh : dist/MJCoin.app 만들기 (맥에서만 가능). 처음 열 때 경고 나오면 오른쪽 클릭 > 열기
  - 오류 기록: ~/Library/Application Support/MJCoin/mjcoin.log
bazzite/  리눅스(바지트) 판 (창: GTK4 + WebKit6, 네트워크: libsoup)
  - mj_coin.py, install.sh (~/.local/share/mj-coin 에 복사, 앱 목록 등록)
공통: web/index.html(또는 index.html) + lightweight-charts.js 화면은 세 판 모두 같은 파일

화면(index.html)과 파이썬 사이 약속
-----------------------------------
화면 -> 파이썬 : window.webkit.messageHandlers.mjcoin.postMessage(JSON 문자열)
   {"id":번호,"url":"https://..."}     -> 파이썬이 받아서 window.mjReply(id, 상태코드, 본문) 호출
      허용 주소: api.upbit.com, api.stock.naver.com, polling.finance.naver.com
   {"notify":{"title":..,"body":..}}   -> 바탕화면 알림
   {"subscribe":["KRW-BTC","USDT-BTC",...]} -> 업비트 실시간 구독 목록 변경 (새로 보내면 업비트가 통째로 교체, 시험 확인)
   윈도우/맥판은 index.html 맨 앞 연결 코드가 이것을 window.pywebview.api.post(...)로 바꿔 보냄
파이썬 -> 화면 : window.mjWs(메시지) / window.mjWsBatch([메시지...]) / window.mjWsState('open'|'reopen'|'closed')
주의: 화면(WebKit)에서 업비트로 직접 fetch/웹소켓 하면 429로 막힌 적이 있어서 네트워크는 파이썬이 맡음.
네이버 증권 주의: 비공식 API. 분봉 응답의 accumulatedTradingVolume 은 이름과 달리 "1분 거래량"(합계 = 하루 거래량 확인).
  분봉에 넥스트레이드(~20:00) 포함. 주/월봉은 startDateTime을 YYYYMMDDHHmm 형식으로 줘야 데이터가 옴.

시험 상태
---------
- 바지트판: 실제로 사용 중, 화면 캡처로 확인.
- 윈도우판: 바지트에서 Proton(wine) + 윈도우 파이썬 3.12.10(NuGet판) + PyInstaller 6.22.3 + pywebview 6.2.1 + NSIS 3.11 로 빌드.
  설치/제거는 wine에서 시험 OK. 네트워크 부분은 리눅스에서 가짜 창으로 시험 OK. 실제 윈도우 창·알림은 아직 미시험.
  깃허브 빌드: 저장소의 .github/workflows/windows.yml 이 윈도우 PC에서 설치 파일을 만들어
  https://github.com/alswls01/mjcoin/releases/tag/windows-build 에 올림
- 맥판: 네트워크 부분만 리눅스에서 가짜 창으로 시험 OK. 맥 실기 미시험.
안 되면 오류 기록(mjcoin.log)과 화면 오류를 보고 고치면 됨.

라이선스
--------
lightweight-charts.js : TradingView Lightweight Charts v4.2.3, Apache License 2.0 (차트 왼쪽 아래 TV 로고가 출처 표시)
아이콘 : Lucide "sheet" 아이콘(ISC 라이선스, 아이콘_라이선스_Lucide_ISC.txt) + 초록 배경
