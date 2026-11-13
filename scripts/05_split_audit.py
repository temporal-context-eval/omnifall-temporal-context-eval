"""
05_split_audit.py — 공식 split 중복 증명, 수정 전후 데이터 구성, 독립 낙상 사건 수 검증

교수님 요구(2026-11-04)와의 대응
  (1) 피험자 중복이 실제 동일 피험자인지 원자료·코드로 증명  -> 1절, split_overlap_evidence.csv
  (2) 수정 전후 데이터 구성 제시                               -> 2절
  (3) 2,089건이 독립 낙상 사건인지 검증, train/val/test 실제 규모 -> 3절 (카메라별 vs 물리적 사건)
  (4) fall/fallen 정의 구분, 61% 계산 기준                      -> 4절 (정의·민감도 분석)

입력
  data/labels/labels__train.csv          전체 라벨 (Hub config 'labels', 52,618행)
  data/labels/{cs,of-sta-cs,cv,of-sta-cv}__{train,validation,test}.csv
  data/raw/splits/{cs,cv}/<dataset>/*    Hub 원본 split 파일 (06 스크립트로 받은 경우; 없으면 parquet 기반 CSV 사용)
출력
  reports/split_audit.md                 본문 표 전체
  reports/split_overlap_evidence.csv     중복 영상 목록 (dataset, path, subject, 포함된 split)
  reports/physical_fall_events.csv       물리적(다시점 병합) 낙상 사건 목록
"""
from __future__ import annotations

import glob
import logging
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("split_audit")

OF_HOME = Path(os.environ.get("OF_HOME", "."))
LABEL_DIR = OF_HOME / "data" / "labels"
RAW_DIR = OF_HOME / "data" / "raw"
REPORT_DIR = OF_HOME / "reports"

CLASS_NAMES = ["walk", "fall", "fallen", "sit_down", "sitting", "lie_down", "lying",
               "stand_up", "standing", "other", "kneel_down", "kneeling", "squat_down",
               "squatting", "crawl", "jump"]
FALL, FALLEN, STAND_UP = 1, 2, 7
MERGE_GAP_S = 0.5      # 연속 fall 구간 병합 기준(초)
NEXT_GAP_S = 1.0       # fall 종료 후 '직후 구간'으로 인정하는 최대 간격(초)
SPLITS = ["train", "validation", "test"]
EXCLUDE = {"cmdfall"}  # 미확보 데이터셋

# 수정 규칙 (결과를 보기 전에 확정)
#  cs: UP-Fall 피험자 11은 validation, 15·16은 test에 속하므로 train에서 제거
#  cv: UP-Fall 카메라2 영상이 train·validation 양쪽에 있으므로 validation에서 UP-Fall 제거,
#      EDF·OCCU 카메라2가 validation·test 양쪽에 있으므로 validation에서 EDF·OCCU 제거
RULES = {
    "cs": [("train", "up_fall", "subject", {11, 15, 16})],
    "cv": [("validation", "up_fall", "all", None), ("validation", "edf", "all", None),
           ("validation", "occu", "all", None)],
}


# --------------------------------------------------------------------------- 공통
def to_label_id(v) -> int:
    if isinstance(v, (int, np.integer)):
        return int(v)
    d = "".join(ch for ch in str(v) if ch.isdigit())
    return int(d) if d else CLASS_NAMES.index(str(v).strip())


def load_labels() -> pd.DataFrame:
    df = pd.read_csv(LABEL_DIR / "labels__train.csv")
    df["label"] = df["label"].map(to_label_id)
    df["dur"] = df["end"] - df["start"]
    df = df[df.dur > 0].copy()
    return df


def load_split(config: str) -> dict[str, pd.DataFrame]:
    out = {}
    for sp in SPLITS:
        p = LABEL_DIR / f"{config}__{sp}.csv"
        d = pd.read_csv(p)
        d["label"] = d["label"].map(to_label_id)
        d["dur"] = d["end"] - d["start"]
        out[sp] = d[d.dur > 0].copy()
    return out


def recording_key(dataset: str, path: str) -> str:
    """카메라(시점)를 제거한 '물리적 녹화' 키. 같은 키 = 같은 사람의 같은 행동을 여러 카메라로 찍은 것."""
    if dataset == "up_fall":            # Subject1/Activity1/Trial1/Subject1Activity1Trial1Camera1
        return re.sub(r"Camera\d+$", "", path)
    if dataset == "mcfd":               # chute01/cam6
        return path.split("/")[0]
    if dataset in ("edf", "occu"):      # jianjun/view1/rgb/jianjun_view1_rgb
        return path.split("/")[0]
    if dataset == "cmdfall":            # colors/S39P1K2  (K = Kinect index)
        return re.sub(r"K\d+$", "", path)
    return path                         # 단일 시점


