"""
11_verify_design.py — 연구설계 수치 재계산·검증 (교수님 지시서 과제 1·2·3·5의 라벨 기반 항목)

omnifall_eval.py 의 규칙(사전 확정)만 사용해 설계 문서의 모든 수치를 다시 계산하고,
표와 CSV 로 남긴다. 영상이 필요한 항목(원본 영상 해시, 데이터셋 간 동일 영상)은 '보류'로 표시한다.

입력: data/labels/{labels,of-sta-cs,of-itw,cs}__*.csv
출력: reports/design_verification/design_verification.md
      reports/design_verification/dv_events_stream.csv, dv_events_physical.csv, dv_split_composition.csv,
      dv_nonfall_hours.csv, dv_window_validity.csv, dv_id_consistency.csv, dv_fallen_ratio.csv
실행: python scripts/11_verify_design.py
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import omnifall_eval as E  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("verify")
OF_HOME = Path(os.environ.get("OF_HOME", "."))
LAB = OF_HOME / "data" / "labels"
REP = OF_HOME / "reports" / "design_verification"
EXCLUDE = {"cmdfall"}
SPLITS = ["train", "validation", "test"]
WINDOWS = [1, 2, 4, 8, 16]
UPFALL_REMOVE_FROM_TRAIN = {11, 15, 16}


def load(name: str) -> pd.DataFrame:
    return E.prepare_labels(pd.read_csv(LAB / f"{name}.csv"))


def fmt(t: pd.DataFrame) -> str:
    return t.to_markdown(floatfmt=".2f")


# ------------------------------------------------------------------ 0. 라벨 품질
def label_quality() -> pd.DataFrame:
    """config·split 별 완전 중복 행 수, 중복이 있는 영상 수, 같은 영상 안 구간 겹침(0.1s 미만/이상)."""
    rows = []
    for cfg, sp in [("of-itw", "train"), ("of-itw", "validation"), ("of-itw", "test"),
                    ("of-sta-cs", "train"), ("of-sta-cs", "validation"), ("of-sta-cs", "test")]:
        raw = pd.read_csv(LAB / f"{cfg}__{sp}.csv")
        raw = raw[~raw.dataset.isin(EXCLUDE)]
        key = ["dataset", "path", "label", "start", "end"]
        dup = raw.duplicated(subset=key)
        d = E.prepare_labels(raw)
        tiny = real = 0.0; realn = 0
        for _, g in d.groupby(["dataset", "path"]):
            s = g.start.values; e = g.end.values
            o = np.minimum(e[:, None], e[None, :]) - np.maximum(s[:, None], s[None, :])
            o = np.triu(o, 1)
            tiny += o[(o > 1e-6) & (o < 0.1)].sum(); real += o[o >= 0.1].sum(); realn += int((o >= 0.1).sum())
        rows.append({"config": cfg, "split": sp, "행 수": len(raw), "완전 중복 행": int(dup.sum()),
                     "중복 있는 영상": raw[dup].groupby(["dataset", "path"]).ngroups,
                     "겹침<0.1s 합(s)": tiny, "겹침≥0.1s 쌍": realn, "겹침≥0.1s 합(h)": real / 3600,
                     "비낙상 h(단순 합)": d[~d.label.isin([E.FALL, E.FALLEN])].dur.sum() / 3600,
                     "비낙상 h(합집합)": E.nonfall_hours(d)})
    return pd.DataFrame(rows).set_index(["config", "split"])


# ------------------------------------------------------------------ 1. ID 일관성 (경로 vs 열)
def id_consistency(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ds, g in df.groupby("dataset"):
        cam_p = g.path.map(lambda p: E.camera_from_path(ds, p))
        sub_p = g.path.map(lambda p: E.subject_from_path(ds, p))
        rows.append(dict(
            dataset=ds, rows=len(g),
            cam_in_path=int(cam_p.notna().sum()),
            cam_mismatch=int(((cam_p.notna()) & (cam_p != g.cam)).sum()),
            subject_in_path=int(sub_p.notna().sum()),
            subject_mismatch=int(((sub_p.notna()) & (sub_p != g.subject)).sum()),
            recordings=g.rec.nunique(), streams=g.path.nunique(),
            cams_per_recording=round(g.path.nunique() / g.rec.nunique(), 2),
        ))
    return pd.DataFrame(rows).set_index("dataset")


# ------------------------------------------------------------------ 2. 사건 수
def event_tables(df: pd.DataFrame):
    ev_s = E.extract_events(df)                       # 스트림별
    ev_p = E.extract_events(E.reference_streams(df))  # 기준 카메라(물리적)
    t = pd.DataFrame({
        "스트림(영상) 수": df.groupby("dataset").path.nunique(),
        "녹화 수": df.groupby("dataset").rec.nunique(),
        "fall 구간 수": df[df.label == E.FALL].groupby("dataset").size(),
        "사건(스트림별)": ev_s.groupby("dataset").size(),
        "병합된 구간 수(스트림별)": ev_s.groupby("dataset").merged_in.sum(),
        "사건(물리적, 기준 카메라)": ev_p.groupby("dataset").size(),
        "피험자 수(id≥0)": df.groupby("dataset").subject.apply(lambda s: s[s >= 0].nunique()),
    }).fillna(0).astype(int)
    t.loc["합계"] = t.sum()
    return ev_s, ev_p, t


def merge_sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for gap in [0.0, 0.5, 1.0, 2.0]:
        rows[f"gap≤{gap}s"] = {"사건(스트림별)": len(E.extract_events(df, gap)),
                              "사건(물리적)": len(E.extract_events(E.reference_streams(df), gap))}
    return pd.DataFrame(rows).T


def fallen_ratio(ev: pd.DataFrame, name: str) -> dict:
    nxt_fallen = (ev.next_label == E.FALLEN) & (ev.next_gap <= 1.0)
    has_next = ev.next_label >= 0
    return {"집계": name, "분모(전체 사건)": len(ev), "분자(직후 fallen)": int(nxt_fallen.sum()),
            "비율_%": 100 * nxt_fallen.mean(), "직후 구간 있는 사건": int(has_next.sum()),
            "비율_%(분모=직후 구간 있음)": 100 * nxt_fallen.sum() / max(has_next.sum(), 1)}


# ------------------------------------------------------------------ 3. split 구성
def composition(parts: dict[str, pd.DataFrame], exclude: set) -> pd.DataFrame:
    rows = {}
    for sp, d in parts.items():
        d = d[~d.dataset.isin(exclude)]
        ref = E.reference_streams(d)
        rows[sp] = {
            "데이터셋": d.dataset.nunique(),
            "스트림": d.groupby(["dataset", "path"]).ngroups,
            "녹화": d.groupby(["dataset", "rec"]).ngroups,
            "피험자(id≥0)": d[d.subject >= 0].groupby(["dataset", "subject"]).ngroups,
            "사건(스트림별)": len(E.extract_events(d)),
            "사건(물리적)": len(E.extract_events(ref)),
            "비낙상 h(전 스트림 합산)": E.nonfall_hours(d),
            "비낙상 h(기준 카메라)": E.nonfall_hours(ref),
        }
    return pd.DataFrame(rows).T


def apply_cs_rule(parts: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    out = {k: v.copy() for k, v in parts.items()}
    d = out["train"]
    out["train"] = d[~((d.dataset == "up_fall") & d.subject.isin(UPFALL_REMOVE_FROM_TRAIN))].copy()
    return out


def overlaps(parts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for a, b in [("train", "validation"), ("train", "test"), ("validation", "test")]:
        A, B = parts[a], parts[b]
        kp = set(zip(A.dataset, A.path)) & set(zip(B.dataset, B.path))
        kr = set(zip(A.dataset, A.rec)) & set(zip(B.dataset, B.rec))
        sa = A[(A.subject >= 0) & ~A.dataset.isin({"mcfd", "OOPS"})]; sb = B[(B.subject >= 0) & ~B.dataset.isin({"mcfd", "OOPS"})]
        ks = set(zip(sa.dataset, sa.subject)) & set(zip(sb.dataset, sb.subject))
        rows.append({"분할 쌍": f"{a} ∩ {b}", "스트림 중복": len(kp), "녹화 중복": len(kr),
                     "피험자 중복": len(ks), "피험자 목록": str(sorted(ks)) if ks else ""})
    return pd.DataFrame(rows).set_index("분할 쌍")


# ------------------------------------------------------------------ 4. 윈도우 유효성
def window_validity(ev_p: pd.DataFrame) -> pd.DataFrame:
    """물리적 사건 기준: 사건 시작 전 실제 관찰 가능 시간(t0 - vid_start)이 W 이상인 비율과 패딩 비율."""
    pre = ev_p.t0 - ev_p.vid_start
    rows = []
    for ds, g in ev_p.groupby("dataset"):
        p = g.t0 - g.vid_start
        r = {"dataset": ds, "사건 수": len(g), "앞 맥락 중앙값(s)": p.median()}
        for W in WINDOWS:
            r[f"W={W}s 완전 관찰 %"] = 100 * (p >= W).mean()
            r[f"W={W}s 평균 패딩 비율 %"] = 100 * (np.clip(W - p, 0, W) / W).mean()
        rows.append(r)
    tot = {"dataset": "합계", "사건 수": len(ev_p), "앞 맥락 중앙값(s)": pre.median()}
    for W in WINDOWS:
        tot[f"W={W}s 완전 관찰 %"] = 100 * (pre >= W).mean()
        tot[f"W={W}s 평균 패딩 비율 %"] = 100 * (np.clip(W - pre, 0, W) / W).mean()
    rows.append(tot)
    return pd.DataFrame(rows).set_index("dataset")


# ------------------------------------------------------------------ 메인
def main() -> int:
    REP.mkdir(parents=True, exist_ok=True)
    md = ["# 연구설계 수치 재계산·검증 보고서", "",
          "- 규칙: `scripts/omnifall_eval.py` 머리말의 사전 확정값 (병합 0.5s, 허용 −0.5/+3.0s, 불응 2.0s, 기준 카메라 = 최소 번호)",
          "- 라벨 원본: Hub config `labels` (리비전 83572a37). 음수 시작은 0으로 자르고 길이 0 구간은 제외",
          f"- 제외 데이터셋: {', '.join(sorted(EXCLUDE))}. 영상 파일이 필요한 항목(SHA-256, 데이터셋 간 동일 영상)은 보류로 표시", ""]

    df_all = load("labels__train")
    df = df_all[~df_all.dataset.isin(EXCLUDE)].copy()

    # 0. 라벨 품질: 완전 중복 행, 같은 영상 안 라벨 구간 겹침
    lq = label_quality()
    lq.to_csv(REP / "dv_label_quality.csv")
    md += ["## 0. 라벨 파일 품질: 완전 중복 행과 구간 겹침", fmt(lq), "",
           "- **OOPS(of-itw) 라벨에는 완전히 같은 행이 2~3번 들어간 영상이 있습니다** (test 572개 중 117개, 869행). "
           "원인은 Hub 의 split 파일입니다: `splits/cs/OOPS/test.csv` 는 716행이지만 고유 경로는 572개(train 205/165, val 92/81)이고, 라벨 원본 `labels/OOPS.csv`(4,022행)에는 중복이 없습니다. "
           "패키지가 라벨과 split 을 결합할 때 중복 경로만큼 라벨 행이 복제되며, 길이를 합산하는 계산은 이 행을 그 배수로 셉니다. 설계 자료의 OOPS test 비낙상 1.77h 는 이 중복을 포함한 값이었고, 중복 제거 후 합집합은 아래 4절의 값입니다. "
           "`omnifall_eval.prepare_labels()` 가 첫 단계에서 완전 중복 행을 제거하며(단위 테스트 `test_exact_duplicate_rows_dropped_once`), 사건 수는 병합 규칙 때문에 중복의 영향을 받지 않습니다.",
           "- Staged 라벨의 겹침은 대부분 경계의 수 ms 차이(라벨 반올림)이고, 0.1s 이상 겹침은 동작 전이 구간(fallen↔stand_up, stand_up↔walk 등)에 집중됩니다. 비낙상 시간은 합집합으로 계산해 이중 계산을 피하고, 라벨별 시간(RQ3 분모)은 라벨 길이 합이므로 겹친 구간이 두 라벨 모두에 들어갑니다(각주로 명시).", ""]

    # 1. ID 일관성
    idc = id_consistency(df)
    idc.to_csv(REP / "dv_id_consistency.csv")
    md += ["## 1. 경로와 열(subject·cam)의 일관성, 녹화·카메라 구조", fmt(idc), "",
           "경로에서 읽은 카메라 번호·피험자 번호가 cam·subject 열과 어긋난 행 수가 mismatch 열입니다. 0이면 경로 기준 녹화 키가 열 기준과 일치합니다.", ""]

    # 2. 사건 수
    ev_s, ev_p, t_ev = event_tables(df)
    ev_s.to_csv(REP / "dv_events_stream.csv", index=False)
    ev_p.to_csv(REP / "dv_events_physical.csv", index=False)
    md += ["## 2. 낙상 사건 수 재계산 (CMDFall 제외)", fmt(t_ev), "",
           f"- 스트림별 사건 {len(ev_s)}건 = 설계 문서의 2,089건, 물리적 사건 {len(ev_p)}건 = 1,530건이어야 합니다.",
           "- 물리적 사건은 녹화별 기준 카메라(최소 번호) 스트림의 사건만 센 것입니다. 같은 피험자의 반복 녹화는 서로 다른 녹화이므로 별개 사건으로 세며, 통계적 독립은 가정하지 않습니다.", "",
           "### 2.1 병합 간격 민감도", fmt(merge_sensitivity(df)), "",
           "### 2.2 fall → fallen 비율의 분자·분모 (직후 구간 인정 간격 1.0s)"]
    fr = pd.DataFrame([fallen_ratio(ev_s, "스트림별 (CMDFall 제외)"), fallen_ratio(ev_p, "물리적 (CMDFall 제외)"),
                       fallen_ratio(E.extract_events(df_all), "스트림별 (전체)")]).set_index("집계")
    fr.to_csv(REP / "dv_fallen_ratio.csv")
    md += [fmt(fr), ""]

    # 3. split 구성 (of-sta-cs 주 실험, cs 참고, of-itw)
    md += ["## 3. 분할 구성: 중복 검증과 수정 전후 (영상·녹화·피험자·사건·비낙상 시간)"]
    comp_rows = []
    for cfg in ["of-sta-cs", "cs"]:
        parts = {sp: load(f"{cfg}__{sp}") for sp in SPLITS}
        fixed = apply_cs_rule(parts)
        md += [f"### 3.{cfg}: 수정 전 중복", fmt(overlaps({k: v[~v.dataset.isin(EXCLUDE)] for k, v in parts.items()})), "",
               f"### 3.{cfg}: 수정 후 중복 (train에서 UP-Fall 피험자 {sorted(UPFALL_REMOVE_FROM_TRAIN)} 제거)",
               fmt(overlaps({k: v[~v.dataset.isin(EXCLUDE)] for k, v in fixed.items()})), ""]
        before, after = composition(parts, EXCLUDE), composition(fixed, EXCLUDE)
        t = pd.concat({"수정 전": before, "수정 후": after}, axis=0)
        t.index = [f"{a} · {b}" for a, b in t.index]
        md += [f"### 3.{cfg}: 수정 전후 구성", fmt(t), ""]
        tt = t.copy(); tt.insert(0, "config", cfg); comp_rows.append(tt)
    pd.concat(comp_rows).to_csv(REP / "dv_split_composition.csv")

    itw = {sp: load(f"of-itw__{sp}") for sp in SPLITS}
    md += ["### 3.OOPS (of-itw): train/validation/test 중복", fmt(overlaps(itw)), "",
           "OOPS 는 피험자 id 가 없어(−1) 영상 단위로만 중복을 확인할 수 있습니다. 본 연구는 OOPS train 을 쓰지 않고, validation 은 임계값 보정 보조 분석에만, test 는 최종 평가에만 씁니다.", ""]
    itw_comp = composition(itw, set()); itw_comp.to_csv(REP / "dv_split_composition_oops.csv")
    md += ["OOPS 분할별 구성:", fmt(itw_comp), ""]

    # 4. 비낙상 시간 (기준 카메라 vs 전 스트림) — 평가 대상 시간표
    md += ["## 4. 시간당 오경보의 분모: 평가 대상 시간표", "",
           "사건 검출률의 분모(기준 카메라의 물리적 사건)와 일치시키기 위해, 비낙상 시간도 **기준 카메라 스트림만** 합산합니다. 설계 문서의 Staged test 2.27h 는 전 스트림(다중 카메라) 합산값, OOPS test 1.77h 는 중복 행을 포함한 단순 합이었으므로 아래 '기준 카메라' 열(중복 제거·합집합)로 교체합니다. 다중 카메라 시간은 합산하지 않습니다. 라벨 없는 구간과 fallen 구간은 분모에서 제외됩니다(라벨 구간만 합산하므로 자동 제외)."]
    sta = {sp: load(f"of-sta-cs__{sp}") for sp in SPLITS}
    sta_fixed = apply_cs_rule(sta)
    rows = []
    for name, d in [("Staged validation", sta_fixed["validation"]), ("Staged test", sta_fixed["test"]),
                    ("OOPS validation", itw["validation"]), ("OOPS test", itw["test"])]:
        d = d[~d.dataset.isin(EXCLUDE)]
        ref = E.reference_streams(d)
        for ds, g in ref.groupby("dataset"):
            rows.append({"평가셋": name, "dataset": ds, "기준 카메라 스트림 수": g.path.nunique(),
                         "물리적 사건": len(E.extract_events(g)),
                         "비낙상 h(기준 카메라)": E.nonfall_hours(g),
                         "비낙상 h(전 스트림 합산)": E.nonfall_hours(d[d.dataset == ds]),
                         "fallen h(기준 카메라, 분모 제외)": g[g.label == E.FALLEN].dur.sum() / 3600,
                         "라벨 구간 h(기준 카메라)": g.dur.sum() / 3600})
        rows.append({"평가셋": name, "dataset": "합계", "기준 카메라 스트림 수": ref.path.nunique(),
                     "물리적 사건": len(E.extract_events(ref)),
                     "비낙상 h(기준 카메라)": E.nonfall_hours(ref), "비낙상 h(전 스트림 합산)": E.nonfall_hours(d),
                     "fallen h(기준 카메라, 분모 제외)": ref[ref.label == E.FALLEN].dur.sum() / 3600,
                     "라벨 구간 h(기준 카메라)": ref.dur.sum() / 3600})
    nf = pd.DataFrame(rows).set_index(["평가셋", "dataset"])
    nf.to_csv(REP / "dv_nonfall_hours.csv")
    md += [fmt(nf), ""]
    # 라벨별 시간 (기준 카메라, Staged test / OOPS test) — RQ3 분모
    lab_rows = {}
    for name, d in [("Staged test", sta_fixed["test"]), ("OOPS test", itw["test"])]:
        ref = E.reference_streams(d[~d.dataset.isin(EXCLUDE)])
        lab_rows[name] = E.per_label_hours(ref)
    lt = pd.DataFrame(lab_rows).fillna(0)
    md += ["라벨별 시간 h (기준 카메라) — 라벨별 오경보율(RQ3)의 분모:", fmt(lt), ""]

    # 5. 윈도우 유효성 (물리적 사건, 분할별)
    md += ["## 5. 시간 맥락 길이 W 의 유효성: 완전 관찰 가능 사건 비율과 패딩 비율", "",
           "사건 시작 전 실제 영상 길이(t0 − 영상 시작)가 W 이상이면 '완전 관찰'. 부족분은 첫 프레임 패딩이며, 패딩 비율 = max(0, W − 앞 맥락)/W 의 사건 평균입니다. 물리적 사건(기준 카메라) 기준."]
    for name, d in [("Staged train(수정 후)", sta_fixed["train"]), ("Staged validation", sta_fixed["validation"]),
                    ("Staged test", sta_fixed["test"]), ("OOPS test", itw["test"])]:
        evp = E.extract_events(E.reference_streams(d[~d.dataset.isin(EXCLUDE)]))
        wv = window_validity(evp)
        wv.to_csv(REP / f"dv_window_validity_{name.split('(')[0].replace(' ', '_')}.csv")
        md += [f"### 5.{name}", fmt(wv), ""]
    md += ["### 5.시간 정렬 정의",
           "- 프레임 추출: 각 영상에서 7.5 fps 목표 시각(0, 0.1333, 0.2667, …)에 가장 가까운 실제 프레임(타임스탬프 기준)을 취한다. 가변 프레임률(UP-Fall)도 타임스탬프로 정렬된다.",
           "- 판정 시각: t_k = 영상 시작 + 0.2k. 판정은 t_k 이하의 가장 최근 프레임까지만 사용한다(미래 프레임 없음).",
           "- 윈도우: [t_k − W, t_k]. 프레임 수 = round(7.5·W). 영상 시작 이전 부분은 첫 프레임을 반복해 채우고 패딩 개수를 기록한다.",
           "- 패딩의 모델별 영향: B(이동 평균)는 패딩 프레임의 점수가 첫 프레임 점수로 고정돼 윈도우 초반 평균이 첫 프레임에 끌린다. C(GRU)는 반복 입력이 은닉 상태를 특정 방향으로 밀 수 있다. A는 영향이 없다. 따라서 주 분석(전체 사건, 패딩 허용)과 함께 '완전 관찰 부분집합(앞 맥락 ≥ W)' 분석을 모든 조건에 공통으로 실행해 결론이 달라지는지 보고한다.", ""]

    # 5.5 사건 앞뒤 여유 분포 (W 유효성 해석의 근거)
    evp_all = ev_p.assign(pre=ev_p.t0 - ev_p.vid_start, length=ev_p.vid_end - ev_p.vid_start, post=ev_p.vid_end - ev_p.t1)
    ctx = evp_all.groupby("dataset")[["pre", "length", "post"]].median().round(2)
    ctx.columns = ["앞 맥락 중앙값(s)", "영상 길이 중앙값(s)", "뒤 여유 중앙값(s)"]
    ctx.to_csv(REP / "dv_event_context.csv")
    md += ["### 5.사건 전후 여유의 데이터셋별 분포 (물리적 사건, 중앙값)", fmt(ctx), ""]

    # 6. 해석과 설계 조정 제안 (결정은 지도교수와 협의)
    sta_test_evp = E.extract_events(E.reference_streams(sta_fixed["test"][~sta_fixed["test"].dataset.isin(EXCLUDE)]))
    pre_t = sta_test_evp.t0 - sta_test_evp.vid_start
    md += ["## 6. 검증 결과 해석과 설계 조정 제안", "",
           "1. **FA/h 분모 교체**: Staged test 비낙상 시간은 전 스트림 합산 2.27h → 기준 카메라 1.25h, OOPS test 는 중복 행 포함 1.77h → 1.33h 로 바뀝니다. 사건 분모(121건·631건)와 같은 스트림 집합에서 계산되므로 지시서 3항의 불일치가 해소됩니다. 전 스트림 합산값은 '다시점 모두를 독립 스트림으로 평가하는 대안'의 수치로 병기합니다.",
           f"2. **시간 맥락 W 의 실제 유효성(가장 중요한 발견)**: Staged test 121건 중 사건 시작 전 실제 영상이 1초 이상인 사건은 {int((pre_t >= 1).sum())}건({100 * (pre_t >= 1).mean():.0f}%), 2초 이상 {int((pre_t >= 2).sum())}건({100 * (pre_t >= 2).mean():.0f}%), 4초 이상 {int((pre_t >= 4).sum())}건, 8초 이상 {int((pre_t >= 8).sum())}건, 16초 이상 {int((pre_t >= 16).sum())}건입니다. "
           "UP-Fall(57건)은 영상 길이 9.9s 에 낙상이 0.7s 에서 시작하고, GMDCSA24·CAUCAFall 도 앞 맥락 중앙값이 1.5~1.8s 입니다. 즉 Staged 의 절반 이상에서 W≥2 의 윈도우는 대부분 첫 프레임 패딩으로 채워지며, 이 사건들에서 W 를 늘리는 것은 '정보가 늘어나는 것'이 아니라 '패딩이 늘어나는 것'입니다. "
           "반면 OOPS test 631건은 앞 맥락 중앙값 4.1s 로 W=2 까지 85%, W=4 까지 51% 가 완전 관찰됩니다.",
           "3. **제안 (협의 필요)**: (a) 주 분석의 W 후보를 {1, 2, 4, 8}s 로 두고 16s 는 완전 관찰 사건이 충분한 OOPS·장편 데이터셋(EDF, OCCU, MCFD, Le2i)에서만 탐색 분석으로 보고. "
           "(b) 모든 W 조건에서 '완전 관찰 부분집합'(앞 맥락 ≥ W) 결과를 전체 사건 결과와 나란히 보고하고, 결론은 두 분석이 일치하는 범위에서만 내림. "
           "(c) W 효과의 주 검정 대상을 OOPS test(앞 맥락이 충분하고 사건 수가 가장 많음)로 두고 Staged test 는 도메인 내 기준선으로 보고하는 방안을 검토. "
           "(d) 탐지 지연은 사건 시작 후의 양이므로 앞 맥락 부족의 영향을 직접 받지 않지만, 뒤 여유(GMDCSA24 중앙값 2.4s, Le2i 2.6s)가 허용 구간 +3.0s 보다 짧은 사건이 있어 허용 구간이 영상 끝에서 잘리는 비율을 결과와 함께 보고.",
           "4. **라벨 중복 행**: OOPS 라벨의 완전 중복 행은 OmniFall 저자에게 보고할 사항이며, 본 연구의 모든 계산은 중복 제거 후 수행합니다.", ""]

    # 7. 보류 항목
    md += ["## 7. 영상 확보 후 수행할 항목 (보류)",
           "- Hub 원본 split 파일(`splits/cs/**`)과 라벨 CSV 의 SHA-256: `06_fetch_raw_hub_files.py` 실행 후 `12_hash_inventory.py` 로 생성",
           "- 데이터셋 간 동일 원본 영상 여부: 변환된 mp4 의 콘텐츠 해시(프레임 샘플 perceptual hash)로 데이터셋 간 대조",
           "- 영상 길이와 라벨 범위의 불일치(라벨이 영상 끝을 넘는 구간): 실제 영상 길이 확인 후 자름", ""]

    out = REP / "design_verification.md"
    out.write_text("\n".join(md), encoding="utf-8")
    LOG.info("저장: %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
