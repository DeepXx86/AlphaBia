#!/usr/bin/env bash
set -e
WIN=/mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk/src
DST=/root/makruk
CUDA_ROOT=/usr/local/cuda-12.4
LOG=/root/cuda_build.log

mkdir -p "$DST"
cp -ru "$WIN/cpp" "$DST/" 2>/dev/null || cp -r "$WIN/cpp" "$DST/"
cp -ru "$WIN/scripts_makruk" "$DST/" 2>/dev/null || true

cd "$DST/cpp"
rm -rf build_cuda
echo "== configure ==" | tee "$LOG"
cmake -B build_cuda \
  -DUSE_BACKEND=CUDA -DCMAKE_BUILD_TYPE=Release -DNO_GIT_REVISION=1 -DUSE_TCMALLOC=0 \
  -DCMAKE_CUDA_COMPILER="$CUDA_ROOT/bin/nvcc" \
  -DCUDAToolkit_ROOT="$CUDA_ROOT" \
  -DCMAKE_CUDA_ARCHITECTURES=89 \
  -DCUDNN_INCLUDE_DIR=/usr/include \
  -DCUDNN_LIBRARY=/usr/lib/x86_64-linux-gnu/libcudnn.so \
  >>"$LOG" 2>&1 && echo "CONFIGURE_OK" | tee -a "$LOG" || { echo "CONFIGURE_FAILED" | tee -a "$LOG"; tail -25 "$LOG"; exit 1; }

echo "== build ==" | tee -a "$LOG"
cmake --build build_cuda -j"$(nproc)" >>"$LOG" 2>&1 && echo "BUILD_OK" | tee -a "$LOG" || { echo "BUILD_FAILED" | tee -a "$LOG"; grep -iE 'error:' "$LOG" | head -25; exit 1; }
ls -la "$DST/cpp/build_cuda/katago" | tee -a "$LOG"
echo "CUDA_ENGINE_DONE"
