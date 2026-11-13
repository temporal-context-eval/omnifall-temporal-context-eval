"""
04_label_stats.py — OmniFall 확인 메모용 라벨 통계 산출

입력 : $OF_HOME/data/labels/labels__*.csv (01_save_labels.py 결과)
       $OF_HOME/data/labels/{of-sta-cs,of-sta-cv,cs}__<split>.csv
출력 : $OF_HOME/reports/omnifall_label_stats.md  (메모에 그대로 인용할 표)
       $OF_HOME/reports/fall_events.csv           (낙상 사건 단위 목록)

교수님 검토 의견과의 대응
  - "fall/fallen/lie_down/lying 라벨 체계 확인"     -> 표 2, 표 3
  - "fallen state 포함 여부는 데이터 확인 후 결정"  -> 표 3 (fall 뒤 fallen 지속시간·동반 비율)
  - "사건 단위 지표 / 시간당 오경보"               -> 표 4 (사건 수, 비낙상 시간 = FA/h 분모)
  - "윈도우 크기 조건별 탐색"                      -> 표 5 (낙상 직전 확보 가능한 맥락 길이)
  - "동일 split"                                   -> 표 6 (split별 사건 수·비낙상 시간)

사건(event) 정의(초안, 메모에서 확정): 같은 영상(path) 안에서 label==fall 세그먼트가
MERGE_GAP_S 이하 간격으로 이어지면 하나의 낙상 사건으로 본다. 사건 시작 = 첫 fall 세그먼트 start.
"""
from __future__ import annotations

import glob
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("label_stats")

OF_HOME = Path(os.environ.get("OF_HOME", "."))
LABEL_DIR = OF_HOME / "data" / "labels"
REPORT_DIR = OF_HOME / "reports"

CLASS_NAMES = ["walk", "fall", "fallen", "sit_down", "sitting", "lie_down", "lying",
               "stand_up", "standing", "other", "kneel_down", "kneeling", "squat_down",
               "squatting", "crawl", "jump"]
FALL, FALLEN, SIT_DOWN, LIE_DOWN, LYING, STAND_UP = 1, 2, 3, 5, 6, 7
TARGETS = {"fall": FALL, "fallen": FALLEN, "lie_down": LIE_DOWN, "lying": LYING}
MERGE_GAP_S = 0.5     # 연속 fall 세그먼트 병합 기준
NEXT_GAP_S = 1.0      # fall 직후 세그먼트로 인정하는 최대 간격
MULTI_VIEW = {"cmdfall", "up_fall", "edf", "occu", "mcfd"}


# ---------------------------------------------------------------- 로딩
def to_label_id(v) -> int:
    """'1fall' 같은 문자열 라벨이나 정수 라벨을 정수 id로 통일한다."""
    if isinstance(v, (int, np.integer)):
        return int(v)
    s = str(v).strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits:
        return int(digits)
    return CLASS_NAMES.index(s)


def load_csvs(pattern: str) -> pd.DataFrame:
    files = sorted(glob.glob(str(LABEL_DIR / pattern)))
    if not files:
        raise FileNotFoundError(f"{LABEL_DIR}/{pattern} 없음 — 01_save_labels.py 먼저 실행")
    frames = []
    for f in files:
        d = pd.read_csv(f)
        d["split"] = Path(f).stem.split("__")[-1]
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df["label"] = df["label"].map(to_label_id)
    df["dur"] = df["end"] - df["start"]
    return df


def sanity_report(df: pd.DataFrame) -> list[str]:
    """음수 시작시간, 길이 0 이하 세그먼트 등 이상치를 기록한다."""
    notes = []
    neg = (df["start"] < 0).sum()
    bad = (df["dur"] <= 0).sum()
    if neg:
        notes.append(f"- start < 0 세그먼트 {neg}건 (데이터셋: "
                     f"{', '.join(sorted(df.loc[df.start < 0, 'dataset'].unique()))}) — 0으로 클리핑 필요 여부 검토")
    if bad:
        notes.append(f"- end <= start 세그먼트 {bad}건 — 분석에서 제외")
    return notes


