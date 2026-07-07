#!/usr/bin/env bash
set -u
DIR="${1:-/root/mk192/data/models}"
POLL="${2:-30}"
MAXP="${3:-480}"

base=$(ls -t "$DIR" 2>/dev/null | head -1)
echo "[wait_and_stop] current newest: ${base:-<none>} ; waiting for the next export..."

i=0
while [ "$i" -lt "$MAXP" ]; do
  newest=$(ls -t "$DIR" 2>/dev/null | head -1)
  if [ -n "$newest" ] && [ "$newest" != "$base" ]; then
    echo "[wait_and_stop] NEW MODEL: $newest  ($(date))"
    break
  fi
  sleep "$POLL"
  i=$((i + 1))
done
[ "$i" -ge "$MAXP" ] && echo "[wait_and_stop] timed out waiting; stopping anyway."

PAUSE=/mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk/run_model_play/logs/mk_paused.flag
mkdir -p "$(dirname "$PAUSE")" 2>/dev/null
touch "$PAUSE"
echo "[wait_and_stop] watchdog PAUSED (created mk_paused.flag) - it will stay stopped."

pkill -9 -f "[u]buntu_alphazero_train" 2>/dev/null || true
pkill -9 -f "[t]imeout 2400"           2>/dev/null || true
pkill -9 -f "[k]atago selfplay"        2>/dev/null || true
pkill -9 -f "[t]rain.py"               2>/dev/null || true
sleep 3

echo "[wait_and_stop] training procs left (expect none):"
ps -eo pid,args | grep -E "[u]buntu_alphazero|[k]atago selfplay|[t]rain.py" || echo "  none"
echo "[wait_and_stop] play-server gtp engine (kept alive):"
ps -eo pid,args | grep "[k]atago gtp" || echo "  (none running)"
echo "[wait_and_stop] STOPPED. newest model: $(ls -t "$DIR" 2>/dev/null | head -1)"
echo "[wait_and_stop] To RESUME training (also re-arms the watchdog): run launch_az.sh"
