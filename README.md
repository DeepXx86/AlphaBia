# AlphaBia

A Makruk (Thai chess) engine trained from zero by AlphaZero-style self-play, on a single RTX 4060 at home.

This is a hobby project. I wanted to see how far a normal gaming PC can push a variant that has almost no neural engines. Turns out: pretty far. The engine learned everything from self-play only - no opening books, no human games, no handcrafted eval.

## Credits

The whole codebase is built on **[KataGomo](https://github.com/hzyhhzy/KataGomo)** by hzyhhzy, specifically the [AnimalChess2025 branch](https://github.com/hzyhhzy/KataGomo/tree/AnimalChess2025), which itself is a fork of [KataGo](https://github.com/lightvector/KataGo) by lightvector. I did not write the engine core, the search, or the training pipeline - those people did, and they did it well. What I added is the Makruk game logic, rules, tests, and the training runs.

Btw **Claude** helped me a lot throughout this project :)

## What's implemented

* Full Makruk rules: piece movement (Khun, Rua, Ma, Khon, Met, Bia), directional pieces, Bia promotion to Bia Gae, check, checkmate, and stalemate
* Thai draw counting rules:

  * 2 rooks: 8
  * 1 rook: 16
  * 2 bishops: 22
  * 2 knights: 32
  * 1 bishop: 44
  * 1 knight: 64
  * Only Met / promoted Bia Gae remaining: 64
* 64-move board counting rule
* Threefold repetition draw
* One move = two engine plies: first selecting the from-square, then selecting the to-square. Keep this in mind if you script against GTP.
* Test harness that plays real matches against Fairy-Stockfish over UCI, with strict rule enforcement and PGN output: `test/engine_match.py`


## The model

There is one model in the [releases](../../releases): **model_192** (b15c192). It was trained on my RTX 4060 for roughly 50-70 hours of self-play. It beats Fairy-Stockfish makruk at low skill levels and holds its own a bit above that. Endgame conversion under the counting rule is the hard part and it is still improving.

If you want to continue training, my honest recommendation: don't keep growing this net - start a **b20c256** and train it on data generated with model_192 (or its own self-play). The bigger net has a much higher ceiling. Expect around **2-3 days** on similar hardware before it reaches the level of the model I'm giving you, and it climbs past it from there.

## Building

Same as KataGo/KataGomo. Linux or WSL:

```
cd cpp
cmake -B build -DUSE_BACKEND=CUDA -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
```

Use `-DUSE_BACKEND=EIGEN` for CPU-only. You need cuDNN for the CUDA backend.

## Running

Play/analyze over GTP:

```
./cpp/build/katago gtp -config <your gtp config> -model model.bin.gz
```

Self-play training loop (selfplay -> shuffle -> train -> export) is in `scripts_makruk/ubuntu_alphazero_train.sh` with the config in `scripts_makruk/makruk_selfplay_alphazero.cfg`. The python training side is under `scripts/alphabia/trainsgd/`.

Rule unit tests build standalone without any GPU:

```
bash scripts_makruk/build_selftest.sh
./build_selftest/makruk_selftest.exe
```

To benchmark against Fairy-Stockfish, drop a `fairy-stockfish-largeboard` binary into `test/` and run `test/engine_match.py`.

## License

This repository is released under the MIT License. See [`LICENSE`](./LICENSE).

----------------------------------------
