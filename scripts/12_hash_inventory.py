"""
12_hash_inventory.py — 원본 파일 목록과 SHA-256 해시 (교수님 지시서 과제 1 제출물)

대상
  - data/raw/**            : 06_fetch_raw_hub_files.py 가 받은 Hub 원본(split 파일, 라벨 CSV, 문서)
  - data/labels/*.csv      : 01_save_labels.py 가 저장한 config별 라벨 CSV (분석 입력)
  - reports/*.csv          : 05/11 이 만든 중복 증거·사건 단위 CSV (분석 출력)
출력
  - reports/raw_file_inventory.csv  (relpath, bytes, sha256, group)
  - reports/raw_file_inventory.md   (요약 + Hub 리비전)
실행: python scripts/12_hash_inventory.py   (외부 패키지 불필요)
"""
from __future__ import annotations

import csv
import hashlib
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("hash")
OF_HOME = Path(os.environ.get("OF_HOME", "."))
GROUPS = [("hub_raw", OF_HOME / "data" / "raw", "**/*"),
          ("labels_csv", OF_HOME / "data" / "labels", "*.csv"),
          ("report_csv", OF_HOME / "reports", "*.csv"),
          ("verification_csv", OF_HOME / "reports" / "design_verification", "*.csv")]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    rows = []
    for group, root, pattern in GROUPS:
        if not root.exists():
            LOG.warning("없음: %s (건너뜀)", root)
            continue
        files = sorted(p for p in root.glob(pattern) if p.is_file() and not p.name.startswith("raw_file_inventory"))
        for p in files:
            rows.append({"group": group, "relpath": p.relative_to(OF_HOME).as_posix(),
                         "bytes": p.stat().st_size, "sha256": sha256_of(p)})
        LOG.info("%s: %d개", group, len(files))

    out_csv = OF_HOME / "reports" / "raw_file_inventory.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["group", "relpath", "bytes", "sha256"])
        w.writeheader(); w.writerows(rows)

    rev_file = OF_HOME / "data" / "raw" / "REVISION.txt"
    rev = rev_file.read_text().strip() if rev_file.exists() else "(REVISION.txt 없음 — 06 실행 필요)"
    key = [r for r in rows if r["relpath"].startswith("data/raw/splits/cs/up_fall/") or r["relpath"].startswith("data/raw/labels/")]
    md = ["# 원본 파일 목록과 SHA-256", "", f"- Hub 리비전: `{rev}`",
          f"- 파일 수: " + ", ".join(f"{g} {sum(r['group'] == g for r in rows)}개" for g, _, _ in GROUPS),
          f"- 전체 목록: `reports/raw_file_inventory.csv`", "",
          "## 핵심 파일 (UP-Fall cross-subject split, 라벨 원본)", "",
          "| 파일 | 바이트 | SHA-256 |", "|:--|--:|:--|"]
    md += [f"| {r['relpath']} | {r['bytes']:,} | `{r['sha256']}` |" for r in key]
    (OF_HOME / "reports" / "raw_file_inventory.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    LOG.info("저장: %s (%d개 파일)", out_csv, len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