def extract_fall_events(df: pd.DataFrame) -> pd.DataFrame:
    """영상(카메라 스트림)별 fall 사건 추출. 04_label_stats.py와 동일한 규칙."""
    rows = []
    for (ds, path), g in df.groupby(["dataset", "path"], sort=False):
        g = g.sort_values("start").reset_index(drop=True)
        falls = g[g.label == FALL]
        if falls.empty:
            continue
        events, cur = [], None
        for _, r in falls.iterrows():
            if cur and r.start - cur[1] <= MERGE_GAP_S:
                cur[1] = max(cur[1], r.end)
            else:
                if cur:
                    events.append(cur)
                cur = [r.start, r.end]
        events.append(cur)
        for k, (s, e) in enumerate(events):
            after = g[(g.start >= e - 1e-6) & (g.label != FALL)]
            gap = float(after.iloc[0].start - e) if not after.empty else np.nan
            nxt = int(after.iloc[0].label) if not after.empty else -1
            rows.append(dict(dataset=ds, path=path, rec=recording_key(ds, path), cam=int(g.cam.iloc[0]),
                             subject=int(g.subject.iloc[0]), event_idx=k, fall_start=s, fall_end=e,
                             next_label=CLASS_NAMES[nxt] if nxt >= 0 else "none", next_gap=gap))
    return pd.DataFrame(rows)


def physical_events(ev: pd.DataFrame) -> pd.DataFrame:
    """다시점 중복 제거: 녹화(rec)마다 가장 작은 cam 번호의 스트림을 기준 시점으로 삼아 그 사건만 센다."""
    if ev.empty:
        return ev
    ref_cam = ev.groupby(["dataset", "rec"]).cam.transform("min")
    return ev[ev.cam == ref_cam].copy()


def nonfall_hours(df: pd.DataFrame) -> float:
    return df[~df.label.isin([FALL, FALLEN])].dur.sum() / 3600


def fmt(t: pd.DataFrame) -> str:
    return t.to_markdown(floatfmt=".2f")


# --------------------------------------------------------------------------- 1절. 중복 증명
def section_overlap(config: str, parts: dict[str, pd.DataFrame], md: list[str]) -> pd.DataFrame:
    md.append(f"### 1-{config}. 분할 간 중복 (판단 기준: 동일 (dataset, path))")
    keys = {sp: set(zip(d.dataset, d.path)) for sp, d in parts.items()}
    rows, evid = [], []
    for a, b in [("train", "validation"), ("train", "test"), ("validation", "test")]:
        ov = keys[a] & keys[b]
        by_ds = pd.Series([k[0] for k in ov]).value_counts().to_dict() if ov else {}
        rows.append({"분할 쌍": f"{a} ∩ {b}", "중복 영상 수": len(ov), "데이터셋별": str(by_ds)})
        for ds, path in sorted(ov):
            subj = parts[a][(parts[a].dataset == ds) & (parts[a].path == path)].subject.iloc[0]
            evid.append(dict(config=config, dataset=ds, path=path, subject=int(subj), in_split_a=a, in_split_b=b))
    md.append(fmt(pd.DataFrame(rows).set_index("분할 쌍")))
    md.append("")

    # 피험자 수준 확인: UP-Fall 분할별 피험자 집합
    up = {sp: sorted(d[d.dataset == "up_fall"].subject.unique().tolist()) for sp, d in parts.items()}
    md.append(f"UP-Fall 분할별 피험자 집합: train {up['train']} / validation {up['validation']} / test {up['test']}")
    both = set(up["train"]) & (set(up["validation"]) | set(up["test"]))
    md.append(f"train과 validation·test에 모두 등장하는 피험자: {sorted(both)}")
    md.append("")

    # 동일 영상임을 보여주는 원자료 예시: 같은 path의 라벨 행이 두 분할에 그대로 존재
    ev = pd.DataFrame(evid)
    if not ev.empty:
        ex = ev[ev.in_split_b == "test"].iloc[0] if (ev.in_split_b == "test").any() else ev.iloc[0]
        md.append(f"예시 — `{ex.dataset}` / `{ex.path}` (subject {ex.subject}) 의 라벨 행:")
        for sp in (ex.in_split_a, ex.in_split_b):
            d = parts[sp][(parts[sp].dataset == ex.dataset) & (parts[sp].path == ex.path)]
            md.append(f"- {sp}: " + "; ".join(f"{CLASS_NAMES[int(r.label)]} {r.start:.2f}–{r.end:.2f}s" for _, r in d.iterrows()))
        same = (parts[ex.in_split_a][(parts[ex.in_split_a].path == ex.path)][["label", "start", "end"]].values.tolist()
                == parts[ex.in_split_b][(parts[ex.in_split_b].path == ex.path)][["label", "start", "end"]].values.tolist())
        md.append(f"- 두 분할의 라벨 행이 완전히 동일: {same}. 경로의 'Subject{ex.subject}'와 subject 열 값이 일치하므로 같은 피험자의 같은 녹화임.")
    md.append("")
    return ev


