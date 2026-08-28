# CHANGELOG

## [2.0.27] 修复合并回归：SellConfig 类定义丢失导致 EXE 启动崩溃

### 改动
- **根因**：合并提交 `1e3ffe3` 解决冲突时误删了 `models/config.py` 中的 `class SellConfig`，但保留了 `AppConfig.sell: SellConfig` 字段引用。两个父分支（`1e3ffe3^1`/`^2`）与 upstream 均完整保留该类，仅合并结果丢失。表现为打包后 `python main.py` 在模块导入期即抛 `NameError: name 'SellConfig' is not defined`，EXE 完全无法启动。
- **修复**：在 `FriendConfig` 之前补回 `SellConfig`（仅文档字符串、无字段，与父分支/upstream 一致）。
- **排查**：用 AST 对比合并提交与两个父分支的全部 `.py` 顶层符号（class/函数/模块级赋值），确认 `SellConfig` 是**唯一**丢失的符号，无其它合并回归残留；诊断脚本用后即删。

### 验证
- `python -c "import main"` 通过（此前在导入期崩溃）；`AppConfig()` 实例化正常。
- 待重新打包：EXE 应能正常启动到 GUI。

## [2.0.26] 多尺度匹配架构优化 + 隐藏 NMS bug 修复 + 离线回归测试

### 改动
- **架构优化①（可配置基准尺度）**：`CVDetector.__init__` 新增 `base_scales` 参数，`bot_engine` 通过 `config.scale_search` 注入；`_priority_scales` 始终把 `base`、配置基准集合与硬编码 `BASE_SCALES` 三者取并集，确保搜索范围永不窄于 `BASE_SCALES`（极端 DPI/缩放仍可微调）。
- **架构优化②（EMA 冷启动预热）**：新增 `_seed_scale_ema()`，在 `load_templates()` 后为每个模板在尺度 `1.0` 预置基线 EMA；首帧即按最优尺度排序，配合匹配层早停跳过全 8 档扫描，加速收敛。
- **架构优化③（收敛重复匹配逻辑）**：删除与 `_match_template_with_scales` 重复的私有方法 `_match_template`；`detect_all`/`detect_category`/`detect_single_template` 三个公开入口统一收敛到 `_match_template_with_scales`，并移除调用方不再需要的 `gray_screen` 局部变量（`detect_quick`/`detect_targeted` 的 `gray_screen` 仍用于各自逻辑，保留）。
- **隐藏 bug 修复**：`_nms` 定义为实例方法却缺 `@staticmethod`，被 `self._nms(results, iou_threshold=0.5)` 调用时 `self` 被当作首个位置参数注入，导致 `iou_threshold` 同时收到位置与关键字值而抛 `TypeError`；`detect_all`/`detect_single_template` 一旦有匹配即崩溃。已补 `@staticmethod`。
- **测试**：新增 `tests/test_cv_detector_scales.py`（无需真实游戏窗口），覆盖尺度集合不截断、EMA 命中排序、`_seed_scale_ema` 幂等、`base_scales` 并集、三个检测入口脱离 `gray_screen` 可运行；已在 `.gitignore` 加例外纳入版本控制。

### 验证
- 全仓 `compileall` 通过；`core/cv_detector.py` 全文 grep 确认无 `_match_template(`（旧 4 参）残留、无重复 `_match_template_with_scales_roi`；lint 清零。
- `python tests/test_cv_detector_scales.py` 全部 PASS。
- 待真实窗口实测：一键务农/收获/浇水/仓库复查在高 DPI 或多实例窗口下稳定命中，CPU 无回归。

## [2.0.25] 多尺度检测漏检根因修复（一键务农/收获/浇水等按钮）

