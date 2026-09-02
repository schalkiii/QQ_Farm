"""调试捕获：真机运行时保存截图 + 结构化上下文，用于定位"卡在哪"。

背景
----
GUI 自动化项目无法在本机复现（没有游戏窗口、无法模拟真机交互），
因此**真机日志 + 截图**是唯一可靠的反馈信号。截图让具备多模态能力的
分析者（人或模型）可以直接"看"界面状态，而不是靠猜。

产出
----
    logs/debug/<YYYY-MM-DD>/<HHMMSS>_<tag>[_<scene>].png   界面截图
    logs/debug/<YYYY-MM-DD>/<HHMMSS>_<tag>[_<scene>].json  结构化上下文

JSON 内含：时间、tag、场景、窗口 rect、全部检测项（名称/置信度/坐标）、
以及调用方传入的 extra 字典（如任务分发决策、地块状态等）。

设计原则
--------
- 任何异常都不得影响主流程（全部 try/except 并降级为 debug 日志）。
- 按 tag 白名单控制，默认只在"值得看"的节点触发，避免刷爆磁盘。
- 自动清理：超过 max_files 后删除最旧文件。
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

try:
    import cv2

    _HAS_CV2 = True
except Exception:  # pragma: no cover - cv2 应始终可用，这里只是防御
    _HAS_CV2 = False


class DebugCapture:
    """关键节点保存截图与上下文，供事后（含多模态）分析。"""

    def __init__(self, base_dir: str | Path, enabled: bool = True,
                 max_files: int = 300, events: Iterable[str] | None = None):
        self.base_dir = Path(base_dir)
        self.enabled = bool(enabled)
        self.max_files = int(max_files)
        # 白名单；None 或空集合表示"全部允许"
        evs = set(events) if events else None
        self.events: set[str] | None = evs or None
        self._lock = threading.Lock()
        self._saved = 0

    # ------------------------------------------------------------------ #
    # 控制接口
    # ------------------------------------------------------------------ #
    def allows(self, tag: str) -> bool:
        """该 tag 是否允许捕获"""
        if not self.enabled:
            return False
        if not self.events:
            return True
        return tag in self.events

    def enable(self, enabled: bool = True) -> None:
        self.enabled = bool(enabled)

    def _ensure_dir(self) -> Path | None:
        try:
            d = self.base_dir / time.strftime("%Y-%m-%d")
            d.mkdir(parents=True, exist_ok=True)
            return d
        except Exception as e:  # pragma: no cover
            logger.debug(f"debug 目录创建失败: {e}")
            return None

    # ------------------------------------------------------------------ #
    # 核心：保存截图 + 上下文
    # ------------------------------------------------------------------ #
    def capture(self, cv_img, tag: str, *, scene=None, detections=None,
                rect=None, extra: dict[str, Any] | None = None) -> Path | None:
        """保存一张调试截图及其上下文。失败返回 None，绝不抛异常。"""
        if cv_img is None or not _HAS_CV2 or not self.allows(tag):
            return None

        d = self._ensure_dir()
        if d is None:
            return None

        try:
            with self._lock:
                ts = time.strftime("%H%M%S")
                scene_s = str(getattr(scene, "value", scene) or "")
                stem = f"{ts}_{tag}" + (f"_{scene_s}" if scene_s else "")

                img_path = d / f"{stem}.png"
                ok = cv2.imwrite(str(img_path), cv_img)
                if not ok:
                    logger.debug(f"debug 截图写入失败: {img_path}")
                    return None

                ctx: dict[str, Any] = {
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "tag": tag,
                    "scene": scene_s,
                    "rect": list(rect) if rect else None,
                    "detections": [
                        {
                            "name": det.name,
                            "confidence": round(float(det.confidence), 4),
                            "x": int(det.x),
                            "y": int(det.y),
                            "w": int(getattr(det, "w", 0) or 0),
                            "h": int(getattr(det, "h", 0) or 0),
                        }
                        for det in (detections or [])
                    ],
                    "extra": extra or {},
                }
                (d / f"{stem}.json").write_text(
                    json.dumps(ctx, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                self._saved += 1
                if self._saved % 25 == 0:
                    self._cleanup(d)

                logger.info(f"🐞 debug 截图: {img_path}")
                return img_path
        except Exception as e:  # pragma: no cover
            logger.debug(f"debug 截图异常: {e}")
            return None

    # ------------------------------------------------------------------ #
    # 清理
    # ------------------------------------------------------------------ #
    def _cleanup(self, d: Path) -> None:
        """保留最近 max_files 张，删除更旧的（连同 json）"""
        try:
            files = sorted(d.glob("*.png"), key=lambda p: p.stat().st_mtime,
                           reverse=True)
            for p in files[self.max_files:]:
                try:
                    p.unlink()
                    j = p.with_suffix(".json")
                    if j.exists():
                        j.unlink()
                except Exception:
                    pass
        except Exception:  # pragma: no cover
            pass
