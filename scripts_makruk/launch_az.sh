#!/usr/bin/env bash
S=/mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk/src/scripts_makruk
GENS="${1:-50}"; GAMES="${2:-300}"; SAMPLES="${3:-300000}"; KIND="${4:-b10c128}"; NAME="${5:-az}"; BASE="${6:-/root/mk}"
rm -f /mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk/run_model_play/logs/mk_paused.flag 2>/dev/null || true
pkill -9 -f ubuntu_alphazero 2>/dev/null || true
pkill -9 -f 'katago selfplay' 2>/dev/null || true
sleep 1
sed -i 's/\r$//' "$S/ubuntu_alphazero_train.sh"
cd /root
setsid nohup bash "$S/ubuntu_alphazero_train.sh" "$GENS" "$GAMES" "$SAMPLES" "$KIND" "$NAME" "$BASE" > "/root/az_run_$NAME.log" 2>&1 < /dev/null &
PID=$!
echo "launched detached, pid $PID"
sleep 8
echo "--- alive? ---"
ps -eo pid,args | grep -E '[u]buntu_alphazero|[k]atago selfplay' | head
