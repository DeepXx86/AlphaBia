#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

mkdir -p build_selftest

clang++ -std=c++17 -O2 -w \
  -DNOMINMAX -DBYTE_ORDER=1234 -DLITTLE_ENDIAN=1234 -DBIG_ENDIAN=4321 \
  cpp/tests_makruk/makruk_selftest.cpp \
  cpp/game/board.cpp cpp/game/boardhistory.cpp cpp/game/gamelogic.cpp cpp/game/rules.cpp \
  cpp/core/global.cpp cpp/core/hash.cpp cpp/core/rand.cpp cpp/core/rand_helpers.cpp \
  cpp/core/sha2.cpp cpp/core/timer.cpp cpp/core/datetime.cpp cpp/core/md5.cpp cpp/core/bsearch.cpp \
  -lws2_32 \
  -o build_selftest/makruk_selftest.exe

echo "built build_selftest/makruk_selftest.exe"