### 改动
- **根因**：`cv_detector._priority_scales` 收敛后只返回 `base` 的前 `_TOP_K=3` 档，而 `base` 常被调用方传成窄集合 `SCALES_FAST=[1.0,0.9,1.1]`（`quick_detect` 默认、bot_engine/land_scan/plant 等内联列表）。按钮一旦落在 0.9~1.1 之外（高 DPI / 窗口缩放），首帧搜不到 → EMA 永远不记录该尺度 → **永久漏检**。这正是"一键务农/收获/浇水"按钮点不到的根因。
- **修复**：`_priority_scales` 不再截断到 `_TOP_K`，改为始终把 `base` 与完整 `BASE_SCALES=[0.8..1.5]` 取并集后按 EMA 降序返回；匹配层 `scale_max>0.95` 早停保证稳态下仍只跑 1~3 档、性能不变。一处修复覆盖 harvest/maintain/popup/friend/targeted/land_scan/bot_engine/plant 全部调用点。
- **死代码**：删除失效的 `_TOP_K` 常量。
- **一致性**：`detect_targeted`/`warehouse_seed_scan` 中重复的完整尺度字面量统一引用 `BASE_SCALES`；bot_engine/land_scan/plant/targeted_prank 的内联窄尺度列表统一为 `BASE_SCALES`/`SCALES_FAST`；`SCALES_FAST` 文档补充"检测器会自动补足完整尺度"；清理 harvest/maintain 未使用的 `SCALES_FAST` 导入及与代码行为不符的误导注释。
- 说明：harvest/maintain 的 `quick_detect` 调用此前未显式传 `scales`，注释却声称已回退全尺度，实际仍走窄集合；根因修复后无需逐点补传。

### 验证
- 改动文件 `python -m py_compile` 通过；全文 grep 确认无 `_TOP_K` 及内联窄尺度残留；lint 清零。
- 待真实窗口实测：一键务农/收获/浇水按钮在高 DPI 或多实例窗口下应稳定命中，CPU 占用无回归。

## [2.0.24] 代码质量清理（等价变换，零行为变更）

参考 `code-quality-sw.md` / `architecture-optimization-sw.md` 两个 skill 对本仓做优化。本版本为**纯等价变换**：删除死代码/重复逻辑、修正误导性注释与可变默认参数、收敛重复常量；功能行为不变。架构层优化建议见 [ARCH_OPTIMIZATION.md](ARCH_OPTIMIZATION.md)（按收益/风险排序，仅建议未直接改代码）。

### 改动
- **死代码**：删除 `models/config.py:get_default_tasks` 中重复且被覆盖的 `repair`/`restart` 条目（隐蔽配置 bug）；删除无调用方的 `base.py:pinch_zoom_out`、`targeted_prank.py:_detect_prankable_by_template`/`_execute_prank`；删除与 `CATEGORY_DEFAULTS` 重复的 `cv_detector._BUILTIN_CATEGORY_DEFAULTS`（调用点 `template_panel.py` 同步改引用）；删除 `land_scan.py` 不可达分支。
- **重复收敛**：`_SCALES_FAST` 三处私有定义统一引用 `BaseStrategy.SCALES_FAST`；`_find_any_name` 三份私有实现统一改用 `BaseStrategy.find_any`。
- **命名/注释/导入**：`farm_state.Action` 裸可变默认 `dict={}` → `Field(default_factory=dict)`；修正 `cv_detector.detect_targeted` 误导性注释；删除未用导入 `friend_name_ocr.numpy`、`server.PILImage`。
- 保留 `land_scan._run_pre_scan_maintain`：CLAUDE.md 明确要求"地块巡查只读桩必须保持 no-op"。

### 验证
- 改动文件 `python -m py_compile` 全部通过；全文 grep 确认无残留引用。
- 待真实窗口实测：多实例启停、买种复查、偷菜/捣乱、大窗口匹配无回归。

## [2.0.23] 多尺度匹配自适应收敛（免重采模板 + 提速）

