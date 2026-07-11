#!/usr/bin/env bash
set -u
BASE="${1:-/root/mk192}"
GAMES="${2:-8}"
NANCHORS="${3:-4}"
NAME_RE='^az[0-9]+-s[0-9]+'

KATAGO=/root/makruk/cpp/build_cuda/katago
[ -x /root/makruk/cpp/build_trt/katago ] && KATAGO=/root/makruk/cpp/build_trt/katago
CFG_SRC=/mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk/src/scripts_makruk/makruk_match.cfg
CSV="$BASE/elo_matches.csv"
export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}

[ -f "$CSV" ] || echo "timestamp,stepA,stepB,games,awins,bwins,draws" > "$CSV"

# All model dirs sorted by step number
mapfile -t MODELS < <(ls "$BASE/data/models" 2>/dev/null | grep -E "$NAME_RE" \
  | sed -E 's/^az[0-9]+-s([0-9]+).*/\1 \0/' | sort -n | cut -d' ' -f2)
N=${#MODELS[@]}
if [ "$N" -lt 2 ]; then echo "elo_ladder: need >=2 models, have $N"; exit 0; fi

NEWEST="${MODELS[$((N-1))]}"
step_of() { echo "$1" | sed -E 's/^az[0-9]+-s([0-9]+).*/\1/'; }

# Anchors at spread quantiles of the remaining history (dedup, exclude newest)
declare -A SEEN
ANCHORS=()
for i in $(seq 1 "$NANCHORS"); do
  idx=$(( (N-2) * i / (NANCHORS+1) ))
  cand="${MODELS[$idx]}"
  [ "$cand" = "$NEWEST" ] && continue
  [ -n "${SEEN[$cand]:-}" ] && continue
  SEEN[$cand]=1; ANCHORS+=("$cand")
done

echo "elo_ladder: newest=$NEWEST vs ${#ANCHORS[@]} anchors, $GAMES games each"
for ANCH in "${ANCHORS[@]}"; do
  TMP=/tmp/elo_match.cfg
  tr -d '\r' < "$CFG_SRC" > "$TMP"
  {
    echo "nnModelFile0=$BASE/data/models/$NEWEST/model.bin.gz"
    echo "nnModelFile1=$BASE/data/models/$ANCH/model.bin.gz"
    echo "numGamesTotal=$GAMES"
  } >> "$TMP"
  SGFD=/tmp/elo_ladder_sgfs
  rm -rf "$SGFD"; mkdir -p "$SGFD"
  "$KATAGO" match -config "$TMP" -sgf-output-dir "$SGFD" > /tmp/elo_match.log 2>&1 || {
    echo "elo_ladder: match failed vs $ANCH (see /tmp/elo_match.log)"; continue; }
  # Parse results: bot A = newest (nnModelFile0), bot B = anchor
  read -r AW BW DR <<< "$(python3 - "$SGFD" <<'PY'
import glob, re, sys
aw = bw = dr = 0
for f in glob.glob(sys.argv[1] + "/*.sgf*"):
    txt = open(f, errors="replace").read()
    for g in txt.split("(;")[1:]:
        pb = re.search(r"PB\[([^\]]*)\]", g)
        pw = re.search(r"PW\[([^\]]*)\]", g)
        re_ = re.search(r"RE\[([^\]]*)\]", g)
        if not (pb and pw and re_): continue
        r = re_.group(1)
        if r.startswith("B+"): w = pb.group(1)
        elif r.startswith("W+"): w = pw.group(1)
        else: dr += 1; continue
        if w == "A": aw += 1
        else: bw += 1
print(aw, bw, dr)
PY
)"
  TOT=$((AW + BW + DR))
  TS=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$TS,$(step_of "$NEWEST"),$(step_of "$ANCH"),$TOT,$AW,$BW,$DR" >> "$CSV"
  echo "  vs $ANCH: A=$AW B=$BW draws=$DR"
done
echo "elo_ladder: done -> $CSV"