# ---------------------------------------------------------------- 사건 추출
def extract_fall_events(df: pd.DataFrame) -> pd.DataFrame:
    """영상별로 fall 세그먼트를 사건 단위로 병합하고 전후 맥락을 기록한다."""
    rows = []
    for (ds, path), g in df.groupby(["dataset", "path"], sort=False):
        g = g.sort_values("start").reset_index(drop=True)
        vid_start, vid_end = g["start"].min(), g["end"].max()
        falls = g[g["label"] == FALL]
        if falls.empty:
            continue
        # 연속 fall 세그먼트 병합
        events, cur = [], None
        for _, r in falls.iterrows():
            if cur and r["start"] - cur[1] <= MERGE_GAP_S:
                cur[1] = max(cur[1], r["end"])
            else:
                if cur:
                    events.append(cur)
                cur = [r["start"], r["end"]]
        events.append(cur)

        for k, (s, e) in enumerate(events):
            after = g[(g["start"] >= e - 1e-6) & (g["start"] - e <= NEXT_GAP_S) & (g["label"] != FALL)]
            nxt = int(after.iloc[0]["label"]) if not after.empty else -1
            fallen_dur = float(after.iloc[0]["dur"]) if nxt == FALLEN else 0.0
            before = g[(g["end"] <= s + 1e-6) & (g["label"] != FALL)]
            prev = int(before.iloc[-1]["label"]) if not before.empty else -1
            rows.append(dict(
                dataset=ds, path=path, event_idx=k,
                subject=int(g["subject"].iloc[0]), cam=int(g["cam"].iloc[0]),
                fall_start=s, fall_end=e, fall_dur=e - s,
                pre_context_s=s - vid_start,          # 낙상 이전 확보 가능한 관찰 시간
                post_context_s=vid_end - e,
                prev_label=CLASS_NAMES[prev] if prev >= 0 else "none",
                next_label=CLASS_NAMES[nxt] if nxt >= 0 else "none",
                fallen_dur=fallen_dur,
            ))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 표 생성
def q(s: pd.Series, p: float) -> float:
    return float(np.nanpercentile(s, p)) if len(s) else float("nan")