### 改动
- 针对 v2.0.22 把搜索档从 3 扩到 8（开销约 2.7×）带来的性能回退，新增**按模板历史的自适应尺度搜索**，取代"手动重采模板"的折中方案。
- `core/cv_detector.py` 新增：`BASE_SCALES=[0.8..1.5]`、`_TOP_K=3`、`_FULL_RESCAN_EVERY=200`、`_EMA_ALPHA=0.3`。
  - `CVDetector._scale_ema`/`_scale_hits`：按模板名记录每个 scale 的命中置信度 EMA 与次数（仅在命中时更新，缺席不计罚）。
  - `_priority_scales(name)`：收敛后只返回历史最优前 `_TOP_K` 档并排序（最优档最前，触发早停）；每 `_FULL_RESCAN_EVERY` 次检测强制返回全 8 档扫描，捕捉窗口尺寸漂移（改窗口/换显示器）。
  - 早停由"仅 scale==1.0 且 >0.95"泛化为"任意 scale 命中 >0.95 即停"，使正确档排首位后单档即可结束。
  - `_match_template` / `_match_template_with_scales` / `_match_template_with_scales_roi` 三处均接入选后尺度 + 命中记录 + 泛化早停。
  - `_load_scale_stats`/`_save_scale_stats`：统计持久化到 `templates/scale_stats.json`，实现**跨启动热启动**（下次启动直接收敛，无需重新学习）。
- 效果：运行初期全 8 档跑（约 1~2 帧后收敛），之后每模板每帧仅 ~3 档且常单档早停 → 接近 v2.0.22 之前的速度，同时保留 0.8~1.5 全窗口容差与鲁棒性，且无需人工重采模板。

### 验证
- `core/cv_detector.py` basedpyright lint 清零；`python -m py_compile` 通过。
- 待打包实测：大窗口下匹配应正常且 CPU 占用较 v2.0.22 明显下降；改窗口/换屏后约 200 次检测内自动重新收敛。

## [2.0.22] 窗口尺寸容差放大到 1.5 + 开始/停止/关闭卡顿修复

### 改动
- **A. 放大模板匹配容差上限到 1.5（用户选择）**：
  - `utils/display.py`：`MAX_SCALE` 由 `1.2` 提到 `1.5`（窗口可放到原生 1054 的 1.5×，即约 822×1581）。
  - `core/cv_detector.py`：实时检测 `detect_targeted` 的 `fast_scales` 默认集合由 `[1.0,0.9,1.1]` 扩到 `[0.8,0.9,1.0,1.1,1.2,1.3,1.4,1.5]`；全量多尺度 `_match_template_multiscale` 的 `scales` 同步扩到同集合。
  - `utils/warehouse_seed_scan.py`：两处 `detect_targeted` 的 `scales` 同步扩到 1.5。
  - 风险：每模板每帧多尺度匹配档位由 3 增到 8，匹配开销约 2.7×；如介意性能，推荐在目标窗口尺寸下重采模板（选项 C），使检测器 1.0 尺度即可命中，无需放大搜索范围。
- **B. 开始/停止/关闭卡顿修复**：根因是 `_on_start`/`_on_stop`/`closeEvent` 在 **GUI 线程同步调用** `engine.start()/stop()`；而 `engine.start()` 内含 `time.sleep(2)`+`time.sleep(0.5)`（bot_engine.py:521/524），`engine.stop()` 会循环等待运行中的 Worker 线程结束（可能数十秒，bot_engine.py:580-597），导致界面冻结、点叉挂起。
  - 新增 `gui/main_window._EngineOpThread`（QThread 封装），把 `engine.start/stop` 移到后台线程执行；结束信号回 GUI 线程更新按钮状态。
  - 覆盖：主界面「开始」「停止」、F10 热键停止、关闭窗口（`closeEvent` 后台停止所有引擎并立即 `accept()`，窗口秒关）。
  - 注意：多实例「启动全部/停止全部」(`_on_start_all`/`_on_stop_all`) 仍同步执行（含顺序 5s 等待），本次未改；如需要可后续同样异步化。

### 验证
- 四个改动文件 basedpyright lint 清零。
- 待打包实测：开始/停止/关闭应即时响应（按钮显示"启动中/停止中"而非卡死）；深色+大屏下窗口最大到约 822×1581；模板匹配需重验（尤其 1.3~1.5× 档位）。

