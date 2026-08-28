"""ROI 比例换算工具。

把在基准分辨率下定义的 ROI（x1, y1, x2, y2）按当前帧尺寸等比映射到
实际截图，避免在非基准分辨率/非 16:9 显示器下因坐标写死而裁掉元素
（与“尺度窄集合漏检”同源的“分辨率窄假设”潜藏问题）。
"""
from __future__ import annotations


def scale_roi(
    roi: tuple[int, int, int, int],
    src_w: int,
    src_h: int,
    dst_w: int,
    dst_h: int,
) -> tuple[int, int, int, int]:
    """将 ROI 从 (src_w, src_h) 基准尺寸等比缩放到 (dst_w, dst_h)。

    任一尺寸无效（<=0）时原样返回，避免除零。
    """
    if src_w <= 0 or src_h <= 0 or dst_w <= 0 or dst_h <= 0:
        return roi
    sx = dst_w / src_w
    sy = dst_h / src_h
    x1, y1, x2, y2 = roi
    return (
        int(round(x1 * sx)),
        int(round(y1 * sy)),
        int(round(x2 * sx)),
        int(round(y2 * sy)),
    )
