# QQ Farm Vision Bot

基于 OpenCV 视觉识别的 QQ 经典农场自动化工具。纯本地运行，不读取内存、不修改数据包，支持 PyQt6 GUI、多实例、多窗口后台运行、Web 控制面板、老板键和大小号跨实例协作。

> **项目来源**：基于 [LuckyTiger12138/QQ_Farm](https://github.com/LuckyTiger12138/QQ_Farm) 修改，参考 [megumiss/qq-farm-copilot](https://github.com/megumiss/qq-farm-copilot) / [rainnight6/qq-farm-copilot](https://github.com/rainnight6/qq-farm-copilot) 的部分思路。

**仓库**：[GitHub](https://github.com/LuckyTiger12138/QQ_Farm)

> 本项目主要发布渠道是 [GitHub Releases](https://github.com/LuckyTiger12138/QQ_Farm/releases)，不维护 Gitee 镜像。

## 当前能力

| 分类 | 功能 |
|------|------|
| **农场操作** | 一键收获、特殊作物成熟收获、一键务农（除草/浇水/除虫）、拖拽播种、自动施肥、土地扩建/升级、仓库出售 |
| **播种策略** | 最优经验作物、最高等级作物、指定作物 + 次级作物回退、仓库优先播种、跳过活动作物、种子面板动态翻页 |
| **自动买种** | 商店买种已接入 goods 价格元数据、OCR 价格匹配、名称消歧、仓库格子复查和 `shop_` 模板兜底 |
| **好友系统** | 好友巡查、帮忙、一键务农、偷菜、偷特殊作物、定点偷菜、跨实例捣乱与清理 |
| **多实例** | 每个实例独立配置、日志、截图、任务状态；支持窗口占用保护、窗口序号选择、窗口位置持久化 |
| **大小号通讯** | 大号地块成熟广播，小号自动接收并注入高优先级偷菜任务；支持好友捣乱通知 |
| **自动启动** | 可通过 QQ 农场 `.lnk` 快捷方式自动拉起窗口，并用 OCR 自动选择账号 |
| **窗口监控** | 游戏窗口关闭自动重启；支持黑屏、断网/异地登录、远程登录等异常检测 |
| **恢复与状态** | 任务失败后可按勾选触发 repair/restart，支持限次保护；状态总览显示运行状态、任务队列和下次执行时间 |
| **调试诊断** | 设置面板可开启调试模式，按实例写入 `debug_YYYY-MM-DD.log` 和 `task_trace_YYYY-MM-DD.jsonl` |
| **安全体验** | 后台 PostMessageW 操作不抢占鼠标、F9/F10/F11 全局热键、老板键完美隐藏窗口 |
| **界面工具** | PyQt6 GUI、任务面板、功能开关、模板管理、地块详情、全局设置、可选 FastAPI Web 面板 |
| **模板管理** | 截图绑定 hwnd、多边形采集、阈值调节、批量测试、种子批量导入、采集图标支持 |
| **构建发布** | PyInstaller 打包、GitHub Actions 自动构建发布、自定义 Release Notes |

## 相对上游仓库的增强

本项目基于 [LuckyTiger12138/QQ_Farm](https://github.com/LuckyTiger12138/QQ_Farm) 修改，并参考 [megumiss/qq-farm-copilot](https://github.com/megumiss/qq-farm-copilot) / [rainnight6/qq-farm-copilot](https://github.com/rainnight6/qq-farm-copilot) 的部分思路。相较上游，本仓库在以下方向做了增强或新增（各版本细节见 [CHANGELOG](CHANGELOG.md)，架构优化建议见 [ARCH_OPTIMIZATION.md](ARCH_OPTIMIZATION.md)）：

- **多实例与隔离**：每个 QQ/微信窗口独立 `BotEngine`、配置、日志、截图目录；窗口占用保护避免多开互相抢占。
- **任务调度系统**：基于优先级的 `TaskExecutor`，支持 interval/daily 触发、失败重试、启用时段、配置热更新与跨实例动态任务注入。
- **大小号跨实例协作**：`CrossInstanceBus` 消息总线实现"大号成熟广播 → 小号定点偷菜"与"跨实例捣乱"，含去重与中文 task key `捣乱`。
- **地块巡查与成熟预估**：`land_scan` 两阶段滑动扫描 + OCR 采集等级/成熟倒计时，供大小号通讯；地块详情面板给出升级预估。
- **自动买种增强**：`goods` 价格元数据 + OCR 名称消歧 + 仓库 3×5 格复查与失败冷却的安全阀。
- **窗口监控与异常恢复**：黑屏、断网/异地登录、远程登录检测，窗口关闭自动重启；多 QQ 下 OCR 自动选择账号。
- **界面与体验**：PyQt6 GUI（任务面板/模板管理/地块详情/全局设置）、可选 FastAPI Web 控制面板、老板键与全局热键。
- **GUI 性能**：模板列表延迟加载、截图与日志合并限频刷新、开始/停止/关闭卡顿修复（后台线程）。
- **深色与外观**：原生标题栏跟随深色主题（Mica/Acrylic 暗色模式）。
- **显示适配**：窗口尺寸自动锁定竖屏原生比例，模板匹配容差放大到 **0.8~1.5**，支持 32:9 带鱼屏等任意比例；并引入**多尺度匹配自适应收敛**（按模板历史命中动态收敛尺度顺序，免去重采模板且接近原生速度）。
- **调试诊断**：Debug 日志 + `task_trace_*.jsonl` 调度诊断。
- **工程化**：PyInstaller 一键打包、GitHub Actions 自动构建发布、自定义 Release Notes。

## 环境要求

- Windows 10/11
- Python 3.10+
- PC 端 QQ 或微信，手动打开或配置快捷方式启动 QQ 经典农场小程序
- 任意比例显示器（含 32:9 带鱼屏）：游戏窗口会按桌面工作区高度自动锁定竖屏原生比例，模板匹配稳定

## 快速开始

### 1. 安装

**一键安装**：双击 `setup.bat`，自动安装依赖并创建桌面快捷方式。

**手动安装**：

```bash
git clone https://github.com/LuckyTiger12138/QQ_Farm.git
cd QQ_Farm
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

### 2. 启动

```bash
python main.py
```

热键：

- `F9`：暂停 / 恢复
- `F10`：停止
- `F11`：老板键，隐藏 / 恢复游戏窗口
- 鼠标移到左上角：pyautogui FAILSAFE 紧急停止

### 3. 首次模板检查

进入 **模板管理** 面板：

1. 检查核心按钮、地块、种子模板是否完整。
2. 播种依赖 `seed_` 模板；自动买种 OCR 不稳时会用 `shop_` 模板兜底，购买复查依赖 `ws_` 仓库种子模板。
3. 缺少模板时，用「截屏采集」重新框选；种子图可批量导入：

```bash
python tools/import_seeds.py
```

> 模板建议在自己的设备上采集。分辨率、DPI、平台差异都会影响匹配稳定性。不规则按钮建议使用多边形框选并保存带 alpha 通道的 PNG。

### 4. 运行

点击「开始」后程序会：

1. 找到或启动游戏窗口。

### 窗口尺寸与界面缩放

游戏窗口默认**自动适配显示器**：启动时按桌面工作区高度锁定竖屏原生比例（`581:1054`）等比放大，并限制在模板匹配容差（0.8~1.5）内，
因此无论 16:9、16:10 还是 32:9 带鱼屏都能稳定匹配。相关配置在 `planting` 段：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `auto_fit_window` | `true` | 启动时按桌面分辨率自动推算 `window_width/height`，保持竖屏比例 |
| `window_width` / `window_height` | `581` / `1054` | 仅在 `auto_fit_window=false` 时手动生效 |
| `ui_scale` | `0.0` | 控制面板 UI 缩放比；`0` 表示跟随系统缩放比（如 125% 屏自动放大），`>0` 时强制使用该值 |

> 仅影响本程序控制面板与游戏窗口渲染尺寸，不影响后台截图的采集坐标（按 hwnd 真实像素截图）。

### GUI 性能说明

- 模板管理页模板列表**延迟加载**：启动不再同步构建 700+ 缩略图，进入该页或启动 600ms 后自动加载。
- 截图预览与运行日志均做了**合并限频刷新**，避免高频更新导致控制面板卡顿。
- 若启用「云母/亚克力」毛玻璃效果后仍感觉卡顿，可关闭全局设置中的毛玻璃开关（DWM 模糊在频繁重绘时开销较大）。
2. 调整窗口位置并绑定 hwnd。
3. 循环执行：截屏 → 模板匹配 → 场景识别 → 策略决策 → 前台/后台点击。

## 播种与买种

| 功能 | 当前状态 |
|------|----------|
| **种子面板翻页** | 已支持动态翻页查找目标种子：检测 `btn_seed_select_right.png`，翻页后重新截屏匹配，按钮消失则视为末页 |
| **仓库优先播种** | 可在设置面板开启「仓库优先」，优先从仓库种子列表中选种 |
| **次级作物回退** | 播种策略为「手动指定」时可设置次级作物；首选种子没有或用完时，会优先尝试次级作物 |
| **活动作物过滤** | 支持 `skip_event_crops`，避免策略自动选择活动/特殊作物 |
| **自动买种** | OCR 优先按 goods 单价匹配，名称 OCR 消歧，同价候选不会盲点第一个；失败后回退 `shop_` 模板 |
| **仓库格子复查** | 购买前/后会打开仓库种子页，按 3x5 格子扫描 `ws_作物名`，记录 `slot_index/raw_index/confidence`；复查失败会进入冷却，避免重复误买 |
| **锁定格兼容** | 已预留 `icon_item_locked` / `icon_seed_locked` 锁图标识别，有模板时自动启用；没有锁模板时不阻塞正常买种 |
| **建议配置** | 自动买种仍受商店截图/OCR 影响，识别不稳时先关闭该功能，手动补种；下一阶段会继续补“按仓库序号在播种弹窗选种” |

### 新增作物维护

项目内置 Codex skill：`skills/qq-farm-add-seed/`。它会为特殊作物分配连续 ID，更新 `configs/plants.json`，并创建可替换的 `seed_` / `ws_` X 占位模板：

```powershell
python skills/qq-farm-add-seed/scripts/add_seed.py --repo . --name "新作物"
```

脚本拒绝覆盖已存在的模板，只会为新作物追加禁用项；用户替换为实际截图后，在模板管理中启用对应模板即可。设置面板的作物下拉框由 `plants.json` 动态加载，无需额外修改界面代码。

## 多实例与大小号通讯

程序支持同时运行多个农场实例，每个实例拥有独立配置、日志、截图和任务状态。

### 多实例使用建议

1. 打开多个 QQ/微信小程序窗口。
2. 在右侧实例栏创建或克隆实例。
3. 为每个实例配置窗口选择规则和窗口位置。
4. 分别点击实例启动按钮，或使用全部启动。

窗口选择支持：

- `auto`：自动选择可用窗口
- `index:N`：按窗口序号选择
- hwnd 锁定：实例启动后会尽量复用已绑定窗口，避免抢占其他实例窗口

### 自动启动与选择账号

多 QQ 环境下，配置游戏快捷方式和账号关键词后，程序可自动处理选择账号窗口：

```text
未找到窗口 → 启动 .lnk 快捷方式 → 截取选择账号窗口
→ OCR 匹配账号关键词 → 点击账号 → 点击确定 → 绑定游戏窗口
```

选择账号依赖 OCR。未安装或识别失败时，需要手动选择账号。

### 跨实例偷菜

大号开启「发送成熟通知」，小号开启「接收偷菜任务」后：

```text
大号地块巡查 → 检测即将成熟 → post_alert
→ 小号 TaskExecutor 轮询 → 注入 targeted_steal 高优先级任务
→ 定点访问好友并偷指定地块
```

### 跨实例捣乱

2.0.16 起新增跨实例捣乱链路：

- 发送方识别可捣乱目标后广播请求。
- 接收方注入中文 task key `捣乱`。
- `TargetedPrankStrategy` 执行好友捣乱。
- 消息总线包含去重，避免短时间重复触发同一配对。

## 任务系统

`TaskExecutor` 支持 interval / daily 触发、优先级队列、失败重试、启用时间段、动态任务注入和配置热更新。

默认任务包括：

| 任务 | 说明 |
|------|------|
| `main` | 农场主流程：收获、务农、播种、买种、扩建、升级 |
| `profile` | 个人信息 OCR，采集等级、金币、点券、经验 |
| `friend` | 好友巡查、偷菜、帮忙、特殊作物处理 |
| `land_scan` | 地块巡查，采集普通/红/黑/金/紫晶土地等级、成熟倒计时，供大小号通讯使用 |
| `timed_harvest` | 基于地块巡查倒计时执行轻量收获；不隐式拉起完整主流程 |
| `gift` | QQSVIP 礼包、商城免费商品、邮件领取 |
| `sell` | 仓库批量出售 |
| `task` | 任务奖励领取 / 出售果实入口兜底 |
| `fertilize` | 定时施肥 |
| `share` | 每日分享奖励 |
| `repair` | 任务级修复：重置停止标志、重建窗口上下文、关闭干扰弹窗 |
| `restart` | 任务级重启：释放缓存窗口并重新绑定/启动游戏窗口 |
| `捣乱` | 跨实例好友捣乱任务 |

旧版 `features` 开关会同步到 `tasks.<task>.features`，保持配置兼容。

开启「设置 → 高级 → 启用 Debug 日志」后，每个实例会在 `instances/{id}/logs/` 下生成：

- `debug_YYYY-MM-DD.log`：完整调试文本日志。
- `task_trace_YYYY-MM-DD.jsonl`：任务调度诊断事件，可查看任务开始/结束、时间窗跳过、动态注入、恢复触发等原因。

开启调试模式后，GUI 主界面的**日志面板级别会自动从 INFO 降到 DEBUG**，性能优化中降级为 `logger.debug` 的诊断信息（如 `AppConfig.save` 的写盘/跳过记录、连续相同状态跳过调度等）会重新在界面上实时可见；关闭调试模式后恢复 INFO，避免高频 debug 日志冲垮 GUI 主线程。

## 异常与窗口监控

当前已覆盖：

- 游戏窗口关闭后自动重启
- 多实例窗口占用保护，避免误抢其他实例窗口
- 黑屏检测
- 断网 / 异地登录检测
- 远程登录场景处理
- 商城、任务、邮件、活动返回按钮等干扰页面关闭
- 端午活动返回按钮 `btn_dw_back`
- repair/restart 仅作为失败恢复许可使用：对应任务勾选且恢复配置允许时，才会由失败任务触发；不会按普通 interval 自行重启窗口。
- repair/restart 遵守 `max_repair_attempts` / `max_restart_attempts`，调试模式会记录触发源任务和跳过原因。

## 状态总览

- 状态总览每 500ms 刷新运行状态、任务队列和下次执行时间。
- 操作次数统计和每日动作统计落盘已移除，界面不再显示“操作统计”。

## Web 端控制

设置面板启用 Web 服务后，可访问：

```text
http://localhost:8080
```

功能包括：

- 实时截图预览
- 状态查看
- 启动、停止、暂停、恢复
- 配置编辑
- 最近日志查看

Web 服务依赖 `fastapi` 和 `uvicorn`，在 `requirements.txt` 中作为可选 Web 依赖列出。

## 版本更新摘要

最近主要更新来自 Git 提交记录：

- **v2.0.16**：跨实例捣乱功能、好友捣乱策略、窗口持久化、中文 task key `捣乱` 修复。
- **v2.0.15**：GitHub Actions 自动构建发布、Release Notes 文件机制、直接发布 EXE。
- **v2.0.14**：窗口监控新增断网 / 异地登录检测。
- **v2.0.13**：修复多实例窗口监控过滤误判。
- **v2.0.12**：窗口监控新增黑屏检测。
- **v2.0.11**：多实例窗口占用机制、模板截图绑定 hwnd。
- **v2.0.10**：偷菜策略优化、新增采集图标。
- **v2.0.9**：多实例启动自动选择账号。
- **v2.0.5+**：稀有作物、特殊作物成熟图标、特殊作物偷菜、等级输入上限扩展。
- **v2.0.4**：一键务农合并除草/浇水/除虫，新增活动作物。
- **v2.0.0**：多实例、任务调度、模板与种子/商店/仓库体系大规模升级。

## 近期修复记录（高 DPI 截图与稳定性）

相对上游的核心 bugfix 已通过 PR #11 提交（保守版：不含 `AGENTS.md`，`auto_start` 默认关闭）。每点含「修改前问题 → 为什么改」：

- **`main.py` DPI 感知（核心）**：修改前进程 DPI Unaware，150% 缩放下 `GetWindowRect` 返回逻辑像素 `563×1026`，`PrintWindow` 截图只截到左上角约 2/3，底部工具栏（一键务农 / 仓库 / 商店 / 图鉴 / 装扮 / 好友）整排被裁，相关按钮永远检测不到、任务永不触发；`btn_一键务农` 最佳置信度仅 0.46。改为所有 Qt 导入前 `SetProcessDpiAwareness(2)`（回退 `SetProcessDPIAware`），`GetWindowRect` 变物理像素 `844×1539`，置信度 0.46→0.94 并真实点击走完流程。
- **`core/scene_detector.py` 提前算 `has_land`**：修改前自己农场被 `friend_check` 误判为好友列表，导致依赖 `FARM_OVERVIEW` 的任务（一键务农、偷菜）永不触发；改为基于 land 锚点提前判定。
- **`core/window_manager.py` 窗口自愈**：修改前窗口被拖出屏幕后点击全落空、场景检测死循环；改为检测到窗口中心离屏自动拉回可见区域。
- **`core/bot_engine.py` 每轮同步 rect/handle**：修改前窗口运行中移位 / 缩放后缓存过期、点击坐标错位；改为每轮重取窗口 rect/handle。
- **`tasks/land_scan.py` 锚点 plausibility + 种植状态**：修改前误识别锚点通过成对间距校验导致网格歪到仓库 / 商店区误点，已种植分支仅凭 `not countdown` 误标 `need_planting`；改为锚点位置合理性校验（单边偏离丢弃、双边不可信跳过本轮，宁可漏扫不误点）+ 已种植分支「无倒计时且无作物状态」才标不需种植。
- **`core/strategies/plant.py` 空地网格校验 + 阈值自适应**：修改前只按模板名（`land_*`）过滤候选导致误点已种植地块，且像素阈值（400/45）硬编码在 DPI 修复后失配；改为每个 `land_empty` 中心须落在最近真实地块中心 ±45px 内，阈值按基线帧（`581×1054`）比例缩放 `_scale`，适配任意 DPI / 分辨率。
- **`gui/main_window.py` + `models/config.py` `auto_start`**：修改前启动 exe 需手动点「开始」；新增 `auto_start` 配置，**默认关闭**（避免无值守自启，用户可显式开启）。
- **`core/debug_capture.py`**：运行时按场景 / 标签保存截图 + 结构化 JSON，供排查模板匹配。
- **`build.bat`**：修正 onefile 产物验证路径（原按 onedir 校验必失败）。
- **`templates/btn_一键务农.png`**：更新模板适配 DPI 修复后的更清晰画面。

## 代码质量与 Lint

项目使用 `ruff` / `pyflakes` 做静态检查。本轮清理聚焦**确定性、零风险的真实缺陷**，未做大规模风格重构：

- **未使用导入（F401）**：删除 `bot_engine.py`、`task_panel.py`、`land_scan.py` 等多处冗余 `import`；为 `core/strategies/__init__.py` 添加 `__all__` 保留包级公开 API（供 `from core.strategies import X` 使用），而非删除再导出。
- **未使用变量（F841）**：删除 `current_state`、`shadow`、`cat_color`、`color`、`found_planted`、`seed_id`、`paths`、`inv` 等死变量。
- **无占位符 f-string（F541）**：将误用 f 前缀的常量字符串还原为普通字符串。
- **未定义名称（F821）**：恢复被误删的 `QSizePolicy` 导入（`template_panel.py` 实际使用了它）。
- **字典重复 key（pyflakes）**：`AppConfig` 默认任务表 `repair` / `restart` 各重复定义一次，后值覆盖前值；删除重复项，每个任务 key 唯一。
- **重复定义（pyflakes）**：`main_window.py` 的 `closeEvent` 被定义两次，后者覆盖前者导致多实例引擎未被停止；保留含多实例停止逻辑的版本，删除早期重复定义。`SellConfig` 重复类定义已合并为一份。

可选依赖探测导入（如 `friend_name_ocr.py` 的 `OCRItem` / `OCRTool`）用于设置 `HAS_OCR` 可用标志，属有意保留，已加 `# noqa: F401` 标注。

## 已知限制

- 自动买种已加入价格校验和仓库格子复查，但商店商品识别仍需真实窗口实测；建议保留 `shop_` 模板兜底，识别不稳时关闭自动买种。
- 高 DPI 屏幕已通过进程级 `PROCESS_PER_MONITOR_DPI_AWARE`(见 `main.py`)修复坐标虚拟化:截图按物理像素采集,不再因 DPI 导致底部工具栏被裁 / 按钮检测不到。仍建议标准比例显示器以保证模板匹配稳定。
- OCR 功能受窗口缩放、字体渲染、截图质量影响，选择账号、个人信息、地块巡查、买种均可能需要实测；紫晶土地依赖 `icon_land_amethyst.png` 模板和 OCR 文本/颜色兜底。
- 后台模式使用 Windows 消息模拟，部分微信/QQ 容器版本可能表现不一致。

## 项目结构

```text
qq-farm/
├── main.py                    # 程序入口，GUI / Web 生命周期
├── core/                      # 核心引擎
│   ├── bot_engine.py          # 主控编排、任务入口、跨实例注入
│   ├── action_executor.py     # 前台 / 后台操作执行
│   ├── cv_detector.py         # OpenCV 模板匹配
│   ├── scene_detector.py      # 场景识别
│   ├── cross_instance_bus.py  # 跨实例消息总线
│   ├── task_executor.py       # 异步任务调度
│   ├── window_manager.py      # 窗口查找、启动、选择账号、老板键
│   └── strategies/            # 各类策略
├── tasks/                     # 独立任务模块，如地块巡查
├── gui/                       # PyQt6 界面
├── web/                       # FastAPI Web 控制面板
├── models/                    # 配置、状态和作物数据模型
├── utils/                     # OCR、日志、路径、地块网格、统计等工具
├── configs/                   # 配置模板、作物数据、UI 文案
├── templates/                 # 模板图片与阈值
├── tools/                     # 模板采集、种子导入等工具
├── skills/                    # 项目内维护的 Codex 技能
└── .github/                   # GitHub Actions 与 Release Notes
```

## 常见问题

**找不到游戏窗口？** 确保小程序已打开；或配置 `.lnk` 快捷方式让程序自动启动。

**多实例选错窗口？** 优先使用每个实例独立窗口选择规则；启动后 hwnd 会绑定，避免其他实例抢占。

**播种找不到种子？** 检查 `btn_seed_select_right.png` 和目标 `seed_*.png` 模板；动态翻页依赖翻页按钮模板。

**自动买种不灵敏？** 检查 OCR 依赖，重新采集目标 `shop_*.png` 与 `ws_*.png` 模板，并测试阈值；仍不稳定时先关闭自动买种。

**模板匹配不准确？** 使用模板管理重新采集；不规则图标建议多边形框选。

**游戏意外关闭或黑屏？** 窗口监控会自动检测并尝试重启；多实例场景下会避免占用其他实例窗口。

**晚上/后台任务没按预期执行？** 打开调试模式后查看 `instances/{id}/logs/task_trace_YYYY-MM-DD.jsonl`，重点看 `task_out_of_time_range`、`task_start`、`task_finish`、`prank_task_skipped`、`recovery_task_skipped`。

## License

MIT

## 免责声明

本项目仅供学习研究 OpenCV 视觉识别、桌面自动化和 PyQt6 工程实践使用。自动化操作可能违反游戏服务条款，由此产生的一切后果由使用者自行承担。
