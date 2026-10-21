# 呼吸的花园 · Mac / Windows 真实摄像头测试版

## Windows 1.1.1 测试版

支持 Windows 10/11 **x64**，建议 Windows 11；此包不是 Windows ARM64 原生构建。
独立运行，不需要安装 Python、TouchDesigner，也不需要联网下载识别模型。
保留 1.1 的增强光色、30%–220%亮度调节和可隐藏的互动指引。
内置 Noto Sans CJK SC 开源中文字体，不依赖 Windows 预装中文语言包；字体与许可证均离线包含。

1. 运行 `BreathingGarden-Windows-x64-Setup.exe` 安装到当前用户目录，无需管理员权限。
   或把 `BreathingGarden-Windows-x64.zip` **完整解压**，运行文件夹中的 `BreathingGarden.exe`。
   不要在压缩包内直接运行，不要单独移动 EXE；旁边的 `_internal` 包含模型、Qt 和 Python。
2. 本测试版没有付费 Windows 代码签名，SmartScreen 可能提示未知发布者；只运行你确认来源和校验值的文件。
   若单位策略阻止未知应用，请联系管理员，不要关闭系统安全保护。
3. 点击“打开摄像头设置”，检查 设置 → 隐私和安全性 → 摄像头 → 摄像头访问，以及允许桌面应用访问摄像头。
   Windows 桌面应用没有 macOS 式的授权请求流程；“由 Windows 系统管理”不代表已经确认授权成功。
   参见 [Microsoft 摄像头权限说明](https://support.microsoft.com/en-us/windows/privacy/manage-app-permissions-for-a-camera-in-windows)。
4. 关闭可能占用相机的软件，选择内置相机或 USB webcam，点击“开始互动”。首次加载模型需要几秒。
5. 勾选摄像头背景和骨架检查识别；伸直食指慢慢画、停留约0.8秒开花、在枝条附近捏合后松开消散。
   微笑改变色温，张嘴增强呼吸。Ctrl+F / 双击画面全屏，Esc 返回，H 切换指引。
6. 无摄像头也可使用“模拟输入演示”。应用不录制或上传图像；识别与生长均在本机运行。

Windows 日志：`%LOCALAPPDATA%\BreathingGarden\Logs\app.log`。
如果无设备，检查 USB 连接、Windows 隐私设置和驱动，再刷新列表。检测失败时不会自动切换到另一台相机。
DirectShow 设备枚举与 OpenCV DirectShow 捕获使用同一顺序。

### 在 Windows 从源码构建

安装 Python 3.11 x64 与 [Inno Setup 6](https://jrsoftware.org/isdl.php)，在仓库根目录执行：

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r breathing_garden_app/requirements-windows.txt
.venv\Scripts\python -m unittest discover -s breathing_garden_td/tests -v
$env:QT_QPA_PLATFORM = 'offscreen'
.venv\Scripts\python -m unittest breathing_garden_app.test_app breathing_garden_app.test_platform interactive_app.test_permissions -v
.venv\Scripts\python breathing_garden_app/build_windows.py
```

正常从源码启动时不要保留 `QT_QPA_PLATFORM=offscreen`：

```powershell
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
.venv\Scripts\python -m breathing_garden_app.launch
```

从源码启动前可执行 `.venv\Scripts\python -m breathing_garden_app.resources` 下载并校验固定版本中文字体；
构建脚本会自动处理此步骤。没有该资源时源码启动使用系统字体回退，成品包不需要下载。

GitHub Actions：`.github/workflows/build-breathing-garden-windows.yml` 在真实 Windows runner 打包，
运行纯 Python / UI 测试，并静默安装到中文路径，验证离线模型实际推理、窗口与全屏模拟互动。
CI 没有实体摄像头，因此不代表真实摄像头、实际显示器色彩或60FPS已通过验收。
界面与字体检查使用原生 Windows 图形后端；仅无窗口单元测试使用 offscreen。

## Mac 版本

双击 `Breathing Garden.app` 运行。也可以打开 `BreathingGarden.dmg`，把应用拖入 Applications。
无需 TouchDesigner、Python 或联网下载模型。只适用于 Apple Silicon Mac（M1 及更新）、macOS 14.5+。
此为本地开发签名版本，未通过 Apple 公证；不要将未公证的本地开发版本视为正式跨机器发行包。

## 1.1 更新：更清晰的光色与互动指引

枝条提高了色彩和透明度表现，并修正 Retina 屏幕下线宽过细的问题；花朵与星尘也更容易看清。
增强只发生在显示层，不改变植物生长、寿命和捏合判定；消散末尾仍会完全透明。
生命亮度显示百分比，可在30%–220%之间调整。LOW 档也保留清晰的枝条，只减少额外光晕。

窗口顶部默认显示三步指引，并随识别状态提示下一步操作；停留开花时会显示进度条。
点击“隐藏指引 / 互动指引”或按 H 开关，设置会保存。全屏始终隐藏指引与开发界面，
按 Esc 返回后恢复原来的指引显示设置。

## 开始测试真实摄像头

1. 首次打开，允许系统弹窗中的摄像头权限。已拒绝时点“打开摄像头设置”，
   在系统设置 → 隐私与安全性 → 摄像头中开启“呼吸的花园 / Breathing Garden”。
2. 退出 TouchDesigner、旧“光感互动”或可能占用摄像头的软件，再选择 Mac 内置相机或 USB webcam。
3. 点击“开始互动”。允许授权本身不会自动开启摄像头。
4. 先勾选“显示摄像头（仅测试）”与“显示骨架与指尖（仅测试）”，确认脸、手腕和手指完整入镜。
5. 伸出食指并慢慢移动，播种细线与枝条；在一处停留约 .8 秒开花。
6. 在植物附近捏合保持约 .15 秒，然后松开，触发柔和消散。不是捏合时爆炸。
7. 张嘴改变呼吸幅度，微笑缓慢改变颜色。面部动作映射不代表心理状态识别。
8. 关闭测试背景与骨架，双击画面或按 ⌘F 进入纯画面全屏，Esc 返回。

界面顶部显示“食指绘制 / 捏合中 / 等待手部入镜”；底部显示植物、枝条、花、微光数量、识别 FPS、
绘制时间、mouth/smile 值。全屏不会显示这些开发信息，也不会显示摄像头背景或骨架。
摄像头的录制指示灯由系统控制。本应用不保存或上传摄像头帧，只在内存中识别和绘制。

## 演示和性能

“模拟输入演示”不使用摄像头，执行同一套模拟绘制、开花和消散。
“重置花园”清空当前生命；暂停摄像头只停止输入，已有生命继续生长并自然消散。
镜像、亮度、面部响应、相机和画质会保存；首次默认隐藏摄像头背景。

NORMAL 保留极轻柔的描边光晕；LOW 降低枝条和粒子预算，关闭额外宽描边。
选择画质会重置花园。持续低帧率时会柔和降级，但不保证任何追踪/硬件负载下都达到60 FPS。

花园计算复用 `breathing_garden_td/garden_engine.py`；独立版用 Qt 原生绘制替代 TD 的 SOP/Line MAT/Bloom。
它不是把 TouchDesigner `.toe` 当成视频播放，也不是 TD 运行时封装；生长和输入协议与原型共用。

## 故障排查

- 有授权但无法打开：关闭其它用相机的软件，暂停→刷新设备→重新开始。
- 没有手：查看骨架，确保完整手掌、手腕和食指入镜，适当后退，改善照明。
- 有手但不绘制：伸直食指；捏合会暂停绘制。界面应显示“食指绘制”。
- 消散没有触发：保持捏合再松开，指尖需靠近枝条；如果期间手部丢失，保护逻辑不会伪造释放事件。
- 镜像相反：切换“镜像画面”。新的追踪坐标统一来自镜像后的识别图像，避免二次翻转。
- 偶尔断笔：手部跳跃、切手、坐标或相机数据超时会主动断笔，防止横跨画面的错误长线。
- 卡顿：切 LOW，关闭测试背景和骨架，降低同时运行的软件负载。
- 日志：`~/Library/Logs/BreathingGarden/app.log`，最多3个约1 MB文件，不含摄像头图像。
- 旧“光感互动”仍可单独使用。本版本为新应用，未覆盖它。

## 从源码构建与验证

使用仓库现有且已验证的 Python 3.11 虚拟环境：

```bash
interactive_app/.venv/bin/python -m breathing_garden_app.app
interactive_app/.venv/bin/python breathing_garden_app/build_mac.py
QT_QPA_PLATFORM=offscreen interactive_app/.venv/bin/python -m unittest breathing_garden_app.test_app interactive_app.test_permissions -v
```

依赖版本沿用 `interactive_app/requirements.txt`，模型资源与许可证沿用原独立应用。
构建会验证模型 SHA-256 和完整 `.app` 签名，再生成 DMG。

打包后可在不打开摄像头的条件下验证：

```bash
'dist/Breathing Garden.app/Contents/MacOS/Breathing Garden' --verify-models /tmp/garden-models.json
'dist/Breathing Garden.app/Contents/MacOS/Breathing Garden' --smoke-test /tmp/garden-preview
```

真实摄像头测试需要用户授予系统权限；不会通过脚本自动开启权限开关。
