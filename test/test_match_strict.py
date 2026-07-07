#!/usr/bin/env python3
import subprocess, re, sys, os

FSF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fairy-stockfish-largeboard_x86-64")

def fsf_query(fen):
    p = subprocess.Popen([FSF], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    out, _ = p.communicate(
        f"uci\nsetoption name UCI_Variant value makruk\nposition fen {fen}\nd\ngo perft 1\nquit\n", timeout=30)
    in_check = False
    for l in out.splitlines():
        if "Checkers:" in l:
            in_check = bool(l.split("Checkers:")[1].strip())
    legal = re.findall(r"^([a-h][1-8][a-h][1-8][a-z]?):\s*\d+", out, re.M)
    return in_check, legal

def main():
    fails = 0
    fen = "4r3/8/2k5/8/8/8/8/4K3 w - - 0 1"
    in_check, legal = fsf_query(fen)
    ok = in_check and len(legal) > 0
    print(f"[{'ok' if ok else 'FAIL'}] check_with_escape: in_check={in_check} legal={len(legal)} (is_checkmate={in_check and len(legal)==0})")
    fails += 0 if ok else 1

    fen2 = "rr6/2k5/8/8/8/8/8/K7 w - - 0 1"
    in_check2, legal2 = fsf_query(fen2)
    ok2 = in_check2 and len(legal2) == 0
    print(f"[{'ok' if ok2 else 'FAIL'}] true_mate_detected: in_check={in_check2} legal={len(legal2)}")
    fails += 0 if ok2 else 1

    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine_match.py")).read()
    ok3 = "max_move_draw" in src and "adjudicated at cap" not in src
    print(f"[{'ok' if ok3 else 'FAIL'}] harness_cap_is_draw_not_material_win")
    ok4 = "false_mate_blocked" in src
    print(f"[{'ok' if ok4 else 'FAIL'}] harness_final_mate_verification_present")
    fails += (0 if ok3 else 1) + (0 if ok4 else 1)

    print("ALL PASS" if fails == 0 else f"{fails} FAILURES")
    sys.exit(0 if fails == 0 else 1)

if __name__ == "__main__":
    main()

