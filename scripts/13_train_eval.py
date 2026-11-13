"""
13_train_eval.py — A/B/C 학습, validation 운영점 확정(설계 동결), test 1회 평가

연구설계(검증 보고서 6절)의 고정 요소
  - 특징: data/features/<model>/<dataset>/<path>.npz (frozen SigLIP2, 7.5 fps) — 세 조건 동일
  - 판정: 0.2 s 간격 t_k, t_k 이하 프레임만 사용, 영상 시작 이전은 첫 프레임 패딩
  - 학습 라벨: fall=1, fall·fallen 외 라벨=0, fallen·미라벨 프레임은 학습 제외
  - A: 프레임 단독 로지스틱 회귀 (L2 정규화 특징, class_weight=balanced)
  - B: A 의 프레임 점수를 [t−W, t] 에서 평균 (학습 없음)
  - C: 단층 GRU(은닉 256), 윈도우 W 의 특징 열 → 끝 프레임 라벨, 씨드 3개
  - 운영점: Staged validation(기준 카메라)에서 EDR ≥ 90% 를 만족하는 최소 FA/h 임계값.
            validation 녹화 단위 부트스트랩 2,000회마다 다시 고른 임계값 색인의 중앙값을 채택.
            만족하는 임계값이 없으면 최대 EDR 중 최소 FA/h.
  - 임계값 격자: sigmoid(linspace(-8, 8, 161)) — 모델·데이터와 무관하게 사전 고정
  - 평가: Staged test, OOPS test 각 1회, 기준 카메라 스트림, 분리 보고
  - 불확실성: 녹화 단위 군집 부트스트랩 2,000회, 조건 간 차이는 같은 재표집의 쌍체 차이
  - 제외: cmdfall(미확보), up_fall(앞 맥락 0.7 s — 검증 보고서 5절; --exclude 로 변경 가능)

단계
  fit  : train 으로 A·C 학습, validation 점수·운영점 → runs/<name>/design_freeze.json (test 미접근)
  test : design_freeze.json 의 모델·임계값으로 test 1회 평가, test_access_log.md 에 기록
실행 (WSL, venv)
  python scripts/13_train_eval.py --stage fit
  python scripts/13_train_eval.py --stage test
  옵션: --windows 1 2 4 8 16  --seeds 0 1 2  --epochs 8  --name main  --exclude cmdfall up_fall
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import pickle
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import omnifall_eval as E  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("train_eval")

OF_HOME = Path(os.environ.get("OF_HOME", "."))
LAB = OF_HOME / "data" / "labels"
FPS = E.TARGET_FPS
GRID = 1.0 / (1.0 + np.exp(-np.linspace(-8, 8, 161)))   # 임계값 격자 (사전 고정)
TARGET_EDR = 0.90
N_BOOT = 2000
PAUC_MAX = 10.0      # FA/h 0~10 구간의 EDR 곡선 아래 면적(정규화)

# 평가 집합: (이름, config, split, 역할)
EVAL_SETS = {
    "staged_val": ("of-sta-cs", "validation"),
    "oops_val": ("of-itw", "validation"),
    "staged_test": ("of-sta-cs", "test"),
    "oops_test": ("of-itw", "test"),
}


# =============================================================================== 데이터
@dataclass
class Stream:
    dataset: str
    path: str
    subject: int
    segs: list            # [(label, start, end)]
    vid_start: float
    vid_end: float
    ft: np.ndarray        # 프레임 시각 (T,)
    feat: np.ndarray      # (T, D) float16
    offset: int = 0       # 전역 특징 텐서에서의 시작 위치


def load_labels(cfg: str, split: str, exclude: set) -> pd.DataFrame:
    df = E.prepare_labels(pd.read_csv(LAB / f"{cfg}__{split}.csv"))
    return df[~df.dataset.isin(exclude)].copy()


def load_streams(df: pd.DataFrame, feat_root: Path, ref_only: bool):
    """라벨 표 → Stream 목록. 특징 파일이 없는 스트림은 제외하고, 실제로 쓴 라벨 행만 돌려준다."""
    if ref_only:
        df = E.reference_streams(df)
    streams, keep, missing = [], [], []
    for (ds, p), g in df.groupby(["dataset", "path"], sort=True):
        f = feat_root / ds / f"{p}.npz"
        if not f.exists():
            missing.append(f"{ds}/{p}")
            continue
        z = np.load(f)
        feat, ft = z["feat"], z["t"].astype(np.float64)
        if len(feat) == 0:
            missing.append(f"{ds}/{p}")
            continue
        segs = sorted(zip(g.label.astype(int), g.start.astype(float), g.end.astype(float)), key=lambda x: x[1])
        streams.append(Stream(ds, p, int(g.subject.iloc[0]), segs, float(g.start.min()), float(g.end.max()), ft, feat))
        keep.append(g.index.values)
    if missing:
        LOG.warning("특징 파일 없음 %d개 스트림 제외 (예: %s)", len(missing), missing[:3])
    used = df.loc[np.concatenate(keep)] if keep else df.iloc[:0]
    return streams, used, missing


def frame_targets(s: Stream) -> np.ndarray:
    """프레임별 학습 목표: 1=fall, 0=그 밖의 라벨, -1=fallen·미라벨(학습 제외). 겹침은 fall > fallen > 기타 우선."""
    y = np.full(len(s.ft), -1, dtype=np.int8)
    order = sorted(s.segs, key=lambda x: {E.FALL: 2, E.FALLEN: 1}.get(x[0], 0))
    for lab, a, b in order:
        m = (s.ft >= a) & (s.ft < b)
        y[m] = 1 if lab == E.FALL else (-1 if lab == E.FALLEN else 0)
    return y


def l2n(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32)
    return x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-8)


def decision_index(s: Stream):
    """판정 시각과, 각 판정 시각 이하의 마지막 프레임 색인(없으면 -1)."""
    dec = E.decision_times(s.vid_start, s.vid_end)
    last = np.searchsorted(s.ft, dec + 1e-9, side="right") - 1
    return dec, last


def window_index(last: np.ndarray, W: float) -> tuple[np.ndarray, np.ndarray]:
    """판정별 윈도우 프레임 색인 (n_dec, need), 패딩 개수. frames_for_window 와 동일 규칙(벡터화)."""
    need = max(1, int(round(W * FPS)))
    idx = last[:, None] - np.arange(need)[::-1][None, :]
    pad = np.clip(need - 1 - last, 0, need)
    return np.clip(idx, 0, None), pad


# =============================================================================== 모델
def fit_A(train: list[Stream], seed: int = 0):
    from sklearn.linear_model import LogisticRegression
    X, y = [], []
    for s in train:
        t = frame_targets(s)
        m = t >= 0
        X.append(l2n(s.feat[m])); y.append(t[m])
    X, y = np.concatenate(X), np.concatenate(y)
    LOG.info("A 학습: 프레임 %d (fall %d, 비낙상 %d)", len(y), int(y.sum()), int((y == 0).sum()))
    clf = LogisticRegression(C=1.0, class_weight="balanced", max_iter=3000, random_state=seed)
    clf.fit(X, y)
    return clf


def frame_scores_A(clf, s: Stream) -> np.ndarray:
    return clf.predict_proba(l2n(s.feat))[:, 1]


def build_gru(dim: int, hidden: int = 256):
    import torch.nn as nn

    class GRUHead(nn.Module):
        def __init__(self):
            super().__init__()
            self.norm = nn.LayerNorm(dim)
            self.gru = nn.GRU(dim, hidden, batch_first=True)
            self.out = nn.Linear(hidden, 1)

        def forward(self, x):
            _, h = self.gru(self.norm(x))
            return self.out(h[-1]).squeeze(-1)

    return GRUHead()


def stack_features(streams: list[Stream], device):
    """모든 스트림 특징을 한 텐서로 이어 붙이고 각 스트림의 offset 을 기록 (GPU 에서 윈도우를 바로 모으기 위함)."""
    import torch
    off = 0
    for s in streams:
        s.offset = off
        off += len(s.feat)
    big = np.concatenate([s.feat for s in streams]).astype(np.float16)
    return torch.from_numpy(big).to(device)


def fit_C(train: list[Stream], W: float, seed: int, epochs: int, device: str, neg_ratio: int = 4, batch: int = 256):
    import torch
    torch.manual_seed(seed); np.random.seed(seed)
    rng = np.random.default_rng(seed)
    feats = stack_features(train, device)
    pos, neg = [], []
    for i, s in enumerate(train):
        t = frame_targets(s)
        g = s.offset + np.arange(len(t))
        local = np.arange(len(t))
        pos.append(np.stack([np.full((t == 1).sum(), i), local[t == 1]], 1))
        neg.append(np.stack([np.full((t == 0).sum(), i), local[t == 0]], 1))
    pos, neg = np.concatenate(pos), np.concatenate(neg)
    offsets = np.array([s.offset for s in train])
    need = max(1, int(round(W * FPS)))
    ar = np.arange(need)[::-1]
    model = build_gru(feats.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    lossf = torch.nn.BCEWithLogitsLoss()
    LOG.info("C 학습 W=%g seed=%d: 양성 %d, 음성 %d (에폭당 음성 %d배 표집)", W, seed, len(pos), len(neg), neg_ratio)
    model.train()
    for ep in range(epochs):
        n_neg = min(len(neg), neg_ratio * len(pos))
        samp = np.concatenate([pos, neg[rng.choice(len(neg), n_neg, replace=False)]])
        yv = np.concatenate([np.ones(len(pos)), np.zeros(n_neg)]).astype(np.float32)
        perm = rng.permutation(len(samp))
        tot = 0.0
        for b in range(0, len(perm), batch):
            j = perm[b:b + batch]
            si, fi = samp[j, 0], samp[j, 1]
            gidx = offsets[si][:, None] + np.clip(fi[:, None] - ar[None, :], 0, None)
            x = feats[torch.from_numpy(gidx).to(device)].float()
            y = torch.from_numpy(yv[j]).to(device)
            loss = lossf(model(x), y)
            opt.zero_grad(); loss.backward(); opt.step()
            tot += float(loss.detach()) * len(j)
        LOG.info("  epoch %d/%d loss %.4f", ep + 1, epochs, tot / len(perm))
    model.eval()
    return model


def decision_scores_C(model, streams: list[Stream], W: float, device: str, batch: int = 1024) -> list[np.ndarray]:
    import torch
    feats = stack_features(streams, device)
    out = []
    with torch.inference_mode():
        for s in streams:
            _, last = decision_index(s)
            idx, _ = window_index(last, W)
            g = torch.from_numpy(s.offset + idx).to(device)
            sc = []
            for b in range(0, len(g), batch):
                sc.append(torch.sigmoid(model(feats[g[b:b + batch]].float())).cpu().numpy())
            out.append(np.concatenate(sc) if sc else np.zeros(0))
    del feats
    return out


def decision_scores_AB(frame_p: list[np.ndarray], streams: list[Stream], W: float | None) -> list[np.ndarray]:
    """W=None 이면 A(마지막 프레임 점수), 아니면 B(윈도우 평균, 첫 프레임 패딩)."""
    out = []
    for p, s in zip(frame_p, streams):
        _, last = decision_index(s)
        if W is None:
            out.append(p[np.clip(last, 0, None)])
        else:
            idx, _ = window_index(last, W)
            out.append(p[idx].mean(1))
    return out


# =============================================================================== 평가
def stream_curve(s: Stream, scores: np.ndarray):
    """격자 임계값별 (검출 사건 수, FA 수). 단조성을 이용해 같은 경보 집합은 재사용."""
    labels = E.StreamLabels(s.segs, s.vid_start, s.vid_end)
    dec, _ = decision_index(s)
    det = np.zeros(len(GRID), dtype=np.int32)
    fa = np.zeros(len(GRID), dtype=np.int32)
    prev_n, prev = -1, (0, 0)
    for k, th in enumerate(GRID):
        alarms = dec[scores >= th]
        if len(alarms) == 0:
            break
        if len(alarms) != prev_n:
            r = E.match_alarms(labels, alarms)
            prev = (int(r.events.detected.sum()), int((r.clusters.status == "FA").sum()))
            prev_n = len(alarms)
        det[k], fa[k] = prev
    return det, fa


def op_details(s: Stream, scores: np.ndarray, th: float):
    labels = E.StreamLabels(s.segs, s.vid_start, s.vid_end)
    dec, _ = decision_index(s)
    r = E.match_alarms(labels, dec[scores >= th])
    ev = r.events.assign(dataset=s.dataset, path=s.path, pre_ctx=r.events.t0 - s.vid_start)
    cl = r.clusters.assign(dataset=s.dataset, path=s.path)
    return ev, cl


def stream_nonfall_h(s: Stream) -> float:
    return E._union_length([(a, b) for lab, a, b in s.segs if lab not in (E.FALL, E.FALLEN)]) / 3600.0


def n_events(s: Stream) -> int:
    return len(E.StreamLabels(s.segs, s.vid_start, s.vid_end).fall_events())


def select_op(det: np.ndarray, fa: np.ndarray, nev: np.ndarray, nfh: np.ndarray) -> int:
    """det, fa: (grid,) 합계. EDR≥목표 중 최소 FA/h(동률이면 높은 EDR, 낮은 색인). 없으면 최대 EDR 중 최소 FA/h."""
    edr = det / max(nev, 1)
    fah = fa / max(nfh, 1e-9)
    ok = np.where(edr >= TARGET_EDR - 1e-12)[0]
    if len(ok) == 0:
        ok = np.where(edr == edr.max())[0]
    best = ok[np.lexsort((ok, -edr[ok], fah[ok]))]
    return int(best[0])


def pauc(det: np.ndarray, fa: np.ndarray, nev: float, nfh: float) -> float:
    edr = det / max(nev, 1)
    fah = fa / max(nfh, 1e-9)
    xs = np.linspace(0, PAUC_MAX, 201)
    o = np.argsort(fah)
    f_sorted, e_cum = fah[o], np.maximum.accumulate(edr[o])
    pos = np.searchsorted(f_sorted, xs, side="right") - 1
    return float(np.where(pos >= 0, e_cum[np.clip(pos, 0, None)], 0.0).mean())


def cluster_ids(streams: list[Stream], level: str) -> np.ndarray:
    if level == "subject":
        keys = [f"{s.dataset}:{s.subject}" if s.subject >= 0 else f"{s.dataset}:{s.path}" for s in streams]
    else:  # recording (기준 카메라만 쓰므로 스트림 = 녹화)
        keys = [f"{s.dataset}:{E.recording_key(s.dataset, s.path)}" for s in streams]
    _, inv = np.unique(keys, return_inverse=True)
    return inv


# =============================================================================== 유틸
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def conditions(windows, seeds):
    cond = [("A", None, None)]
    cond += [(f"B_W{w:g}", w, None) for w in windows]
    cond += [(f"C_W{w:g}_s{s}", w, s) for w in windows for s in seeds]
    return cond


def compute_scores(sets: dict, clf, cmodels: dict, cond, device):
    """sets: 이름→streams. 반환: scores[set][cond] = [stream별 판정 점수]."""
    out = {}
    for name, streams in sets.items():
        fp = [frame_scores_A(clf, s) for s in streams]
        out[name] = {}
        for cname, W, seed in cond:
            if cname == "A":
                out[name][cname] = decision_scores_AB(fp, streams, None)
            elif cname.startswith("B_"):
                out[name][cname] = decision_scores_AB(fp, streams, W)
            else:
                out[name][cname] = decision_scores_C(cmodels[(W, seed)], streams, W, device)
        LOG.info("점수 계산: %s (%d 스트림, %d 조건)", name, len(streams), len(cond))
    return out


def curves_for(streams, scores_by_cond):
    """조건별 (n_streams, grid) det·fa 행렬."""
    res = {}
    for cname, sc in scores_by_cond.items():
        D = np.zeros((len(streams), len(GRID)), np.int32)
        F = np.zeros_like(D)
        for i, (s, x) in enumerate(zip(streams, sc)):
            D[i], F[i] = stream_curve(s, x)
        res[cname] = (D, F)
    return res


def boot_select(D, F, nev, nfh, clusters, rng) -> tuple[int, list[int]]:
    """validation 군집 부트스트랩으로 운영점 색인 분포 → 중앙값 색인."""
    C = clusters.max() + 1
    Dc = np.zeros((C, D.shape[1])); Fc = np.zeros_like(Dc); Nc = np.zeros(C); Hc = np.zeros(C)
    np.add.at(Dc, clusters, D); np.add.at(Fc, clusters, F); np.add.at(Nc, clusters, nev); np.add.at(Hc, clusters, nfh)
    picks = []
    for _ in range(N_BOOT):
        j = rng.integers(0, C, C)
        picks.append(select_op(Dc[j].sum(0), Fc[j].sum(0), Nc[j].sum(), Hc[j].sum()))
    return int(np.median(picks)), picks


# =============================================================================== 단계: fit
def stage_fit(args):
    import torch
    device = "cuda" if torch.cuda.is_available() and args.device != "cpu" else "cpu"
    run = OF_HOME / "runs" / args.name
    (run / "models").mkdir(parents=True, exist_ok=True)
    feat_root = OF_HOME / "data" / "features" / args.model
    excl = set(args.exclude)
    windows, seeds = args.windows, args.seeds
    cond = conditions(windows, seeds)

    tr_df = load_labels("of-sta-cs", "train", excl)
    tr_df = tr_df[~((tr_df.dataset == "up_fall") & tr_df.subject.isin([11, 15, 16]))]  # 분할 누수 수정
    train, tr_used, tr_miss = load_streams(tr_df, feat_root, ref_only=False)
    LOG.info("train 스트림 %d (모든 카메라 사용)", len(train))

    clf = fit_A(train, seed=0)
    with open(run / "models" / "A_logreg.pkl", "wb") as f:
        pickle.dump(clf, f)
    cmodels = {}
    for W in windows:
        for sd in seeds:
            m = fit_C(train, W, sd, args.epochs, device)
            torch.save(m.state_dict(), run / "models" / f"C_W{W:g}_s{sd}.pt")
            cmodels[(W, sd)] = m

    # validation (기준 카메라)
    val_sets, val_meta = {}, {}
    for name in ["staged_val", "oops_val"]:
        cfg, sp = EVAL_SETS[name]
        st, used, miss = load_streams(load_labels(cfg, sp, excl), feat_root, ref_only=True)
        val_sets[name] = st
        val_meta[name] = dict(streams=len(st), events=int(sum(n_events(s) for s in st)),
                              nonfall_h=float(E.nonfall_hours(used)), missing=len(miss))
    scores = compute_scores(val_sets, clf, cmodels, cond, device)
    with open(run / "val_scores.pkl", "wb") as f:
        pickle.dump(scores, f)

    rng = np.random.default_rng(12345)
    rows, thresholds = [], {"staged": {}, "oops_recal": {}}
    for name, key in [("staged_val", "staged"), ("oops_val", "oops_recal")]:
        st = val_sets[name]
        nev = np.array([n_events(s) for s in st]); nfh = np.array([stream_nonfall_h(s) for s in st])
        cl = cluster_ids(st, "recording")
        cur = curves_for(st, scores[name])
        for cname, (D, F) in cur.items():
            k_point = select_op(D.sum(0), F.sum(0), nev.sum(), nfh.sum())
            k_med, picks = boot_select(D, F, nev, nfh, cl, rng)
            q25, q75 = np.percentile(picks, [25, 75])
            thresholds[key][cname] = dict(idx=k_med, th=float(GRID[k_med]), idx_point=k_point,
                                          idx_q25=float(q25), idx_q75=float(q75))
            rows.append(dict(set=name, cond=cname, th=GRID[k_med], th_point=GRID[k_point],
                             th_q25=GRID[int(q25)], th_q75=GRID[int(q75)],
                             EDR=D.sum(0)[k_med] / nev.sum(), FA_per_h=F.sum(0)[k_med] / nfh.sum(),
                             pAUC=pauc(D.sum(0), F.sum(0), nev.sum(), nfh.sum()),
                             met_target=bool(D.sum(0).max() / nev.sum() >= TARGET_EDR)))
    sel = pd.DataFrame(rows)
    sel.to_csv(run / "val_selection.csv", index=False)
    LOG.info("validation 운영점:\n%s", sel[sel.set == "staged_val"].to_string(index=False, float_format="%.3f"))

    freeze = dict(
        created=time.strftime("%F %T"), stage="fit",
        config=dict(model=args.model, windows=windows, seeds=seeds, epochs=args.epochs, exclude=sorted(excl),
                    target_edr=TARGET_EDR, grid="sigmoid(linspace(-8,8,161))", n_boot=N_BOOT,
                    pre_tol=E.PRE_TOL, post_tol=E.POST_TOL, refractory=E.REFRACTORY, merge_gap=E.MERGE_GAP,
                    decision_step=E.DECISION_STEP, fps=FPS, train_streams=len(train), train_missing=len(tr_miss)),
        val_meta=val_meta, thresholds=thresholds,
        files={p.name: sha256(p) for p in sorted((run / "models").glob("*"))} | {"val_scores.pkl": sha256(run / "val_scores.pkl")},
        code={p: sha256(Path(__file__).parent / p) for p in ["13_train_eval.py", "omnifall_eval.py"]},
    )
    (run / "design_freeze.json").write_text(json.dumps(freeze, ensure_ascii=False, indent=1), encoding="utf-8")
    LOG.info("설계 동결 기록: %s (sha256 %s)", run / "design_freeze.json", sha256(run / "design_freeze.json")[:16])


# =============================================================================== 단계: test
def boot_metrics(D, F, nev, nfh, lat_by_stream, clusters, idx_mat, k):
    """한 조건의 재표집별 지표 (EDR, FA/h, 지연 중앙값, pAUC) — idx_mat: (N_BOOT, C) 군집 색인."""
    C = clusters.max() + 1
    Dc = np.zeros((C, D.shape[1])); Fc = np.zeros_like(Dc); Nc = np.zeros(C); Hc = np.zeros(C)
    np.add.at(Dc, clusters, D); np.add.at(Fc, clusters, F); np.add.at(Nc, clusters, nev); np.add.at(Hc, clusters, nfh)
    lat_c = [[] for _ in range(C)]
    for i, l in enumerate(lat_by_stream):
        lat_c[clusters[i]].extend(l)
    lat_c = [np.asarray(l) for l in lat_c]
    out = np.zeros((len(idx_mat), 4))
    for b, j in enumerate(idx_mat):
        d, f, n, h = Dc[j].sum(0), Fc[j].sum(0), Nc[j].sum(), Hc[j].sum()
        L = np.concatenate([lat_c[c] for c in j])
        out[b] = [d[k] / max(n, 1), f[k] / max(h, 1e-9), np.median(L) if len(L) else np.nan, pauc(d, f, n, h)]
    return out


def ci(x):
    x = x[~np.isnan(x)]
    return (np.percentile(x, 2.5), np.percentile(x, 97.5)) if len(x) else (np.nan, np.nan)


def holm(p: np.ndarray) -> np.ndarray:
    o = np.argsort(p); m = len(p); adj = np.empty(m); run = 0.0
    for r, i in enumerate(o):
        run = max(run, (m - r) * p[i]); adj[i] = min(1.0, run)
    return adj


def stage_test(args):
    import torch
    device = "cuda" if torch.cuda.is_available() and args.device != "cpu" else "cpu"
    run = OF_HOME / "runs" / args.name
    fz_path = run / "design_freeze.json"
    if not fz_path.exists():
        sys.exit("design_freeze.json 없음 — 먼저 --stage fit 을 실행하십시오.")
    fz = json.loads(fz_path.read_text(encoding="utf-8"))
    for fn, h in fz["files"].items():
        p = run / ("models/" + fn if fn != "val_scores.pkl" else fn)
        if sha256(p) != h:
            sys.exit(f"동결 이후 파일이 바뀜: {p}")
    log_path = run / "test_access_log.md"
    if log_path.exists() and not args.force_retest:
        sys.exit("test 는 이미 1회 평가됨 (test_access_log.md). 재평가가 정당하면 --force-retest 로 사유와 함께 기록하십시오.")
    cfg = fz["config"]
    windows, seeds, excl = cfg["windows"], cfg["seeds"], set(cfg["exclude"])
    cond = conditions(windows, seeds)
    feat_root = OF_HOME / "data" / "features" / cfg["model"]

    with open(run / "models" / "A_logreg.pkl", "rb") as f:
        clf = pickle.load(f)
    cmodels = {}
    dim = None
    for W in windows:
        for sd in seeds:
            sdict = torch.load(run / "models" / f"C_W{W:g}_s{sd}.pt", map_location=device)
            dim = sdict["norm.weight"].shape[0]
            m = build_gru(dim).to(device); m.load_state_dict(sdict); m.eval()
            cmodels[(W, sd)] = m

    test_sets, used_df = {}, {}
    for name in ["staged_test", "oops_test"]:
        c, sp = EVAL_SETS[name]
        st, used, miss = load_streams(load_labels(c, sp, excl), feat_root, ref_only=True)
        test_sets[name], used_df[name] = st, used
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"| {time.strftime('%F %T')} | {', '.join(test_sets)} | {len(cond)} 조건 | design_freeze sha256 {sha256(fz_path)} "
                f"| 13_train_eval.py {sha256(Path(__file__))[:16]} | {'재평가: ' + args.force_retest if args.force_retest else '최초 1회'} |\n")
    scores = compute_scores(test_sets, clf, cmodels, cond, device)

    out = run / "results"
    out.mkdir(exist_ok=True)
    main_rows, pair_rows, subset_rows, ds_rows, lab_rows, curve_rows, op_ev_all = [], [], [], [], [], [], []
    for name, st in test_sets.items():
        thr_key = "staged"
        nev = np.array([n_events(s) for s in st]); nfh = np.array([stream_nonfall_h(s) for s in st])
        cl = cluster_ids(st, "recording")
        rng = np.random.default_rng(2026)
        idx_mat = rng.integers(0, cl.max() + 1, (N_BOOT, cl.max() + 1))
        cur = curves_for(st, scores[name])
        boots, ops = {}, {}
        for cname, (D, F) in cur.items():
            k = fz["thresholds"][thr_key][cname]["idx"]
            evs, cls = zip(*[op_details(s, x, GRID[k]) for s, x in zip(st, scores[name][cname])])
            ev, clu = pd.concat(evs, ignore_index=True), pd.concat(cls, ignore_index=True)
            ev["cond"] = cname; ev["set"] = name
            op_ev_all.append(ev)
            lat_by = [e.loc[e.detected, "latency"].tolist() for e in evs]
            boots[cname] = boot_metrics(D, F, nev, nfh, lat_by, cl, idx_mat, k)
            ops[cname] = (ev, clu, k)
            for kk in range(len(GRID)):
                curve_rows.append(dict(set=name, cond=cname, th=GRID[kk], EDR=D.sum(0)[kk] / nev.sum(),
                                       FA_per_h=F.sum(0)[kk] / nfh.sum()))
            # 데이터셋별
            for ds in sorted(set(s.dataset for s in st)):
                m = np.array([s.dataset == ds for s in st])
                ds_rows.append(dict(set=name, cond=cname, dataset=ds, events=int(nev[m].sum()),
                                    nonfall_h=nfh[m].sum(), EDR=D[m].sum(0)[k] / max(nev[m].sum(), 1),
                                    FA=int(F[m].sum(0)[k]), FA_per_h=F[m].sum(0)[k] / max(nfh[m].sum(), 1e-9)))
            # 라벨별 FA율
            lh = E.per_label_hours(used_df[name])
            fr = E.fa_rate_by_label(clu, lh).assign(set=name, cond=cname)
            lab_rows.append(fr)

        # 조건 묶음: C 는 씨드 평균
        groups = {"A": ["A"]}
        groups |= {f"B_W{w:g}": [f"B_W{w:g}"] for w in windows}
        groups |= {f"C_W{w:g}": [f"C_W{w:g}_s{s}" for s in seeds] for w in windows}
        gboot = {g: np.nanmean([boots[c] for c in cs], axis=0) for g, cs in groups.items()}
        for g, cs in groups.items():
            pts = []
            for c in cs:
                ev, clu, k = ops[c]
                D, F = cur[c]
                lat = ev.loc[ev.detected, "latency"]
                pts.append([D.sum(0)[k] / nev.sum(), F.sum(0)[k] / nfh.sum(), lat.median() if len(lat) else np.nan,
                            lat.quantile(0.9) if len(lat) else np.nan, pauc(D.sum(0), F.sum(0), nev.sum(), nfh.sum()),
                            int(F.sum(0)[k])])
            pts = np.array(pts)
            row = dict(set=name, cond=g, n_events=int(nev.sum()), nonfall_h=float(nfh.sum()),
                       EDR=pts[:, 0].mean(), FA_per_h=pts[:, 1].mean(), n_FA=pts[:, 5].mean(),
                       lat_med=pts[:, 2].mean(), lat_p90=pts[:, 3].mean(), pAUC=pts[:, 4].mean())
            for j, key in enumerate(["EDR", "FA_per_h", "lat_med", "pAUC"]):
                lo, hi = ci(gboot[g][:, j]); row[f"{key}_lo"], row[f"{key}_hi"] = lo, hi
            if len(cs) > 1:
                row["EDR_seed_range"] = f"{pts[:, 0].min():.3f}–{pts[:, 0].max():.3f}"
                row["FA_seed_range"] = f"{pts[:, 1].min():.2f}–{pts[:, 1].max():.2f}"
                row["pAUC_seed_range"] = f"{pts[:, 4].min():.3f}–{pts[:, 4].max():.3f}"
            main_rows.append(row)

        # 쌍체 비교
        comps = [(f"B_W{w:g}", "A") for w in windows] + [(f"C_W{w:g}", "A") for w in windows] + \
                [(f"C_W{w:g}", f"B_W{w:g}") for w in windows] + \
                [(f"B_W{w:g}", f"B_W{windows[0]:g}") for w in windows[1:]] + \
                [(f"C_W{w:g}", f"C_W{windows[0]:g}") for w in windows[1:]]
        prow = []
        for a, b in comps:
            d = gboot[a] - gboot[b]
            for j, key in enumerate(["EDR", "FA_per_h", "lat_med", "pAUC"]):
                x = d[:, j][~np.isnan(d[:, j])]
                p = 2 * min((x <= 0).mean(), (x >= 0).mean()) if len(x) else np.nan
                lo, hi = ci(d[:, j])
                prow.append(dict(set=name, comparison=f"{a} − {b}", metric=key, diff=np.nanmean(d[:, j]),
                                 lo=lo, hi=hi, p_boot=min(1.0, p), family=f"{a[0]}:{key}"))
        pr = pd.DataFrame(prow)
        pr["p_holm"] = np.nan
        for fam, g in pr.groupby("family"):
            pr.loc[g.index, "p_holm"] = holm(g.p_boot.fillna(1).values)
        pair_rows.append(pr)

        # 추세: pAUC, FA/h 를 log2 W 에 회귀 (주 W 집합)
        main_w = [w for w in windows if w in args.main_windows]
        xw = np.log2(main_w)
        for mdl in ["B", "C"]:
            for j, key in [(1, "FA_per_h"), (3, "pAUC")]:
                Y = np.stack([gboot[f"{mdl}_W{w:g}"][:, j] for w in main_w], 1)
                slopes = np.array([np.polyfit(xw, y, 1)[0] for y in Y])
                lo, hi = ci(slopes)
                pr2 = pd.DataFrame([dict(set=name, comparison=f"{mdl}: 기울기 vs log2 W ({','.join(f'{w:g}' for w in main_w)})",
                                         metric=key, diff=np.nanmean(slopes), lo=lo, hi=hi,
                                         p_boot=2 * min((slopes <= 0).mean(), (slopes >= 0).mean()), family="trend", p_holm=np.nan)])
                pair_rows.append(pr2)

        # 완전 관찰 부분집합 (앞 맥락 ≥ W): 같은 부분집합에서 A, B_W, C_W 비교
        allev = pd.concat([ops[c][0] for c in cur], ignore_index=True)
        for w in windows:
            sub_cond = ["A", f"B_W{w:g}"] + [f"C_W{w:g}_s{s}" for s in seeds]
            r = dict(set=name, W=w)
            for c in sub_cond:
                e = ops[c][0]
                m = e.pre_ctx >= w
                r["n_subset"] = int(m.sum())
                r[f"EDR_{c}"] = e.loc[m, "detected"].mean() if m.any() else np.nan
                r[f"EDRall_{c}"] = e.detected.mean()
            r[f"EDR_C_W{w:g}"] = np.nanmean([r[f"EDR_C_W{w:g}_s{s}"] for s in seeds])
            r[f"EDRall_C_W{w:g}"] = np.nanmean([r[f"EDRall_C_W{w:g}_s{s}"] for s in seeds])
            subset_rows.append(r)

    pd.DataFrame(main_rows).to_csv(out / "results_main.csv", index=False)
    pd.concat(pair_rows, ignore_index=True).to_csv(out / "results_paired.csv", index=False)
    pd.DataFrame(subset_rows).to_csv(out / "results_subset.csv", index=False)
    pd.DataFrame(ds_rows).to_csv(out / "results_by_dataset.csv", index=False)
    pd.concat(lab_rows, ignore_index=True).to_csv(out / "results_fa_by_label.csv", index=False)
    pd.DataFrame(curve_rows).to_csv(out / "curves.csv", index=False)
    pd.concat(op_ev_all, ignore_index=True).to_csv(out / "events_at_op.csv", index=False)

    # OOPS 보조: OOPS validation 으로 다시 보정한 임계값
    st = test_sets["oops_test"]
    nev = np.array([n_events(s) for s in st]); nfh = np.array([stream_nonfall_h(s) for s in st])
    rec = []
    for cname in scores["oops_test"]:
        D, F = curves_for(st, {cname: scores["oops_test"][cname]})[cname]
        for key in ["staged", "oops_recal"]:
            k = fz["thresholds"][key][cname]["idx"]
            rec.append(dict(cond=cname, threshold_from=key, th=GRID[k], EDR=D.sum(0)[k] / nev.sum(), FA_per_h=F.sum(0)[k] / nfh.sum()))
    pd.DataFrame(rec).to_csv(out / "results_oops_recalibration.csv", index=False)

    mr = pd.DataFrame(main_rows)
    LOG.info("결과 요약:\n%s", mr[["set", "cond", "n_events", "nonfall_h", "EDR", "FA_per_h", "lat_med", "pAUC"]]
             .to_string(index=False, float_format="%.3f"))
    LOG.info("저장: %s", out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["fit", "test"], required=True)
    ap.add_argument("--name", default="main")
    ap.add_argument("--model", default="siglip2")
    ap.add_argument("--windows", type=float, nargs="+", default=[1, 2, 4, 8, 16])
    ap.add_argument("--main-windows", type=float, nargs="+", default=[1, 2, 4, 8])
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--exclude", nargs="+", default=["cmdfall", "up_fall"])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--force-retest", default="", help="재평가 사유 (기록됨)")
    args = ap.parse_args()
    t0 = time.time()
    stage_fit(args) if args.stage == "fit" else stage_test(args)
    LOG.info("소요 %.1f분", (time.time() - t0) / 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
