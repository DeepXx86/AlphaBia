#!/usr/bin/env python3
import argparse, os, re, subprocess, sys, glob, datetime

PIPE = subprocess.PIPE

def std_fen_to_engine(fen):
    parts = fen.strip().split()
    board = parts[0]
    active = (parts[1] if len(parts) > 1 else "w").lower()
    flipped = "/".join(reversed(board.split("/")))
    return flipped, ("w" if active == "w" else "b")

def engine_sq_to_std(coord):
    coord = coord.strip().lower()
    if len(coord) < 2 or not ("a" <= coord[0] <= "h") or not coord[1].isdigit():
        return None
    r = int(coord[1])
    return f"{coord[0]}{9 - r}" if 1 <= r <= 8 else None

# rank flip 9-r is its own inverse, so std->engine is the same transform
std_sq_to_engine = engine_sq_to_std

def harvest_fail_positions(trace, who, why, path, offsets=(16, 40, 80), cap=20000):
    """Feed lost/count-drawn games back into selfplay as start positions
    (engine cfg keys: startFENsFile / startFENsProb). Line format matches the
    engine's loader: '<engine-fen> <w|b> <movenumslc>'."""
    if not (who == "fsf" or (who == "draw" and
            (why.startswith("count_draw") or why.startswith("max_move_draw")))):
        return 0
    lines = []
    for off in offsets:
        if len(trace) <= off:
            continue
        fen = trace[len(trace) - 1 - off].get("fen_before")
        if not fen:
            continue
        f = fen.split()
        eb, es = std_fen_to_engine(fen)
        slc = int(f[4]) if len(f) >= 5 and f[4].isdigit() else 0
        lines.append(f"{eb} {es} {min(slc, 400)}")
    if not lines:
        return 0
    existing = []
    if os.path.exists(path):
        with open(path) as fh:
            existing = [l.strip() for l in fh if l.strip()]
    seen = set(existing)
    added = [l for l in lines if l not in seen and not seen.add(l)]
    merged = (existing + added)[-cap:]
    with open(path, "w") as fh:
        fh.write("\n".join(merged) + "\n")
    return len(added)

