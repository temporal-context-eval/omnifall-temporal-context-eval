"""
10_extract_features.py — 프레임 특징 추출 (연구설계 자료 5.2절·7절 1단계)

설계 고정값
  - 인코더: 고정(frozen) 이미지 인코더, 프레임당 임베딩 1개. 1순위 SigLIP2, 대체 DINOv2
  - 샘플링: 7.5 fps (OmniFall 프로토콜과 동일)
  - 전처리: 모델 프로세서 기본값 (SigLIP2 224×224, DINOv2 224 center crop)
  - 저장: data/features/<model>/<dataset>/<path>.npz  (feat: T×D float16, t: T float32 초 단위)
  - 한 번 추출한 영상은 건너뜀 → UP-Fall처럼 나중에 들어오는 영상은 같은 명령을 다시 실행
  - 추출 로그와 모델 식별자(해시)를 data/features/<model>/MANIFEST.jsonl 에 기록 (재현용)

실행 (WSL, venv 활성화 상태)
  단일 GPU:   python scripts/10_extract_features.py
  GPU 2장:    CUDA_VISIBLE_DEVICES=0 nohup python scripts/10_extract_features.py --shard 0 --nshards 2 > logs/10_gpu0.log 2>&1 &
              CUDA_VISIBLE_DEVICES=1 nohup python scripts/10_extract_features.py --shard 1 --nshards 2 > logs/10_gpu1.log 2>&1 &
  일부만:     python scripts/10_extract_features.py --datasets le2i OOPS
  연기 테스트: python scripts/10_extract_features.py --datasets GMDCSA24 --limit 3
  모델 교체:  python scripts/10_extract_features.py --model dinov2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("extract")

OF_HOME = Path(os.environ.get("OF_HOME", "."))
FEAT_ROOT = OF_HOME / "data" / "features"
TARGET_FPS = 7.5
MODELS = {
    # 이름: (HF 모델 id, 임베딩 추출 방식)
    "siglip2": ("google/siglip2-base-patch16-224", "siglip"),
    "dinov2": ("facebook/dinov2-base", "dino"),
}


def ensure_deps():
    try:
        import transformers  # noqa: F401
        import av  # noqa: F401
    except ImportError:
        LOG.info("transformers / av 설치")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "transformers>=4.49", "av>=10"])


# --------------------------------------------------------------------------- 영상 디코딩
def iter_frames(video_path: Path, target_fps: float):
    """영상을 열어 target_fps 간격에 가장 가까운 프레임을 (초, RGB ndarray)로 순서대로 낸다.
    가변 프레임률(UP-Fall)도 타임스탬프 기준으로 처리된다."""
    import av
    step = 1.0 / target_fps
    next_t = 0.0
    with av.open(str(video_path)) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        tb = float(stream.time_base)
        for frame in container.decode(stream):
            if frame.pts is None:
                continue
            t = frame.pts * tb
            if t + 1e-6 < next_t:
                continue
            yield t, frame.to_ndarray(format="rgb24")
            # 긴 공백(프레임 드롭)이 있어도 다음 목표 시각을 현재 시각 기준으로 당긴다
            next_t = max(next_t + step, t + step * 0.5)


# --------------------------------------------------------------------------- 모델
class Encoder:
    def __init__(self, name: str, device: str, batch: int):
        import torch
        from transformers import AutoImageProcessor, AutoModel
        self.name, self.kind = name, MODELS[name][1]
        self.model_id = MODELS[name][0]
        self.device, self.batch = device, batch
        self.proc = AutoImageProcessor.from_pretrained(self.model_id)
        self.model = AutoModel.from_pretrained(self.model_id, torch_dtype=torch.float16).to(device).eval()
        self.torch = torch
        # 재현용 식별자: 모델 가중치 파일의 해시 대신 config+id 해시 (가중치는 HF 리비전으로 고정 권장)
        self.ident = hashlib.sha1(json.dumps({"id": self.model_id, "cfg": self.model.config.to_dict()},
                                             sort_keys=True, default=str).encode()).hexdigest()[:12]

    @property
    def dim(self) -> int:
        cfg = self.model.config
        return getattr(getattr(cfg, "vision_config", cfg), "hidden_size", None) or cfg.hidden_size

    def encode(self, frames: list[np.ndarray]) -> np.ndarray:
        torch = self.torch
        out = []
        with torch.inference_mode():
            for i in range(0, len(frames), self.batch):
                px = self.proc(images=frames[i:i + self.batch], return_tensors="pt")["pixel_values"]
                px = px.to(self.device, dtype=torch.float16)
                if self.kind == "siglip":
                    emb = self.model.get_image_features(pixel_values=px)
                    # transformers 버전에 따라 텐서 또는 BaseModelOutputWithPooling 이 돌아온다
                    if not torch.is_tensor(emb):
                        emb = emb.pooler_output if getattr(emb, "pooler_output", None) is not None else emb[0]
                else:  # dino: CLS 토큰
                    emb = self.model(pixel_values=px).last_hidden_state[:, 0]
                if emb.ndim != 2:
                    raise RuntimeError(f"임베딩 차원 이상: {tuple(emb.shape)}")
                out.append(emb.float().cpu().numpy().astype(np.float16))
        return np.concatenate(out, 0) if out else np.zeros((0, self.dim), np.float16)


# --------------------------------------------------------------------------- 메인
def list_videos(datasets: list[str] | None):
    """라벨에 있는 모든 영상(dataset, path, 파일경로). 디스크에 없는 영상은 제외."""
    import omnifall
    ds = omnifall.load("labels", video=True)
    if hasattr(ds, "keys"):
        ds = ds[list(ds.keys())[0]]
    seen, items, missing = set(), [], 0
    for d, p, v in zip(ds["dataset"], ds["path"], ds["video"]):
        if datasets and d not in datasets:
            continue
        if (d, p) in seen:
            continue
        seen.add((d, p))
        if v is None:
            missing += 1
            continue
        items.append((d, p, Path(v)))
    items.sort()
    return items, missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="siglip2", choices=list(MODELS))
    ap.add_argument("--datasets", nargs="*", default=None)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--chunk-frames", type=int, default=512, help="메모리 보호: 이 수만큼 모아 인코딩")
    ap.add_argument("--limit", type=int, default=0, help="연기 테스트: 이 샤드에서 처음 N개 영상만 처리")
    args = ap.parse_args()

    ensure_deps()
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    LOG.info("device=%s model=%s shard=%d/%d", device, args.model, args.shard, args.nshards)

    items, missing = list_videos(args.datasets)
    items = items[args.shard::args.nshards]
    if args.limit:
        items = items[:args.limit]
    LOG.info("대상 영상 %d개 (디스크에 없는 영상 %d개 제외, 이 샤드 담당분)", len(items), missing)

    out_root = FEAT_ROOT / args.model
    out_root.mkdir(parents=True, exist_ok=True)
    manifest = out_root / "MANIFEST.jsonl"

    enc = None
    done = skipped = failed = 0
    t0 = time.time()
    for k, (d, p, vpath) in enumerate(items, 1):
        out = out_root / d / f"{p}.npz"
        if out.exists():
            skipped += 1
            continue
        if enc is None:
            enc = Encoder(args.model, device, args.batch)
            LOG.info("모델 %s (%s) dim=%d ident=%s", enc.model_id, device, enc.dim, enc.ident)
        try:
            ts, feats, buf, buf_t = [], [], [], []
            for t, fr in iter_frames(vpath, TARGET_FPS):
                buf.append(fr); buf_t.append(t)
                if len(buf) >= args.chunk_frames:
                    feats.append(enc.encode(buf)); ts.extend(buf_t); buf, buf_t = [], []
            if buf:
                feats.append(enc.encode(buf)); ts.extend(buf_t)
            feat = np.concatenate(feats, 0) if feats else np.zeros((0, enc.dim), np.float16)
            if len(feat) == 0:
                raise RuntimeError("디코딩된 프레임이 없음")
            out.parent.mkdir(parents=True, exist_ok=True)
            # np.savez 는 .npz 로 끝나지 않는 이름에 .npz 를 덧붙이므로 임시 파일도 .npz 로 끝나게 둔다
            tmp = out.with_suffix(".tmp.npz")
            np.savez(tmp, feat=feat, t=np.asarray(ts, np.float32))
            tmp.replace(out)
            with open(manifest, "a", encoding="utf-8") as f:
                f.write(json.dumps({"dataset": d, "path": p, "frames": int(len(feat)), "dim": int(feat.shape[1]),
                                    "fps": TARGET_FPS, "model": enc.model_id, "ident": enc.ident,
                                    "video_bytes": vpath.stat().st_size, "ts": time.strftime("%F %T")},
                                   ensure_ascii=False) + "\n")
            done += 1
            if done % 20 == 0:
                el = time.time() - t0
                LOG.info("진행 %d/%d (추출 %d, 건너뜀 %d, 실패 %d) %.1f초/영상", k, len(items), done, skipped, failed, el / max(done, 1))
        except Exception as exc:
            failed += 1
            LOG.error("실패 %s/%s: %s", d, p, exc)
    LOG.info("완료: 추출 %d, 이미 있음 %d, 실패 %d, 소요 %.1f분", done, skipped, failed, (time.time() - t0) / 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
