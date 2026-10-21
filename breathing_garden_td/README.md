# 呼吸的花园 / The Breathing Garden

这是可运行的 TouchDesigner 2D 互动原型：真实、持久的菌丝枝条由独立 Python 世界模拟，
不是 Feedback TOP 残影。识别模型不在本项目内，现有手部和面部追踪只负责七个输入通道。
没有用户时，枝条仍继续生长、衰老；星尘漂浮，最终回到安静的黑暗。

## 1. 环境与入口

- 本机实测：macOS、Apple Silicon、TouchDesigner **2025.33070**。
- 建议使用同版本或更新的正式版本；旧版本存在参数差异，builder 会明确报错而不是静默跳过必要配置。
- 标准 Python 引擎要求 Python 3.9+；推荐 Python 3.11+。只用标准库，无 pip 依赖。
- 输出 1280×720；正交相机宽 2，世界范围 X = [-1,1]，Y = [-0.5625,0.5625]。
- 目标显示 60 FPS，模拟与 SOP 重建 30 Hz；最终速度取决于设备和追踪系统。
- TouchDesigner Non-Commercial 在本原型分辨率内可使用，但商业用途应遵守授权。
- `.toe` 若已交付，可直接打开 `The_Breathing_Garden.toe`；默认 TEST_MODE，不调用摄像头。

本次已实际保存该 `.toe`，关闭 TD 后重新打开，**33 项内部检查全部通过**。
报告为 `qa/td-reopen-validation.json`；七个内嵌 DAT 与交付源码的一致性检查为
`qa/embedded-source-check.json`。TD 自动保存的 `.1.toe` 是同内容的编号版本，
直接打开不带编号的入口文件即可。

## 2. 文件说明

| 文件 | 用途 |
|---|---|
| `garden_engine.py` | 纯 Python 固定步进、输入清洗、枝条、开花、消散、生命周期、渲染路径 |
| `build_garden_td.py` | **自包含成品 builder**，内嵌全部引擎/回调，不依赖磁盘路径 |
| `builder_template.py` / `pack_builder.py` | builder 开发源码及机械打包器；普通使用不需要运行 |
| `branches_sop_callbacks.py` | Script SOP 的真实线段、花瓣、星尘几何及 Cd RGBA |
| `frame_execute_callbacks.py` | TD 每帧入口与异常报告 |
| `garden_runtime.py` | CHOP 输入、30 Hz 世界更新、60 FPS TOP 链和诊断桥接 |
| `stage3_tracking_adapter.py` | 可选：适配仓库已有第三阶段 landmark CHOP；不加载识别模型 |
| `reset_controls.py` | 自定义 Reset 参数的 Parameter Execute DAT 回调 |
| `validate_garden_td.py` | TD 内部节点/材质/相机/回调/输出检查 |
| `tests/` | 引擎单元测试、自包含 payload 一致性和 Python 语法检查 |
| `td_integration_tests.py` | 显式执行的 TD 集成测试；会重建花园，不要在演出中运行 |
| `td_performance_monitor.py` | 显式执行的本机性能采样，不包含在最终演示网络 |
| `qa/` | 实际测试报告、输出预览；`bootstrap/` 为临时测试工程，不是交付入口 |

`qa_bootstrap.py` / `prepare_td_qa.py` 仅供本机自动集成测试，包含本机 QA 目录。
**可移植成品是 builder 和保存后的最终 `.toe`，它们不依赖这些 QA 文件。**

## 3. 在 TouchDesigner 中运行 builder

1. 打开一个包含 `/project1` 的标准工程，先保存自己的现有工程。
2. 在任意位置创建 **Text DAT**。把 `build_garden_td.py` 的**完整内容**复制进去。
3. 右键该 DAT，选择 **Run Script**。不要粘到 Script SOP 的参数栏，也不要仅导入为模块。
4. 开始播放时间线，建议工程帧率 60。builder 不修改 `/project1/garden` 外部的节点与时间设置。
5. 等待几秒，打开 `/project1/garden/out1` 的 Viewer。

