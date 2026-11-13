"""
omnifall_eval.py — 사건 단위 평가 라이브러리 (연구설계 자료 4절·6절의 규칙을 코드로 고정)

이 파일 하나가 논문의 모든 사건 단위 지표를 계산한다. 규칙을 바꾸려면 여기만 바꾸고,
test_omnifall_eval.py 의 단위 테스트가 모두 통과해야 한다.

규칙 요약 (사전 확정)
  사건         : 같은 영상 안의 fall 구간을 간격 MERGE_GAP(0.5s) 이하이면 병합. t0 = 첫 start, t1 = 마지막 end
  녹화(rec)    : 카메라를 제거한 경로 (다시점 데이터셋에서 같은 낙상을 찍은 여러 카메라 = 같은 녹화)
  기준 카메라  : 녹화별로 카메라 번호가 가장 작은 스트림 (사건 수와 비낙상 시간 모두 이 스트림으로 계산)
  허용 구간    : [t0 - PRE_TOL(0.5), t1 + POST_TOL(3.0)], 영상 범위로 자름
  경보 묶음    : 경보 시각 간격 ≤ REFRACTORY(2.0s) 이면 한 묶음. 묶음 시각 = 첫 경보
  검출 성공    : 허용 구간 안에 묶음 시각이 있음. 사건당 1회. 한 묶음은 한 사건에만 배정(가장 가까운 t0)
  오경보       : 어떤 허용 구간에도 없고, fallen 구간도 아니며, 라벨이 있는 구간 안에 있는 묶음
  무시         : fallen 구간, 라벨 없는 구간, 이미 검출된 사건 허용 구간 안의 추가 묶음
  비낙상 시간  : fall·fallen 을 뺀 라벨 구간 길이 합 (기준 카메라 스트림만)
  탐지 지연    : 검출 성공 사건에서 max(0, 첫 묶음 시각 - t0). 미검출은 NaN (중앙값에서 제외, 건수 보고)
  판정 시각    : t_k = k·DECISION_STEP(0.2s). 각 판정은 t_k 이하의 가장 최근 프레임까지 사용
  윈도우       : [t_k - W, t_k]. 영상 시작 이전 부분은 첫 프레임으로 패딩 (패딩 비율 기록)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

# ------------------------------------------------------------------ 상수 (사전 확정값)
FALL, FALLEN = 1, 2
MERGE_GAP = 0.5
PRE_TOL, POST_TOL = 0.5, 3.0
REFRACTORY = 2.0
DECISION_STEP = 0.2
TARGET_FPS = 7.5
CLASS_NAMES = ["walk", "fall", "fallen", "sit_down", "sitting", "lie_down", "lying",
               "stand_up", "standing", "other", "kneel_down", "kneeling", "squat_down",
               "squatting", "crawl", "jump"]
MULTI_VIEW = {"cmdfall", "up_fall", "edf", "occu", "mcfd"}


# ------------------------------------------------------------------ 식별자
def recording_key(dataset: str, path: str) -> str:
    """카메라(시점)를 제거한 녹화 키."""
    if dataset == "up_fall":            # Subject1/Activity1/Trial1/Subject1Activity1Trial1Camera1
        return re.sub(r"Camera\d+$", "", path)
    if dataset == "mcfd":               # chute01/cam6
        return path.split("/")[0]
    if dataset in ("edf", "occu"):      # jianjun/view1/rgb/jianjun_view1_rgb
        return path.split("/")[0]
    if dataset == "cmdfall":            # colors/S39P1K2
        return re.sub(r"K\d+$", "", path)
    return path


def camera_from_path(dataset: str, path: str) -> int | None:
    """경로에서 카메라 번호를 읽는다 (cam 열과 대조용). 단일 시점은 None."""
    pats = {"up_fall": r"Camera(\d+)$", "mcfd": r"cam(\d+)$", "edf": r"view(\d+)/", "occu": r"view(\d+)/", "cmdfall": r"K(\d+)$"}
    if dataset not in pats:
        return None
    m = re.search(pats[dataset], path)
    return int(m.group(1)) if m else None


def subject_from_path(dataset: str, path: str) -> int | None:
    """경로에서 피험자 번호를 읽는다 (subject 열과 대조용)."""
    pats = {"up_fall": r"^Subject(\d+)/", "cmdfall": r"S(\d+)P", "caucafall": r"S(\d+)$", "GMDCSA24": r"Subject_?(\d+)"}
    if dataset not in pats:
        return None
    m = re.search(pats[dataset], path)
    return int(m.group(1)) if m else None


# ------------------------------------------------------------------ 사건 추출
def merge_fall_segments(segs: Sequence[tuple[float, float]], gap: float = MERGE_GAP) -> tuple[list[tuple[float, float]], int]:
    """정렬된 fall 구간을 간격 ≤ gap 이면 병합. (사건 목록, 병합으로 사라진 구간 수) 반환."""
    events: list[list[float]] = []
    merged = 0
    for s, e in sorted(segs):
        if events and s - events[-1][1] <= gap:
            events[-1][1] = max(events[-1][1], e)
            merged += 1
        else:
            events.append([s, e])
    return [(a, b) for a, b in events], merged


def prepare_labels(df: pd.DataFrame) -> pd.DataFrame:
    """라벨 표 정규화: 완전 중복 행 제거, 정수 라벨, 길이>0, 음수 시작은 0으로 자름, rec 열 추가.

    주의: Hub 의 OOPS split 파일(splits/cs/OOPS/{train,val,test}.csv)에 같은 경로가 2~3번 적혀 있어
    (test.csv 716행 중 고유 경로 572개), 패키지가 라벨과 split 을 결합하면 해당 영상의 라벨 행이 그만큼 복제된다
    (of-itw test 3,673행 중 869행이 복제본; 라벨 원본 labels/OOPS.csv 4,022행 자체는 중복 없음).
    길이를 합산하는 모든 계산(비낙상 시간, 라벨별 시간)이 그 배수로 세이므로 여기서 먼저 제거한다. 제거된 행 수는 d.attrs["dropped_duplicates"] 에 남긴다."""
    d = df.copy()
    if d["label"].dtype == object or str(d["label"].dtype).startswith("string"):
        d["label"] = d["label"].map(lambda v: int("".join(ch for ch in str(v) if ch.isdigit())))
    n0 = len(d)
    d = d.drop_duplicates(subset=["dataset", "path", "label", "start", "end"])
    d.attrs["dropped_duplicates"] = n0 - len(d)
    d["start"] = d["start"].clip(lower=0.0)
    d = d[d["end"] > d["start"]].copy()
    d["dur"] = d["end"] - d["start"]
    d["rec"] = [recording_key(a, b) for a, b in zip(d["dataset"], d["path"])]
    return d


def extract_events(df: pd.DataFrame, gap: float = MERGE_GAP) -> pd.DataFrame:
    """영상(카메라 스트림)별 낙상 사건. 열: dataset, path, rec, cam, subject, t0, t1, vid_start, vid_end, next_label, next_gap, merged_in."""
    rows = []
    for (ds, path), g in df.groupby(["dataset", "path"], sort=False):
        g = g.sort_values("start")
        falls = g[g.label == FALL]
        if falls.empty:
            continue
        events, merged = merge_fall_segments(list(zip(falls.start, falls.end)), gap)
        vid_start, vid_end = float(g.start.min()), float(g.end.max())
        for k, (t0, t1) in enumerate(events):
            after = g[(g.start >= t1 - 1e-6) & (g.label != FALL)]
            rows.append(dict(dataset=ds, path=path, rec=recording_key(ds, path), cam=int(g.cam.iloc[0]),
                             subject=int(g.subject.iloc[0]), event_idx=k, t0=t0, t1=t1,
                             vid_start=vid_start, vid_end=vid_end,
                             next_label=int(after.iloc[0].label) if not after.empty else -1,
                             next_gap=float(after.iloc[0].start - t1) if not after.empty else np.nan,
                             merged_in=merged if k == 0 else 0))
    cols = ["dataset", "path", "rec", "cam", "subject", "event_idx", "t0", "t1", "vid_start", "vid_end", "next_label", "next_gap", "merged_in"]
    return pd.DataFrame(rows, columns=cols)


# ------------------------------------------------------------------ 기준 카메라
def reference_cameras(df: pd.DataFrame, rule: str = "min") -> dict[tuple[str, str], int]:
    """녹화별 기준 카메라. rule: 'min'(기본) 또는 'max'."""
    agg = df.groupby(["dataset", "rec"]).cam.agg(rule)
    return {k: int(v) for k, v in agg.items()}


def reference_streams(df: pd.DataFrame, rule: str = "min") -> pd.DataFrame:
    """기준 카메라 스트림의 라벨 행만 남긴다 (단일 시점은 그대로)."""
    ref = reference_cameras(df, rule)
    keep = [ref[(d, r)] == c for d, r, c in zip(df.dataset, df.rec, df.cam)]
    return df[keep].copy()


# ------------------------------------------------------------------ 시간 분모
def nonfall_hours(df: pd.DataFrame) -> float:
    """fall·fallen 을 뺀 라벨 구간 길이 합 (시간). 같은 스트림 안 겹침은 합집합으로 계산."""
    total = 0.0
    for _, g in df[~df.label.isin([FALL, FALLEN])].groupby(["dataset", "path"]):
        total += _union_length(list(zip(g.start, g.end)))
    return total / 3600.0


def per_label_hours(df: pd.DataFrame) -> pd.Series:
    return (df.groupby("label").dur.sum() / 3600.0).rename(lambda i: CLASS_NAMES[i])


def _union_length(iv: Iterable[tuple[float, float]]) -> float:
    tot, cur_s, cur_e = 0.0, None, None
    for s, e in sorted(iv):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                tot += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        tot += cur_e - cur_s
    return tot


# ------------------------------------------------------------------ 경보 처리
def cluster_alarms(alarm_times: Sequence[float], refractory: float = REFRACTORY) -> list[tuple[float, float, int]]:
    """경보 시각을 간격 ≤ refractory 로 묶는다. (첫 시각, 마지막 시각, 개수) 목록."""
    out: list[list] = []
    for t in sorted(alarm_times):
        if out and t - out[-1][1] <= refractory:
            out[-1][1] = t
            out[-1][2] += 1
        else:
            out.append([t, t, 1])
    return [(a, b, n) for a, b, n in out]


@dataclass
class StreamLabels:
    """한 스트림(영상)의 라벨: 구간 목록과 영상 범위."""
    segments: list[tuple[int, float, float]]           # (label, start, end)
    vid_start: float = 0.0
    vid_end: float = field(default=None)

    def __post_init__(self):
        if self.vid_end is None:
            self.vid_end = max((e for _, _, e in self.segments), default=0.0)

    def label_at(self, t: float) -> int | None:
        """시각 t 의 라벨 (없으면 None). 경계는 [start, end)."""
        for lab, s, e in self.segments:
            if s <= t < e:
                return lab
        return None

    def fall_events(self, gap: float = MERGE_GAP) -> list[tuple[float, float]]:
        return merge_fall_segments([(s, e) for lab, s, e in self.segments if lab == FALL], gap)[0]


@dataclass
class MatchResult:
    events: pd.DataFrame      # t0, t1, win_lo, win_hi, detected, first_alarm, latency
    clusters: pd.DataFrame    # t_first, t_last, n, status(TP/TP_DUP/FA/IGN_FALLEN/IGN_UNLABELED), event_idx, label_at


def match_alarms(labels: StreamLabels, alarm_times: Sequence[float], *,
                 pre_tol: float = PRE_TOL, post_tol: float = POST_TOL,
                 refractory: float = REFRACTORY, gap: float = MERGE_GAP) -> MatchResult:
    """경보–사건 매칭. 규칙은 파일 머리말 참고."""
    events = labels.fall_events(gap)
    windows = [(max(labels.vid_start, t0 - pre_tol), min(labels.vid_end, t1 + post_tol)) for t0, t1 in events]
    clusters = cluster_alarms(alarm_times, refractory)

    ev_rows = [dict(event_idx=i, t0=t0, t1=t1, win_lo=lo, win_hi=hi, detected=False, first_alarm=np.nan, latency=np.nan)
               for i, ((t0, t1), (lo, hi)) in enumerate(zip(events, windows))]
    cl_rows = []
    for (tf, tl, n) in clusters:
        # 허용 구간 안에 있으면: 가장 가까운 t0 의 사건에 배정 (한 묶음은 한 사건에만)
        cands = [i for i, (lo, hi) in enumerate(windows) if lo <= tf <= hi]
        if cands:
            i = min(cands, key=lambda j: abs(events[j][0] - tf))
            if not ev_rows[i]["detected"]:
                ev_rows[i].update(detected=True, first_alarm=tf, latency=max(0.0, tf - events[i][0]))
                status = "TP"
            else:
                status = "TP_DUP"
            cl_rows.append(dict(t_first=tf, t_last=tl, n=n, status=status, event_idx=i, label_at=labels.label_at(tf)))
            continue
        lab = labels.label_at(tf)
        if lab is None:
            status = "IGN_UNLABELED"
        elif lab == FALLEN:
            status = "IGN_FALLEN"
        elif lab == FALL:
            # 허용 구간 밖인데 fall 라벨 — 병합 gap 보다 먼 fall 조각 등. 사건으로 다뤄지지 않은 fall 은 무시
            status = "IGN_FALL_OUTSIDE"
        else:
            status = "FA"
        cl_rows.append(dict(t_first=tf, t_last=tl, n=n, status=status, event_idx=-1, label_at=lab))
    ev = pd.DataFrame(ev_rows, columns=["event_idx", "t0", "t1", "win_lo", "win_hi", "detected", "first_alarm", "latency"])
    cl = pd.DataFrame(cl_rows, columns=["t_first", "t_last", "n", "status", "event_idx", "label_at"])
    return MatchResult(ev, cl)


# ------------------------------------------------------------------ 지표
def summarize(results: Iterable[MatchResult], nonfall_h: float) -> dict:
    """여러 스트림의 매칭 결과를 합쳐 지표를 낸다."""
    ev = pd.concat([r.events for r in results], ignore_index=True) if results else pd.DataFrame()
    cl = pd.concat([r.clusters for r in results], ignore_index=True) if results else pd.DataFrame()
    n_ev = len(ev)
    n_det = int(ev.detected.sum()) if n_ev else 0
    n_fa = int((cl.status == "FA").sum()) if len(cl) else 0
    lat = ev.loc[ev.detected, "latency"] if n_ev else pd.Series(dtype=float)
    return dict(
        n_events=n_ev, n_detected=n_det,
        EDR=n_det / n_ev if n_ev else np.nan,
        miss_rate=1 - n_det / n_ev if n_ev else np.nan,
        n_FA=n_fa, nonfall_h=nonfall_h,
        FA_per_h=n_fa / nonfall_h if nonfall_h > 0 else np.nan,
        latency_median=float(lat.median()) if len(lat) else np.nan,
        latency_p90=float(lat.quantile(0.9)) if len(lat) else np.nan,
        n_ign_fallen=int((cl.status == "IGN_FALLEN").sum()) if len(cl) else 0,
        n_ign_unlabeled=int((cl.status == "IGN_UNLABELED").sum()) if len(cl) else 0,
    )


def fa_rate_by_label(clusters: pd.DataFrame, label_hours: pd.Series) -> pd.DataFrame:
    """라벨별 오경보율(건/h). label_hours 는 per_label_hours() 결과."""
    fa = clusters[clusters.status == "FA"].groupby("label_at").size()
    rows = []
    for lab_id, h in label_hours.items():
        lid = CLASS_NAMES.index(lab_id) if isinstance(lab_id, str) else lab_id
        n = int(fa.get(lid, 0))
        rows.append(dict(label=CLASS_NAMES[lid], hours=h, n_FA=n, FA_per_h=n / h if h > 0 else np.nan))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ 시간 정렬 / 윈도우
def decision_times(vid_start: float, vid_end: float, step: float = DECISION_STEP) -> np.ndarray:
    """판정 시각 t_k = vid_start + k·step, vid_end 이하."""
    n = int(np.floor((vid_end - vid_start) / step + 1e-9)) + 1
    return vid_start + step * np.arange(n)


def frames_for_window(frame_ts: np.ndarray, t: float, W: float, fps: float = TARGET_FPS) -> tuple[np.ndarray, int]:
    """판정 시각 t 에서 윈도우 [t-W, t] 에 해당하는 프레임 인덱스와 패딩 개수.
    프레임은 t 이하의 것만 사용(미래 정보 없음). 윈도우가 영상 시작 이전이면 첫 프레임을 반복(패딩)."""
    need = int(round(W * fps))
    idx = np.where(frame_ts <= t + 1e-9)[0]
    if len(idx) == 0:
        return np.zeros(need, dtype=int), need
    last = idx[-1]
    lo = last - need + 1
    if lo >= 0:
        return np.arange(lo, last + 1), 0
    pad = -lo
    return np.concatenate([np.zeros(pad, dtype=int), np.arange(0, last + 1)]), pad
