#!/bin/bash
# MJ코인 바지트(리눅스) 설치: 파일 복사 + 앱 목록 등록
set -e
D="$HOME/.local/share/mj-coin"
mkdir -p "$D" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/256x256/apps"
cp index.html lightweight-charts.js mj_coin.py "$D/"
chmod +x "$D/mj_coin.py"
cp mjcoin.png "$HOME/.local/share/icons/hicolor/256x256/apps/io.github.kmj.MJCoin.png"
sed "s|^Exec=.*|Exec=$D/mj_coin.py|; s|^Icon=.*|Icon=io.github.kmj.MJCoin|" io.github.kmj.MJCoin.desktop > "$HOME/.local/share/applications/io.github.kmj.MJCoin.desktop"
echo "설치 완료: 앱 목록에서 MJ코인 실행"