class Gtp:
    def __init__(self, argv):
        self.p = subprocess.Popen(argv, stdin=PIPE, stdout=PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    def cmd(self, s):
        self.p.stdin.write(s + "\n"); self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if line == "":
                raise RuntimeError("KataGo exited")
            line = line.rstrip("\r\n")
            if line.startswith("="):
                return line[1:].strip()
            if line.startswith("?"):
                raise RuntimeError("GTP error: " + line)
    def close(self):
        try: self.cmd("quit")
        except Exception: self.p.kill()

class Uci:
    def __init__(self, path, variant="makruk", skill=2):
        self.p = subprocess.Popen([path], stdin=PIPE, stdout=PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        self._send("uci"); self._wait("uciok")
        self._send(f"setoption name UCI_Variant value {variant}")
        self._send(f"setoption name Skill Level value {skill}")
        self._send("isready"); self._wait("readyok")
        self._send("ucinewgame")
    def _send(self, s): self.p.stdin.write(s + "\n"); self.p.stdin.flush()
    def _rl(self):
        l = self.p.stdout.readline()
        if l == "": raise RuntimeError("Fairy-Stockfish exited")
        return l
    def _wait(self, tok):
        while tok not in self._rl(): pass
    def _pos(self, moves):
        self._send("position startpos" + ((" moves " + " ".join(moves)) if moves else ""))
    def fen_turn_check(self, moves):
        self._pos(moves); self._send("d"); self._send("isready")
        fen = None; in_check = False
        while True:
            l = self._rl()
            m = re.search(r"Fen:\s*(.+)", l)
            if m: fen = m.group(1).strip()
            if "Checkers:" in l: in_check = bool(l.split("Checkers:")[1].strip())
            if "readyok" in l: break
        return fen, (fen.split()[1] if fen else "w"), in_check
    def legal(self, moves):
        self._pos(moves); self._send("go perft 1")
        mv = []
        while True:
            l = self._rl().strip()
            m = re.match(r"([a-h][1-8][a-h][1-8][a-z]?):\s*\d+", l)
            if m: mv.append(m.group(1))
            if l.startswith("Nodes searched"): break
        return mv
    def bestmove(self, moves, movetime):
        self._pos(moves); self._send(f"go movetime {movetime}")
        while True:
            l = self._rl()
            if l.startswith("bestmove"): return l.split()[1]
    def evaluate(self, moves, depth=12):
        self._pos(moves); self._send(f"go depth {depth}")
        kind, val = "cp", 0
        while True:
            l = self._rl()
            m = re.search(r"score (cp|mate) (-?\d+)", l)
            if m: kind, val = m.group(1), int(m.group(2))
            if l.startswith("bestmove"): break
        return kind, val
    def close(self):
        try: self._send("quit")
        except Exception: self.p.kill()

def play_game(kata, fsf, cfg_visits, kata_white, movetime, max_plies):
    kata.cmd("boardsize 8"); kata.cmd("clear_board")
    kata.cmd(f"kata-set-param maxVisits {cfg_visits}")
    moves = []
    trace = []
    kata_side = "w" if kata_white else "b"
    start_fen, _, _ = fsf.fen_turn_check([])
    result = ("draw", f"move cap {max_plies}")
    for ply in range(max_plies):
        fen, turn, in_check = fsf.fen_turn_check(moves)
        f = fen.split()
        if len(f) >= 5 and f[3].isdigit() and int(f[3]) > 0 and f[4].isdigit() \
           and int(f[4]) >= int(f[3]):
            result = ("draw", f"count_draw (count {f[4]}/{f[3]} plies)")
            break
        legal = fsf.legal(moves)
        if not legal:
            if in_check:
                result = ("kata" if turn != kata_side else "fsf"), "checkmate"
            else:
                result = ("draw", "stalemate")
            break
        raw = ""
        if turn == kata_side:
            # No setfen here: KataGo keeps its own continuous board so movenumslc,
            # counting state, and repetition history survive across turns.
            frm = kata.cmd("genmove b"); to = kata.cmd("genmove b")
            raw = f"{frm} {to}"
            cand = (engine_sq_to_std(frm) or "") + (engine_sq_to_std(to) or "")
            full = next((m for m in legal if m.startswith(cand)), None)
            if full is None:
                trace.append({"ply": ply, "turn": turn, "fen_before": fen, "raw": raw,
                              "parsed": cand, "legal": False})
                result = ("fsf", f"KATA_ILLEGAL {cand} (engine {frm}-{to}) not legal")
                break
            moves.append(full)
        else:
            mv = fsf.bestmove(moves, movetime)
            if mv == "(none)":
                result = ("draw", "fsf no move"); break
            raw = mv
            ef, et = std_sq_to_engine(mv[:2]), std_sq_to_engine(mv[2:4])
            if ef is None or et is None:
                result = ("draw", f"HARNESS_ERROR bad FSF move format {mv}"); break
            try:
                kata.cmd(f"play b {ef}"); kata.cmd(f"play b {et}")
            except RuntimeError as e:
                result = ("draw", f"DESYNC kata rejected FSF move {mv}: {e}"); break
            moves.append(mv)
        fen_a, turn_a, chk_a = fsf.fen_turn_check(moves)
        trace.append({"ply": ply, "turn": turn, "move": moves[-1], "raw": raw, "legal": True,
                      "fen_before": fen, "fen_after": fen_a, "in_check_after": chk_a,
                      "legal_count_after": len(fsf.legal(moves))})
    who, why = result
    if why.startswith("move cap"):
        kind, val = fsf.evaluate(moves, 12)
        who = "draw"
        why = f"max_move_draw (info: eval {kind} {val} for side-to-move)"
    fen_f, turn_f, chk_f = fsf.fen_turn_check(moves)
    legal_f = fsf.legal(moves)
    if why == "checkmate" and (len(legal_f) > 0 or not chk_f):
        print(f"  !!! FALSE-WIN BLOCKED: claimed mate but in_check={chk_f} legal={len(legal_f)}")
        who, why = "draw", "false_mate_blocked"
    print(f"  [final] fen={fen_f} turn={turn_f} in_check={chk_f} legal={len(legal_f)} "
          f"plies={len(moves)} reason={why} result_source=canonical_fsf_board")
    return who, why, moves, start_fen, trace

def write_pgn(idx, white, black, moves, start_fen, result, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fn = os.path.join(out_dir, f"game{idx}_{ts}.pgn")
    try:
        import pyffish as sf
        toks, fen = [], start_fen
        for m in moves:
            toks.append(sf.get_san("makruk", fen, m))
            fen = sf.get_fen("makruk", fen, [m])
    except Exception as e:
        print(f"  [pgn] SAN conversion failed ({e}); writing UCI moves instead")
        toks = moves
    body = []
    for i, t in enumerate(toks):
        if i % 2 == 0: body.append(f"{i//2 + 1}. {t}")
        else: body[-1] += f" {t}"
    with open(fn, "w") as f:
        f.write('[Event "KataGo vs Fairy-Stockfish"]\n[Site "local engine match"]\n')
        f.write(f'[Date "{datetime.date.today().strftime("%Y.%m.%d")}"]\n[Variant "Makruk"]\n')
        f.write(f'[White "{white}"]\n[Black "{black}"]\n[Result "{result}"]\n')
        f.write(f'[FEN "{start_fen}"]\n[SetUp "1"]\n\n')
        f.write(" ".join(body) + f" {result}\n")
    return fn

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--katago", default="/root/makruk/cpp/build_cuda/katago")
    ap.add_argument("--config", default="/mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk/run_model_play/gtp_play.cfg")
    ap.add_argument("--model", default="")
    ap.add_argument("--fsf", default="/mnt/e/Desktop/Tools/LearnLanguage/cpp/Makruk/test/fairy-stockfish-largeboard_x86-64")
    ap.add_argument("--games", type=int, default=2)
    ap.add_argument("--visits", type=int, default=800)
    ap.add_argument("--fsf-skill", type=int, default=2)
    ap.add_argument("--movetime", type=int, default=500)
    ap.add_argument("--max-plies", type=int, default=400)
    a = ap.parse_args()

    model = a.model
    if not model:
        cands = sorted(glob.glob("/root/mk192/data/models/az192-*/model.bin.gz"), key=os.path.getmtime)
        if not cands: sys.exit("no model found; pass --model")
        model = cands[-1]
    print(f"KataGo model: {model}")
    print(f"FSF skill {a.fsf_skill}, KataGo visits {a.visits}\n")
    os.chmod(a.fsf, 0o755)

    pgn_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "games")
    fsf_name = f"FairyStockfish(skill{a.fsf_skill})"
    score = {"kata": 0.0, "fsf": 0.0}
    results = []
    for g in range(a.games):
        kata = Gtp([a.katago, "gtp", "-config", a.config, "-model", model])
        fsf = Uci(a.fsf, skill=a.fsf_skill)
        kata_white = (g % 2 == 0)
        who, why, moves, start_fen, trace = play_game(kata, fsf, a.visits, kata_white, a.movetime, a.max_plies)
        kata.close(); fsf.close()
        import json as _json
        os.makedirs(pgn_dir, exist_ok=True)
        with open(os.path.join(pgn_dir, f"game{g+1}_trace.json"), "w") as tf:
            _json.dump({"result": who, "reason": why, "plies": trace}, tf, indent=1)
        results.append((who, why))
        fails_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fail_positions.txt")
        n_harvested = harvest_fail_positions(trace, who, why, fails_path)
        if n_harvested:
            print(f"  [curriculum] harvested {n_harvested} position(s) -> {fails_path}")
        if who == "kata": score["kata"] += 1
        elif who == "fsf": score["fsf"] += 1
        else: score["kata"] += 0.5; score["fsf"] += 0.5
        if who == "draw": res = "1/2-1/2"
        elif who == "kata": res = "1-0" if kata_white else "0-1"
        else: res = "0-1" if kata_white else "1-0"
        white = "KataGo" if kata_white else fsf_name
        black = fsf_name if kata_white else "KataGo"
        pgn = write_pgn(g + 1, white, black, moves, start_fen, res, pgn_dir)
        side = "White" if kata_white else "Black"
        print(f"Game {g+1}: KataGo({side}) -> winner={who} ({why}), {len(moves)} plies  [{res}]  -> {pgn}")
        if "ILLEGAL" in why:
            print("   >>> ILLEGAL MOVE from the net on a correct board = it's the NET, not the web bridge.")
    print(f"\nFINAL  KataGo {score['kata']} - {score['fsf']} Fairy-Stockfish (skill {a.fsf_skill})")
    n = len(results)
    w = sum(1 for x, _ in results if x == "kata")
    l = sum(1 for x, _ in results if x == "fsf")
    d = n - w - l
    if n > 0:
        import math
        p = (w + 0.5 * d) / n
        var = (w * (1 - p) ** 2 + d * (0.5 - p) ** 2 + l * (0 - p) ** 2) / n
        se = math.sqrt(var / n) if n > 1 else 0.5
        def to_elo(x):
            x = min(max(x, 1e-3), 1 - 1e-3)
            return -400.0 * math.log10(1.0 / x - 1.0)
        lo, hi = to_elo(p - 1.96 * se), to_elo(p + 1.96 * se)
        print(f"Elo vs this opponent: {to_elo(p):+.0f}  95% CI [{lo:+.0f}, {hi:+.0f}]  (n={n}; CI meaningless below ~30 games)")
    print(f"PGNs saved in: {pgn_dir}")

    # Append a machine-readable summary for the training dashboard
    hist_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_history.csv")
    kata_mates = sum(1 for w, y in results if w == "kata" and y == "checkmate")
    fsf_mates = sum(1 for w, y in results if w == "fsf" and y == "checkmate")
    count_draws = sum(1 for w, y in results if y.startswith("count_draw"))
    cap_draws = sum(1 for w, y in results if y.startswith("max_move_draw"))
    other = len(results) - kata_mates - fsf_mates - count_draws - cap_draws
    new_file = not os.path.exists(hist_csv)
    with open(hist_csv, "a") as hf:
        if new_file:
            hf.write("timestamp,model,skill,visits,games,kata_pts,fsf_pts,"
                     "kata_mates,fsf_mates,count_draws,cap_draws,other\n")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hf.write(f"{ts},{os.path.basename(os.path.dirname(model))},{a.fsf_skill},{a.visits},"
                 f"{len(results)},{score['kata']},{score['fsf']},"
                 f"{kata_mates},{fsf_mates},{count_draws},{cap_draws},{other}\n")
    print(f"Eval history appended: {hist_csv}")

if __name__ == "__main__":
    main()

