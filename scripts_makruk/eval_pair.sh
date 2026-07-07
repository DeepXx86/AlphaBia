#!/usr/bin/env bash
S=/mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk/src/scripts_makruk
A="$1"; B="$2"; N="${3:-24}"
echo "A = $(basename "$A")"
echo "B = $(basename "$B")"
bash "$S/run_match.sh" "$A" "$B" "$N" >/dev/null 2>&1
bash "$S/match_result.sh"
