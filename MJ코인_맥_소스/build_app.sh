#!/bin/bash
# MJ코인.app 만들기 → dist/MJCoin.app (응용 프로그램 폴더로 끌어다 놓으면 설치)
# 필요: python3 (맥에 Xcode 명령어 도구 또는 python.org 설치판)
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade -r requirements.txt
.venv/bin/python -m PyInstaller --noconfirm --windowed --name MJCoin --icon mjcoin_1024.png \
  --osx-bundle-identifier io.github.kmj.MJCoin --add-data "web:web" \
  --collect-submodules keyring.backends mj_coin_mac.py
echo "완료: dist/MJCoin.app"
echo "처음 열 때 '확인되지 않은 개발자' 경고가 나오면: 오른쪽 클릭 > 열기"
open dist
