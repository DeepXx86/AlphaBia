#!/usr/bin/env python3

# claude make btw
import argparse, csv, datetime, glob, html, json, math, os, re

def fsf_skill_elo(skill):
    return 1000 + 120 * skill


def load_tracker(base):
    path = os.path.join(base, "train_progress.csv")
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "ts": datetime.datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S"),
                    "step": int(r["step"]),
                    "p0loss": float(r["p0loss"]) if r.get("p0loss") else None,
                    "vloss": float(r["vloss"]) if r.get("vloss") else None,
                })
            except (ValueError, KeyError):
                continue
    rows.sort(key=lambda r: r["step"])
    return rows

RE_RESULT = re.compile(r"RE\[([^\]]*)\]")
RE_STEP = re.compile(r"-s(\d+)-")

def load_selfplay(base):
    out = []
    for mdir in glob.glob(os.path.join(base, "data", "selfplay", "*")):
        m = RE_STEP.search(os.path.basename(mdir))
        if not m:
            continue
        step = int(m.group(1))
        wins = losses = draws = 0
        for f in glob.glob(os.path.join(mdir, "sgfs", "*.sgf*")):
            try:
                with open(f, errors="replace") as fh:
                    for res in RE_RESULT.findall(fh.read()):
                        if res.startswith("B+"): wins += 1
                        elif res.startswith("W+"): losses += 1
                        else: draws += 1
            except OSError:
                continue
        total = wins + losses + draws
        if total > 0:
            out.append({"step": step, "games": total, "draws": draws,
                        "drawpct": 100.0 * draws / total})
    out.sort(key=lambda r: r["step"])
    return out

def load_evals(eval_csv):
    rows = []
    if not eval_csv or not os.path.exists(eval_csv):
        return rows
    with open(eval_csv) as f:
        for r in csv.DictReader(f):
            try:
                m = RE_STEP.search(r["model"])
                rows.append({
                    "ts": r["timestamp"], "model": r["model"],
                    "step": int(m.group(1)) if m else 0,
                    "skill": int(r["skill"]), "games": int(r["games"]),
                    "kata": float(r["kata_pts"]), "fsf": float(r["fsf_pts"]),
                    "kata_mates": int(r["kata_mates"]), "fsf_mates": int(r["fsf_mates"]),
                    "count_draws": int(r["count_draws"]),
                })
            except (ValueError, KeyError):
                continue
    rows.sort(key=lambda r: r["step"])
    return rows

def load_elo_matches(base):
    path = os.path.join(base, "elo_matches.csv")
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                rows.append((int(r["stepA"]), int(r["stepB"]), int(r["awins"]),
                             int(r["bwins"]), int(r["draws"])))
            except (ValueError, KeyError):
                continue
    return rows

# ---------------------------------------------------------------- elo math

def bradley_terry(matches):
    """Fit Elo ratings from (stepA, stepB, awins, bwins, draws) rows.
    Gradient ascent on the logistic likelihood, draws = half points.
    Anchored: oldest model = 0. Returns sorted [(step, elo), ...]."""
    steps = sorted({s for m in matches for s in (m[0], m[1])})
    if len(steps) < 2:
        return []
    r = {s: 0.0 for s in steps}
    for it in range(3000):
        k = 6.0 * (0.998 ** it)
        grad = {s: 0.0 for s in steps}
        for a, b, aw, bw, dr in matches:
            n = aw + bw + dr
            if n == 0:
                continue
            score = (aw + 0.5 * dr) / n
            expect = 1.0 / (1.0 + 10 ** (-(r[a] - r[b]) / 400.0))
            g = (score - expect) * n
            grad[a] += g
            grad[b] -= g
        for s in steps:
            r[s] += k * grad[s]
    base = r[steps[0]]
    return [(s, r[s] - base) for s in steps]

def fsf_elo(row):
    """FSF-anchored Elo estimate + a rough +-error from the game count."""
    n = max(1, row["games"])
    p = row["kata"] / n
    lo = 0.5 / n            # clamp within half a game of 0%/100%
    p = min(max(p, lo), 1 - lo)
    elo = fsf_skill_elo(row["skill"]) + 400 * math.log10(p / (1 - p))
    err = 400.0 / math.sqrt(n)  # rough 1-sigma scale, just for the tooltip
    return elo, err

