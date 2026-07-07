#!/bin/bash
cd /mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk
echo "=== P1 regression: false-win tests ==="
python3 test/test_match_strict.py
echo
echo "=== P2 harness smoke (1 short game, verifies trace+final-verification) ==="
rm -f test/games/*.pgn test/games/*_trace.json
timeout 240 python3 test/engine_match.py --games 1 --visits 100 --movetime 150 --max-plies 60 2>&1 | tail -6
ls test/games/ | head -3
echo
echo "=== P6 generator distribution (prob=1.0 config, 24 games) ==="
sed 's/randomInitPieceProb = 0.15/randomInitPieceProb = 1.0/; s/maxVisits = 600.*/maxVisits = 60/; s/cheapSearchVisits = 200/cheapSearchVisits = 40/' src/scripts_makruk/makruk_selfplay_alphazero.cfg > /tmp/gen_test.cfg
rm -rf /tmp/gen_smoke
timeout 200 /root/makruk/cpp/build_cuda/katago selfplay -models-dir /root/mk192/data/models -config /tmp/gen_test.cfg -output-dir /tmp/gen_smoke -max-games-total 24 > /tmp/gen_smoke.log 2>&1
echo "selfplay exit=$?"
echo "error lines: $(grep -ciE 'error|illegal|assert' /tmp/gen_smoke.log)"
echo "-- opening position distribution --"
find /tmp/gen_smoke -name '*.sgfs' -exec cat {} \; | grep -oE 'OP\[[^]]*\]' | sort | uniq -c | sort -rn | head -12
echo "=== BATTERY DONE ==="
