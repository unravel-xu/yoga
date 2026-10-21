# 光感互动 · Mac 独立版

双击 `Light Interaction.app`，或打开 `LightInteraction.dmg`，把应用拖入 Applications。
无需安装 TouchDesigner、Python 或额外模型；运行时不需要网络。

当前构建适用于 Apple Silicon（M1/M2/M3/M4 等）、macOS 14.5 及以上。
这是本地开发签名版本，未经过 Apple 公证；跨电脑分发时可能需要在
“系统设置 → 隐私与安全性”中选择“仍要打开”。Intel Mac 需在 Intel 环境重新构建。

## 使用

1. 首次启动时，应用自动请求摄像头权限；在系统弹窗中选择允许。
2. 选择 Mac 内置摄像头或 USB webcam，点击“开始互动”。授权本身不会自动打开摄像头。
3. 面向摄像头，让面部和双手都进入画面。
4. 微笑、张嘴、皱眉会改变光晕与双手光效的配色。
5. 拇指和食指捏合触发光粒爆发，张掌扩大光环，挥手产生拖尾。
6. 双击画面或按 ⌘F 全屏展示；Esc 恢复控制界面。

“显示摄像头背景”关闭后仅展示光效。灵敏度、光效强度、镜像和摄像头选择会被记住。
“校准中性表情”使用本次运行的约两秒自然表情作为基线，重新启动互动后重置。
“体验演示”使用模拟数据，不开启摄像头。状态栏的 FPS 表示识别更新速率。

画面与模型推理均在本机内存中运行，不录制、不上传。表情状态用于艺术互动映射。

## 故障处理

- 无权限：点击窗口下方“打开摄像头设置”，直接前往系统设置的摄像头页面，
  允许“光感互动 / Light Interaction”，返回应用后会自动检查权限，再点击“开始互动”。
  macOS 若提示退出并重新打开，请按系统提示操作。已拒绝的权限不会重复弹窗申请。
- 权限受限：检查屏幕使用时间或联系设备管理员；应用无法绕过系统策略。
- 摄像头打不开：退出占用摄像头的程序，包括 TouchDesigner，再点击“开始互动”。
- USB webcam 拔插后：暂停互动，点击“刷新设备”，重新选择设备并开始。
- 看不到双手：移远一些，确保手指和手腕完整入镜。
- 错误日志：`~/Library/Logs/LightInteraction/app.log`（不含摄像头图像）。

## 从源码运行与构建

使用 Python 3.11（本机验证版本为 3.11.15）：

```bash
python3.11 -m venv interactive_app/.venv
interactive_app/.venv/bin/python -m pip install -r interactive_app/requirements.txt
interactive_app/.venv/bin/python interactive_app/build_mac.py
```

构建脚本从 Google 官方版本 1 地址获取模型并验证 SHA-256，生成图标、打包动态依赖，
验证应用签名，再生成 DMG。运行源码前需先完成一次构建以准备模型：

```bash
interactive_app/.venv/bin/python -m interactive_app.app
```

构建产物位于仓库根目录的 `dist/`：

- `Light Interaction.app`：可直接运行，模型和依赖已内置。
- `LightInteraction.dmg`：安装包，含 Applications 快捷入口和使用说明。

## 实现与验证

- `engine.py`：MediaPipe Face Landmarker + Hand Landmarker、表情平滑、独立左右手状态。
- `canvas.py`：面部光晕、双手光环、连续拖尾和有数量上限的粒子。
- `app.py`：原生 Qt 窗口、macOS 权限、摄像头线程、设置与全屏。
- `LightInteraction.spec`：PyInstaller app bundle、摄像头用途说明和离线资源。

独立版对应 TouchDesigner 第三阶段的交互逻辑，光效使用 Qt 重新绘制。
模型、运行时和 GUI 打包后可用以下参数验证，不需要开启摄像头：

```bash
'dist/Light Interaction.app/Contents/MacOS/Light Interaction' --verify-models /tmp/light-models.json
'dist/Light Interaction.app/Contents/MacOS/Light Interaction' --smoke-test /tmp/light-preview
```

第三方许可证位于应用包的 `Contents/Resources/licenses`；详见 `THIRD_PARTY_NOTICES.md`。

本机构建环境里，MediaPipe 0.10.21 的 wheel 文件名标记为 universal2，内部 WHEEL 元数据却标记为 x86_64，
因此 `pip check` 会报告平台标签不一致。实际 native 库含 arm64 切片；已验证其最低系统版本为 14.5，
并在 Apple M4 Pro 上完成真实模型推理和打包后启动验证。
