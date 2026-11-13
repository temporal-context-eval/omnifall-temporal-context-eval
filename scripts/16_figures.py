"""
16_figures.py — 논문 그림 1~7을 결과 파일(CSV)에서 생성 (교정본 F1 항목)

입력(기본 경로는 --data 로 지정; D:\\omnifall 기준):
  그림 1  reports/design_verification/dv_window_validity_{Staged_train,Staged_validation,Staged_test,OOPS_test}.csv
  그림 2  (데이터 없음: 파이프라인 블록도)
  그림 3  reports/design_verification/eval_edge_cases.csv  (단위 테스트가 낸 판정 출력)
  그림 4  runs/main/results/results_main.csv
  그림 5  runs/main/results/curves.csv
  그림 6  runs/main/results/results_main.csv
  그림 7  runs/main/analysis/F7_*_scores.csv, F7_*_labels.csv, F7_*_case.json
출력: <out>/fig1_pre_context.png … fig7_cases.png (400 dpi, 1단 폭 3.45 in)
실행: python scripts/16_figures.py --data . --out paper/figs
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

plt.rcParams.update({"font.size": 7, "font.family": "DejaVu Sans", "axes.titlesize": 7, "legend.fontsize": 6})
COL = {"A": "#444444", "B": "#d08c2a", "C": "#2a6fd0"}
W_ALL = [1, 2, 4, 8, 16]
W_MAIN = [1, 2, 4, 8]


def fig1(data: Path, out: Path):
    rows = {}
    for name, f in [("Staged train", "Staged_train"), ("Staged validation", "Staged_validation"),
                    ("Staged test", "Staged_test"), ("OOPS test", "OOPS_test")]:
        d = pd.read_csv(data / f"dv_window_validity_{f}.csv")
        d = d[d.dataset != "합계"]
        ex = d[d.dataset != "up_fall"]
        n = ex["사건 수"].sum()
        rows[name] = [(ex[f"W={w}s 완전 관찰 %"] * ex["사건 수"]).sum() / n for w in W_ALL]
        if f == "Staged_test":
            n2 = d["사건 수"].sum()
            rows["Staged test incl. UP-Fall (ref.)"] = [(d[f"W={w}s 완전 관찰 %"] * d["사건 수"]).sum() / n2 for w in W_ALL]
    fig, ax = plt.subplots(figsize=(3.45, 2.3))
    sty = {"OOPS test": ("#2a6fd0", "-", "o"), "Staged test": ("#b03030", "-", "s"), "Staged validation": ("#888", "--", "^"),
           "Staged train": ("#888", ":", "v"), "Staged test incl. UP-Fall (ref.)": ("#b03030", ":", "x")}
    for k, v in rows.items():
        c, ls, mk = sty[k]
        ax.plot(np.log2(W_ALL), v, color=c, ls=ls, marker=mk, ms=3, lw=1, label=k)
    ax.set_xticks(np.log2(W_ALL)); ax.set_xticklabels([str(w) for w in W_ALL])
    ax.set_xlabel("Temporal context W (s)"); ax.set_ylabel("Events with pre-event\nfootage ≥ W (%)"); ax.set_ylim(0, 100)
    ax.grid(alpha=.3, lw=.4); ax.legend(frameon=False, ncol=1, loc="upper right")
    fig.tight_layout(pad=.3); fig.savefig(out / "fig1_pre_context.png", dpi=400); plt.close(fig)
    pd.DataFrame(rows, index=[f"W={w}" for w in W_ALL]).T.to_csv(out / "fig1_values.csv")


def fig2(out: Path):
    fig = plt.figure(figsize=(3.45, 2.9)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

    def box(x, y, w, h, t, fc="#eef3fb", ec="#2a6fd0"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.5", fc=fc, ec=ec, lw=.7))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=5.9, linespacing=1.22)

    def arr(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", lw=.7, color="#333", mutation_scale=7, shrinkA=0, shrinkB=0))

    def line(xs, ys): ax.plot(xs, ys, color="#333", lw=.7)
    box(2, 84, 28, 13, "Video stream\n7.5 fps frames"); box(36, 84, 28, 13, "Frozen SigLIP2\n768-d embedding")
    box(70, 84, 28, 13, "Decision every 0.2 s\nwindow [t$_k$−W, t$_k$]\nfirst-frame padding")
    arr(30.6, 90.5, 35.4, 90.5); arr(64.6, 90.5, 69.4, 90.5)
    line([84, 84], [83.4, 79]); line([16, 84], [79, 79])
    for x in (16, 50, 84): arr(x, 79, x, 74.4)
    box(2, 61, 28, 13, "A  single frame\n(logistic reg.)", fc="#f2f2f2", ec="#444")
    box(36, 61, 28, 13, "B  mean of A scores\nover W s (no training)", fc="#fbf1e4", ec="#d08c2a")
    box(70, 61, 28, 13, "C  1-layer GRU\nover W s (3 seeds)", fc="#e8f0fc", ec="#2a6fd0")
    for x in (16, 50, 84): line([x, x], [60.4, 56])
    line([16, 84], [56, 56]); arr(16, 56, 16, 51.4)
    box(2, 38, 28, 13, "Score ≥ θ → alarm\nθ fixed on staged val.\n(EDR ≥ 90%)"); box(36, 38, 28, 13, "Alarm bundles\n(adjacent gap ≤ 2 s)")
    box(70, 38, 28, 13, "First alarm in\n[t0−0.5 s, t1+3 s]\n→ event detected")
    arr(30.6, 44.5, 35.4, 44.5); arr(64.6, 44.5, 69.4, 44.5); arr(84, 37.4, 84, 29.6)
    box(2, 10, 96, 19, "EDR = detected events / all events\nFA/h = FA bundles / non-fall hours (reference camera)\nlatency = first alarm − t0;  95% CI: recording-level bootstrap", fc="#eef7ee", ec="#3a8a3a")
    fig.savefig(out / "fig2_pipeline.png", dpi=400); plt.close(fig)


def fig3(data: Path, out: Path):
    """단위 테스트 출력(eval_edge_cases.csv)의 사례를 공통 타임라인(fall 10–12 s, fallen 12–30 s)에 그린다."""
    d = pd.read_csv(data / "eval_edge_cases.csv")
    label_en = [("먼저", "alarm before window → FA, missed"), ("전방", "in leading margin → TP, latency 0"),
                ("후방 여유 밖", "after margin, in fallen → ignored"), ("후방", "in trailing margin (+3 s) → TP"),
                ("여러 묶음", "two bundles, one event → TP + duplicate"), ("라벨 없는", "alarm in unlabeled gap → ignored"),
                ("경보 없음", "no alarm → missed, latency NaN"), ("영상 끝", "fall at video end → window clipped")]
    def en(k):
        for key, v in label_en:
            if key in k: return v
        return k
    cases = [(en(r.case), json.loads(r.alarms), r.actual_status, bool(r.ok)) for r in d.itertuples()]
    fig, ax = plt.subplots(figsize=(3.45, 2.6))
    ax.axvspan(10, 12, color="#e7a1a1", alpha=.6); ax.axvspan(12, 30, color="#e9d3a8", alpha=.5)
    ax.axvspan(9.5, 15, ymin=0, ymax=1, color="none", ec="#2a6fd0", ls="--", lw=.8)
    ax.text(11, len(cases) + .3, "fall", ha="center", fontsize=5.5); ax.text(21, len(cases) + .3, "fallen", ha="center", fontsize=5.5)
    ax.text(12.3, -.9, "tolerance [t0−0.5, t1+3.0]", fontsize=5.2, color="#2a6fd0")
    for i, (name, al, status, ok) in enumerate(cases):
        y = len(cases) - 1 - i
        col = {"FA": "#b03030", "TP": "#2a7a2a"}.get(str(status).split(",")[0], "#777")
        for t in al:
            ax.plot(t, y, "v", color=col, ms=4)
        ax.text(-0.5, y, name + ("" if ok else "  [MISMATCH]"), ha="right", va="center", fontsize=5.4)
    ax.set_xlim(-0.2, 31); ax.set_ylim(-1.2, len(cases) + .9); ax.set_yticks([]); ax.set_xlabel("time (s)")
    for s in ["top", "right", "left"]: ax.spines[s].set_visible(False)
    ax.tick_params(length=2, pad=1)
    fig.subplots_adjust(left=0.58, right=0.99, top=0.95, bottom=0.14); fig.savefig(out / "fig3_edge_cases.png", dpi=400); plt.close(fig)


def fig4(data: Path, out: Path):
    m = pd.read_csv(data / "results_main.csv")
    sets = [("staged_test", "(a) Staged test (in-domain reference)"), ("oops_test", "(b) OOPS test (primary)")]
    fig, ax = plt.subplots(2, 2, figsize=(3.45, 3.4))
    for j, (st, title) in enumerate(sets):
        d = m[m.set == st].set_index("cond")
        for r, (key, lab) in enumerate([("FA_per_h", "FA/h"), ("EDR", "EDR")]):
            a = ax[r, j]
            a.axhline(d.loc["A", key], color=COL["A"], ls="--", lw=.8, label="A")
            a.axhspan(d.loc["A", key + "_lo"], d.loc["A", key + "_hi"], color=COL["A"], alpha=.08)
            for mdl in ["B", "C"]:
                y = np.array([d.loc[f"{mdl}_W{w}", key] for w in W_ALL]); lo = np.array([d.loc[f"{mdl}_W{w}", key + "_lo"] for w in W_ALL]); hi = np.array([d.loc[f"{mdl}_W{w}", key + "_hi"] for w in W_ALL])
                x = np.log2(W_ALL) + (-.07 if mdl == "B" else .07)
                a.errorbar(x, y, yerr=[y - lo, hi - y], marker="o", ms=2.5, capsize=1.5, color=COL[mdl], label=mdl, lw=.9, elinewidth=.7)
            a.set_xticks(np.log2(W_ALL)); a.set_xticklabels([str(w) for w in W_ALL]); a.axvspan(3.5, 4.5, color="k", alpha=.05)
            if r == 1: a.set_xlabel("W (s)")
            if j == 0: a.set_ylabel(lab)
            if r == 0: a.set_title(title, fontsize=6.5)
            if key == "EDR": a.set_ylim(0, 1)
            a.grid(alpha=.3, lw=.4); a.tick_params(length=2, pad=1.5)
    ax[0, 0].legend(loc="upper left", frameon=False, ncol=3, handlelength=1.2, columnspacing=.6)
    fig.tight_layout(pad=.3, h_pad=.4, w_pad=.5); fig.savefig(out / "fig4_w_effect.png", dpi=400); plt.close(fig)


def fig5(data: Path, out: Path):
    c = pd.read_csv(data / "curves.csv")
    sets = [("staged_test", "(a) Staged test"), ("oops_test", "(b) OOPS test")]
    sty = {"A": ("A", COL["A"], "-"), "B_W4": ("B, W=4", COL["B"], "-"), "C_W1": ("C, W=1", "#8fb5ec", "-"), "C_W4": ("C, W=4", COL["C"], "-"), "C_W16": ("C, W=16", "#123a7a", "--")}
    fig, ax = plt.subplots(2, 1, figsize=(3.45, 3.6))
    for j, (st, title) in enumerate(sets):
        a = ax[j]
        for g, (lab, cc, ls) in sty.items():
            dd = c[(c.set == st) & (c.cond.str.replace(r"_s\d", "", regex=True) == g)]
            for k, (cond, e) in enumerate(dd.groupby("cond")):
                e = e.sort_values("FA_per_h")
                a.plot(e.FA_per_h, np.maximum.accumulate(e.EDR), color=cc, ls=ls, lw=.9, alpha=.95 if k == 0 else .3, label=lab if k == 0 else None, drawstyle="steps-post")
        a.set_xscale("symlog", linthresh=1); a.set_xlim(0, 1000); a.set_ylim(0, 1); a.grid(alpha=.3, lw=.4)
        a.set_ylabel("EDR"); a.set_title(title, loc="left"); a.tick_params(length=2, pad=1.5)
        a.axvspan(0, 10, color="g", alpha=.06)
    ax[1].set_xlabel("False alarms per hour"); ax[1].legend(loc="upper left", frameon=False, ncol=2)
    fig.tight_layout(pad=.3, h_pad=.6); fig.savefig(out / "fig5_curves.png", dpi=400); plt.close(fig)


def fig6(data: Path, out: Path):
    m = pd.read_csv(data / "results_main.csv")
    fig, ax = plt.subplots(2, 1, figsize=(3.45, 3.6))
    for j, (st, title) in enumerate([("staged_test", "(a) Staged test (in-domain reference)"), ("oops_test", "(b) OOPS test (primary evaluation)")]):
        d = m[m.set == st].set_index("cond"); a = ax[j]
        a.plot(d.loc["A", "FA_per_h"], d.loc["A", "EDR"], "s", color=COL["A"], ms=4, label="A (single frame)")
        for mdl, lab in [("B", "B (moving average)"), ("C", "C (GRU)")]:
            xs = [d.loc[f"{mdl}_W{w}", "FA_per_h"] for w in W_MAIN]; ys = [d.loc[f"{mdl}_W{w}", "EDR"] for w in W_MAIN]
            a.plot(xs, ys, "-o", color=COL[mdl], ms=3, lw=.9, label=lab)
            for w, x, y in zip(W_MAIN, xs, ys): a.annotate(str(w), (x, y), xytext=(2, 2), textcoords="offset points", fontsize=5.5, color=COL[mdl])
            x16, y16 = d.loc[f"{mdl}_W16", "FA_per_h"], d.loc[f"{mdl}_W16", "EDR"]
            a.plot(x16, y16, "o", mfc="none", color=COL[mdl], ms=3); a.annotate("16", (x16, y16), xytext=(2, 2), textcoords="offset points", fontsize=5.5, color=COL[mdl])
        a.invert_xaxis(); a.set_ylabel("EDR"); a.set_title(title, loc="left"); a.grid(alpha=.3, lw=.4); a.tick_params(length=2, pad=1.5)
    ax[1].set_xlabel("FA/h at operating point (← fewer false alarms)"); ax[0].legend(frameon=False, loc="lower left")
    fig.tight_layout(pad=.3, h_pad=.6); fig.savefig(out / "fig6_oppoint.png", dpi=400); plt.close(fig)


def fig7(data: Path, out: Path):
    fig, ax = plt.subplots(2, 1, figsize=(3.45, 3.8))
    for j, (tag, title) in enumerate([("staged_detected", "(a) Staged test: detected event"), ("oops_missed_prestarted", "(b) OOPS test: missed event (pre-started bundle)")]):
        sc = pd.read_csv(data / f"F7_{tag}_scores.csv"); lb = pd.read_csv(data / f"F7_{tag}_labels.csv"); case = json.load(open(data / f"F7_{tag}_case.json"))
        t0 = case["t0"]; lo, hi = max(case["vid_start"], t0 - 12), min(case["vid_end"], t0 + 10)
        a = ax[j]
        for r in lb.itertuples():
            if r.label_name == "fall": a.axvspan(r.start, r.end, color="#e7a1a1", alpha=.6)
            elif r.label_name == "fallen": a.axvspan(r.start, r.end, color="#e9d3a8", alpha=.5)
        t1 = lb[(lb.label_name == "fall") & (lb.start <= t0 + 0.01)].end.max() if (lb.label_name == "fall").any() else t0
        a.axvspan(t0 - 0.5, t1 + 3.0, color="none", ec="#2a6fd0", ls="--", lw=.8)
        for cname, lab, cc in [("A", "A", COL["A"]), ("B_W4", "B, W=4", COL["B"]), ("C_W4_s0", "C, W=4", COL["C"])]:
            m = (sc.t >= lo) & (sc.t <= hi)
            a.plot(sc.t[m], sc[f"score_{cname}"][m], color=cc, lw=.9, label=lab)
            a.axhline(sc[f"th_{cname}"].iloc[0], color=cc, lw=.5, ls=":")
            al = sc.t[m & sc[f"alarm_{cname}"]]
            a.plot(al, np.full(len(al), 1.04 + 0.05 * ["A", "B_W4", "C_W4_s0"].index(cname)), "|", color=cc, ms=4, mew=.8)
        a.set_xlim(lo, hi); a.set_ylim(0, 1.22); a.set_ylabel("Fall score"); a.set_title(title, loc="left"); a.grid(alpha=.3, lw=.4); a.tick_params(length=2, pad=1.5)
        a.text(lo + 0.2, 1.17, f"{case['dataset']}/{case['path']}", fontsize=5, color="#555")
    ax[1].set_xlabel("time (s)"); ax[0].legend(frameon=False, loc="upper left", ncol=3, handlelength=1.2)
    fig.tight_layout(pad=.3, h_pad=.6); fig.savefig(out / "fig7_cases.png", dpi=400); plt.close(fig)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", default="."); ap.add_argument("--out", default="paper/figs")
    a = ap.parse_args(); data = Path(a.data); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    # 입력을 한 폴더에 모아 쓰거나(--data), D:\omnifall 구조를 그대로 쓴다
    def find(f):
        for p in [data / f, data / "reports" / "design_verification" / f, data / "runs" / "main" / "results" / f, data / "runs" / "main" / "analysis" / f]:
            if p.exists(): return p.parent
        raise FileNotFoundError(f)
    fig1(find("dv_window_validity_Staged_test.csv"), out); fig2(out); fig3(find("eval_edge_cases.csv"), out)
    fig4(find("results_main.csv"), out); fig5(find("curves.csv"), out); fig6(find("results_main.csv"), out); fig7(find("F7_staged_detected_scores.csv"), out)
    print("saved to", out)


if __name__ == "__main__":
    main()
