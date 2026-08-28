"""OpenCV 视觉检测引擎 - 模板匹配识别游戏UI元素"""
import json
import os
import cv2
import numpy as np
from dataclasses import dataclass, field
from loguru import logger
from PIL import Image, ImageSequence


SUPPORTED_TEMPLATE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif')
MAX_GIF_TEMPLATE_FRAMES = 16

# 多尺度自适应搜索配置
BASE_SCALES = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
_FULL_RESCAN_EVERY = 200   # 每 N 次检测强制全尺度扫描，捕捉窗口尺寸漂移
_EMA_ALPHA = 0.3           # 命中置信度指数滑动平均系数


@dataclass
class DetectResult:
    """单个检测结果"""
    name: str           # 模板名称，如 "btn_harvest", "icon_weed"
    category: str       # 类别，如 "button", "status_icon", "crop"
    x: int              # 匹配中心x（相对于截图）
    y: int              # 匹配中心y
    w: int              # 匹配区域宽
    h: int              # 匹配区域高
    confidence: float   # 匹配置信度 0~1
    extra: dict = field(default_factory=dict)

    @property
    def center(self) -> tuple[int, int]:
        return self.x, self.y

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """左上角和右下角 (x1, y1, x2, y2)"""
        return (self.x - self.w // 2, self.y - self.h // 2,
                self.x + self.w // 2, self.y + self.h // 2)


# 模板类别定义
TEMPLATE_CATEGORIES = {
    "btn": "button",
    "bth": "button",  # 施肥按钮等特殊按钮
    "icon": "status_icon",
    "crop": "crop",
    "ui": "ui_element",
    "land": "land",
    "seed": "seed",
    "shop": "shop",
    "friend": "ui_element",  # 好友列表页标识
    "ws": "warehouse_seed",  # 仓库种子（用于仓库界面检测）
}


class CVDetector:
    """基于OpenCV模板匹配的游戏UI检测器"""

    # 类别默认阈值
    CATEGORY_DEFAULTS: dict[str, float] = {
        "button": 0.8,
        "status_icon": 0.8,
        "crop": 0.8,
        "ui_element": 0.8,
        "land": 0.7,
        "seed": 0.8,
        "shop": 0.8,
        "warehouse_seed": 0.8,  # 新增：仓库种子
        "unknown": 0.8,
    }


    def __init__(self, templates_dir: str = "templates",
                 base_scales: list[float] | None = None):
        self._templates_dir = templates_dir
        # 多尺度搜索基准集合（可由配置覆盖，用于极端 DPI/缩放微调）
        self._base_scales = list(base_scales) if base_scales else BASE_SCALES
        self._templates: dict[str, list[dict]] = {}  # category -> [{name, image, mask}]
        self._templates_by_name: dict[str, list[dict]] = {}  # name -> template variants（快速查找）
        self._loaded = False
        self._disabled_names: set[str] = set()
        self._disabled_file = os.path.join(templates_dir, "disabled.json")
        self._thresholds: dict[str, float] = {}
        self._thresholds_file = os.path.join(templates_dir, "thresholds.json")
        self._category_overrides: dict[str, float] = {}  # 用户自定义的类别阈值

        # 多尺度自适应搜索状态
        self._scale_ema: dict[str, dict[float, float]] = {}   # name -> {scale: 置信度EMA}
        self._scale_hits: dict[str, dict[float, int]] = {}    # name -> {scale: 命中次数}
        self._frame: int = 0
        self._scale_stats_file = os.path.join(templates_dir, "scale_stats.json")

        self._load_disabled()
        self._load_thresholds()

    def _load_disabled(self):
        """从 disabled.json 加载已禁用的模板列表"""
        if os.path.exists(self._disabled_file):
            try:
                with open(self._disabled_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._disabled_names = set(data.get("disabled", []))
            except Exception as e:
                logger.warning(f"读取禁用模板配置失败: {e}")
                self._disabled_names = set()

    def _save_disabled(self):
        """保存禁用模板列表到 disabled.json"""
        try:
            os.makedirs(os.path.dirname(self._disabled_file), exist_ok=True)
            with open(self._disabled_file, "w", encoding="utf-8") as f:
                json.dump({"disabled": sorted(self._disabled_names)}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存禁用模板配置失败: {e}")

    def is_template_disabled(self, name: str) -> bool:
        return name in self._disabled_names

    def set_template_enabled(self, name: str, enabled: bool):
        """启用或禁用指定模板"""
        if enabled:
            self._disabled_names.discard(name)
        else:
            self._disabled_names.add(name)
        self._save_disabled()

    def get_disabled_templates(self) -> set[str]:
        return set(self._disabled_names)

    # ── 单模板阈值 ─────────────────────────────────────────

    def _load_thresholds(self):
        """从 thresholds.json 加载单模板阈值和类别阈值覆盖"""
        if os.path.exists(self._thresholds_file):
            try:
                with open(self._thresholds_file, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                self._thresholds = {k: float(v) for k, v in data.get("thresholds", {}).items()}
                self._category_overrides = {k: float(v) for k, v in data.get("category_overrides", {}).items()}
            except Exception as e:
                logger.warning(f"读取模板阈值配置失败: {e}")
                self._thresholds = {}
                self._category_overrides = {}

    def _save_thresholds(self):
        """保存单模板阈值和类别阈值覆盖到 thresholds.json"""
        try:
            os.makedirs(os.path.dirname(self._thresholds_file), exist_ok=True)
            with open(self._thresholds_file, "w", encoding="utf-8") as f:
                json.dump({
                    "thresholds": self._thresholds,
                    "category_overrides": self._category_overrides,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存模板阈值配置失败: {e}")

    # ── 多尺度自适应搜索 ─────────────────────────────────────

    def _priority_scales(self, name: str, base: list[float] | None = None) -> list[float]:
        """返回该模板本帧应搜索的尺度顺序（EMA 排序，始终覆盖完整基准尺度）。

        返回列表按历史命中置信度 EMA 降序排列，最可能是真实尺度的档排在最前，
        配合匹配层的 early-exit（scale_max > 0.95 即停止）可在稳态下只跑 1~3 档，
        性能与过去相当。关键在于：无论调用方传入的 base 多窄（如 SCALES_FAST 的
        3 档），这里都会自动补足完整 BASE_SCALES（或配置基准集合），避免收敛后
        把真实尺度永久排除在外（这正是“一键务农”等按钮在高 DPI/窗口缩放时
        漏检的根因）。
        """
        # 全尺度兜底：base（调用方窄集合）+ 配置基准集合 + 硬编码 BASE_SCALES
        # 三者取并集，确保无论配置多窄都至少覆盖 BASE_SCALES，杜绝尺度集过窄漏检
        full: list[float] = list(base) if base else []
        for scale in self._base_scales:
            if scale not in full:
                full.append(scale)
        for scale in BASE_SCALES:
            if scale not in full:
                full.append(scale)

        # 周期性全尺度扫描的语义已由上面的并集覆盖，这里保留分支以维持统计落盘时机
        if self._frame % _FULL_RESCAN_EVERY == 0:
            return full

        ema = self._scale_ema.get(name)
        if not ema:
            return full

        def _key(scale: float) -> tuple:
            return (ema.get(scale, 0.0), self._scale_hits.get(name, {}).get(scale, 0))

        return sorted(full, key=_key, reverse=True)

    def _record_hit(self, name: str, scale: float, conf: float):
        """记录某模板在某尺度上的命中，更新 EMA 与计数（只在命中时更新）。"""
        ema = self._scale_ema.setdefault(name, {})
        hits = self._scale_hits.setdefault(name, {})
        ema[scale] = ema.get(scale, 0.0) * (1 - _EMA_ALPHA) + conf * _EMA_ALPHA
        hits[scale] = hits.get(scale, 0) + 1

    def _load_scale_stats(self):
        """载入尺度命中统计，实现跨启动热启动。"""
        try:
            if os.path.exists(self._scale_stats_file):
                with open(self._scale_stats_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._scale_ema = {
                    k: {float(s): float(v) for s, v in d.items()}
                    for k, d in data.get("ema", {}).items()
                }
                self._scale_hits = {
                    k: {float(s): int(v) for s, v in d.items()}
                    for k, d in data.get("hits", {}).items()
                }
        except Exception:
            pass

    def _save_scale_stats(self):
        """持久化尺度命中统计。"""
        try:
            data = {
                "ema": {k: {str(s): v for s, v in d.items()}
                        for k, d in self._scale_ema.items()},
                "hits": {k: {str(s): v for s, v in d.items()}
                         for k, d in self._scale_hits.items()},
            }
            with open(self._scale_stats_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def _seed_scale_ema(self):
        """为已加载模板在尺度 1.0 预置基线 EMA，使首帧即按最优尺度排序、
        配合匹配层早停跳过全 8 档扫描，加速冷启动（仅补充统计中缺失的模板）。
        """
        baseline = 0.8
        for name in self._templates_by_name:
            ema = self._scale_ema.setdefault(name, {})
            if 1.0 not in ema:
                ema[1.0] = baseline
                self._scale_hits.setdefault(name, {})[1.0] = 0

    def get_template_threshold(self, name: str) -> float:
        """获取模板阈值：单模板 > 类别覆盖 > 内置类别默认 > 全局默认 0.8"""
        if name in self._thresholds:
            return self._thresholds[name]
        prefix = name.split("_")[0]
        cat = TEMPLATE_CATEGORIES.get(prefix, "unknown")
        if cat in self._category_overrides:
            return self._category_overrides[cat]
        return self.CATEGORY_DEFAULTS.get(cat, 0.8)

    def set_template_threshold(self, name: str, value: float):
        """设置单模板阈值并持久化"""
        value = max(0.1, min(1.0, round(value, 2)))
        self._thresholds[name] = value
        self._save_thresholds()

    def get_all_thresholds(self) -> dict[str, float]:
        return dict(self._thresholds)

    def reset_template_threshold(self, name: str):
        """移除单模板自定义阈值，恢复为类别默认"""
        if name in self._thresholds:
            del self._thresholds[name]
            self._save_thresholds()

    # ── 类别默认阈值 ─────────────────────────────────────────

    def get_category_defaults(self) -> dict[str, float]:
        """获取当前生效的类别阈值（用户覆盖 > 内置默认）"""
        result = dict(self.CATEGORY_DEFAULTS)
        result.update(self._category_overrides)
        return result

    def set_category_default(self, category: str, value: float):
        """设置类别默认阈值覆盖"""
        value = max(0.1, min(1.0, round(value, 2)))
        self._category_overrides[category] = value
        self._save_thresholds()

    def reset_category_defaults(self):
        """重置所有类别阈值为内置默认值"""
        self._category_overrides.clear()
        self._save_thresholds()

    def get_all_template_names(self) -> list[str]:
        """返回 templates/ 目录下所有模板文件名（不含扩展名）"""
        names = []
        if not os.path.exists(self._templates_dir):
            return names
        for filename in os.listdir(self._templates_dir):
            if filename.lower().endswith(SUPPORTED_TEMPLATE_EXTENSIONS):
                names.append(os.path.splitext(filename)[0])
        return sorted(names)

    def load_templates(self):
        """加载所有模板图片"""
        self._templates = {}
        self._templates_by_name = {}
        if not os.path.exists(self._templates_dir):
            os.makedirs(self._templates_dir, exist_ok=True)
            logger.warning(f"模板目录 {self._templates_dir} 为空，请先采集模板")
            return

        count = 0
        logical_count = 0
        skipped = 0
        for filename in os.listdir(self._templates_dir):
            if not filename.lower().endswith(SUPPORTED_TEMPLATE_EXTENSIONS):
                continue

            name = os.path.splitext(filename)[0]

            # 跳过被禁用的模板
            if name in self._disabled_names:
                skipped += 1
                continue

            filepath = os.path.join(self._templates_dir, filename)
            templates = self._load_template_variants(filepath)
            if not templates:
                logger.warning(f"无法读取模板: {filename}")
                continue
            logical_count += 1

            # 从文件名前缀判断类别: btn_harvest.png -> button
            prefix = name.split("_")[0]
            category = TEMPLATE_CATEGORIES.get(prefix, "unknown")

            if category not in self._templates:
                self._templates[category] = []

            for frame_index, template in enumerate(templates):
                # 处理带 alpha 通道的模板（用于 mask 匹配）
                mask = None
                if template.ndim == 3 and template.shape[2] == 4:
                    alpha = template[:, :, 3]
                    if not np.all(alpha == 255):
                        mask = alpha
                    template = template[:, :, :3]

                # 处理灰度图：预处理并缓存
                if template.ndim == 2:
                    template = cv2.cvtColor(template, cv2.COLOR_GRAY2BGR)
                gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

                tpl_data = {
                    "name": name,
                    "image": template,
                    "gray": gray,
                    "mask": mask,
                    "category": category,
                    "frame_index": frame_index,
                }
                self._templates[category].append(tpl_data)
                self._templates_by_name.setdefault(name, []).append(tpl_data)
                count += 1

        self._loaded = True
        self._load_scale_stats()
        self._seed_scale_ema()
        msg = f"已加载 {logical_count} 个模板"
        if count != logical_count:
            msg += f"（{count} 个匹配变体）"
        msg += f"，分 {len(self._templates)} 个类别"
        if skipped:
            msg += f"（跳过 {skipped} 个已禁用）"
        logger.info(msg)

    def _load_template_variants(self, filepath: str) -> list[np.ndarray]:
        """读取模板文件；GIF 会拆分为去重后的少量帧。"""
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.gif':
            return self._load_gif_template_variants(filepath)

        # cv2.imread 不支持中文路径，用 numpy 中转
        template = cv2.imdecode(
            np.fromfile(filepath, dtype=np.uint8), cv2.IMREAD_UNCHANGED
        )
        return [template] if template is not None else []

    def _load_gif_template_variants(self, filepath: str) -> list[np.ndarray]:
        """读取 GIF 模板的代表帧，保留 alpha 作为 mask。"""
        variants: list[np.ndarray] = []
        seen: set[bytes] = set()
        try:
            with Image.open(filepath) as image:
                for frame in ImageSequence.Iterator(image):
                    if len(variants) >= MAX_GIF_TEMPLATE_FRAMES:
                        break
                    rgba = np.array(frame.convert("RGBA"))
                    bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
                    key = bgra.tobytes()
                    if key in seen:
                        continue
                    seen.add(key)
                    variants.append(bgra)
        except Exception as e:
            logger.warning(f"读取 GIF 模板失败: {os.path.basename(filepath)} | {e}")
        return variants

    def detect_all(self, screenshot: np.ndarray,
                   threshold: float = 0.8) -> list[DetectResult]:
        """在截图中检测所有已加载的模板"""
        if not self._loaded:
            self.load_templates()

        self._frame += 1
        if self._frame % _FULL_RESCAN_EVERY == 0:
            self._save_scale_stats()

        results = []

        for category, templates in self._templates.items():
            for tpl in templates:
                matches = self._match_template_with_scales(
                    screenshot, tpl, threshold, self._priority_scales(tpl["name"])
                )
                results.extend(matches)

        # 过滤掉置信度异常的结果（inf, nan, >1.0）
        results = [r for r in results
                   if not (r.confidence != r.confidence or  # nan 检查
                           r.confidence == float('inf') or
                           r.confidence == float('-inf') or
                           r.confidence > 1.0)]

        # 去重：按类别分组 NMS，防止同一位置被多个同类模板重复匹配
        results = self._nms_by_category(results, iou_threshold=0.3)
        # 按置信度排序
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def detect_category(self, screenshot: np.ndarray,
                        category: str,
                        threshold: float = 0.8) -> list[DetectResult]:
        """只检测指定类别的模板"""
        if not self._loaded:
            self.load_templates()

        self._frame += 1
        if self._frame % _FULL_RESCAN_EVERY == 0:
            self._save_scale_stats()

        results = []

        templates = self._templates.get(category, [])
        for tpl in templates:
            matches = self._match_template_with_scales(
                screenshot, tpl, threshold, self._priority_scales(tpl["name"])
            )
            results.extend(matches)

        # 过滤掉置信度异常的结果（inf, nan, >1.0）
        results = [r for r in results
                   if not (r.confidence != r.confidence or  # nan 检查
                           r.confidence == float('inf') or
                           r.confidence == float('-inf') or
                           r.confidence > 1.0)]

        results = self._nms(results, iou_threshold=0.5)
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def detect_single_template(self, screenshot: np.ndarray,
                                name: str,
                                threshold: float = 0.7) -> list[DetectResult]:
        """只检测指定名称的单个模板"""
        if not self._loaded:
            self.load_templates()

        self._frame += 1
        if self._frame % _FULL_RESCAN_EVERY == 0:
            self._save_scale_stats()

        results: list[DetectResult] = []
        for tpl in self._templates_by_name.get(name, []):
            results.extend(self._match_template_with_scales(
                screenshot, tpl, threshold, self._priority_scales(tpl["name"])
            ))

        results = [r for r in results
                   if not (r.confidence != r.confidence or
                           r.confidence == float('inf') or
                           r.confidence == float('-inf') or
                           r.confidence > 1.0)]
        results = self._nms(results, iou_threshold=0.5)
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def detect_quick(self, screenshot: np.ndarray,
                     name: str,
                     threshold: float = 0.8) -> DetectResult | None:
        """极速检测：单模板 + 仅 scale 1.0，返回首个匹配或 None"""
        if not self._loaded:
            self.load_templates()

        tpl = self._find_template(name)
        if tpl is None:
            return None

        tpl_img = tpl["image"]
        tpl_mask = tpl["mask"]
        th, tw = tpl_img.shape[:2]
        sh, sw = screenshot.shape[:2]
        if tw >= sw or th >= sh:
            return None

        use_color = tpl["category"] == "land"

        if use_color:
            confidences = []
            for c in range(3):
                screen_ch = screenshot[:, :, c]
                tpl_ch = tpl_img[:, :, c]
                if tpl_mask is not None:
                    match_result = cv2.matchTemplate(screen_ch, tpl_ch, cv2.TM_CCOEFF_NORMED, mask=tpl_mask)
                else:
                    match_result = cv2.matchTemplate(screen_ch, tpl_ch, cv2.TM_CCOEFF_NORMED)
                confidences.append(match_result)
            match_result = np.mean(confidences, axis=0)
        else:
            gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            gray_tpl = cv2.cvtColor(tpl_img, cv2.COLOR_BGR2GRAY)
            if tpl_mask is not None:
                match_result = cv2.matchTemplate(gray_screen, gray_tpl, cv2.TM_CCOEFF_NORMED, mask=tpl_mask)
            else:
                match_result = cv2.matchTemplate(gray_screen, gray_tpl, cv2.TM_CCOEFF_NORMED)

        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(match_result)
        if max_val < threshold:
            return None

        return DetectResult(
            name=name,
            category=tpl["category"],
            x=max_loc[0] + tw // 2,
            y=max_loc[1] + th // 2,
            w=tw,
            h=th,
            confidence=float(max_val),
        )

    def detect_targeted(self, screenshot: np.ndarray,
                        names: list[str],
                        thresholds: dict[str, float] | None = None,
                        scales: list[float] | None = None,
                        roi_map: dict[str, tuple[int, int, int, int]] | None = None) -> list[DetectResult]:
        """快速检测：只扫描指定模板名称，使用精简尺度集合
        
        Args:
            screenshot: 截图
            names: 要检测的模板名列表
            thresholds: 单模板阈值覆盖 {template_name: threshold}
            scales: 自定义尺度集合，未传入时回退到完整 BASE_SCALES
            roi_map: ROI 区域映射 {template_name: (x1, y1, x2, y2)}，只在指定区域检测
        
        Returns:
            list[DetectResult]: 检测结果列表
        """
        if not self._loaded:
            self.load_templates()

        self._frame += 1
        if self._frame % _FULL_RESCAN_EVERY == 0:
            self._save_scale_stats()

        if not names:
            return []
        
        # 去重
        name_set = set(names)
        # 未显式传入 scales 时回退到完整 BASE_SCALES；_priority_scales 会进一步
        # 把任意传入的窄尺度集合补足为完整 BASE_SCALES，避免漏检
        fast_scales = scales or BASE_SCALES

        results = []
        gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        
        for name in name_set:
            template_variants = self._templates_by_name.get(name, [])
            if not template_variants:
                continue

            # 获取阈值
            thresh = (thresholds.get(name, 0.8) if thresholds
                      else self.get_template_threshold(name))

            for tpl in template_variants:
                # 检查是否有 ROI
                roi = roi_map.get(name) if roi_map else None
                if roi is not None:
                    # ROI 匹配：在局部区域搜索，再将命中坐标映射回全图
                    x1, y1, x2, y2 = [int(v) for v in roi]
                    sh, sw = screenshot.shape[:2]
                    x1 = max(0, min(x1, sw - 1))
                    y1 = max(0, min(y1, sh - 1))
                    x2 = max(x1 + 1, min(x2, sw))
                    y2 = max(y1 + 1, min(y2, sh))
                    if x2 > x1 and y2 > y1:
                        roi_img = screenshot[y1:y2, x1:x2]
                        roi_gray = gray_screen[y1:y2, x1:x2]
                        tpl_matches = self._match_template_with_scales_roi(
                            roi_img, roi_gray, tpl, thresh,
                            self._priority_scales(tpl["name"], fast_scales),
                            offset=(x1, y1)
                        )
                        results.extend(tpl_matches)
                else:
                    # 全图匹配
                    tpl_matches = self._match_template_with_scales(
                        screenshot, tpl, thresh,
                        self._priority_scales(tpl["name"], fast_scales)
                    )
                    results.extend(tpl_matches)

        # 过滤异常置信度
        results = [r for r in results
                   if not (r.confidence != r.confidence or  # nan 检查
                           r.confidence == float('inf') or
                           r.confidence == float('-inf') or
                           r.confidence > 1.0)]
        
        # 按类别分组 NMS 去重
        return self._nms_by_category(results, iou_threshold=0.3)

    def _match_template_with_scales_roi(self, roi_img, roi_gray, tpl, threshold, scales, offset):
        """在 ROI 区域内进行模板匹配，返回相对于全图的坐标
        
        Args:
            roi_img: ROI 区域彩色图
            roi_gray: ROI 区域灰度图
            tpl: 模板数据
            threshold: 匹配阈值
            scales: 缩放集合
            offset: ROI 区域左上角在全图中的偏移 (x, y)
        
        Returns:
            list[DetectResult]: 检测结果列表（坐标已映射到全图）
        """
        results = []
        tpl_img = tpl["image"]
        tpl_mask = tpl.get("mask")
        tpl_gray = tpl.get("gray")
        th, tw = tpl_img.shape[:2]
        rh, rw = roi_img.shape[:2]
        category = tpl["category"]
        offset_x, offset_y = offset

        for scale in scales:
            new_w = int(tw * scale)
            new_h = int(th * scale)
            if new_w >= rw or new_h >= rh or new_w < 10 or new_h < 10:
                continue

            resized_mask = None
            if tpl_mask is not None:
                resized_mask = cv2.resize(tpl_mask, (new_w, new_h),
                                          interpolation=cv2.INTER_NEAREST)

            if category == "land":
                resized_tpl = cv2.resize(tpl_img, (new_w, new_h))
                confidences = []
                for c in range(3):
                    screen_ch = roi_img[:, :, c]
                    tpl_ch = resized_tpl[:, :, c]
                    if resized_mask is not None:
                        mr = cv2.matchTemplate(screen_ch, tpl_ch,
                                               cv2.TM_CCOEFF_NORMED,
                                               mask=resized_mask)
                    else:
                        mr = cv2.matchTemplate(screen_ch, tpl_ch,
                                               cv2.TM_CCOEFF_NORMED)
                    confidences.append(mr)
                match_result = np.mean(confidences, axis=0)
            else:
                if tpl_gray is not None:
                    resized_tpl = cv2.resize(tpl_gray, (new_w, new_h))
                else:
                    resized_tpl = cv2.resize(cv2.cvtColor(tpl_img, cv2.COLOR_BGR2GRAY), (new_w, new_h))
                if resized_mask is not None:
                    match_result = cv2.matchTemplate(
                        roi_gray, resized_tpl, cv2.TM_CCOEFF_NORMED,
                        mask=resized_mask)
                else:
                    match_result = cv2.matchTemplate(
                        roi_gray, resized_tpl, cv2.TM_CCOEFF_NORMED)

            np.nan_to_num(match_result, copy=False, nan=-1.0,
                          posinf=-1.0, neginf=-1.0)

            locations = np.where(match_result >= threshold)
            scale_max = 0.0
            for pt_y, pt_x in zip(*locations):
                confidence = float(match_result[pt_y, pt_x])
                scale_max = max(scale_max, confidence)
                # 坐标映射回全图
                results.append(DetectResult(
                    name=tpl["name"],
                    category=tpl["category"],
                    x=pt_x + new_w // 2 + offset_x,
                    y=pt_y + new_h // 2 + offset_y,
                    w=new_w,
                    h=new_h,
                    confidence=confidence,
                ))

            if scale_max > 0:
                self._record_hit(tpl["name"], scale, scale_max)
            if scale_max > 0.95:
                break

        return results

    def _find_template(self, name: str) -> dict | None:
        """按名称查找模板数据"""
        variants = self._templates_by_name.get(name, [])
        return variants[0] if variants else None

    def _match_template_with_scales(self, screenshot: np.ndarray,
                                     tpl: dict,
                                     threshold: float,
                                     scales: list[float]) -> list[DetectResult]:
        """使用指定尺度集合进行模板匹配"""
        results = []
        tpl_img = tpl["image"]
        tpl_mask = tpl.get("mask")
        tpl_gray = tpl.get("gray")
        th, tw = tpl_img.shape[:2]
        sh, sw = screenshot.shape[:2]
        category = tpl["category"]

        gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

        for scale in scales:
            new_w = int(tw * scale)
            new_h = int(th * scale)
            if new_w >= sw or new_h >= sh or new_w < 10 or new_h < 10:
                continue

            resized_mask = None
            if tpl_mask is not None:
                resized_mask = cv2.resize(tpl_mask, (new_w, new_h),
                                          interpolation=cv2.INTER_NEAREST)

            if category == "land":
                resized_tpl = cv2.resize(tpl_img, (new_w, new_h))
                confidences = []
                for c in range(3):
                    screen_ch = screenshot[:, :, c]
                    tpl_ch = resized_tpl[:, :, c]
                    if resized_mask is not None:
                        mr = cv2.matchTemplate(screen_ch, tpl_ch,
                                               cv2.TM_CCOEFF_NORMED,
                                               mask=resized_mask)
                    else:
                        mr = cv2.matchTemplate(screen_ch, tpl_ch,
                                               cv2.TM_CCOEFF_NORMED)
                    confidences.append(mr)
                match_result = np.mean(confidences, axis=0)

            else:
                # 使用缓存的灰度图
                if tpl_gray is not None:
                    resized_tpl = cv2.resize(tpl_gray, (new_w, new_h))
                else:
                    resized_tpl = cv2.resize(
                        cv2.cvtColor(tpl_img, cv2.COLOR_BGR2GRAY), (new_w, new_h))
                if resized_mask is not None:
                    match_result = cv2.matchTemplate(
                        gray_screen, resized_tpl, cv2.TM_CCOEFF_NORMED,
                        mask=resized_mask)
                else:
                    match_result = cv2.matchTemplate(
                        gray_screen, resized_tpl, cv2.TM_CCOEFF_NORMED)

            np.nan_to_num(match_result, copy=False, nan=-1.0,
                          posinf=-1.0, neginf=-1.0)

            locations = np.where(match_result >= threshold)
            scale_max = 0.0
            for pt_y, pt_x in zip(*locations):
                confidence = float(match_result[pt_y, pt_x])
                scale_max = max(scale_max, confidence)
                results.append(DetectResult(
                    name=tpl["name"],
                    category=tpl["category"],
                    x=pt_x + new_w // 2,
                    y=pt_y + new_h // 2,
                    w=new_w,
                    h=new_h,
                    confidence=confidence,
                ))

            if scale_max > 0:
                self._record_hit(tpl["name"], scale, scale_max)
            if scale_max > 0.95:
                break

        return results


    @staticmethod
    def _nms(results: list[DetectResult],
             iou_threshold: float = 0.5) -> list[DetectResult]:
        """非极大值抑制，去除重叠检测"""
        if len(results) <= 1:
            return results

        # 按置信度降序排列
        results.sort(key=lambda r: r.confidence, reverse=True)
        keep = []

        while results:
            best = results.pop(0)
            keep.append(best)
            remaining = []
            for r in results:
                if _iou(best.bbox, r.bbox) < iou_threshold:
                    remaining.append(r)
            results = remaining

        return keep

    def _nms_by_category(self, results: list[DetectResult],
                         iou_threshold: float = 0.3) -> list[DetectResult]:
        """按类别分组做 NMS，防止同一块地被多个同类模板重复匹配
        使用中心点距离去重，阈值 25px
        """
        by_cat: dict[str, list[DetectResult]] = {}
        for r in results:
            by_cat.setdefault(r.category, []).append(r)

        final = []
        for cat, cat_results in by_cat.items():
            cat_results.sort(key=lambda r: r.confidence, reverse=True)
            kept = []
            for r in cat_results:
                is_duplicate = False
                for k in kept:
                    dist = ((r.x - k.x) ** 2 + (r.y - k.y) ** 2) ** 0.5
                    if dist < 25:
                        is_duplicate = True
                        break
                if not is_duplicate:
                    kept.append(r)
            final.extend(kept)

        final.sort(key=lambda r: r.confidence, reverse=True)
        return final

    @staticmethod
    def pil_to_cv2(image: Image.Image) -> np.ndarray:
        """PIL Image 转 OpenCV 格式"""
        rgb = np.array(image.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def draw_results(self, screenshot: np.ndarray,
                     results: list[DetectResult]) -> np.ndarray:
        """在截图上绘制检测结果（用于调试）"""
        output = screenshot.copy()
        overlay = output.copy()
        colors = {
            "button": (0, 200, 255),      # 亮橙
            "status_icon": (0, 100, 255),  # 亮蓝
            "crop": (0, 255, 100),         # 亮绿
            "ui_element": (255, 255, 0),   # 青
            "land": (180, 180, 180),       # 浅灰
            "seed": (255, 50, 255),        # 粉紫
            "shop": (0, 200, 200),         # 黄绿
            "unknown": (0, 0, 255),        # 红色
        }
        for r in results:
            color = colors.get(r.category, (0, 0, 255))
            x1, y1, x2, y2 = r.bbox
            # 半透明填充
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
            # 粗边框
            cv2.rectangle(output, (x1, y1), (x2, y2), color, 3)
        # 混合半透明叠加
        cv2.addWeighted(overlay, 0.25, output, 0.75, 0, output)
        # 标签绘制在叠加后，保证清晰
        for r in results:
            color = colors.get(r.category, (0, 0, 255))
            x1, y1, x2, y2 = r.bbox
            cv2.rectangle(output, (x1, y1), (x2, y2), color, 3)
            label = f"{r.confidence:.2f}"
            # 标签背景
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = max(0.5, min(output.shape[0] / 800, 1.0))
            thickness = max(1, int(scale * 1.5))
            (tw, th), _ = cv2.getTextSize(label, font, scale, thickness)
            ly = max(y1 - 6, th + 4)
            cv2.rectangle(output, (x1, ly - th - 4), (x1 + tw + 8, ly + 4), color, -1)
            cv2.putText(output, label, (x1 + 4, ly),
                        font, scale, (255, 255, 255), thickness, cv2.LINE_AA)
        return output


def _iou(box1: tuple, box2: tuple) -> float:
    """计算两个框的IoU"""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0
