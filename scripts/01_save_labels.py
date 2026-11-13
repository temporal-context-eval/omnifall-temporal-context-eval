"""
01_save_labels.py
OmniFall 라벨/스플릿을 Hugging Face Hub에서 내려받아 CSV로 저장한다.

저장 위치: $OF_HOME/data/labels/<config>__<split>.csv
  - labels          : Staged 8종 + OOPS 전체 세그먼트 (분석 기준 원본)
  - of-sta-cs/-cv   : Staged 8종, cross-subject / cross-view
  - of-itw          : OOPS (실환경)
  - cs / cv         : Staged + OOPS 통합 스플릿
"""
import logging
import os
import sys
from pathlib import Path

import omnifall

LOG = logging.getLogger("save_labels")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

OUT_DIR = Path(os.environ.get("OF_HOME", ".")) / "data" / "labels"
CONFIGS = ["labels", "of-sta-cs", "of-sta-cv", "of-itw", "cs", "cv"]


def save_config(name: str) -> int:
    """config 하나를 split별 CSV로 저장하고 저장한 행 수를 돌려준다."""
    parts = omnifall.load(name)
    # load()는 Dataset 또는 DatasetDict를 돌려줌
    if hasattr(parts, "keys"):
        items = parts.items()
    else:
        items = [("all", parts)]
    total = 0
    for split, ds in items:
        df = ds.to_pandas()
        out = OUT_DIR / f"{name}__{split}.csv"
        df.to_csv(out, index=False)
        LOG.info("%-10s %-11s %7d rows -> %s", name, split, len(df), out.name)
        total += len(df)
    return total


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failed = []
    for name in CONFIGS:
        try:
            save_config(name)
        except Exception as exc:  # 네트워크/Hub 오류는 기록하고 다음 config 진행
            LOG.error("config '%s' 저장 실패: %s", name, exc)
            failed.append(name)
    if failed:
        LOG.error("실패한 config: %s (재실행하면 해당 부분만 다시 받음)", failed)
        return 1
    LOG.info("라벨 저장 완료. 다음: python scripts/04_label_stats.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
