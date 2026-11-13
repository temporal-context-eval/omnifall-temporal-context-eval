"""
15_ab_recalc.py — 교정본(2026-11-09) 12쪽 B1~B6, D1, D2, A1 재계산 (원본 결과 파일 → 표)

입력: runs/<name>/design_freeze.json, test_access_log.md, results/{results_main,results_paired,curves,events_at_op}.csv
출력: runs/<name>/recalc/ab_recalc.md  (+ 각 표 CSV)
원칙: 점추정치는 results_main.csv 값으로 계산, 구간·p는 results_paired.csv(쌍체 부트스트랩)에서 가져온다.
실행: python scripts/15_ab_recalc.py --name main
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

OF_HOME = Path(os.environ.get("OF_HOME", "."))
W_MAIN = [1, 2, 4, 8]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def md_table(df: pd.DataFrame, fmt=".3f") -> str:
    return df.to_markdown(floatfmt=fmt)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="main")
    a = ap.parse_args()
    run = OF_HOME / "runs" / a.name
    out = run / "recalc"
    out.mkdir(exist_ok=True)
    m = pd.read_csv(run / "results" / "results_main.csv").set_index(["set", "cond"])
    p = pd.read_csv(run / "results" / "results_paired.csv")
    c = pd.read_csv(run / "results" / "curves.csv")
    e = pd.read_csv(run / "results" / "events_at_op.csv")
    c["g"] = c.cond.str.replace(r"_s\d", "", regex=True)
    e["g"] = e.cond.str.replace(r"_s\d", "", regex=True)
    md = ["# A·B 재계산 결과 (자동 생성)", ""]

    # A1 — 해시·시각
    fz = json.loads((run / "design_freeze.json").read_text(encoding="utf-8"))
    md += ["## A1. 파일 해시와 시각", "",
           f"- design_freeze.json: created {fz['created']}, sha256 {sha(run / 'design_freeze.json')}",
           f"- exclude: {fz['config']['exclude']}, windows {fz['config']['windows']}, seeds {fz['config']['seeds']}",
           f"- test_access_log.md: sha256 {sha(run / 'test_access_log.md')}",
           "```", (run / "test_access_log.md").read_text(encoding="utf-8").strip(), "```", ""]
    for f in ["results_main.csv", "results_paired.csv", "curves.csv", "events_at_op.csv"]:
        md.append(f"- results/{f}: {sha(run / 'results' / f)}")
    md.append("")

    # B1·B2 — 기울기
    rows = []
    x = np.log2(W_MAIN)
    for st in ["oops_test", "staged_test"]:
        for mdl in ["B", "C"]:
            for key in ["FA_per_h", "pAUC", "EDR"]:
                y = [m.loc[(st, f"{mdl}_W{w}"), key] for w in W_MAIN]
                slope = np.polyfit(x, y, 1)[0]
                tr = p[(p.set == st) & (p.family == "trend") & (p.comparison.str.startswith(mdl)) & (p.metric == key)]
                r = dict(set=st, model=mdl, metric=key, slope_point=slope)
                if len(tr):
                    r |= dict(boot_mean=tr.iloc[0]["diff"], ci_lo=tr.iloc[0].lo, ci_hi=tr.iloc[0].hi, p_boot=tr.iloc[0].p_boot)
                rows.append(r)
    b12 = pd.DataFrame(rows)
    b12.to_csv(out / "B1_B2_slopes.csv", index=False)
    md += ["## B1·B2. log2 W 기울기 (W = 1,2,4,8)", "", md_table(b12.set_index(["set", "model", "metric"])), ""]

    # B3·B4 — 쌍체 차이
    rows = []
    for st in ["staged_test", "oops_test"]:
        for w in W_MAIN:
            for a_, b_ in [(f"C_W{w}", "A"), (f"C_W{w}", f"B_W{w}"), (f"B_W{w}", "A")]:
                q = p[(p.set == st) & (p.comparison == f"{a_} − {b_}")].set_index("metric")
                for key in ["FA_per_h", "lat_med", "EDR", "pAUC"]:
                    r = dict(set=st, comparison=f"{a_} − {b_}", metric=key,
                             diff_point=m.loc[(st, a_), key] - m.loc[(st, b_), key])
                    if key in q.index:
                        r |= dict(boot_mean=q.loc[key, "diff"], ci_lo=q.loc[key, "lo"], ci_hi=q.loc[key, "hi"], p_holm=q.loc[key, "p_holm"])
                    rows.append(r)
    b34 = pd.DataFrame(rows)
    b34.to_csv(out / "B3_B4_paired.csv", index=False)
    md += ["## B3·B4. 쌍체 차이 (점추정 = 표 값 차이, 구간 = 쌍체 부트스트랩)", "",
           md_table(b34[b34.metric.isin(["FA_per_h", "lat_med"])].set_index(["set", "comparison", "metric"])), ""]

    # B5 — C 씨드 범위 (pAUC)
    b5 = m.loc[("staged_test", [f"C_W{w}" for w in [1, 2, 4, 8, 16]]), ["pAUC", "pAUC_seed_range", "FA_per_h", "FA_seed_range", "EDR", "EDR_seed_range"]]
    b5.to_csv(out / "B5_seed_ranges.csv")
    md += ["## B5. C 조건 씨드 범위 (Staged test)", "", md_table(b5), ""]

    # B6 — 감소율
    rows = []
    for st in ["staged_test", "oops_test"]:
        A = m.loc[(st, "A"), "FA_per_h"]
        for w in [1, 2, 4, 8, 16]:
            rows.append(dict(set=st, W=w, FA_A=A, FA_C=m.loc[(st, f"C_W{w}"), "FA_per_h"],
                             reduction_pct=100 * (1 - m.loc[(st, f"C_W{w}"), "FA_per_h"] / A)))
    b6 = pd.DataFrame(rows)
    b6.to_csv(out / "B6_reduction.csv", index=False)
    md += ["## B6. A 대비 C 운영점 FA/h 감소율", "", md_table(b6.set_index(["set", "W"]), ".1f"), ""]

    # D1 — 목표 EDR 최소 FA/h (사후)
    rows = []
    for st, tg in [("oops_test", 0.4), ("staged_test", 0.8)]:
        for g in ["A"] + [f"B_W{w}" for w in W_MAIN] + [f"C_W{w}" for w in W_MAIN]:
            vals, mx = [], []
            for cond, d in c[(c.set == st) & (c.g == g)].groupby("cond"):
                ok = d[d.EDR >= tg]
                vals.append(ok.FA_per_h.min() if len(ok) else np.nan)
                mx.append(d.EDR.max())
            vals = np.array(vals)
            rows.append(dict(set=st, target_EDR=tg, cond=g, min_FA_per_h=np.nanmean(vals) if np.isfinite(vals).any() else np.nan,
                             seeds_reaching=f"{int(np.isfinite(vals).sum())}/{len(vals)}", max_EDR_mean=np.mean(mx)))
    d1 = pd.DataFrame(rows)
    d1.to_csv(out / "D1_min_fa_at_target.csv", index=False)
    md += ["## D1 (사후). 목표 EDR 달성 최소 FA/h", "", md_table(d1.set_index(["set", "cond"])), ""]

    # D2 — 공통 사건 집합 (앞 맥락 ≥ 8 s)
    rows = []
    for st in ["staged_test", "oops_test"]:
        sub = e[(e.set == st) & (e.pre_ctx >= 8)]
        r = dict(set=st, n_events=int((sub.cond == "A").sum()))
        for g in ["A"] + [f"B_W{w}" for w in W_MAIN] + [f"C_W{w}" for w in W_MAIN]:
            r[g] = sub[sub.g == g].groupby("cond").detected.mean().mean()
        rows.append(r)
    d2 = pd.DataFrame(rows)
    d2.to_csv(out / "D2_common_event_set.csv", index=False)
    md += ["## D2 (사후). 공통 사건 집합(앞 맥락 ≥ 8 s) EDR", "", md_table(d2.set_index("set")), ""]

    (out / "ab_recalc.md").write_text("\n".join(md), encoding="utf-8")
    print("저장:", out / "ab_recalc.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