## [2.0.21] 原生标题栏跟随深色主题

### 改动
- 修复深色模式下**程序标题栏发白**：根因是 `gui/acrylic.py` 的 `enable_mica()` 早期把 `DWMWA_USE_IMMERSIVE_DARK_MODE` **写死为浅色(0)**；而 qfluentwidgets 的 `Theme` 只影响 Qt 控件，不影响 Windows 原生标题栏，导致开启毛玻璃时标题栏恒白。
- 新增 `gui/acrylic.set_dark_titlebar(hwnd, is_dark)`，按应用主题用 `DwmSetWindowAttribute` 设置原生标题栏暗色模式（Win10 1809+/Win11）。
- `enable_mica()` 不再强制浅色标题栏；`MainWindow._apply_window_material()` 在启用/关闭毛玻璃后统一调用 `set_dark_titlebar()`，覆盖启动（`showEvent` 50ms 兜底）、运行时切主题、实例切换等所有路径。
- 注：状态总览/模板管理里的「手机界面」白块是**游戏实时截图本身**（QQ 农场 UI 本就浅色），属截图内容而非应用外观，应用无法改色；其外层预览卡片/画布背景已是深色主题。

### 验证
- `gui/acrylic.py`、`gui/main_window.py` basedpyright lint 清零。
- 待 `pyinstaller build.spec --clean --noconfirm` 打包实测：深色模式 + 毛玻璃开关下标题栏应为深色；切主题即时生效。

## [2.0.20] GUI 性能优化（启动加速 + 运行时去卡顿）

### 改动
- **启动加速**：`TemplatePanel` 不再在 `__init__` 同步加载全部模板——改为延迟到首次进入模板页（`ensure_templates_loaded()`）或窗口显示 600ms 后兜底加载。
  原逻辑会一次性 `os.listdir` 并为 700+ 模板各构建一个 `TemplateCard` 缩略图控件并解码图片，是启动慢的主因。
  `CVDetector.detect` 自带 `ensure_loaded` 守卫，检测与 UI 加载互不依赖，延迟加载绝对安全；切换实例/编辑模板仍 `force=True` 重载。
- **截图预览去卡顿**：`main_window` 将高频 `screenshot_updated`/`detection_result` 信号合并，仅缓存最新一帧，由 ~10fps 定时器限频刷新；
  预览缩放由 `SmoothTransformation` 改为 `FastTransformation`（预览尺寸小，画质无损且 GUI 线程开销大幅下降）。
- **日志面板去卡顿**：`LogPanel.append_log` 改为入缓冲，`~120ms` 定时器批量渲染，每批仅滚动一次（替代原逐行 `setValue` 滚动）；
  仅在用户已处于底部时自动跟随，过滤/清空逻辑同步修正。

### 验证
- 三处改动文件 basedpyright lint 清零。
- 待 `pyinstaller build.spec --clean --noconfirm` 重新打包实测：启动应明显加快（不再卡在模板列表构建），运行中截图预览与日志滚动应更顺滑。

## [2.0.19] 窗口尺寸自动适配显示器 + GUI 缩放跟随系统

### 改动
- 新增 `utils/display.py`：读取主显示器工作区（物理像素）与系统缩放比（DPI/96），
  按"锁定竖屏原生比例、按工作区高度等比放大、限制在模板容差 0.8~1.2"推算游戏窗口尺寸。
- `models/config.py`：`PlantingConfig` 新增 `auto_fit_window`（默认 true）与 `ui_scale`（默认 0）。
- `main.py`：移除写死的 `QT_SCALE_FACTOR=1.25`，改为 `planting.ui_scale>0` 时用配置值，
  否则跟随系统缩放比（解决高 DPI / 带鱼屏上控制面板过小、且此前固定 25% 放大在非 125% 屏不准的问题）。
- `core/bot_engine.py`：`start()` 在 resize 游戏窗口前，若 `auto_fit_window` 为真，自动计算并写回
  `window_width/height`（仅当与当前值偏离时落盘），使得任意比例显示器启动即正确的竖屏尺寸。

