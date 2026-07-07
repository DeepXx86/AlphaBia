#!/usr/bin/env bash
MK="${1:-/root/mk192}"
CSV="$MK/train_progress.csv"
STDOUT="$MK/data/train/az192/stdout.txt"

[ -f "$CSV" ] || echo "timestamp,step,p0loss,vloss" > "$CSV"

newest=$(ls -t "$MK/data/models" 2>/dev/null | grep '^az192-' | head -1)
step=$(echo "$newest" | sed -E 's/^az192-s([0-9]+)-.*/\1/')
line=$(grep -E 'p0loss = ' "$STDOUT" 2>/dev/null | tail -1)
ploss=$(echo "$line" | sed -nE 's/.*p0loss = ([0-9.]+).*/\1/p')
vloss=$(echo "$line" | sed -nE 's/.*vloss[ =]+([0-9.]+).*/\1/p')
ts=$(date '+%Y-%m-%d %H:%M:%S')

last_step=$(tail -1 "$CSV" 2>/dev/null | cut -d, -f2)
if [ -n "$step" ] && [ "$step" != "$last_step" ]; then
  echo "$ts,$step,${ploss:-},${vloss:-}" >> "$CSV"
fi

echo "=== Makruk training progress (oldest -> newest) ==="
column -t -s, "$CSV" | tail -18
echo "--- loop alive? (want 1) ---"
ps -eo pgid,cmd | grep '[u]buntu_alphazero_train' | tr -s ' ' | cut -d' ' -f1 | sort -u | wc -l
