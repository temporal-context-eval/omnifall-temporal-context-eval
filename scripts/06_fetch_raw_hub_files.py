"""
06_fetch_raw_hub_files.py — OmniFall Hub 원자료(raw) 내려받기 (WSL에서 실행)

목적: 공식 split 중복 문제를 '가공된 parquet'이 아니라 Hub의 원본 split 파일과
      라벨 CSV로 증명하기 위함 (교수님 요구: 원자료와 코드로 증명).
저장: $OF_HOME/data/raw/  (splits/**, labels/*.csv, 문서 md)
리비전: 2026-11-03 라벨 다운로드 시점과 동일한 커밋으로 고정
"""
import logging
import os
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("fetch_raw")

REPO = "simplexsigil2/omnifall"
REVISION = "83572a37b9e3081df8c06a56874b1d1f2a19386c"   # 라벨 다운로드 시 사용된 커밋
OUT = Path(os.environ.get("OF_HOME", ".")) / "data" / "raw"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        path = snapshot_download(
            repo_id=REPO, repo_type="dataset", revision=REVISION, local_dir=OUT,
            allow_patterns=["splits/**", "labels/*.csv", "*.md", "data_files/oops_video_mapping.csv"],
        )
    except Exception as exc:
        LOG.error("다운로드 실패: %s", exc)
        return 1
    files = sorted(p.relative_to(OUT).as_posix() for p in Path(path).rglob("*") if p.is_file())
    LOG.info("받은 파일 %d개", len(files))
    for f in files:
        print("  ", f)
    (OUT / "REVISION.txt").write_text(f"{REPO}@{REVISION}\n", encoding="utf-8")
    LOG.info("완료. 다음: python scripts/05_split_audit.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
