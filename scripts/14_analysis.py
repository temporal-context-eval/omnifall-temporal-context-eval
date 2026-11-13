"""
14_analysis.py — 교정본(2026-11-09) C(사전 지정 보조 분석)·D(사후 분석)·F(그림 7 데이터) 산출

동결된 모델·임계값(runs/<name>/design_freeze.json, models/)을 그대로 불러 test 점수를 다시 계산해 파일로 저장하고,
그 점수 파일에서 모든 보조·사후 분석을 계산한다. 모델·임계값·W 는 바꾸지 않는다.
test 재접근은 test_access_log.md 에 사유와 함께 기록한다.

C1  운영점 EDR 0.80 / 0.95 (validation 에서 식 (12)(13)으로 다시 선택) → test 결과
C2  Staged test 피험자 단위 군집 부트스트랩 95% CI (EDR·FA/h·pAUC)
C3  민감도: (a) 양성 = fall∪fallen, (b) 전 스트림 평가(Staged), (c) 병합 간격 1.0 s, (d) 데이터셋별
D3  OOPS 미검출 사건 분해: 사전 시작 묶음 / 허용 구간 내 경보 없음
D4  사건 시작 전 W 초 구간의 평균 점수 (Staged vs OOPS)
F7  그림 7 용 판정 시각별 점수·경보 데이터 (Staged 검출 사례 1, OOPS 사전 시작 묶음 사례 1)
G1  OOPS 미러(pengxiang/oops) 저장소 리비전

실행 (WSL, venv):  python scripts/14_analysis.py --name main
출력: runs/<name>/analysis/*.csv, analysis_summary.md, runs/<name>/test_scores.pkl
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import omnifall_eval as E  # noqa: E402
import importlib
T = importlib.import_module("13_train_eval")  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("analysis")
OF_HOME = T.OF_HOME
GRID = T.GRID
W_MAIN = [1, 2, 4, 8]


def group_of(c: str) -> str:
    return c.split("_s")[0] if c.startswith("C_") else c


def load_models(run: Path, fz: dict, device: str):
    import torch
    with open(run / "models" / "A_logreg.pkl", "rb") as f:
        clf = pickle.load(f)
    cm = {}
    for W in fz["config"]["windows"]:
        for sd in fz["config"]["seeds"]:
            sdict = torch.load(run / "models" / f"C_W{W:g}_s{sd}.pt", map_location=device)
            m = T.build_gru(sdict["norm.weight"].shape[0]).to(device); m.load_state_dict(sdict); m.eval()
            cm[(W, sd)] = m
    return clf, cm


def op_metrics(streams, scores, th, *, gap=E.MERGE_GAP, positive_union=False):
    """운영점 지표 (EDR, FA/h, n_FA, 지연 중앙값/p90, 사건·묶음 표). positive_union: fallen 을 fall 로 취급."""
    evs, cls, nev, nfh = [], [], 0, 0.0
    for s, x in zip(streams, scores):
        segs = [(E.FALL if (positive_union and lab == E.FALLEN) else lab, a, b) for lab, a, b in s.segs]
        labels = E.StreamLabels(segs, s.vid_start, s.vid_end)
        dec, _ = T.decision_index(s)
        r = E.match_alarms(labels, dec[x >= th], gap=gap)
        evs.append(r.events.assign(dataset=s.dataset, path=s.path, pre_ctx=r.events.t0 - s.vid_start))
        cls.append(r.clusters.assign(dataset=s.dataset, path=s.path))
        nev += len(r.events)
        nfh += E._union_length([(a, b) for lab, a, b in segs if lab not in (E.FALL, E.FALLEN)]) / 3600.0
    ev, cl = pd.concat(evs, ignore_index=True), pd.concat(cls, ignore_index=True)
    ev["detected"] = ev.detected.astype(bool)
    lat = ev.loc[ev.detected, "latency"]
    n_fa = int((cl.status == "FA").sum())
    return dict(n_events=nev, nonfall_h=nfh, EDR=ev.detected.mean() if nev else np.nan, n_FA=n_fa,
                FA_per_h=n_fa / max(nfh, 1e-9), lat_med=lat.median() if len(lat) else np.nan,
                lat_p90=lat.quantile(0.9) if len(lat) else np.nan), ev, cl


def curves(streams, scores, *, gap=E.MERGE_GAP, positive_union=False):
    D = np.zeros((len(streams), len(GRID)), np.int32); F = np.zeros_like(D)
    for i, (s, x) in enumerate(zip(streams, scores)):
        segs = [(E.FALL if (positive_union and lab == E.FALLEN) else lab, a, b) for lab, a, b in s.segs]
        labels = E.StreamLabels(segs, s.vid_start, s.vid_end)
        dec, _ = T.decision_index(s)
        prev_n, prev = -1, (0, 0)
        for k, th in enumerate(GRID):
            al = dec[x >= th]
            if len(al) == 0:
                break
            if len(al) != prev_n:
                r = E.match_alarms(labels, al, gap=gap)
                prev = (int(r.events.detected.sum()), int((r.clusters.status == "FA").sum())); prev_n = len(al)
            D[i, k], F[i, k] = prev
    return D, F


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="main")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()
    import torch
    device = "cuda" if torch.cuda.is_available() and args.device != "cpu" else "cpu"
    run = OF_HOME / "runs" / args.name
    out = run / "analysis"; out.mkdir(exist_ok=True)
    fz = json.loads((run / "design_freeze.json").read_text(encoding="utf-8"))
    for fn, h in fz["files"].items():
        p = run / ("models/" + fn if fn != "val_scores.pkl" else fn)
        if T.sha256(p) != h:
            sys.exit(f"동결 이후 파일이 바뀜: {p}")
    cfg = fz["config"]; windows, seeds, excl = cfg["windows"], cfg["seeds"], set(cfg["exclude"])
    cond = T.conditions(windows, seeds)
    feat_root = OF_HOME / "data" / "features" / cfg["model"]
    clf, cm = load_models(run, fz, device)
    md = ["# C·D·F 분석 결과 (자동 생성)", "", f"- 설계 동결: {T.sha256(run / 'design_freeze.json')}", f"- 생성: {time.strftime('%F %T')}", ""]

    # ---------------------------------------------------------------- test 점수 (재접근 기록)
    spk = run / "test_scores.pkl"
    if spk.exists():
        with open(spk, "rb") as f:
            S = pickle.load(f)
        LOG.info("저장된 test 점수 사용: %s", spk)
    else:
        with open(run / "test_access_log.md", "a", encoding="utf-8") as f:
            f.write(f"| {time.strftime('%F %T')} | staged_test(기준·전 스트림), oops_test | {len(cond)} 조건 | design_freeze sha256 {T.sha256(run / 'design_freeze.json')} "
                    f"| 14_analysis.py {T.sha256(Path(__file__))[:16]} | 재접근: 교정본 C·D·F 보조·사후 분석용 점수 저장. 모델·임계값·W 불변 |\n")
        S = {}
        for name, ref in [("staged_test", True), ("staged_test_all", False), ("oops_test", True)]:
            c_, sp = T.EVAL_SETS["staged_test" if name.startswith("staged") else name]
            st, used, _ = T.load_streams(T.load_labels(c_, sp, excl), feat_root, ref_only=ref)
            sc = T.compute_scores({name: st}, clf, cm, cond, device)[name]
            fp = [T.frame_scores_A(clf, s) for s in st]
            S[name] = dict(streams=st, scores=sc, frame_scores=fp, used=used)
        with open(spk, "wb") as f:
            pickle.dump(S, f)
        LOG.info("test 점수 저장: %s", spk)
    thr = fz["thresholds"]["staged"]

    # ---------------------------------------------------------------- C1 운영점 EDR 0.80 / 0.95
    with open(run / "val_scores.pkl", "rb") as f:
        VS = pickle.load(f)
    c_, sp = T.EVAL_SETS["staged_val"]
    vst, _, _ = T.load_streams(T.load_labels(c_, sp, excl), feat_root, ref_only=True)
    v_nev = np.array([T.n_events(s) for s in vst]); v_nfh = np.array([T.stream_nonfall_h(s) for s in vst])
    v_cl = T.cluster_ids(vst, "recording")
    vcur = T.curves_for(vst, VS["staged_val"])
    rows = []
    for target in [0.80, 0.90, 0.95]:
        T.TARGET_EDR = target
        rng = np.random.default_rng(12345)
        for cname, (D, F) in vcur.items():
            k_med, picks = T.boot_select(D, F, v_nev, v_nfh, v_cl, rng)
            met = bool(D.sum(0).max() / v_nev.sum() >= target)
            for name in ["staged_test", "oops_test"]:
                r, _, _ = op_metrics(S[name]["streams"], S[name]["scores"][cname], GRID[k_med])
                rows.append(dict(target=target, set=name, cond=cname, group=group_of(cname), th=GRID[k_med], val_met_target=met) | r)
    T.TARGET_EDR = 0.90
    c1 = pd.DataFrame(rows)
    c1.to_csv(out / "C1_operating_points.csv", index=False)
    c1g = c1.groupby(["target", "set", "group"])[["EDR", "FA_per_h", "lat_med", "n_FA"]].mean().reset_index()
    c1g["val_met_target(all seeds)"] = c1.groupby(["target", "set", "group"]).val_met_target.all().values
    c1g.to_csv(out / "C1_operating_points_grouped.csv", index=False)
    md += ["## C1. 운영점 EDR 0.80 / 0.90 / 0.95 (validation 재선택 → test)", "", c1g.to_markdown(index=False, floatfmt=".3f"), ""]

    # ---------------------------------------------------------------- C2 피험자 단위 부트스트랩 (Staged test)
    st = S["staged_test"]["streams"]; sc = S["staged_test"]["scores"]
    nev = np.array([T.n_events(s) for s in st]); nfh = np.array([T.stream_nonfall_h(s) for s in st])
    rows = []
    for level in ["recording", "subject"]:
        cl = T.cluster_ids(st, level)
        rng = np.random.default_rng(2026)
        idx_mat = rng.integers(0, cl.max() + 1, (T.N_BOOT, cl.max() + 1))
        boots = {}
        for cname in sc:
            D, F = curves(st, sc[cname]); k = thr[cname]["idx"]
            _, ev, _ = op_metrics(st, sc[cname], GRID[k])
            lat_by = [ev[(ev.path == s.path) & ev.detected].latency.tolist() for s in st]
            boots[cname] = T.boot_metrics(D, F, nev, nfh, lat_by, cl, idx_mat, k)
        for g in sorted(set(group_of(c) for c in sc)):
            b = np.nanmean([boots[c] for c in sc if group_of(c) == g], axis=0)
            r = dict(level=level, group=g, n_clusters=int(cl.max() + 1))
            for j, key in enumerate(["EDR", "FA_per_h", "lat_med", "pAUC"]):
                lo, hi = T.ci(b[:, j]); r[f"{key}_lo"], r[f"{key}_hi"] = lo, hi
            rows.append(r)
    c2 = pd.DataFrame(rows)
    c2.to_csv(out / "C2_subject_vs_recording_ci.csv", index=False)
    md += ["## C2. Staged test 95% CI: 녹화 단위 vs 피험자 단위 군집 부트스트랩", "", c2.to_markdown(index=False, floatfmt=".3f"), ""]

    # ---------------------------------------------------------------- C3 민감도
    rows = []
    for name in ["staged_test", "oops_test"]:
        st_, sc_ = S[name]["streams"], S[name]["scores"]
        for cname in sc_:
            k = thr[cname]["idx"]
            base, ev0, cl0 = op_metrics(st_, sc_[cname], GRID[k])
            rows.append(dict(set=name, variant="base", cond=cname, group=group_of(cname)) | base)
            r, _, _ = op_metrics(st_, sc_[cname], GRID[k], positive_union=True)
            rows.append(dict(set=name, variant="positive=fall∪fallen", cond=cname, group=group_of(cname)) | r)
            r, _, _ = op_metrics(st_, sc_[cname], GRID[k], gap=1.0)
            rows.append(dict(set=name, variant="merge_gap=1.0s", cond=cname, group=group_of(cname)) | r)
            if name == "staged_test":
                sa, ssc = S["staged_test_all"]["streams"], S["staged_test_all"]["scores"][cname]
                r, _, _ = op_metrics(sa, ssc, GRID[k])
                rows.append(dict(set=name, variant="all_streams", cond=cname, group=group_of(cname)) | r)
                # 데이터셋별
                for ds in sorted(set(s.dataset for s in st_)):
                    m_ = [i for i, s in enumerate(st_) if s.dataset == ds]
                    r, _, _ = op_metrics([st_[i] for i in m_], [sc_[cname][i] for i in m_], GRID[k])
                    rows.append(dict(set=name, variant=f"dataset={ds}", cond=cname, group=group_of(cname)) | r)
    c3 = pd.DataFrame(rows)
    c3.to_csv(out / "C3_sensitivity.csv", index=False)
    c3g = c3.groupby(["set", "variant", "group"])[["n_events", "nonfall_h", "EDR", "FA_per_h", "lat_med"]].mean().reset_index()
    c3g.to_csv(out / "C3_sensitivity_grouped.csv", index=False)
    md += ["## C3. 민감도 (조건군 평균)", "", c3g.to_markdown(index=False, floatfmt=".3f"), ""]

    # ---------------------------------------------------------------- D3 OOPS 미검출 분해
    rows, missed_rows = [], []
    for name in ["oops_test", "staged_test"]:
        st_, sc_ = S[name]["streams"], S[name]["scores"]
        for cname in sc_:
            k = thr[cname]["idx"]
            _, ev, cl = op_metrics(st_, sc_[cname], GRID[k])
            n_missed = pre_started = 0
            for (ds, pth), evp in ev[~ev.detected.astype(bool)].groupby(["dataset", "path"]):
                clp = cl[(cl.dataset == ds) & (cl.path == pth)]
                for _, e_ in evp.iterrows():
                    n_missed += 1
                    pre = ((clp.t_first < e_.win_lo) & (clp.t_last >= e_.win_lo)).any()
                    pre_started += int(pre)
                    missed_rows.append(dict(set=name, cond=cname, dataset=ds, path=pth, t0=e_.t0, win_lo=e_.win_lo, pre_started_bundle=bool(pre)))
            rows.append(dict(set=name, cond=cname, group=group_of(cname), n_missed=n_missed, pre_started=pre_started,
                             pre_started_pct=100 * pre_started / max(n_missed, 1), no_alarm_in_window=n_missed - pre_started))
    d3 = pd.DataFrame(rows); d3.to_csv(out / "D3_missed_breakdown.csv", index=False)
    pd.DataFrame(missed_rows).to_csv(out / "D3_missed_events.csv", index=False)
    d3g = d3.groupby(["set", "group"])[["n_missed", "pre_started", "pre_started_pct", "no_alarm_in_window"]].mean().reset_index()
    md += ["## D3 (사후). 미검출 사건 분해: 사전 시작 묶음 vs 허용 구간 내 경보 없음 (조건군 평균)", "", d3g.to_markdown(index=False, floatfmt=".1f"), ""]

    # ---------------------------------------------------------------- D4 사건 전 W초 평균 점수
    rows = []
    for name in ["staged_test", "oops_test"]:
        st_, fp = S[name]["streams"], S[name]["frame_scores"]
        for s, p_ in zip(st_, fp):
            for t0, t1 in E.StreamLabels(s.segs, s.vid_start, s.vid_end).fall_events():
                r = dict(set=name, dataset=s.dataset, path=s.path, t0=t0, pre_ctx=t0 - s.vid_start)
                for W in W_MAIN:
                    m_ = (s.ft >= t0 - W) & (s.ft < t0)
                    r[f"meanA_pre{W}s"] = p_[m_].mean() if m_.any() else np.nan
                    r[f"n_frames_pre{W}s"] = int(m_.sum())
                m_ = (s.ft >= t0) & (s.ft < t1)
                r["meanA_in_fall"] = p_[m_].mean() if m_.any() else np.nan
                rows.append(r)
    d4 = pd.DataFrame(rows); d4.to_csv(out / "D4_pre_event_scores.csv", index=False)
    d4g = d4.groupby("set")[[f"meanA_pre{W}s" for W in W_MAIN] + ["meanA_in_fall"]].agg(["mean", "median"]).round(3)
    md += ["## D4 (사후). 사건 시작 전 W초 구간의 A 프레임 점수 평균 (사건 단위 → 집계)", "", d4g.to_markdown(), ""]

    # ---------------------------------------------------------------- F7 그림 7 데이터
    def export_case(name, s_idx, tag, t0, t1=None):
        s = S[name]["streams"][s_idx]; dec, _ = T.decision_index(s)
        json.dump(dict(set=name, dataset=s.dataset, path=s.path, t0=float(t0), t1=(None if t1 is None else float(t1)),
                       vid_start=s.vid_start, vid_end=s.vid_end), open(out / f"F7_{tag}_case.json", "w"), indent=1)
        df = pd.DataFrame({"t": dec})
        for cname in ["A", "B_W4", f"C_W4_s{seeds[0]}"]:
            x = S[name]["scores"][cname][s_idx]; df[f"score_{cname}"] = x; df[f"alarm_{cname}"] = x >= GRID[thr[cname]["idx"]]
            df[f"th_{cname}"] = GRID[thr[cname]["idx"]]
        df.to_csv(out / f"F7_{tag}_scores.csv", index=False)
        pd.DataFrame(s.segs, columns=["label", "start", "end"]).assign(label_name=lambda d: d.label.map(lambda v: E.CLASS_NAMES[v])) \
            .to_csv(out / f"F7_{tag}_labels.csv", index=False)
        return f"{s.dataset}/{s.path}"
    # Staged: A·B_W4·C_W4(s0) 모두 검출, C_W4 지연이 중앙값에 가장 가까운 사건
    k4 = thr[f"C_W4_s{seeds[0]}"]["idx"]
    _, evC, _ = op_metrics(S["staged_test"]["streams"], S["staged_test"]["scores"][f"C_W4_s{seeds[0]}"], GRID[k4])
    _, evA, _ = op_metrics(S["staged_test"]["streams"], S["staged_test"]["scores"]["A"], GRID[thr["A"]["idx"]])
    _, evB, _ = op_metrics(S["staged_test"]["streams"], S["staged_test"]["scores"]["B_W4"], GRID[thr["B_W4"]["idx"]])
    key = ["dataset", "path", "event_idx"]
    j = evC.merge(evA[key + ["detected"]], on=key, suffixes=("", "_A")).merge(evB[key + ["detected"]], on=key, suffixes=("", "_B"))
    cand = j[j.detected & j.detected_A & j.detected_B & (j.pre_ctx >= 4)]
    cand = cand.iloc[(cand.latency - cand.latency.median()).abs().argsort()] if len(cand) else j[j.detected]
    srow = cand.iloc[0]
    s_idx = [i for i, s in enumerate(S["staged_test"]["streams"]) if s.dataset == srow.dataset and s.path == srow.path][0]
    case1 = export_case("staged_test", s_idx, "staged_detected", srow.t0, srow.t1)
    # OOPS: C_W4(s0) 미검출 + 사전 시작 묶음, 앞 맥락 가장 긴 사건
    mm = pd.DataFrame(missed_rows); mm = mm[(mm.set == "oops_test") & (mm.cond == f"C_W4_s{seeds[0]}") & mm.pre_started_bundle]
    ostreams = S["oops_test"]["streams"]
    mm["pre_ctx"] = [e_.t0 - [s for s in ostreams if s.path == e_.path][0].vid_start for _, e_ in mm.iterrows()]
    orow = mm.sort_values("pre_ctx", ascending=False).iloc[0]
    o_idx = [i for i, s in enumerate(ostreams) if s.path == orow.path][0]
    case2 = export_case("oops_test", o_idx, "oops_missed_prestarted", orow.t0)
    md += ["## F7. 그림 7 사례", "", f"- (a) Staged 검출 사례: {case1} t0={srow.t0:.1f}s (A·B(W=4)·C(W=4) 모두 검출, C 지연 {srow.latency:.1f} s; 선정 규칙: 앞 맥락 ≥ 4 s 이고 세 조건 모두 검출한 사건 중 C(W=4) 지연이 중앙값에 가장 가까운 사건)",
           f"- (b) OOPS 미검출 사례: {case2} t0={orow.t0:.1f}s (C(W=4) 미검출, 사전 시작 묶음; 선정 규칙: 해당 유형 중 앞 맥락이 가장 긴 사건)", ""]

    # ---------------------------------------------------------------- G1 OOPS 미러 리비전
    try:
        from huggingface_hub import HfApi
        info = HfApi().dataset_info("pengxiang/oops")
        (out / "G1_oops_mirror_revision.txt").write_text(f"pengxiang/oops sha={info.sha} last_modified={info.last_modified}\n")
        md += ["## G1. OOPS 미러 리비전", "", f"- pengxiang/oops @ {info.sha} (last_modified {info.last_modified})", ""]
    except Exception as exc:  # 네트워크 불가 시
        md += ["## G1. OOPS 미러 리비전", "", f"- 조회 실패: {exc}", ""]

    (out / "analysis_summary.md").write_text("\n".join(md), encoding="utf-8")
    LOG.info("저장: %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