# ---------------------------------------------------------------- page build

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="/root/mk192")
    ap.add_argument("--eval-csv", default="")
    ap.add_argument("--out", default="dashboard.html")
    a = ap.parse_args()

    tracker = load_tracker(a.base)
    selfplay = load_selfplay(a.base)
    evals = load_evals(a.eval_csv)
    matches = load_elo_matches(a.base)
    sp_elo = bradley_terry(matches)

    charts = []
    verdicts = []

    # ---- losses
    tr = [r for r in tracker if r["p0loss"] is not None and r["vloss"] is not None]
    if len(tr) >= 2:
        charts.append({
            "title": "Policy / value loss per generation",
            "ylabel": "p0loss", "y2label": "vloss",
            "series": [
                {"name": "p0loss (policy)", "color": "#2563eb", "axis": "l", "mode": "line",
                 "pts": [[r["step"], r["p0loss"]] for r in tr]},
                {"name": "vloss (value, right axis)", "color": "#dc2626", "axis": "r", "mode": "line",
                 "pts": [[r["step"], r["vloss"]] for r in tr]},
            ]})
        v = [r["vloss"] for r in tr]
        q = max(2, len(v) // 4)
        lastq = sum(v[-q:]) / q
        prevq = sum(v[-2 * q:-q]) / q if len(v) >= 2 * q else lastq
        if lastq > prevq * 1.03:
            verdicts.append(("warn", f"vloss rising: {prevq:.3f} -> {lastq:.3f} over the last quarter of generations. "
                                     "If FSF results also stall or regress, suspect overfit."))
        else:
            verdicts.append(("ok", f"vloss stable/falling ({prevq:.3f} -> {lastq:.3f}); no overfit signal from losses."))

    # ---- selfplay elo
    if sp_elo:
        charts.append({
            "title": "Self-play Elo (Bradley-Terry over ladder matches; RELATIVE scale, oldest = 0 — "
                     "inflates over a long run like KataGo's curve)",
            "ylabel": "Elo (relative)",
            "series": [
                {"name": "self-play Elo", "color": "#0f766e", "axis": "l", "mode": "both",
                 "pts": [[s, round(e, 1)] for s, e in sp_elo],
                 "labels": [f"s{s/1e6:.0f}M: {e:+.0f} Elo vs oldest anchor" for s, e in sp_elo]},
            ]})
        verdicts.append(("info", f"Self-play Elo span: {sp_elo[-1][1]-sp_elo[0][1]:+.0f} over "
                                 f"{len({m[0] for m in matches} | {m[1] for m in matches})} rated models "
                                 f"({sum(m[2]+m[3]+m[4] for m in matches)} ladder games). "
                                 "Relative scale only — do not compare with the FSF Elo number."))
    else:
        verdicts.append(("info", "Self-play Elo: no ladder matches yet. The training loop plays them every "
                                 "ELO_EVERY gens (default 12), or run elo_ladder.sh by hand."))

    # ---- FSF-anchored elo + score
    if evals:
        by_skill = {}
        for r in evals:
            by_skill.setdefault(r["skill"], []).append(r)
        colors = {0: "#a1a1aa", 1: "#84cc16", 2: "#16a34a", 3: "#ca8a04", 4: "#ea580c",
                  5: "#dc2626", 6: "#9333ea", 7: "#0e7490", 8: "#1d4ed8"}
        eseries = []
        for sk, rows in sorted(by_skill.items()):
            pts, labels = [], []
            for r in rows:
                e, err = fsf_elo(r)
                pts.append([r["step"], round(e)])
                labels.append(f"vs FSF skill {sk} (~{fsf_skill_elo(sk)}): {r['kata']}-{r['fsf']} in {r['games']} games "
                              f"-> ~{e:.0f} Elo (+-{err:.0f}); {r['kata_mates']} mates, {r['count_draws']} count draws")
            eseries.append({"name": f"vs skill {sk}", "color": colors.get(sk, "#333"),
                            "axis": "l", "mode": "both", "pts": pts, "labels": labels})
        charts.append({
            "title": "FSF-anchored Elo (human-ish scale; anchors ~1000+120*skill, approximate)",
            "ylabel": "Elo (FSF-anchored)",
            "series": eseries})

        sseries = []
        for sk, rows in sorted(by_skill.items()):
            sseries.append({
                "name": f"score% vs skill {sk}", "color": colors.get(sk, "#333"),
                "axis": "l", "mode": "both",
                "pts": [[r["step"], round(100.0 * r["kata"] / max(1, r["games"]), 1)] for r in rows],
                "labels": [f"skill {sk}: {r['kata']}-{r['fsf']} ({r['games']} games, "
                           f"{r['kata_mates']} mates, {r['count_draws']} count draws)" for r in rows]})
        charts.append({
            "title": "FSF benchmark score (50% = even)",
            "ylabel": "score %", "ymin": 0, "ymax": 100, "hline": 50,
            "series": sseries})

        er = evals[-1]
        e, err = fsf_elo(er)
        verdicts.append(("info", f"Latest FSF eval: {er['kata']}-{er['fsf']} vs skill {er['skill']} at s{er['step']/1e6:.0f}M "
                                 f"-> ~{e:.0f} FSF-anchored Elo (+-{err:.0f})."))
        if er["games"] < 30:
            verdicts.append(("warn", f"Only {er['games']} games in the latest eval -> Elo error is +-{err:.0f}. "
                                     "Run 100+ games for a number you can trust."))
    else:
        verdicts.append(("info", "FSF-anchored Elo: no benchmark rows yet — every engine_match.py / "
                                 "eval_fsf_strict.sh run appends to test/eval_history.csv automatically."))

    # ---- selfplay draw rate
    if len(selfplay) >= 2:
        charts.append({
            "title": "Selfplay draw rate (endgame conversion metric — lower is better)",
            "ylabel": "draws %", "ymin": 0, "ymax": 100,
            "series": [
                {"name": "draw %", "color": "#7c3aed", "axis": "l", "mode": "both",
                 "pts": [[r["step"], round(r["drawpct"], 1)] for r in selfplay],
                 "labels": [f"{r['drawpct']:.0f}% of {r['games']} games @ s{r['step']/1e6:.0f}M" for r in selfplay]},
            ]})
        d = [r["drawpct"] for r in selfplay]
        q = max(2, len(d) // 4)
        lastq = sum(d[-q:]) / q
        prevq = sum(d[-2 * q:-q]) / q if len(d) >= 2 * q else lastq
        if lastq < prevq - 2:
            verdicts.append(("ok", f"Selfplay draw rate falling ({prevq:.0f}% -> {lastq:.0f}%): converting more endgames."))
        elif lastq > prevq + 2:
            verdicts.append(("warn", f"Selfplay draw rate rising ({prevq:.0f}% -> {lastq:.0f}%). Watch endgame metrics."))
        else:
            verdicts.append(("info", f"Selfplay draw rate flat around {lastq:.0f}%."))

    # ---- gen wall time
    if len(tracker) >= 3:
        pts = []
        for r0, r1 in zip(tracker, tracker[1:]):
            dt = (r1["ts"] - r0["ts"]).total_seconds() / 60.0
            if 0 < dt < 120:
                pts.append([r1["step"], round(dt, 1)])
        if len(pts) >= 2:
            charts.append({
                "title": "Generation wall time (gaps > 2h excluded)",
                "ylabel": "min / gen",
                "series": [{"name": "min/gen", "color": "#0e7490", "axis": "l", "mode": "line", "pts": pts}]})

    # ---- header
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    stats = []
    if tracker:
        last = tracker[-1]
        gens24 = [r for r in tracker if (last["ts"] - r["ts"]).total_seconds() < 86400]
        stats.append((f"{last['step']/1e6:.1f}M", "steps"))
        stats.append((f"{last['p0loss']:.3f}" if last["p0loss"] is not None else "?", "p0loss"))
        stats.append((f"{last['vloss']:.3f}" if last["vloss"] is not None else "?", "vloss"))
        stats.append((f"{len(gens24)}", "gens / 24h"))
    if sp_elo:
        stats.append((f"{sp_elo[-1][1]:+.0f}", "self-play Elo"))
    if evals:
        e, err = fsf_elo(evals[-1])
        stats.append((f"~{e:.0f}", "FSF Elo (approx)"))
    stats_html = "<div class='stats'>" + "".join(
        f"<div><b>{html.escape(str(v))}</b><span>{html.escape(k)}</span></div>" for v, k in stats) + "</div>"

    vp = "<div class='card'><h2>Health check</h2><ul>"
    if not verdicts:
        vp += "<li>No data yet.</li>"
    for kind, text in verdicts:
        icon = {"ok": "&#9989;", "warn": "&#9888;&#65039;", "info": "&#8505;&#65039;"}[kind]
        vp += f"<li class='{kind}'>{icon} {html.escape(text)}</li>"
    vp += "</ul></div>"

    chart_divs = "".join(
        f"<div class='card'><h2>{html.escape(c['title'])}</h2>"
        f"<div class='chartwrap'><canvas id='ch{i}'></canvas></div></div>"
        for i, c in enumerate(charts))

    page = HTML_TEMPLATE
    page = page.replace("__GENERATED__", now)
    page = page.replace("__BASE__", html.escape(a.base))
    page = page.replace("__STATS__", stats_html)
    page = page.replace("__VERDICTS__", vp)
    page = page.replace("__CHARTDIVS__", chart_divs)
    page = page.replace("__CHARTDATA__", json.dumps(charts))

    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"dashboard written: {a.out}  (tracker={len(tracker)} rows, selfplay={len(selfplay)} models, "
          f"evals={len(evals)}, ladder_matches={len(matches)}, rated_models={len(sp_elo)})")

HTML_TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="300">
<title>AlphaBia training dashboard</title>
<style>
 body { font-family: system-ui, sans-serif; margin: 24px auto; max-width: 1000px; color: #1a1a1a; background:#fafafa; }
 h1 { margin-bottom: 2px; } .sub { color:#777; margin-top:0; }
 .card { background:#fff; border:1px solid #e2e2e2; border-radius:10px; padding:14px 18px; margin:14px 0; }
 .card h2 { font-size:14px; margin:2px 0 8px; color:#333; }
 .stats { display:flex; flex-wrap:wrap; gap:14px; margin:10px 0; }
 .stats div { background:#fff; border:1px solid #e2e2e2; border-radius:10px; padding:10px 18px; text-align:center; }
 .stats b { font-size:20px; display:block; } .stats span { color:#888; font-size:12px; }
 ul { margin:4px 0; padding-left:18px; } li { margin:6px 0; }
 li.warn { color:#92400e; } li.ok { color:#166534; } li.info { color:#374151; }
 .chartwrap { position:relative; }
 canvas { width:100%; height:300px; display:block; cursor:crosshair; border-radius:6px; }
 .tip { position:absolute; pointer-events:none; background:#111827ee; color:#f9fafb; font-size:12px;
        padding:6px 9px; border-radius:6px; white-space:pre; display:none; z-index:5; max-width:420px; white-space:pre-wrap; }
 .hint { color:#999; font-size:11px; margin:2px 0 0; }
</style></head><body>
<h1>AlphaBia &mdash; Makruk training dashboard</h1>
<p class='sub'>generated __GENERATED__ &middot; base __BASE__ &middot; auto-refresh 5 min</p>
__STATS__
__VERDICTS__
__CHARTDIVS__
<p class='hint'>Charts: scroll = zoom (x), drag = pan, double-click = reset, hover = exact values. The y-axis re-fits to what is visible, so zooming in reveals small differences.</p>
<script>
const CHARTS = __CHARTDATA__;

function niceTicks(lo, hi, n) {
  const span = hi - lo || 1;
  const step0 = span / Math.max(1, n);
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  let step = mag;
  for (const m of [1, 2, 2.5, 5, 10]) { if (step0 <= m * mag) { step = m * mag; break; } }
  const ticks = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) ticks.push(v);
  return ticks;
}
const fmtX = v => (Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(v % 1e6 ? 1 : 0) + "M" : String(Math.round(v)));
const fmtY = v => Math.abs(v) >= 1000 ? v.toFixed(0) : (Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(3).replace(/\.?0+$/, ""));

function makeChart(canvas, cfg) {
  const wrap = canvas.parentElement;
  const tip = document.createElement("div");
  tip.className = "tip"; wrap.appendChild(tip);
  const ctx = canvas.getContext("2d");
  const PAD = { l: 58, r: cfg.y2label ? 58 : 16, t: 10, b: 30 };

  let xs = [];
  cfg.series.forEach(s => s.pts.forEach(p => xs.push(p[0])));
  const xFull = [Math.min(...xs), Math.max(...xs)];
  if (xFull[0] === xFull[1]) { xFull[0] -= 1; xFull[1] += 1; }
  let x0 = xFull[0], x1 = xFull[1];
  let drag = null;

  function fitY(axis) {
    let vals = [];
    cfg.series.filter(s => (s.axis || "l") === axis).forEach(s =>
      s.pts.forEach(p => { if (p[0] >= x0 && p[0] <= x1) vals.push(p[1]); }));
    if (!vals.length) return [0, 1];
    let lo = Math.min(...vals), hi = Math.max(...vals);
    if (axis === "l" && cfg.ymin !== undefined) lo = cfg.ymin;
    if (axis === "l" && cfg.ymax !== undefined) hi = cfg.ymax;
    if (lo === hi) { lo -= 1; hi += 1; }
    const pad = (hi - lo) * 0.06;
    return [ (cfg.ymin !== undefined && axis === "l") ? lo : lo - pad,
             (cfg.ymax !== undefined && axis === "l") ? hi : hi + pad ];
  }

  function draw() {
    const dpr = window.devicePixelRatio || 1;
    const W = wrap.clientWidth, H = 300;
    if (!W) { requestAnimationFrame(draw); return; }
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const yl = fitY("l"), yr = fitY("r");
    const px = x => PAD.l + (x - x0) / (x1 - x0) * (W - PAD.l - PAD.r);
    const py = (y, ax) => { const r = ax === "r" ? yr : yl;
      return H - PAD.b - (y - r[0]) / (r[1] - r[0]) * (H - PAD.t - PAD.b); };

    ctx.strokeStyle = "#e5e7eb"; ctx.fillStyle = "#6b7280"; ctx.font = "11px system-ui";
    ctx.lineWidth = 1;
    niceTicks(x0, x1, 7).forEach(v => {
      const x = px(v);
      ctx.beginPath(); ctx.moveTo(x, PAD.t); ctx.lineTo(x, H - PAD.b); ctx.stroke();
      ctx.textAlign = "center"; ctx.fillText(fmtX(v), x, H - PAD.b + 16);
    });
    niceTicks(yl[0], yl[1], 5).forEach(v => {
      const y = py(v, "l");
      ctx.beginPath(); ctx.moveTo(PAD.l, y); ctx.lineTo(W - PAD.r, y); ctx.stroke();
      ctx.textAlign = "right"; ctx.fillText(fmtY(v), PAD.l - 6, y + 4);
    });
    if (cfg.y2label) {
      ctx.fillStyle = "#b91c1c";
      niceTicks(yr[0], yr[1], 5).forEach(v => {
        ctx.textAlign = "left"; ctx.fillText(fmtY(v), W - PAD.r + 6, py(v, "r") + 4);
      });
      ctx.fillStyle = "#6b7280";
    }
    if (cfg.hline !== undefined) {
      ctx.strokeStyle = "#9ca3af"; ctx.setLineDash([3, 4]);
      ctx.beginPath(); ctx.moveTo(PAD.l, py(cfg.hline, "l")); ctx.lineTo(W - PAD.r, py(cfg.hline, "l")); ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.strokeStyle = "#d1d5db";
    ctx.strokeRect(PAD.l, PAD.t, W - PAD.l - PAD.r, H - PAD.t - PAD.b);

    ctx.save();
    ctx.beginPath(); ctx.rect(PAD.l, PAD.t, W - PAD.l - PAD.r, H - PAD.t - PAD.b); ctx.clip();
    cfg.series.forEach(s => {
      const ax = s.axis || "l";
      const vis = s.pts;
      if (s.mode !== "dots" && vis.length > 1) {
        ctx.strokeStyle = s.color; ctx.lineWidth = 1.6; ctx.beginPath();
        vis.forEach((p, i) => { const X = px(p[0]), Y = py(p[1], ax);
          i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); });
        ctx.stroke();
      }
      if (s.mode !== "line") {
        ctx.fillStyle = s.color;
        vis.forEach(p => { const X = px(p[0]), Y = py(p[1], ax);
          if (X >= PAD.l - 4 && X <= W - PAD.r + 4) { ctx.beginPath(); ctx.arc(X, Y, 3, 0, 7); ctx.fill(); } });
      }
    });
    ctx.restore();

    let lx = PAD.l + 8, ly = PAD.t + 14;
    ctx.font = "12px system-ui";
    cfg.series.forEach(s => {
      ctx.fillStyle = s.color; ctx.fillRect(lx, ly - 8, 10, 10);
      ctx.fillStyle = "#374151"; ctx.textAlign = "left"; ctx.fillText(s.name, lx + 14, ly);
      lx += 22 + ctx.measureText(s.name).width;
      if (lx > wrap.clientWidth - 160) { lx = PAD.l + 8; ly += 16; }
    });
    lastAxes = { px, py };
  }

  function xAt(evt) {
    const rect = canvas.getBoundingClientRect();
    const fx = (evt.clientX - rect.left - PAD.l) / (rect.width - PAD.l - PAD.r);
    return x0 + fx * (x1 - x0);
  }
  canvas.addEventListener("wheel", evt => {
    evt.preventDefault();
    const cx = xAt(evt);
    const f = Math.pow(1.25, evt.deltaY > 0 ? 1 : -1);
    x0 = Math.max(xFull[0], cx - (cx - x0) * f);
    x1 = Math.min(xFull[1], cx + (x1 - cx) * f);
    if (x1 - x0 < (xFull[1] - xFull[0]) / 2000) { const m = (x0 + x1) / 2, s = (xFull[1] - xFull[0]) / 4000;
      x0 = m - s; x1 = m + s; }
    draw();
  }, { passive: false });
  canvas.addEventListener("mousedown", evt => { drag = { x: evt.clientX, x0, x1 }; });
  window.addEventListener("mouseup", () => { drag = null; });
  canvas.addEventListener("mousemove", evt => {
    const rect = canvas.getBoundingClientRect();
    if (drag) {
      const dx = (evt.clientX - drag.x) / (rect.width - PAD.l - PAD.r) * (drag.x1 - drag.x0);
      let n0 = drag.x0 - dx, n1 = drag.x1 - dx;
      if (n0 < xFull[0]) { n1 += xFull[0] - n0; n0 = xFull[0]; }
      if (n1 > xFull[1]) { n0 -= n1 - xFull[1]; n1 = xFull[1]; }
      x0 = n0; x1 = n1; draw(); tip.style.display = "none"; return;
    }
    const mx = evt.clientX - rect.left, my = evt.clientY - rect.top;
    let best = null;
    const { px, py } = lastAxes;
    cfg.series.forEach(s => s.pts.forEach((p, i) => {
      const X = px(p[0]), Y = py(p[1], s.axis || "l");
      const d = Math.hypot(X - mx, Y - my);
      if (d < 22 && (!best || d < best.d)) best = { d, s, p, i, X, Y };
    }));
    if (best) {
      const lbl = best.s.labels ? best.s.labels[best.i]
        : best.s.name + "\nstep " + fmtX(best.p[0]) + "  value " + fmtY(best.p[1]);
      tip.textContent = lbl;
      tip.style.display = "block";
      tip.style.left = Math.min(best.X + 12, rect.width - 240) + "px";
      tip.style.top = (best.Y - 8) + "px";
    } else tip.style.display = "none";
  });
  canvas.addEventListener("mouseleave", () => { tip.style.display = "none"; });
  canvas.addEventListener("dblclick", () => { x0 = xFull[0]; x1 = xFull[1]; draw(); });
  window.addEventListener("resize", draw);
  window.addEventListener("load", draw);

  let lastAxes;
  draw();
}

CHARTS.forEach((cfg, i) => makeChart(document.getElementById("ch" + i), cfg));
</script>
</body></html>"""

if __name__ == "__main__":
    main()
