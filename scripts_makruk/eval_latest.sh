#!/usr/bin/env bash
S=/mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk/src/scripts_makruk
MODELS=/root/mk192/data/models
A="$MODELS/$(ls -t "$MODELS" | grep '^az192-' | head -1)"
if ls -d "$MODELS"/az192-s9778688* >/dev/null 2>&1; then
  B="$(ls -d "$MODELS"/az192-s9778688* | head -1)"
else
  B="$MODELS/$(ls "$MODELS" | grep '^az192-' | sort -t- -k2 -n | head -3 | tail -1)"
fi
echo "A (latest) = $(basename "$A")"
echo "B (older)  = $(basename "$B")"
bash "$S/run_match.sh" "$A" "$B" 24 >/dev/null 2>&1
bash "$S/match_result.sh"