builder 会自动创建输入、所有 DAT、Geometry/Camera COMP、Script SOP、Line MAT、
Render TOP、Bloom TOP、Null TOP，设置全部回调、材质、Render/Display Flag 和分辨率。
保存 `.toe` 后这些 DAT 的脚本均内嵌在工程内，无需外部 Python 文件。

重复执行会重建自己拥有的节点，重置花园并回到 TEST_MODE，不生成 `garden1/garden2`。
未知的用户节点保留；已有 Livechop 路径保留，但自定义参数的其它调节值会回到默认。
若 `/project1/garden` 已存在且并非本 builder 创建，脚本会停止，要求先重命名，避免覆盖用户内容。
不要把 builder 的 Text DAT 放进 builder 拥有的子节点中；放在 `/project1` 或花园的自建 Text DAT 即可。

## 4. 测试模式与最终画面

选中 `/project1/garden/garden_controls`，切到自定义 **Garden** 参数页：

- **Input Mode = TEST_MODE**：默认模拟，24 秒循环，包含绘制、停留、捏合/释放、第二段绘制和暂时丢失追踪。
- **Input Mode = LIVE_MODE**：读取自己的真实输入；切换时断开笔画，避免跨坐标源连线。
- **Reset garden**：清空生命，按 Seed 重现模拟。
- **Development diagnostics**：默认关闭；开启后 `diagnostics` DAT 每秒更新统计，不叠加到最终输出。

右键 `out1` → **View** 查看完整画面。需要显示器全屏时，把 Window COMP 的 Operator 指向 `out1`，
再打开该窗口；或在 Perform 布局中只展示这个 TOP。输出不包含按钮、HUD、网格、摄像头背景或指导文字。
本次构建不自动进入全屏，避免占用用户桌面。

## 5. 接入自己的七通道 tracking CHOP

将 `/project1/garden/garden_controls` 的 **Live Tracking CHOP / Livechop** 指向现有 CHOP 的绝对路径，
例如 `/project1/my_tracking/OUT_GARDEN`，再切到 LIVE_MODE。
不需要修改生长引擎。不要把 Livechop 指回 `null_tracking` 或其下游，这会造成循环。

| 通道 | 范围/含义 | 缺失行为 |
|---|---|---|
| `tip_u` | 0–1，左到右，食指尖而非手腕 | 没有坐标则按未追踪处理 |
| `tip_v` | 0–1，**顶部为 0** | 引擎内部仅翻转一次 Y |
| `tracked` | 0/1，有效手部 | 缺失为 0，立即断开当前笔画 |
| `draw` | 0/1，食指正在绘制 | 缺失为 0 |
| `pinch` | 0/1，捏合保持 | 缺失为 0；追踪丢失本身不会触发释放 |
| `mouth` | 0–1，张嘴程度 | 缺失平滑回到基础呼吸 |
| `smile` | 0–1，微笑程度 | 缺失平滑回到冷薄荷色 |

追踪可输出镜像坐标，但应在适配层统一镜像，不要在引擎内二次翻转。
每个 CHOP 一组通道驱动一个交互指尖。双手识别可以在上游选定一只手；切换手时最好先输出 `tracked=0` 一帧。
协议只有一个 tracked，因此无法区分“手势通道暂时缺失”和“用户主动松开捏合”；接入层应始终输出完整的手势通道。
建议在丢帧、设备断开、数据超时（例如 0.2 秒）时主动输出 tracked=0，不要无限保持旧数据。

### 复用本仓库第三阶段追踪

已检查 `touchdesigner/stage3_bootstrap.py` 和旧工程：手部关键点来自
`/project1/hand_tracking/normalized_data`，面部动作单元来自
`/project1/face_tracking/blend_shapes`。旧版手部 helper 已翻转过 Y。

