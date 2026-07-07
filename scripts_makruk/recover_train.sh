#!/usr/bin/env bash
S=/mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk/src/scripts_makruk
MODELS=/root/mk192/data/models

echo "=== removing truncated models (<20MB = incomplete export) ==="
for d in "$MODELS"/az192-*; do
  f="$d/model.bin.gz"
  [ -f "$f" ] || continue
  sz=$(stat -c%s "$f")
  if [ "$sz" -lt 20000000 ]; then
    echo "  removing $(basename "$d") ($((sz/1048576))MB)"
    rm -rf "$d"
  fi
done

echo "=== newest complete model now ==="
ls -t "$MODELS" | grep '^az192-' | head -1
echo "=== train checkpoint present? ==="
ls -la /root/mk192/data/train/az192/*.ckpt 2>/dev/null | tail -1 || echo "no .ckpt (will start fresh from newest model data)"

echo "=== relaunching training ==="
sed -i 's/\r$//' "$S/launch_az.sh"
bash "$S/launch_az.sh" 300 160 300000 b15c192 az192 /root/mk192