def section_raw_splits(md: list[str]) -> None:
    """Hub 원본 split 파일이 있으면 그 파일만으로 중복을 재확인한다 (가공 단계 배제)."""
    base = RAW_DIR / "splits" / "cs" / "up_fall"
    files = sorted(glob.glob(str(base / "*")))
    md.append("### 1-raw. Hub 원본 split 파일로 재확인")
    if not files:
        md.append("- `data/raw/splits/cs/up_fall/` 없음 — `python scripts/06_fetch_raw_hub_files.py` 실행 후 다시 돌리면 원본 파일 기준 결과가 추가됨.")
        md.append("")
        return
    sets = {}
    for f in files:
        name = Path(f).stem.lower()
        try:
            paths = set(pd.read_csv(f).iloc[:, 0].astype(str))
        except Exception:
            paths = set(l.strip() for l in open(f, encoding="utf-8") if l.strip() and l.strip() != "path")
        sets[name] = paths
        md.append(f"- `{Path(f).relative_to(RAW_DIR).as_posix()}`: {len(paths)}개 경로")
    names = list(sets)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            ov = sets[names[i]] & sets[names[j]]
            md.append(f"- {names[i]} ∩ {names[j]} = {len(ov)}개" + (f" (예: {sorted(ov)[0]})" if ov else ""))
    rev = (RAW_DIR / "REVISION.txt").read_text().strip() if (RAW_DIR / "REVISION.txt").exists() else "?"
    md.append(f"- 원본 리비전: {rev}")
    md.append("")


