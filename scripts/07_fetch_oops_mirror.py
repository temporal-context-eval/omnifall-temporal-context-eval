"""
07_fetch_oops_mirror.py — OOPS 원본 아카이브를 Hugging Face 미러에서 내려받기

배경: 공식 주소(https://oops.cs.columbia.edu/data/video_and_anns.tar.gz)가 2026-11-04 기준 404.
      HF에 같은 파일명으로 올라온 미러(pengxiang/oops, 47.9 GB)를 대신 사용한다.
      OOPS 라이선스는 CC BY-NC-SA 4.0 (재배포 허용, 비상업). 논문에는 원 출처를 인용하고
      입수 경로(미러)를 데이터 절에 밝힌다.
저장: $OMNIFALL_DOWNLOAD_DIR/OOPS/video_and_anns.tar.gz
      → 이후 `omnifall prepare OOPS` 가 이 파일을 자동으로 찾아 818개 영상만 추출한다.
검증: prepare 단계에서 Hub의 oops_video_mapping.csv 와 대조해 818개가 모두 있어야 통과.
"""
import logging
import os
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("oops_mirror")

MIRROR_REPO = "pengxiang/oops"
FILENAME = "video_and_anns.tar.gz"
EXPECTED_MIN_BYTES = 40 * 1024**3   # 44.6 GiB 안팎이어야 정상


def main() -> int:
    out_dir = Path(os.environ.get("OMNIFALL_DOWNLOAD_DIR", "data/downloads")) / "OOPS"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / FILENAME
    if target.exists() and target.stat().st_size >= EXPECTED_MIN_BYTES:
        LOG.info("이미 있음: %s (%.1f GiB)", target, target.stat().st_size / 1024**3)
        return 0
    LOG.info("HF 미러 %s 에서 %s 다운로드 시작 (약 47.9 GB, 중단 시 재실행하면 이어받기)", MIRROR_REPO, FILENAME)
    try:
        path = hf_hub_download(repo_id=MIRROR_REPO, repo_type="dataset", filename=FILENAME,
                               local_dir=out_dir)
    except Exception as exc:
        LOG.error("다운로드 실패: %s", exc)
        return 1
    size = Path(path).stat().st_size
    LOG.info("완료: %s (%.1f GiB)", path, size / 1024**3)
    if size < EXPECTED_MIN_BYTES:
        LOG.error("파일 크기가 예상(≥40 GiB)보다 작음 — 손상 가능성. 삭제 후 재실행 필요")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
