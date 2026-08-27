# 架构与代码质量优化建议

本文档配合两个软件工程通用 skill 产出：

- `code-quality-sw.md`：**等价变换**（命名/注释/死代码清理），要求功能行为不变、逐模块验证。
- `architecture-optimization-sw.md`：**仅输出建议**，按"收益/风险比"排序，不直接改代码；落地时遵循 README/AGENTS 的"通用约束"（最小改动 + 逐点验证）。

本仓库无 pytest 套件（测试脚本需真实游戏窗口，已排除），故等价变换以 `python -m py_compile` + 全文引用搜索做机械化验证。

---

## 一、已完成的代码质量优化（v2.0.24，等价变换，零行为变更）

通过子代理全仓扫描 + 引用核验，已落地的清理（详见 [CHANGELOG](CHANGELOG.md) v2.0.24）：

### 死代码清理
- `models/config.py:get_default_tasks`：删除重复且被 dict 覆盖的 `repair`/`restart` 条目（第一份定义的 `interval_seconds` 永远静默失效，是隐蔽配置 bug）。
- `core/strategies/base.py`：删除无调用方的 `pinch_zoom_out`。
- `core/strategies/targeted_prank.py`：删除无调用方的 `_detect_prankable_by_template`、`_execute_prank`。
- `core/cv_detector.py`：删除与 `CATEGORY_DEFAULTS` 完全重复的 `_BUILTIN_CATEGORY_DEFAULTS`（调用点 `template_panel.py` 同步改引用）。
- `tasks/land_scan.py`：删除 `cv_img` 已被前序判断保护后不可达的冗余分支。
- 保留 `_run_pre_scan_maintain`：CLAUDE.md 明确要求"地块巡查只读桩必须保持 no-op"，故**不删**。

### 重复代码收敛
- `_SCALES_FAST` 三处私有定义（`targeted_steal`/`targeted_prank`/`friend`）统一改为引用 `BaseStrategy.SCALES_FAST`。
- `_find_any_name` 三份私有实现（steal/prank/friend）统一改用基类 `BaseStrategy.find_any`（语义完全一致）。

### 命名 / 注释 / 导入
- `models/farm_state.py`：`Action` 的裸可变默认参数 `dict = {}` 改为 `Field(default_factory=dict)`，避免实例间状态共享。
- `core/cv_detector.py`：修正 `detect_targeted` 中"只试 3 个尺度而非 5 个"的误导性注释（实际为 0.8~1.5 全集合）。
- `utils/friend_name_ocr.py`：删除未使用的 `import numpy as np`。
- `web/server.py`：删除未使用的 `from PIL import Image as PILImage`。

> 扫描结论：本仓局部变量命名整体良好，无"i/j 之外、含义不明的 ≤3 字符变量"需强制重命名；全仓裸 `except` 0 处。

---

## 二、架构优化建议（仅建议，按收益/风险排序）

### 1. 多尺度匹配自适应收敛 —— 已实现（v2.0.23）
- **现状**：`core/cv_detector.py` 按模板名记录每尺度命中 EMA + 次数，收敛后只跑历史最优前 3 档并排序触发早停；每 200 次检测强制全 8 档重扫捕捉窗口漂移；统计持久化 `templates/scale_stats.json` 跨启动热启动。
- **收益**：大窗口下匹配接近原生速度，且保留 0.8~1.5 全窗口容差，免手工重采模板。性能大收益、风险低。
- **可继续**：`detect_quick` 目前固定 scale 1.0 单尺度（快速预判 API），可同样接入窄带/自适应，避免非原生窗口尺寸下漏检。

### 2. `plant.py` 定向检测样板收敛 —— 维护性，中收益/中风险
- **现状**：`PlantStrategy` 内 `cv_detector.detect_single_template(...)` 调用约 40+ 处，模板名+阈值+截屏样板高度重复，未复用 `BaseStrategy` 已有的 `quick_detect`/`quick_capture` 封装。
- **方案**：在 `BaseStrategy` 新增 `detect_one(name, rect=None, threshold=None)`，统一"截屏↔定向检测"样板；plant/friend/steal/prank 统一调用。
- **收益**：降低重复、集中阈值/异常处理逻辑；**风险**：调用点极多，需逐点验证语义未变（尤其 ROI 坐标映射）。

### 3. `detect_all` / `detect_category` / `detect_single_template` 后处理重复 —— 维护性，低收益/低风险
- **现状**：三方法尾部均有几乎相同的"异常过滤 + NMS + 按置信度排序"代码。
- **方案**：抽取 `_postprocess(results)` 公共方法收敛。纯等价重构，风险低。

### 4. 自动买种 OCR/定位瓶颈 —— 算法/资源，高收益/高风险
- **现状**（已知限制）：商店商品定位与 OCR 灵敏度不足，是自动买种主要瓶颈；已有价格校验 + 仓库 3×5 格复查 + 失败冷却安全阀。
- **方案**：落地"按仓库序号在播种弹窗翻页选种"，减少对 OCR 命名的强依赖；评估商品 ROI 模板比对替代全图 OCR。
- **收益**：买种稳定性显著提升；**风险**：需真实窗口实测校准。

### 5. 配置预留开关清理 —— 低风险
- **现状**：`stuck_seconds`、`level_ocr_enabled`、`wechat_mouse_guard_enabled`、`virtual_desktop_enabled` 等带"预留"注释但全仓无读取点（部分在 `models/config.py`）。
- **方案**：确认不再需要后删除，或集中标注 `reserved` 避免误判为功能开关。

### 6. 依赖与构建 —— 中收益/低风险
- **现状**：已排除 `torch`/`torchvision`/`easyocr`；`rapidocr_onnxruntime` 仍是较重的 OCR 依赖（`build.spec` 单独拷贝其 `models`/`config.yaml`）。
- **方案**：评估直接用 `onnxruntime` 推理替代 `rapidocr` 上层封装以减少体积；或按需懒加载 OCR 子进程。

### 7. 并发模型 —— 高收益/高风险
- **现状**：每实例 `BotWorker(QThread)` 在独立线程执行任务，但 OCR（`rapidocr`）为 CPU 密集型且受 GIL 限制，会在任务线程内阻塞。
- **方案**：将 OCR 调用迁移到进程池（`concurrent.futures.ProcessPoolExecutor`），避免阻塞任务线程、提升多实例吞吐。
- **风险**：跨进程传递截图（ndarray）与结果需序列化，需评估拷贝开销。

---

## 三、验证方式

- 等价变换：每个文件 `python -m py_compile` + 全文 `grep` 确认无残留引用（已执行，通过）。
- 功能：无自动化测试，需在真实游戏窗口中实测：多实例启停、买种复查、偷菜/捣乱、地块巡查、大窗口（32:9）匹配。
- 性能：对比 v2.0.22 与 v2.0.23+ 在大窗口下的 CPU 占用与单帧匹配耗时。