def table_overview(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("dataset")
    t = pd.DataFrame({
        "views": [("multi" if d in MULTI_VIEW else "single") for d in g.groups],
        "videos": g["path"].nunique(),
        "segments": g.size(),
        "labeled_h": g["dur"].sum() / 3600,
        "subjects": g["subject"].nunique(),
        "cams": g["cam"].nunique(),
    }, index=list(g.groups))
    t.loc["TOTAL"] = ["", t.videos.sum(), t.segments.sum(), t.labeled_h.sum(), "", ""]
    return t


def table_targets(df: pd.DataFrame) -> pd.DataFrame:
    out = {}
    for name, lid in TARGETS.items():
        sub = df[df.label == lid].groupby("dataset")
        out[f"{name}_n"] = sub.size()
        out[f"{name}_h"] = sub["dur"].sum() / 3600
    t = pd.DataFrame(out).fillna(0)
    t.loc["TOTAL"] = t.sum()
    return t


def table_fall_structure(ev: pd.DataFrame) -> pd.DataFrame:
    g = ev.groupby("dataset")
    t = pd.DataFrame({
        "fall_events": g.size(),
        "fall_dur_med_s": g["fall_dur"].median(),
        "fall_dur_p90_s": g["fall_dur"].apply(lambda s: q(s, 90)),
        "→fallen_%": g["next_label"].apply(lambda s: 100 * (s == "fallen").mean()),
        "→stand_up_%": g["next_label"].apply(lambda s: 100 * (s == "stand_up").mean()),
        "→none(영상끝)_%": g["next_label"].apply(lambda s: 100 * (s == "none").mean()),
        "fallen_dur_med_s": g["fallen_dur"].apply(lambda s: s[s > 0].median()),
    })
    allrow = {
        "fall_events": len(ev), "fall_dur_med_s": ev.fall_dur.median(),
        "fall_dur_p90_s": q(ev.fall_dur, 90),
        "→fallen_%": 100 * (ev.next_label == "fallen").mean(),
        "→stand_up_%": 100 * (ev.next_label == "stand_up").mean(),
        "→none(영상끝)_%": 100 * (ev.next_label == "none").mean(),
        "fallen_dur_med_s": ev.fallen_dur[ev.fallen_dur > 0].median(),
    }
    t.loc["TOTAL"] = allrow
    return t


def table_event_denominators(df: pd.DataFrame, ev: pd.DataFrame) -> pd.DataFrame:
    """사건 검출률 분모(낙상 사건 수)와 FA/h 분모(비낙상 시간)."""
    nonfall = df[~df.label.isin([FALL, FALLEN])].groupby("dataset")["dur"].sum() / 3600
    vids = df.groupby("dataset")["path"].nunique()
    fall_vids = ev.groupby("dataset")["path"].nunique()
    t = pd.DataFrame({
        "videos": vids,
        "videos_with_fall": fall_vids,
        "videos_no_fall": vids - fall_vids.reindex(vids.index).fillna(0),
        "fall_events": ev.groupby("dataset").size(),
        "events_per_fall_video": ev.groupby("dataset").size() / fall_vids,
        "nonfall_h(FA/h 분모)": nonfall,
        "lie_down_n(hard neg)": df[df.label == LIE_DOWN].groupby("dataset").size(),
        "sit_down_n(hard neg)": df[df.label == SIT_DOWN].groupby("dataset").size(),
    }).fillna(0)
    t.loc["TOTAL"] = t.sum()
    t.loc["TOTAL", "events_per_fall_video"] = t.loc["TOTAL", "fall_events"] / max(t.loc["TOTAL", "videos_with_fall"], 1)
    return t


def table_pre_context(ev: pd.DataFrame) -> pd.DataFrame:
    """윈도우 길이 W 후보별로, 낙상 전 W초 이상 관찰 가능한 사건 비율(%)."""
    windows = [1, 2, 4, 8, 16]
    g = ev.groupby("dataset")["pre_context_s"]
    t = pd.DataFrame({f"≥{w}s_%": g.apply(lambda s, w=w: 100 * (s >= w).mean()) for w in windows})
    t["pre_ctx_med_s"] = g.median()
    t.loc["TOTAL"] = [100 * (ev.pre_context_s >= w).mean() for w in windows] + [ev.pre_context_s.median()]
    return t


def table_splits(config: str, exclude: set | None = None) -> pd.DataFrame | None:
    try:
        d = load_csvs(f"{config}__*.csv")
    except FileNotFoundError:
        LOG.warning("%s 라벨 없음 — split 표 생략", config)
        return None
    d = d[(d.dur > 0) & ~d.dataset.isin(exclude or set())]
    ev = extract_fall_events(d)
    rows = {}
    for sp, g in d.groupby("split"):
        e = ev[ev.path.isin(g.path) & ev.dataset.isin(g.dataset)] if not ev.empty else ev
        e = e.merge(g[["dataset", "path"]].drop_duplicates(), on=["dataset", "path"])
        rows[sp] = {
            "videos": g.groupby(["dataset", "path"]).ngroups,
            "fall_events": len(e),
            "nonfall_h": g[~g.label.isin([FALL, FALLEN])]["dur"].sum() / 3600,
            "datasets": g["dataset"].nunique(),
        }
    order = [s for s in ["train", "validation", "test"] if s in rows] + [s for s in rows if s not in ("train", "validation", "test")]
    return pd.DataFrame(rows).T.loc[order]


# ---------------------------------------------------------------- 메인
def fmt(t: pd.DataFrame) -> str:
    return t.to_markdown(floatfmt=".2f")


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_csvs("labels__*.csv")
    notes = sanity_report(df)
    df_all = df[df.dur > 0].copy()

    # 두 버전 산출: 전체(공식 벤치마크 기준) / 확보 가능분(CMDFall 제외, 실제 실험 기준)
    for tag, exclude in [("full", set()), ("no_cmdfall", {"cmdfall"})]:
        write_report(df_all[~df_all.dataset.isin(exclude)].copy(), tag, exclude, notes)

    write_comparison(df_all)
    return 0


def write_comparison(df_all: pd.DataFrame) -> None:
    """CMDFall 제외 시 줄어드는 규모를 한 표로 정리 (확인 메모의 '데이터 범위 결정' 근거)."""
    rows = {}
    for tag, d in [("전체", df_all), ("CMDFall 제외", df_all[df_all.dataset != "cmdfall"])]:
        ev = extract_fall_events(d)
        rows[tag] = {
            "datasets": d.dataset.nunique(),
            "videos": d.groupby(["dataset", "path"]).ngroups,
            "labeled_h": d.dur.sum() / 3600,
            "fall_events": len(ev),
            "nonfall_h": d[~d.label.isin([FALL, FALLEN])].dur.sum() / 3600,
            "lie_down_n": int((d.label == LIE_DOWN).sum()),
        }
    t = pd.DataFrame(rows).T
    t.loc["감소율_%"] = 100 * (1 - t.loc["CMDFall 제외"] / t.loc["전체"])
    out = REPORT_DIR / "omnifall_cmdfall_impact.md"
    out.write_text("# CMDFall 제외 영향\n\n" + fmt(t) + "\n", encoding="utf-8")
    LOG.info("저장: %s", out)


def write_report(df: pd.DataFrame, tag: str, exclude: set, notes: list[str]) -> None:
    LOG.info("[%s] 세그먼트 %d건, 데이터셋 %s", tag, len(df), sorted(df.dataset.unique()))
    ev = extract_fall_events(df)
    ev.to_csv(REPORT_DIR / f"fall_events_{tag}.csv", index=False)
    LOG.info("[%s] 낙상 사건 %d건", tag, len(ev))

    md = [f"# OmniFall 라벨 통계 — {tag} (확인 메모 근거자료)", "",
          f"- 제외 데이터셋: {', '.join(sorted(exclude)) or '없음'}",
          f"- 입력: `data/labels/labels__*.csv` (Staged + OOPS, 다시점은 시점별 행 포함)",
          f"- 사건 정의(초안): 동일 영상 내 fall 세그먼트 간격 ≤ {MERGE_GAP_S}s 병합, 사건 시작 = 첫 fall 세그먼트 start",
          f"- 다시점 데이터셋({', '.join(sorted(MULTI_VIEW))})은 한 행동이 시점 수만큼 반복 집계됨", ""]
    if notes:
        md += ["## 데이터 이상치", *notes, ""]
    md += ["## 표 1. 데이터셋 개요", fmt(table_overview(df)), "",
           "## 표 2. 대상 라벨 (fall / fallen / lie_down / lying) 세그먼트 수·시간", fmt(table_targets(df)), "",
           "## 표 3. 낙상 사건 구조 — fall 직후 상태와 fallen 지속시간", fmt(table_fall_structure(ev)), "",
           "## 표 4. 사건 단위 지표의 분모", fmt(table_event_denominators(df, ev)), "",
           "## 표 5. 낙상 직전 확보 가능한 관찰 맥락 (윈도우 탐색 범위 근거)", fmt(table_pre_context(ev)), ""]
    for cfg in ["of-sta-cs", "of-sta-cv", "cs"]:
        t = table_splits(cfg, exclude)
        if t is not None:
            md += [f"## 표 6-{cfg}. split별 사건 수·비낙상 시간", fmt(t), ""]

    out = REPORT_DIR / f"omnifall_label_stats_{tag}.md"
    out.write_text("\n".join(md), encoding="utf-8")
    LOG.info("저장: %s", out)


if __name__ == "__main__":
    sys.exit(main())