在第三阶段工程中运行 builder 后，若发现上述手部 CHOP，会自动把 Livechop 指向
`/project1/garden/stage3_adapter`。该 Script CHOP 使用 index_finger_tip、thumb_tip、wrist、
middle_finger_mcp、index_finger_pip，推导食指伸展和相对掌长的捏合状态；嘴巴读 `jawOpen`，
微笑读左右 `mouthSmile` 的均值。它不启动模型、不改动追踪节点，也不将表情解释为心理状态。

参数 `Handsource`、`Facesource` 可改源路径；`Adapterflipy` 默认开启，适配旧 helper 的 bottom-up 坐标。
如果用原始 MediaPipe top-down 数据，关掉这个开关。没有追踪源时适配器输出有效的七通道空状态。
这是可选接入适配器，最终单机演示 `.toe` 不包含原第三阶段摄像头/MediaPipe 工程。

## 6. 交互和生命周期

- 绘制：坐标指数平滑，世界距离每 .009 采样；沿轨迹每 .125 世界单位播种自主生长端点。
- 生长：30 Hz 固定步进，出生 .45 秒后启动，继承方向、微弯曲、随机扰动，分叉深度最多 3。
- 停留：draw 有效、未捏合，半径 .024 内稳定超过 .72 秒触发；手势去抖约 .067 秒另计。
  同一次停留只触发一次，离开该小范围后才可再次触发。花朵连接到已有植物的最近锚点，六瓣约 1.7 秒展开。
- 捏合释放：稳定的 1→0 边沿，查找半径 .13 内最近生命，让它在 3.8 秒内平滑消散；释放 30–70 个微粒。
  粒子逐渐减速，有缓慢漂移和透明度衰减，3.8–6.5 秒后删除。预算满时数量可能少于 30。
- 呼吸：周期 5.2 秒，mouth 只调振幅；smile 慢慢改变薄荷到略暖的比例，不做真实情绪诊断。
- 生命：默认 48 秒完整生命 + 13 秒平滑衰减。预算压力使最老生命优先在 4.5 秒内柔和退场。
- 追踪丢失或单步跳跃 > .26 世界单位会断笔；恢复从新位置开始，不连接旧位置。

植物数量包含正在消散的生命。达到 9 株时最多保留一个待播种位置，等旧生命退场后补种；
不会无限排队，也不会因旧枝条长期占满预算使新生命永久无法生长。

## 7. 调整生长、颜色、透明度和光效

日常调节直接使用 `garden_controls`：Growstep、Branchprob、Lifefull、Lifefade、Brightness、
Linewidth、Bloom。Seed 和 Quality 在 Reset / 改档后生效；其它数值运行中更新。

更深入修改 `garden_engine.py` 的 `Config` 和调色常量，然后运行：

```bash
python3 breathing_garden_td/pack_builder.py
```

把新 builder 再运行一次；只改磁盘引擎文件不会自动修改已经内嵌的 DAT。
临时试验也可直接编辑 TD 的 `garden_engine` DAT，然后按 Reset；重跑 builder 会覆盖这些临时编辑。

主要预算（NORMAL / LOW）：

| 参数 | NORMAL | LOW |
|---|---:|---:|
| MAX_PLANTS | 9 | 9 |
| MAX_TOTAL_SEGMENTS | 2300 | 1400 |
| MAX_SEGMENTS_PER_PLANT | 660 | 440 |
| DUST_COUNT | 190 | 150 |
| MAX_PARTICLES（不含固定星尘） | 460 | 290 |
| MAX_TIPS_PER_PLANT | 32 | 20 |
| MAX_FLOWERS_PER_PLANT | 4 | 3 |

