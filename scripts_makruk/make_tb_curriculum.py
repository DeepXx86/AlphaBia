#!/usr/bin/env python3
"""3-piece Makruk DTM tablebase -> selfplay curriculum positions (training-only).

Solves K+R, K+S(khon), K+N vs lone K by retrograde analysis in ENGINE orientation
(uppercase = first mover = attacker, fen row 0 = internal y0, attacker khon forward = +y).
Emits start positions whose remaining Thai count budget is tied to the exact
distance-to-mate, so self-play must find near-optimal conversions to score the win.

Output lines: "<engine-fen> <w|b> <movenumslc>"  (same format as fail_positions.txt)

Usage: python3 make_tb_curriculum.py [--out tb_positions.txt] [--per-bucket 250]
"""
import argparse, collections, random, sys

N = 8
def sq(x, y): return y * N + x
def xy(s): return (s % N, s // N)

KING_D = [(-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)]
KNIGHT_D = [(1,2),(2,1),(-1,2),(-2,1),(1,-2),(2,-1),(-1,-2),(-2,-1)]
DIAG_D = [(1,1),(1,-1),(-1,1),(-1,-1)]

def on(x, y): return 0 <= x < N and 0 <= y < N

def king_moves(s):
    x, y = xy(s)
    return [sq(x+dx, y+dy) for dx, dy in KING_D if on(x+dx, y+dy)]

def knight_moves(s):
    x, y = xy(s)
    return [sq(x+dx, y+dy) for dx, dy in KNIGHT_D if on(x+dx, y+dy)]

def khon_moves(s):
    x, y = xy(s)
    out = [sq(x+dx, y+dy) for dx, dy in DIAG_D if on(x+dx, y+dy)]
    if on(x, y+1): out.append(sq(x, y+1))
    return out

def rook_rays(s, occ):
    x, y = xy(s)
    out = []
    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        cx, cy = x+dx, y+dy
        while on(cx, cy):
            t = sq(cx, cy)
            out.append(t)
            if t in occ: break
            cx += dx; cy += dy
    return out

PIECE_MOVES = {"r": None, "s": khon_moves, "n": knight_moves}

def piece_attacks(ptype, ps, occ):
    if ptype == "r": return rook_rays(ps, occ)
    return PIECE_MOVES[ptype](ps)

def adjacent(a, b):
    ax, ay = xy(a); bx, by = xy(b)
    return max(abs(ax-bx), abs(ay-by)) <= 1 and a != b

def solve(ptype):
    S = N * N
    def enc(ak, ap, dk, stm): return ((ak * S + ap) * S + dk) * 2 + stm
    UNKNOWN, ATT_WIN, DEF_LOST = 0, 1, 2
    dtm = {}
    def_out_unresolved = {}

    def valid(ak, ap, dk):
        if ak == ap or ak == dk or ap == dk: return False
        if adjacent(ak, dk): return False
        return True

    def def_in_check(ak, ap, dk):
        occ = {ak, dk}
        return dk in piece_attacks(ptype, ap, occ) or adjacent(ak, dk)

    def def_legal_moves(ak, ap, dk):
        out = []
        occ_att = {ak}
        for t in king_moves(dk):
            if t == ak: continue
            cap = (t == ap)
            nap = ap if not cap else -1
            if adjacent(t, ak): continue
            if nap >= 0:
                occ = {ak, t}
                if t in piece_attacks(ptype, nap, occ): continue
            else:
                if adjacent(ak, t): continue
            out.append((t, cap))
        return out

    def att_legal_moves(ak, ap, dk):
        out = []
        for t in king_moves(ak):
            if t == ap or t == dk or adjacent(t, dk): continue
            out.append(("k", t))
        occ = {ak, dk}
        for t in piece_attacks(ptype, ap, occ):
            if t == ak or t == dk: continue
            out.append(("p", t))
        return out

    states_def = []
    for ak in range(S):
        for ap in range(S):
            for dk in range(S):
                if not valid(ak, ap, dk): continue
                states_def.append((ak, ap, dk))

    from collections import deque
    q = deque()
    for (ak, ap, dk) in states_def:
        moves = def_legal_moves(ak, ap, dk)
        key = enc(ak, ap, dk, 1)
        if not moves:
            if def_in_check(ak, ap, dk):
                dtm[key] = (DEF_LOST, 0)
                q.append((ak, ap, dk, 1))
        else:
            def_out_unresolved[key] = sum(1 for _, cap in moves if not cap)
            if any(cap for _, cap in moves):
                def_out_unresolved[key] = -1

    while q:
        ak, ap, dk, stm = q.popleft()
        if stm == 1:
            d = dtm[enc(ak, ap, dk, 1)][1]
            for t in king_moves(ak):
                pak = t
                if not valid(pak, ap, dk): continue
                if def_in_check(pak, ap, dk): continue
                key = enc(pak, ap, dk, 0)
                cur = dtm.get(key)
                if cur is None:
                    dtm[key] = (ATT_WIN, d + 1)
                    q.append((pak, ap, dk, 0))
            occ = {ak, dk}
            for ps in range(S):
                if ps == ak or ps == dk or ps == ap: continue
                if ap in piece_attacks(ptype, ps, {ak, dk}):
                    if ptype == "r":
                        x1, y1 = xy(ps); x2, y2 = xy(ap)
                        if x1 != x2 and y1 != y2: continue
                        blocked = False
                        dx = (x2 > x1) - (x2 < x1); dy = (y2 > y1) - (y2 < y1)
                        cx, cy = x1 + dx, y1 + dy
                        while (cx, cy) != (x2, y2):
                            if sq(cx, cy) in (ak, dk): blocked = True; break
                            cx += dx; cy += dy
                        if blocked: continue
                    if not valid(ak, ps, dk): continue
                    if def_in_check(ak, ps, dk): continue
                    key = enc(ak, ps, dk, 0)
                    if dtm.get(key) is None:
                        dtm[key] = (ATT_WIN, d + 1)
                        q.append((ak, ps, dk, 0))
        else:
            d = dtm[enc(ak, ap, dk, 0)][1]
            for pdk in range(S):
                if not adjacent(pdk, dk) and pdk != dk: continue
                if pdk == dk: continue
                if not valid(ak, ap, pdk): continue
                key = enc(ak, ap, pdk, 1)
                if key in dtm: continue
                if def_out_unresolved.get(key, -2) < 0: continue
                moved_to_dk_legal = False
                for t, cap in def_legal_moves(ak, ap, pdk):
                    if t == dk and not cap:
                        moved_to_dk_legal = True
                        break
                if not moved_to_dk_legal: continue
                def_out_unresolved[key] -= 1
                if def_out_unresolved[key] == 0:
                    best = 0
                    ok = True
                    for t, cap in def_legal_moves(ak, ap, pdk):
                        if cap: ok = False; break
                        child = dtm.get(enc(ak, ap, t, 0))
                        if child is None or child[0] != ATT_WIN: ok = False; break
                        best = max(best, child[1])
                    if ok:
                        dtm[key] = (DEF_LOST, best + 1)
                        q.append((ak, ap, pdk, 1))
    return dtm, enc

CLASS_MOVES = {"r": 16, "s": 44, "n": 64}

def fen_of(ak, ap, dk, ptype):
    grid = [["1"] * N for _ in range(N)]
    ax, ay = xy(ak); px, py = xy(ap); dx_, dy_ = xy(dk)
    grid[ay][ax] = "K"
    grid[py][px] = ptype.upper()
    grid[dy_][dx_] = "k"
    rows = []
    for row in grid:
        out = ""
        empty = 0
        for c in row:
            if c == "1": empty += 1
            else:
                if empty: out += str(empty); empty = 0
                out += c
        if empty: out += str(empty)
        rows.append(out)
    return "/".join(rows)

def main():
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--out", default=None)
    ap_.add_argument("--per-bucket", type=int, default=250)
    ap_.add_argument("--seed", type=int, default=7)
    a = ap_.parse_args()
    rng = random.Random(a.seed)
    out_path = a.out or (__import__("pathlib").Path(__file__).resolve().parents[2] / "test" / "tb_positions.txt")

    lines = []
    for ptype in ["r", "s", "n"]:
        dtm, enc = solve(ptype)
        att_wins = collections.defaultdict(list)
        def_losses = collections.defaultdict(list)
        S = N * N
        for ak in range(S):
            for ap_s in range(S):
                for dk in range(S):
                    k0 = ((ak * S + ap_s) * S + dk) * 2 + 0
                    v = dtm.get(k0)
                    if v and v[0] == 1:
                        A = (v[1] + 1) // 2
                        att_wins[A].append((ak, ap_s, dk))
                    k1 = k0 + 1
                    v = dtm.get(k1)
                    if v and v[0] == 2 and v[1] > 0:
                        A = v[1] // 2
                        def_losses[A].append((ak, ap_s, dk))
        limit_plies = 2 * (CLASS_MOVES[ptype] - 3)
        total = sum(len(v) for v in att_wins.values())
        print(f"{ptype.upper()}: {total} attacker-to-move wins, max moves-to-mate "
              f"{max(att_wins) if att_wins else 0}, budget {limit_plies}")
        for A, poss in sorted(att_wins.items()):
            need = 2 * A - 1
            rng.shuffle(poss)
            picked = poss[: a.per_bucket]
            for (ak, ap_s, dk) in picked:
                for margin, share in [(0, 0.4), (2, 0.3), (6, 0.2), (-2, 0.1)]:
                    if rng.random() > share: continue
                    slc = limit_plies - need - margin
                    if slc < 0 or slc > 400: continue
                    lines.append(f"{fen_of(ak, ap_s, dk, ptype)} w {slc}")
        for A, poss in sorted(def_losses.items()):
            need = 2 * A
            rng.shuffle(poss)
            picked = poss[: max(20, a.per_bucket // 5)]
            for (ak, ap_s, dk) in picked:
                slc = limit_plies - need - rng.choice([0, 2, 4])
                if slc < 0: continue
                lines.append(f"{fen_of(ak, ap_s, dk, ptype)} b {slc}")

    rng.shuffle(lines)
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} positions -> {out_path}")

if __name__ == "__main__":
    main()