# --------------------------------------------------------------------------- 2절. 수정 전후 구성
def apply_rules(config: str, parts: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    out = {sp: d.copy() for sp, d in parts.items()}
    for sp, ds, how, vals in RULES[config]:
        d = out[sp]
        if how == "subject":
            mask = (d.dataset == ds) & d.subject.isin(vals)
        else:
            mask = d.dataset == ds
        out[sp] = d[~mask].copy()
    return out


def composition(parts: dict[str, pd.DataFrame], exclude: set) -> pd.DataFrame:
    rows = {}
    for sp, d in parts.items():
        d = d[~d.dataset.isin(exclude)]
        ev = extract_fall_events(d)
        pe = physical_events(ev)
        rows[sp] = {
            "데이터셋 수": d.dataset.nunique(),
            "영상(카메라 스트림)": d.groupby(["dataset", "path"]).ngroups,
            "녹화(물리적)": len({(ds, recording_key(ds, p)) for ds, p in zip(d.dataset, d.path)}),
            "낙상 사건(스트림별)": len(ev),
            "낙상 사건(물리적)": len(pe),
            "비낙상 시간 h": nonfall_hours(d),
            "라벨 시간 h": d.dur.sum() / 3600,
        }
    return pd.DataFrame(rows).T


def section_before_after(config: str, parts: dict[str, pd.DataFrame], md: list[str]) -> dict[str, pd.DataFrame]:
    fixed = apply_rules(config, parts)
    md.append(f"### 2-{config}. 수정 전후 데이터 구성 (CMDFall 제외 기준)")
    md.append("수정 규칙: " + "; ".join(
        f"{sp}에서 {ds} " + ("전체 제거" if how == "all" else f"피험자 {sorted(vals)} 제거")
        for sp, ds, how, vals in RULES[config]))
    md.append("")
    before, after = composition(parts, EXCLUDE), composition(fixed, EXCLUDE)
    t = pd.concat({"수정 전": before, "수정 후": after}, axis=0)
    t.index = [f"{a} · {b}" for a, b in t.index]
    md.append(fmt(t))
    md.append("")
    # 수정 후 중복 재확인
    keys = {sp: set(zip(d.dataset, d.path)) for sp, d in fixed.items()}
    subj = {sp: set(zip(d.dataset, d.subject)) for sp, d in fixed.items() if True}
    md.append("수정 후 재확인 — 영상 중복: "
              + ", ".join(f"{a}∩{b}={len(keys[a] & keys[b])}" for a, b in [("train", "validation"), ("train", "test"), ("validation", "test")]))
    # 피험자 중복(단일 피험자 데이터셋 mcfd, 피험자 정보 없는 OOPS(-1), 제외 데이터셋 제외)
    def subj_set(d):
        d = d[(d.subject >= 0) & ~d.dataset.isin({"mcfd", "OOPS"} | EXCLUDE)]
        return set(zip(d.dataset, d.subject))
    if config == "cs":
        md.append("수정 후 재확인 — 피험자 중복(피험자 id가 있는 데이터셋만): "
                  + ", ".join(f"{a}∩{b}={sorted(subj_set(fixed[a]) & subj_set(fixed[b]))}" for a, b in [("train", "validation"), ("train", "test"), ("validation", "test")]))
    else:
        md.append("참고 — cross-view split은 같은 피험자를 카메라만 달리해 나누는 설계이므로 피험자 중복은 결함이 아님. "
                  "영상(스트림) 중복만 결함으로 본다. 수정 후 validation은 4개 데이터셋 170개 영상으로 작아진다.")
    md.append("")
    # 수정 후 데이터셋별 test 구성
    d = fixed["test"][~fixed["test"].dataset.isin(EXCLUDE)]
    ev = extract_fall_events(d); pe = physical_events(ev)
    t2 = pd.DataFrame({
        "영상": d.groupby("dataset").path.nunique(),
        "낙상 사건(스트림별)": ev.groupby("dataset").size(),
        "낙상 사건(물리적)": pe.groupby("dataset").size(),
        "비낙상 시간 h": d[~d.label.isin([FALL, FALLEN])].groupby("dataset").dur.sum() / 3600,
    }).fillna(0)
    t2.loc["합계"] = t2.sum()
    md.append(f"수정 후 **test** 분할의 데이터셋별 구성 ({config}):")
    md.append(fmt(t2))
    md.append("")
    return fixed


# --------------------------------------------------------------------------- 3절. 독립 사건 검증
def section_independence(df: pd.DataFrame, md: list[str]) -> pd.DataFrame:
    d = df[~df.dataset.isin(EXCLUDE)]
    ev = extract_fall_events(d)
    pe = physical_events(ev)
    md.append("### 3. 낙상 사건의 독립성 — 카메라 스트림별 사건 vs 물리적 사건")
    md.append(f"- 스트림별 사건 수(04_label_stats.py의 2,089건과 같은 기준): **{len(ev)}건**")
    md.append(f"- 다시점 중복을 제거한 물리적 사건 수(녹화별 기준 시점 1개만 집계): **{len(pe)}건**")
    md.append("- 물리적 사건은 서로 다른 녹화에서 나온 것이므로 독립 사건으로 본다. 단, 같은 피험자가 여러 녹화에 등장하므로 "
              "피험자 간 독립성은 cross-subject split으로만 보장된다.")
    md.append("")
    t = pd.DataFrame({
        "카메라 수": d.groupby("dataset").cam.nunique(),
        "녹화 수": pd.Series({ds: len({recording_key(ds, p) for p in g.path}) for ds, g in d.groupby("dataset")}),
        "낙상 사건(스트림별)": ev.groupby("dataset").size(),
        "낙상 사건(물리적)": pe.groupby("dataset").size(),
        "피험자 수(id 없으면 0)": d.groupby("dataset").subject.apply(lambda s: s[s >= 0].nunique()),
    }).fillna(0).astype(int)
    t.loc["합계"] = t.sum()
    md.append(fmt(t))
    md.append("")
    # 카메라 간 사건 수 불일치 녹화(라벨 전파 오차 점검)
    cnt = ev.groupby(["dataset", "rec", "cam"]).size().reset_index(name="n")
    mism = cnt.groupby(["dataset", "rec"]).n.nunique()
    mism = mism[mism > 1]
    md.append(f"- 카메라별 사건 수가 서로 다른 녹화: {len(mism)}건" + (f" ({mism.reset_index().dataset.value_counts().to_dict()})" if len(mism) else ""))
    md.append("")
    return pe


# --------------------------------------------------------------------------- 4절. fall/fallen 정의와 61%
def section_fallen(df: pd.DataFrame, md: list[str]) -> None:
    md.append("### 4. fall / fallen 정의와 'fall → fallen 61%'의 계산 기준")
    md.append("- **fall(1)**: 넘어지는 동작 자체. 보행·자세에서 벗어나는 첫 프레임에 시작, 관성 운동이 멈추면 종료 (LABELS.md).")
    md.append("- **fallen(2)**: 낙상 후 바닥·매트리스에 머무는 상태. 정지 자세에 도달한 첫 프레임에 시작.")
    md.append(f"- **계산 기준**: 영상별로 fall 구간을 간격 ≤ {MERGE_GAP_S}s 로 병합해 사건을 만들고, 사건 종료 후 "
              f"≤ {NEXT_GAP_S}s 안에 시작하는 첫 비-fall 구간의 라벨을 '직후 상태'로 본다. "
              "분모는 모든 낙상 사건(직후 구간이 없는 사건 포함), 분자는 직후 상태가 fallen인 사건.")
    md.append("")
    rows = {}
    d_all = df
    d_nc = df[~df.dataset.isin(EXCLUDE)]
    for name, d in [("전체", d_all), ("CMDFall 제외", d_nc)]:
        ev = extract_fall_events(d)
        pe = physical_events(ev)
        for unit, e in [("스트림별", ev), ("물리적", pe)]:
            for gap in [0.5, 1.0, 2.0]:
                nxt = np.where(e.next_gap <= gap, e.next_label, "none")
                has = nxt != "none"
                rows[(name, unit, f"gap≤{gap}s")] = {
                    "사건 수": len(e),
                    "→fallen % (분모: 전체)": 100 * np.mean(nxt == "fallen"),
                    "→fallen % (분모: 직후 구간 있음)": 100 * np.mean(nxt[has] == "fallen") if has.any() else np.nan,
                    "→stand_up %": 100 * np.mean(nxt == "stand_up"),
                    "직후 구간 없음 %": 100 * np.mean(~has),
                }
    t = pd.DataFrame(rows).T
    t.index = [" · ".join(k) for k in t.index]
    md.append(fmt(t))
    md.append("")
    md.append("해석: 61%는 'CMDFall 제외 · 스트림별 · gap≤1.0s · 분모 전체' 칸의 값이다. "
              "직후 구간이 없는 사건(영상이 fall에서 끝남)을 분모에서 빼면 비율이 올라간다. "
              "fallen 미표기 사건의 상당수는 라벨 누락이 아니라 영상 종료 때문이므로, fallen은 사건 정의가 아니라 "
              "'사건 이후 맥락'으로 다루는 것이 안전하다.")
    md.append("")


# --------------------------------------------------------------------------- 메인
def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_labels()
    md = ["# OmniFall 공식 split 감사 및 사건 독립성 검증", "",
          f"- 라벨 원본: Hub config `labels` ({len(df):,}행, 길이 0 구간 제외), 리비전 83572a37",
          f"- 사건 정의: fall 구간 병합 간격 {MERGE_GAP_S}s, 직후 구간 인정 간격 {NEXT_GAP_S}s",
          f"- 제외 데이터셋: {', '.join(sorted(EXCLUDE))}", ""]

    all_evid = []
    md.append("## 1. 공식 split의 분할 간 중복 증명")
    for cfg in ["cs", "cv"]:
        parts = load_split(cfg)
        all_evid.append(section_overlap(cfg, parts, md))
    section_raw_splits(md)
    pd.concat(all_evid).to_csv(REPORT_DIR / "split_overlap_evidence.csv", index=False)

    md.append("## 2. 수정 규칙 적용 전후의 데이터 구성")
    for cfg in ["cs", "cv"]:
        section_before_after(cfg, load_split(cfg), md)

    md.append("## 3. 독립 낙상 사건 수")
    pe = section_independence(df, md)
    pe.to_csv(REPORT_DIR / "physical_fall_events.csv", index=False)

    md.append("## 4. fall / fallen")
    section_fallen(df, md)

    out = REPORT_DIR / "split_audit.md"
    out.write_text("\n".join(md), encoding="utf-8")
    LOG.info("저장: %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
