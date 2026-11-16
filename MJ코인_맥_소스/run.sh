#!/bin/bash
# 앱 만들지 않고 바로 실행 (테스트용). 맥 기본 python3 사용
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python mj_coin_mac.py
