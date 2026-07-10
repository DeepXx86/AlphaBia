#!/usr/bin/env bash
set -e
GENS="${1:-40}"; GAMES="${2:-300}"; SAMPLES="${3:-300000}"
MODEL_KIND="${4:-b10c128}"; TRAIN_NAME="${5:-az}"; BASE="${6:-/root/mk}"

WIN=/mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk
KATAGO=/root/makruk/cpp/build_cuda/katago
[ -x /root/makruk/cpp/build_trt/katago ] && KATAGO=/root/makruk/cpp/build_trt/katago
T=$BASE/scripts/alphabia/trainsgd
CFG=$BASE/scripts_makruk/makruk_selfplay_alphazero.cfg
export PATH=/root/mktorch/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}

mkdir -p "$BASE"
cp -ru "$WIN/src/python" "$WIN/src/scripts" "$WIN/src/scripts_makruk" "$BASE/" 2>/dev/null || true
cd "$BASE" && git init -q 2>/dev/null || true
git config user.email a@b.c 2>/dev/null || true; git config user.name mk 2>/dev/null || true

find "$BASE" -name '*.sh' -exec sed -i 's/\r$//' {} +
sed -i 's/-pos-len 9/-pos-len 8/' "$T/train.sh"
sed -i 's/-min-rows 200000/-min-rows 1000/g' "$T/shuffle.sh"
sed -i '/-intermediate-loss-scale/d' "$T/train.sh"
sed -i 's/-main-loss-scale 0.2/-main-loss-scale 1.0/' "$T/train.sh"
sed -i 's/map_location="cpu")/map_location="cpu", weights_only=False)/' "$T/load_model.py" "$T/edit_checkpoint.py" "$T/migrate_double_v1.py"
sed -i 's/map_location=device)/map_location=device, weights_only=False)/' "$T/train.py"
sed -i 's/if True or torch.cuda.is_available()/if torch.cuda.is_available()/' "$T/train.py"
python - "$T/export.sh" <<'PY'
import sys; p=sys.argv[1]; s=open(p,encoding='utf-8',errors='replace').read().replace('\r','')
open(p,'w',newline='\n').write('#!/bin/bash -eu\n'+s[s.find('set -o pipefail'):])
PY

mkdir -p "$BASE/data/models" "$BASE/data/selfplay"
echo "== REAL AlphaZero: $GENS gens x $GAMES games x $SAMPLES samples, $MODEL_KIND, 600 visits =="

for g in $(seq 1 "$GENS"); do
  echo "================ AZ GEN $g/$GENS ================"
  timeout 10800 "$KATAGO" selfplay -models-dir "$BASE/data/models" -config "$CFG" \
      -output-dir "$BASE/data/selfplay" -max-games-total "$GAMES" 2>&1 | tail -3 || echo "selfplay ended, continuing"
  ( cd "$T" && bash shuffle.sh "$BASE/data" "$BASE/data" /tmp/ktmp 4 256 2>&1 | tail -3 )
  ( cd "$T" && bash train.sh "$BASE/data" "$TRAIN_NAME" "$MODEL_KIND" 256 main -samples-per-epoch "$SAMPLES" 2>&1 | tail -6 )
  ( cd "$T" && bash export.sh makrukAZ "$BASE/data" 0 2>&1 | tail -3 )
  echo "--- loss ---"; grep -E 'p0loss = ' "$BASE/data/train/$TRAIN_NAME/stdout.txt" | tail -1 | cut -c1-90
  echo "--- models ---"; ls "$BASE/data/models" | tail -3
  mkdir -p "$WIN/local_models_$TRAIN_NAME"
  NEWEST=$(ls -t "$BASE/data/models" 2>/dev/null | grep "^$TRAIN_NAME-" | head -1)
  [ -n "$NEWEST" ] && cp -ru "$BASE/data/models/$NEWEST" "$WIN/local_models_$TRAIN_NAME/" 2>/dev/null || true
  bash "$WIN/src/scripts_makruk/train_tracker.sh" "$BASE" >/dev/null 2>&1 || true
done
echo "AZ_DONE"
