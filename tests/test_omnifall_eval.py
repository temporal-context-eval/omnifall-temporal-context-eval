"""
test_omnifall_eval.py — 평가 규칙 단위 테스트 (교수님 지시서 과제 3·4)

실행: pytest scripts/test_omnifall_eval.py -v
      pytest scripts/test_omnifall_eval.py -q --tb=short > reports/eval_unit_tests.log
각 테스트는 '예상 결과'를 코드에 명시하고 실제 결과와 비교한다.
test_expected_vs_actual_table() 은 모든 경계 사례의 예상/실제를 CSV(reports/eval_edge_cases.csv)로 남긴다.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import omnifall_eval as E

REPORT_DIR = Path(os.environ.get("OF_HOME", ".")) / "reports"


# ------------------------------------------------------------------ 사건 병합
def test_merge_gap_rule():
    # 간격 0.4s → 병합, 0.6s → 분리, 경계 0.5s → 병합(≤)
    ev, merged = E.merge_fall_segments([(0, 1.0), (1.4, 2.0), (2.6, 3.0), (3.5, 4.0)])
    assert ev == [(0, 2.0), (2.6, 4.0)]
    assert merged == 2


def test_merge_unsorted_and_overlapping():
    ev, merged = E.merge_fall_segments([(2.0, 3.0), (0.0, 2.5)])
    assert ev == [(0.0, 3.0)] and merged == 1


# ------------------------------------------------------------------ 경보 묶음
def test_cluster_refractory():
    cl = E.cluster_alarms([0.0, 0.2, 1.9, 4.0, 6.1, 9.0])
    # 0.0-1.9 (간격 ≤2) 한 묶음, 4.0-6.1 한 묶음(간격 2.1>2 → 분리됨), 9.0
    assert cl == [(0.0, 1.9, 3), (4.0, 4.0, 1), (6.1, 6.1, 1), (9.0, 9.0, 1)]


# ------------------------------------------------------------------ 매칭 경계 사례
def _labels(segs, vid_end=None):
    return E.StreamLabels(segments=segs, vid_start=0.0, vid_end=vid_end)


def test_basic_detection_and_latency():
    L = _labels([(0, 0, 10), (1, 10, 12), (2, 12, 20), (7, 20, 23)])  # walk, fall 10-12, fallen, stand_up
    r = E.match_alarms(L, [10.6, 10.8])
    assert r.events.detected.iloc[0] and r.events.latency.iloc[0] == pytest.approx(0.6)
    assert list(r.clusters.status) == ["TP"]


def test_alarm_before_window_is_FA():
    L = _labels([(0, 0, 10), (1, 10, 12), (2, 12, 20)])
    r = E.match_alarms(L, [9.0])          # 허용 구간 시작 9.5 보다 이르다 → walk 구간의 오경보
    assert not r.events.detected.iloc[0]
    assert list(r.clusters.status) == ["FA"] and r.clusters.label_at.iloc[0] == 0


def test_alarm_in_pre_tolerance_counts_with_zero_latency():
    L = _labels([(0, 0, 10), (1, 10, 12), (2, 12, 20)])
    r = E.match_alarms(L, [9.6])          # t0-0.5 ≤ 9.6 < t0 → 검출, 지연은 음수 대신 0
    assert r.events.detected.iloc[0] and r.events.latency.iloc[0] == 0.0


def test_alarm_in_post_tolerance_and_fallen_ignored():
    L = _labels([(0, 0, 10), (1, 10, 12), (2, 12, 30)])
    r = E.match_alarms(L, [14.0, 20.0])   # 14.0 ≤ t1+3=15 → TP(지연 4.0); 20.0 은 fallen → 무시
    assert r.events.detected.iloc[0] and r.events.latency.iloc[0] == pytest.approx(4.0)
    assert list(r.clusters.status) == ["TP", "IGN_FALLEN"]


def test_repeated_alarms_in_fallen_are_not_FA():
    L = _labels([(0, 0, 10), (1, 10, 12), (2, 12, 30)])
    r = E.match_alarms(L, [11.0, 16.0, 19.0, 22.0, 25.0])  # 11 TP, 나머지 fallen 안
    assert (r.clusters.status == "FA").sum() == 0
    # 16,19,22,25 는 서로 3초 간격(>2) → 4개 묶음, 모두 fallen 안 → 무시. 11 은 TP. 총 5묶음
    assert (r.clusters.status == "IGN_FALLEN").sum() == 4
    assert len(r.clusters) == 5


def test_multiple_alarms_one_event_counts_once():
    L = _labels([(0, 0, 10), (1, 10, 12), (2, 12, 20)])
    r = E.match_alarms(L, [10.2, 10.4, 13.5])  # 10.2-10.4 한 묶음(TP), 13.5 는 별 묶음(간격 3.1) 허용구간 안 → TP_DUP
    assert r.events.detected.sum() == 1
    assert list(r.clusters.status) == ["TP", "TP_DUP"]
    assert r.events.latency.iloc[0] == pytest.approx(0.2)


def test_cluster_overlapping_two_events_assigned_to_nearest():
    # 두 낙상이 가까움: fall 10-11, stand_up 11-12, fall 12.5-13.5  (12.5-11 = 1.5 > 0.5 → 별개 사건)
    L = _labels([(0, 0, 10), (1, 10, 11), (7, 11, 12), (0, 12, 12.5), (1, 12.5, 13.5), (2, 13.5, 20)])
    assert len(L.fall_events()) == 2
    r = E.match_alarms(L, [12.4])   # 사건1 허용구간 [9.5,14], 사건2 [12.0,16.5] 모두 포함 → 가까운 t0=12.5 사건2에 배정
    assert list(r.events.detected) == [False, True]
    assert r.events.latency.iloc[1] == 0.0
    # 사건1은 미검출 → 지연 NaN
    assert np.isnan(r.events.latency.iloc[0])


def test_event_at_video_start_and_end_windows_clipped():
    L = _labels([(1, 0.0, 1.5), (2, 1.5, 5.0), (0, 5.0, 8.0), (1, 8.0, 9.0)], vid_end=9.0)
    r = E.match_alarms(L, [0.0, 8.9])
    assert list(r.events.win_lo) == [0.0, 7.5]
    assert list(r.events.win_hi) == [4.5, 9.0]          # 영상 끝 9.0 으로 잘림
    assert list(r.events.detected) == [True, True]
    assert r.events.latency.iloc[1] == pytest.approx(0.9)


def test_undetected_event_latency_nan_and_not_in_median():
    L = _labels([(0, 0, 10), (1, 10, 12), (2, 12, 20), (0, 20, 30), (1, 30, 31), (2, 31, 40)])
    r = E.match_alarms(L, [10.5])
    s = E.summarize([r], nonfall_h=1.0)
    assert s["n_events"] == 2 and s["n_detected"] == 1 and s["EDR"] == 0.5
    assert s["latency_median"] == pytest.approx(0.5)


def test_unlabeled_gap_alarm_ignored():
    L = _labels([(0, 0, 10), (1, 20, 21), (2, 21, 25)], vid_end=25)  # 10-20 라벨 없음
    r = E.match_alarms(L, [15.0])
    assert list(r.clusters.status) == ["IGN_UNLABELED"]


def test_FA_per_hour_and_nonfall_time():
    df = pd.DataFrame([
        dict(dataset="x", path="v1", label=0, start=0, end=1800, subject=1, cam=1),
        dict(dataset="x", path="v1", label=1, start=1800, end=1802, subject=1, cam=1),
        dict(dataset="x", path="v1", label=2, start=1802, end=1900, subject=1, cam=1),
        dict(dataset="x", path="v1", label=0, start=1900, end=3600, subject=1, cam=1),
    ])
    d = E.prepare_labels(df)
    h = E.nonfall_hours(d)
    assert h == pytest.approx((1800 + 1700) / 3600)       # fall 2s, fallen 98s 제외
    L = _labels([(0, 0, 1800), (1, 1800, 1802), (2, 1802, 1900), (0, 1900, 3600)])
    r = E.match_alarms(L, [100.0, 500.0, 1801.0, 1850.0, 2500.0])
    s = E.summarize([r], h)
    assert s["n_FA"] == 3 and s["FA_per_h"] == pytest.approx(3 / h)


def test_nonfall_hours_union_of_overlaps():
    df = pd.DataFrame([
        dict(dataset="x", path="v", label=0, start=0, end=10, subject=1, cam=1),
        dict(dataset="x", path="v", label=8, start=5, end=15, subject=1, cam=1),   # 겹침
    ])
    assert E.nonfall_hours(E.prepare_labels(df)) == pytest.approx(15 / 3600)


def test_exact_duplicate_rows_dropped_once():
    """OOPS 라벨처럼 같은 행이 두 번 들어와도 시간·사건이 두 배로 세이지 않는다."""
    rows = [dict(dataset="OOPS", path="v", label=8, start=0, end=10, subject=-1, cam=-1),
            dict(dataset="OOPS", path="v", label=1, start=10, end=12, subject=-1, cam=-1),
            dict(dataset="OOPS", path="v", label=2, start=12, end=20, subject=-1, cam=-1)]
    d = E.prepare_labels(pd.DataFrame(rows + rows))
    assert d.attrs["dropped_duplicates"] == 3 and len(d) == 3
    assert E.nonfall_hours(d) == pytest.approx(10 / 3600)
    assert E.per_label_hours(d)["fallen"] == pytest.approx(8 / 3600)
    assert len(E.extract_events(d)) == 1


# ------------------------------------------------------------------ 기준 카메라 / 다시점
def test_reference_camera_min_rule_and_no_double_time():
    df = pd.DataFrame([
        dict(dataset="up_fall", path="S1/A1/T1/S1A1T1Camera1", label=0, start=0, end=10, subject=1, cam=1),
        dict(dataset="up_fall", path="S1/A1/T1/S1A1T1Camera1", label=1, start=10, end=12, subject=1, cam=1),
        dict(dataset="up_fall", path="S1/A1/T1/S1A1T1Camera2", label=0, start=0, end=10, subject=1, cam=2),
        dict(dataset="up_fall", path="S1/A1/T1/S1A1T1Camera2", label=1, start=10, end=12, subject=1, cam=2),
    ])
    d = E.prepare_labels(df)
    assert E.nonfall_hours(d) == pytest.approx(20 / 3600)            # 스트림별 합산 (두 배)
    ref = E.reference_streams(d)
    assert set(ref.cam) == {1}
    assert E.nonfall_hours(ref) == pytest.approx(10 / 3600)          # 기준 카메라만
    ev_all, ev_ref = E.extract_events(d), E.extract_events(ref)
    assert len(ev_all) == 2 and len(ev_ref) == 1


def test_recording_key_and_camera_parsing():
    assert E.recording_key("up_fall", "Subject3/Activity2/Trial1/Subject3Activity2Trial1Camera2") == "Subject3/Activity2/Trial1/Subject3Activity2Trial1"
    assert E.camera_from_path("up_fall", "Subject3/Activity2/Trial1/Subject3Activity2Trial1Camera2") == 2
    assert E.recording_key("mcfd", "chute07/cam3") == "chute07" and E.camera_from_path("mcfd", "chute07/cam3") == 3
    assert E.recording_key("edf", "peter/view2/rgb/peter_view2_rgb") == "peter" and E.camera_from_path("edf", "peter/view2/rgb/peter_view2_rgb") == 2
    assert E.recording_key("cmdfall", "colors/S39P1K6") == "colors/S39P1" and E.camera_from_path("cmdfall", "colors/S39P1K6") == 6
    assert E.recording_key("le2i", "Home_01/video_3") == "Home_01/video_3" and E.camera_from_path("le2i", "Home_01/video_3") is None
    assert E.subject_from_path("up_fall", "Subject15/Activity1/Trial1/Subject15Activity1Trial1Camera1") == 15


# ------------------------------------------------------------------ 시간 정렬 / 윈도우
def test_decision_times_and_window_padding():
    ts = np.arange(0, 10, 1 / 7.5)                      # 7.5 fps 프레임 시각
    t = E.decision_times(0.0, 10.0)
    assert t[1] == pytest.approx(0.2) and t[-1] <= 10.0
    idx, pad = E.frames_for_window(ts, t=1.0, W=2.0)    # 2초 = 15프레임, 1초 시점엔 8프레임만 존재 → 7개 패딩
    assert len(idx) == 15 and pad == 7 and idx[-1] == 7
    idx2, pad2 = E.frames_for_window(ts, t=9.0, W=2.0)
    assert pad2 == 0 and len(idx2) == 15 and ts[idx2[-1]] <= 9.0 + 1e-9


# ------------------------------------------------------------------ 예상/실제 비교표
def test_expected_vs_actual_table():
    cases = [
        ("경보가 허용 구간보다 먼저", [(0, 0, 10), (1, 10, 12), (2, 12, 20)], [9.0], "FA", False),
        ("허용 구간 전방 여유(−0.5s) 안", [(0, 0, 10), (1, 10, 12), (2, 12, 20)], [9.6], "TP", True),
        ("후방 여유(+3s) 안", [(0, 0, 10), (1, 10, 12), (2, 12, 30)], [14.9], "TP", True),
        ("후방 여유 밖, fallen 안", [(0, 0, 10), (1, 10, 12), (2, 12, 30)], [15.5], "IGN_FALLEN", False),
        ("한 사건에 여러 묶음", [(0, 0, 10), (1, 10, 12), (2, 12, 20)], [10.2, 13.5], "TP,TP_DUP", True),
        ("라벨 없는 구간의 경보", [(0, 0, 10), (1, 20, 21), (2, 21, 25)], [15.0], "IGN_UNLABELED", False),
        ("경보 없음(미검출)", [(0, 0, 10), (1, 10, 12), (2, 12, 20)], [], "", False),
        ("영상 끝 낙상", [(0, 0, 8), (1, 8, 9)], [8.95], "TP", True),
    ]
    rows = []
    for name, segs, alarms, exp_status, exp_det in cases:
        r = E.match_alarms(_labels(segs), alarms)
        act_status = ",".join(r.clusters.status)
        act_det = bool(r.events.detected.iloc[0])
        rows.append(dict(case=name, alarms=str(alarms), expected_status=exp_status, actual_status=act_status,
                         expected_detected=exp_det, actual_detected=act_det,
                         ok=(exp_status == act_status and exp_det == act_det)))
    t = pd.DataFrame(rows)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    t.to_csv(REPORT_DIR / "eval_edge_cases.csv", index=False)
    assert t.ok.all(), t[~t.ok]
