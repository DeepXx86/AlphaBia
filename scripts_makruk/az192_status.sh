#!/usr/bin/env bash
B=/root/mk192
echo "=== generations done (b15c192) ==="
ls "$B/data/models" 2>/dev/null | grep -c '^az192-'
echo "=== models chronological (oldest -> newest) ==="
ls "$B/data/models" 2>/dev/null | grep '^az192-' | sort -t- -k2 -n
echo "=== decisiveness per generation (chronological) ==="
cd "$B/data/selfplay" 2>/dev/null || exit 0
for d in $(ls -d az192-* random 2>/dev/null | sort -t- -k2 -n); do
  [ -d "$d/sgfs" ] || continue
  tot=$(cat "$d"/sgfs/*.sgfs 2>/dev/null | grep -oE 'RE\[[^]]*\]' | wc -l)
  [ "$tot" -eq 0 ] && continue
  dec=$(cat "$d"/sgfs/*.sgfs 2>/dev/null | grep -oE 'RE\[[BW]\+' | wc -l)
  printf "%-26s games=%-4s decisive=%-4s (%s%%)\n" "$d" "$tot" "$dec" "$(( dec*100/tot ))"
done
echo "=== latest train loss ==="
grep -E 'p0loss = ' "$B/data/train/az192/stdout.txt" 2>/dev/null | tail -1 | cut -c1-80