### 验证
- `utils/display.py` 实测得主显示器工作区 `3840x1032`、系统缩放比 `1.5`（150%），窗口推算 `(523, 949)`。
- 全项目 basedpyright lint 清零（含 `models/config.py` 历史 ERROR/重复声明/Any 告警，已局部 `# pyright: ignore` 修复）。
- `pyinstaller build.spec --clean --noconfirm` 重新打包成功，`dist/QQFarmBot.exe` 已生成。

## [2.0.18] GUI 全局缩放 +25%

### 改动
- `main.py`：在入口处设置 `os.environ['QT_SCALE_FACTOR'] = '1.25'`（保留 `QT_ENABLE_HIGHDPI_SCALING=0`）。
  该系数在禁用系统高 DPI 自动缩放的基础上，整体放大多 25%：布局、间距、图标、文字一并等比放大。
- 仅影响本程序控制面板（PyQt6 窗口），不影响游戏窗口采集坐标（后台 PrintWindow 按 hwnd 截图，与 Qt 渲染无关）。
- 可通过环境变量 `QT_SCALE_FACTOR` 覆盖（如临时 `QT_SCALE_FACTOR=1` 还原）。

### 验证
- 已用 `pyinstaller build.spec --clean --noconfirm` 重新打包，`dist/QQFarmBot.exe` 构建成功。

## [2.0.17] 侧边菜单卡死修复（检测失灵 / 一键务农·浇水不点击）

### 问题
日志中出现“检测失灵、卡在某些界面、一键收获/一键务农(含一键浇水)不自动点击”。
根因：游戏侧边菜单（菜单）打开后会遮挡农场主界面，但机器人无法识别也无法关闭该状态：

- `scene_detector.identify_scene` 没有 MENU 场景，`menu_check`（汉堡图标）也不在农场判定指标内。
  菜单打开时画面上仅有 `menu_check` 可见 → 识别结果为 `UNKNOWN` → 主循环直接退出、不做恢复。
- `page.py` 的 `page_menu.links["main"]` 依赖 `menu_goto_main` 模板，但该模板并不存在；
  兜底 `btn_close` 在菜单页也识别不到 → 导航永久卡在菜单页（礼品策略日志中的
  `找不到按钮 ['btn_close','menu_goto_main']` 循环即为此）。
- 菜单一旦打开，`btn_land_right/left`、`btn_harvest`、`btn_一键务农` 全部被遮挡 →
  地块巡查、一键收获、一键务农/浇水全部检测失败（与日志现象完全吻合）。

### 修复
- `core/scene_detector.py`：新增 `Scene.MENU`；当仅 `menu_check` 可见（农场被遮挡）时返回 MENU。
- `core/bot_engine.py`：主循环任务调度新增 `MenuClose`（菜单场景优先收起汉堡）；轻量检查分支也处理 MENU。
  新增 `_task_menu_close`：点击汉堡 `menu_check` 收起侧边菜单，恢复农场主界面。
- `core/ui/page.py`：菜单页返回主页改用始终存在的 `menu_check`（汉堡），移除对缺失模板 `menu_goto_main` 的依赖。
- `core/ui/navigator.py`：关闭弹窗兜底模板加入 `menu_check`，菜单卡死时可点击收起。
- `core/strategies/gift.py`：`_navigate_back_to_main` 在检测到 `menu_check` 时点击收起菜单。
- `tasks/land_scan.py`：`_go_to_main` 前先收起可能打开的侧边菜单，避免锚点检测因遮挡失败。

### 验证
- 后台模式（PrintWindow 按 hwnd 截图，与窗口坐标无关）下，菜单打开时主循环会自检并收起，
  下一轮即回到 `FARM_OVERVIEW` 正常执行收获/务农。
- 农场主界面（含 `menu_check` 与农场指标）仍判定为 `FARM_OVERVIEW`，不会误判为 MENU。
