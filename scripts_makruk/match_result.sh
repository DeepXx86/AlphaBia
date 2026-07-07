#!/usr/bin/env bash
D=/root/mk/match_sgfs
awin=0; bwin=0; draw=0; tot=0
for f in "$D"/*.sgf "$D"/*.sgfs; do
  [ -e "$f" ] || continue
  while IFS= read -r game; do
    pb=$(echo "$game" | grep -oE 'PB\[[^]]*\]' | head -1 | sed 's/PB\[\(.*\)\]/\1/')
    pw=$(echo "$game" | grep -oE 'PW\[[^]]*\]' | head -1 | sed 's/PW\[\(.*\)\]/\1/')
    re=$(echo "$game" | grep -oE 'RE\[[^]]*\]' | head -1)
    [ -z "$re" ] && continue
    tot=$((tot+1))
    if echo "$re" | grep -q 'B+'; then w="$pb"; elif echo "$re" | grep -q 'W+'; then w="$pw"; else draw=$((draw+1)); continue; fi
    if [ "$w" = "A" ]; then awin=$((awin+1)); else bwin=$((bwin+1)); fi
  done < <(tr ';' '\n' < "$f" | grep -E 'PB\[' )
done
echo "Total games: $tot"
echo "A (latest)   wins: $awin"
echo "B (baseline) wins: $bwin"
echo "draws: $draw"
[ "$tot" -gt 0 ] && echo "A score: $(( (awin*100 + draw*50) / tot ))% (win=1, draw=0.5)"
