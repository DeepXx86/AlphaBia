#!/usr/bin/env bash
set -e
A="$1"; B="$2"; N="${3:-40}"
KATAGO=/root/makruk/cpp/build_cuda/katago
BASE=/root/mk/scripts_makruk/makruk_match.cfg
export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}

[ -d "$A" ] && A="$A/model.bin.gz"
[ -d "$B" ] && B="$B/model.bin.gz"

TMP=/root/match_tmp.cfg
cp "$BASE" "$TMP"
{ echo "nnModelFile0=$A"; echo "nnModelFile1=$B"; echo "numGamesTotal=$N"; } >> "$TMP"

rm -rf /root/mk/match_sgfs; mkdir -p /root/mk/match_sgfs
echo "MATCH: A=$(basename $(dirname $A))  vs  B=$(basename $(dirname $B))  games=$N"
"$KATAGO" match -config "$TMP" -sgf-output-dir /root/mk/match_sgfs 2>&1 | grep -iE 'win|score|result|games|bot|elo|draw' | tail -25
echo "MATCH_DONE"