线段上限包含绘制笔画与自主生长；花瓣是独立且有上限的几何，诊断 segments 不计入花瓣和星尘。
色值集中于 BACKGROUND、MINT、OLD、WARM、HIGHLIGHT；透明度在 `paths()` 内控制，
自然/主动退场透明度由 `opacity()` 控制，出生亮度使用平滑渐入。

SOP 总是输出 **Cd RGBA**。TD 2025 的 GPU 渲染属性名是 **Color**，builder 保留工厂默认的
GPU 色属性绑定；旧版本可用 Cd。不要在新版本上把 Line MAT 强改成 Cd，
否则可能全部变白且 Alpha 失效。Bloom 很轻，不应通过高强度 Bloom 掩盖枝条结构。

Alpha 使用经 GPU 数值测试的直通 RGB + `srcblend=sa` / `destblend=omsa`。
MAT 的 `pointcolorpremult=alreadypremult` 在这里用于禁用着色器再次乘 Alpha，
`postmultalpha=False`，在帧缓冲混合阶段统一应用一次 Alpha，并单独混合输出 A。
避免 TD 2025 颜色转换和着色器预乘共同使微弱星尘过暗。测试以两条等长线段比较，
输入 Alpha=.25 时亮度比例应接近 .25，而非 .06。

## 8. TD 内部诊断与故障处理

在 Textport 执行：

```python
op('/project1/garden/validate_garden').module.validate()
```

报告写入 `diagnostics` DAT，检查必需节点、通道、Cd、材质/Alpha、正交相机、几何、分辨率、TOP 连接和 OP 错误。
持续运行状态在 `garden.fetch('metrics')`；每秒更新 FPS、植物/线段/粒子/花朵数、SOP cook time。
builder 的参数存在性检查和非关键兼容信息在 Textport 与 `build_log`。

| 现象 | 检查/处理 |
|---|---|
| Run Script 无反应 | 确认完整复制 **生成后的** build_garden_td.py，不是 builder_template.py；查看 Textport |
| `/project1/garden` 已存在冲突 | 先重命名自己的同名 Base COMP；不要删除不明工程 |
| 参数不存在 / 菜单值无效 | 报错含路径、参数和 TD build；更新到实测版本，或在模板中按实际 API 添加兼容分支后重打包 |
| 只有星尘，没有植物 | 时间线需播放；先用 TEST_MODE。LIVE 时检查 tracked/draw、坐标和 Livechop 路径 |
| 画面全黑 | 查看 render1、branches_sop 的 Errors；检查相机 tz=5、Ortho Width=2、geo material 和 SOP Render Flag |
| 枝条全白或消散不生效 | 检查 Line MAT 的 GPU 色属性 Color/Cd、直通RGB/sa混合、blending，运行诊断 |
| 摄像头权限错误 | 本项目不调用摄像头；先在已有识别工程中解决，再验证七通道输入 |
| 手向上移动却向下画 | tip_v 必须顶部为0；旧第三阶段适配器开 Adapterflipy，原始 MediaPipe 数据关闭它 |
| 拒绝识别/手切换后断笔 | 这是防错误长线的预期保护；检查上游身份保持和 tracked |
| Callback 名字错误 | 必须是 Script SOP 的 callbacks 参数指向其回调 DAT，不要将代码粘进 SOP 参数表达式 |
| TD 提示缺少外部文件 | 最终 builder/TOE 不依赖外部脚本；不要把 qa/bootstrap/Garden_QA.toe 当作成品打开 |

## 9. 性能保护与验证范围

没有逐帧创建 OP，没有逐帧文件读写、全量深拷贝、无限点列表或无界事件队列。
世界固定步进最多补 .25 秒，超过的停顿时间丢弃并计入 dropped_seconds，避免卡顿后长时间追帧。
SOP 30 Hz 重建，TOP 渲染链逐帧运行；Python 中的世界计算和几何生成严格分离。
以 30 Hz 更新的几何采用新生线段透明度渐入，不声称是 60 Hz 几何插值。

