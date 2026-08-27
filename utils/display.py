"""显示器信息工具

提供系统桌面分辨率、系统缩放比读取，以及"游戏窗口尺寸自动适配"计算。
游戏窗口保持竖屏原生比例（581:1054 ≈ 0.551），按工作区可用高度等比放大，
并限制在模板匹配容差（0.8~1.5）内，使 32:9 带鱼屏等任意比例显示器都能稳定匹配。
"""
import ctypes
from dataclasses import dataclass

# 游戏原生竖屏设计比例（581:1054）
NATIVE_ASPECT = 581 / 1054
# 模板多尺度匹配容差（core/cv_detector 各向同性 0.8~1.5）
# 注意：上限必须与 cv_detector 的搜索尺度集合一致，否则放大的窗口模板搜不到
MIN_SCALE = 0.8
MAX_SCALE = 1.5


@dataclass
class DisplayInfo:
    """桌面显示器信息（物理像素 + 系统缩放）"""
    width: int          # 工作区宽度（物理像素，已含 DPI）
    height: int         # 工作区高度（物理像素，已含 DPI）
    scale_factor: float  # 系统缩放比（1.0 = 100%，1.25 = 125%）


def get_display_info() -> DisplayInfo:
    """读取主显示器工作区尺寸（物理像素）与系统缩放比。

    桌面分辨率取"工作区"（排除任务栏）物理像素；
    系统缩放比通过 GetDpiForSystem 相对标准 96 DPI 推算。
    """
    try:
        user32 = ctypes.windll.user32
        # 工作区尺寸（物理像素，已含 DPI 缩放）
        work_area = ctypes.wintypes.RECT()
        user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work_area), 0)
        width = work_area.right - work_area.left
        height = work_area.bottom - work_area.top

        # 系统缩放比：优先用 shcore.GetScaleFactorForDevice(0)（直接返回 100/125/150…），
        # 该 API 进程 DPI 感知足够时即返回真实值；失败再回退到 DPI/96 估算。
        try:
            scale = ctypes.windll.shcore.GetScaleFactorForDevice(0)  # 0=主显示器
            if scale and scale > 0:
                scale_factor = scale / 100.0
            else:
                raise ValueError
        except Exception:
            try:
                dpi = ctypes.windll.user32.GetDpiForSystem()
                scale_factor = dpi / 96.0
            except Exception:
                scale_factor = 1.0

        if width <= 0 or height <= 0:
            width, height, scale_factor = 1920, 1080, 1.0
        return DisplayInfo(width=width, height=height, scale_factor=float(scale_factor))
    except Exception:
        return DisplayInfo(width=1920, height=1080, scale_factor=1.0)


def compute_window_size(info: DisplayInfo | None = None,
                        max_ratio: float = MAX_SCALE) -> tuple[int, int]:
    """按显示器工作区高度推算游戏窗口尺寸，保持竖屏原生比例。

    Args:
        info: 显示器信息；为空则自动获取。
        max_ratio: 允许的最大放大倍数（相对默认 581x1054），超过则钳制，
                   确保在模板匹配容差内。

    Returns:
        (window_width, window_height)，宽/高 ≈ NATIVE_ASPECT。
    """
    if info is None:
        info = get_display_info()

    base_h = 1054
    # 按工作区高度的 92% 作为窗口高度，避免顶到屏幕边缘
    target_h = int(info.height * 0.92)
    # 放大倍数限制在容差区间
    ratio = target_h / base_h
    ratio = min(max(ratio, MIN_SCALE), max_ratio)
    height = int(round(base_h * ratio))
    width = int(round(height * NATIVE_ASPECT))
    return width, height
