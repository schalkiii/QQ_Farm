"""cv_detector 多尺度搜索 / 收敛逻辑的回归测试（无需真实游戏窗口）。

直接运行: python tests/test_cv_detector_scales.py
覆盖点:
  - 根因修复: _priority_scales 不再截断尺度集合，始终覆盖完整基准尺度
  - 架构优化①: base_scales 可由构造参数覆盖，并与 BASE_SCALES 取并集
  - 架构优化②: _seed_scale_ema 为模板预热 EMA（幂等）
  - 架构优化③: 三个检测入口不再依赖调用方计算 gray_screen 即可运行
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from core.cv_detector import BASE_SCALES, CVDetector


def _make_detector(base_scales: list[float] | None = None) -> CVDetector:
    detector = CVDetector(templates_dir="templates", base_scales=base_scales)
    detector.load_templates()
    return detector


def test_priority_scales_full_no_truncation():
    """关键回归：收敛后也必须覆盖完整基准尺度集合，避免高 DPI/缩放漏检。"""
    detector = _make_detector()
    for name in detector._templates_by_name:
        scales = detector._priority_scales(name)
        assert set(scales) == set(BASE_SCALES), (name, scales)
        assert len(scales) == len(BASE_SCALES)
    print("PASS test_priority_scales_full_no_truncation")


def test_priority_scales_emphasizes_hit():
    """命中尺度应排在搜索顺序最前，配合匹配层 early-exit 跳过全档扫描。"""
    detector = _make_detector()
    detector._frame = 1  # 避开周期性全尺度扫描分支（_frame % 200 == 0）
    name = next(iter(detector._templates_by_name))
    detector._scale_ema.setdefault(name, {})[1.2] = 0.95
    detector._scale_hits.setdefault(name, {})[1.2] = 1
    scales = detector._priority_scales(name)
    assert scales[0] == 1.2, scales
    assert set(scales) == set(BASE_SCALES)
    print("PASS test_priority_scales_emphasizes_hit")


def test_seed_ema():
    """EMA 预热：每个模板在尺度 1.0 预置基线，且重复调用幂等。"""
    detector = _make_detector()
    detector._seed_scale_ema()
    for name in detector._templates_by_name:
        assert 1.0 in detector._scale_ema.get(name, {})
    before = {n: dict(detector._scale_ema.get(n, {})) for n in detector._templates_by_name}
    detector._seed_scale_ema()
    after = {n: dict(detector._scale_ema.get(n, {})) for n in detector._templates_by_name}
    assert before == after
    print("PASS test_seed_ema")


def test_base_scales_union():
    """构造参数 base_scales 与 BASE_SCALES 取并集，绝不缩小搜索范围。"""
    custom = [0.95, 1.05]
    detector = CVDetector(templates_dir="templates", base_scales=custom)
    detector.load_templates()
    name = next(iter(detector._templates_by_name))
    scales = detector._priority_scales(name)
    assert set(scales) == set(custom) | set(BASE_SCALES), scales
    print("PASS test_base_scales_union")


def test_detect_runs_without_gray_screen():
    """三个公开检测入口在调用方不再计算 gray_screen 后能正常运行（合成图不报错）。"""
    detector = _make_detector()
    shot = np.zeros((800, 600, 3), dtype=np.uint8)
    category = next(iter(detector._templates))
    name = next(iter(detector._templates_by_name))
    results_all = detector.detect_all(shot, threshold=0.9)
    results_cat = detector.detect_category(shot, category=category, threshold=0.9)
    results_one = detector.detect_single_template(shot, name=name, threshold=0.9)
    assert isinstance(results_all, list)
    assert isinstance(results_cat, list)
    assert isinstance(results_one, list)
    print("PASS test_detect_runs_without_gray_screen")


if __name__ == "__main__":
    test_priority_scales_full_no_truncation()
    test_priority_scales_emphasizes_hit()
    test_seed_ema()
    test_base_scales_union()
    test_detect_runs_without_gray_screen()
    print("\nALL TESTS PASSED")