优先手动选择 LOW。开启 Autolow 时，持续约 8 秒估计 FPS 低于 42，将目标线段/端点/粒子预算调低、
AA 调成 2x，并让超额老生命退场；不重置世界，不突然删除枝条。现存几何/粒子可能在退场期间暂时高于新的目标预算。
自动降档不会清空已有星尘；若需150个星尘，请手动选 LOW（该操作会重置世界）。
关掉不必要的网络 Viewer、减少外部追踪分辨率、降低分叉概率/线段上限比增加 Bloom 更有效。

纯 Python 测试（在仓库根目录）：

```bash
python3 -m unittest discover -s breathing_garden_td/tests -v
```

包含空输入、移动绘制、停止后自主生长、停留阈值/一次触发/连接结构、捏合渐散、追踪丢失/跳跃、
预算公平和上限、生命周期、越界/NaN、缺失面部、30/60/120 FPS 固定输入复现、6 分钟内存采样，
以及内嵌源码一致性和语法检查。内存测试证明该时段缓存受限，不等同于无限时长无泄漏证明。

本次 Python 3.11.15 实际运行 **21 项全部通过**；耗时约 8.6 秒。
也可用 `python3 breathing_garden_td/run_tests.py` 执行并生成 `qa/python-tests.json`。

`qa/td-integration-tests.json` 是实际 TD 测试：粘贴运行、重复建图、保护外部节点、模拟 LIVE 输入路由、
Y 翻转、可选适配器空输入、开花/消散、GPU 像素颜色及全网诊断。
`qa/td-validation.json` 为节点快照，`qa/garden-preview.png` 为真实 Render TOP 输出；不是预渲染输入。
性能报告如存在，为本机一段模拟输入实测，不能视为任何设备和真实摄像头识别下的 60 FPS 保证。
最终本机约 40 秒 NORMAL 测试平均约 60.01 FPS，P95 帧时约 23.50 ms，
平均 SOP cook 约 4.79 ms，P95 SOP cook 约 6.74 ms，观测最多 1700 条植物线段。
并非每一帧都在 16.67 ms 内，也没有在实际摄像头识别负载或所有2300线段场景下作出保证。
详见 `qa/td-performance.json`。TD 集成测试实际 **19 项全部通过**。

仍需现场验证：真实 webcam 输入与延迟、食指/捏合阈值、手身份切换、镜像方向、投影亮度与观看距离、
外部 MediaPipe 同时运行时的帧率，以及目标机器的长时间展览稳定性。其它 TD 构建版本未全部验证。

## 10. 架构与扩展

花园节点由 builder 自动创建；相对目标结构新增 `garden_runtime` 用于 TD 桥接，`input_defaults`
用于无追踪安全回退，`stage3_adapter` 用于可选既有工程接入，`validate_garden` 和 `build_log` 用于诊断。
`branches_sop_callbacks` 是 `geo_growth` 下与 SOP 同级的 DAT，不是 SOP 的子节点（SOP 不能包含子 OP）。
实际路径 `/project1/garden/geo_growth/branches_sop_callbacks`。

所有位置、年龄、分叉、花朵、消散粒子都在 Garden 实例中；换渲染器只需使用 `paths()` 或读取数据类。
若扩展到多机或沉浸式，可复用此引擎和输入协议，另写投影/拼接输出，不必改识别库。

参考核对的 Derivative 官方文档：[Script SOP](https://derivative.ca/UserGuide/Script_SOP)、
[Line MAT](https://derivative.ca/UserGuide/Line_MAT)、[Camera COMP](https://derivative.ca/UserGuide/Camera_COMP)、
[Render TOP](https://derivative.ca/UserGuide/Render_TOP)、[Bloom TOP](https://derivative.ca/UserGuide/Bloom_TOP)、
[Parameter Execute DAT](https://derivative.ca/UserGuide/Parameter_Execute_DAT)。实际参数同时在本机 TD 中检查。
