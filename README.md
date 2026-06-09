# 🎬 VideoTools — 视频集成工具

<div align="center">

[![Release](https://img.shields.io/github/v/release/secure-artifacts/VideoTools?style=for-the-badge&logo=github&color=f43f5e)](https://github.com/secure-artifacts/VideoTools/releases/latest)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078d4?style=for-the-badge&logo=windows)](https://github.com/secure-artifacts/VideoTools/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Build](https://img.shields.io/github/actions/workflow/status/secure-artifacts/VideoTools/release.yml?style=for-the-badge&logo=githubactions&logoColor=white&label=Build)](https://github.com/secure-artifacts/VideoTools/actions)
[![Attestation](https://img.shields.io/badge/SLSA-L2%20Verified-10b981?style=for-the-badge&logo=slsa&logoColor=white)](https://github.com/secure-artifacts/VideoTools/attestations)

**面向内容创作者的 Windows 视频批量处理工具**  
支持视频合并转场、图片合成视频、图片批量裁剪，内置背景音乐库管理

[📥 立即下载](#-下载与安装) · [📖 使用说明](#-功能详解) · [🔒 安全验证](#-安全说明)

</div>

---

## 📸 功能概览

VideoTools 包含三大核心工具，通过顶部导航栏切换：

| 工具 | 功能 |
|------|------|
| 🚀 **视频合并与转场** | 将多个视频片段批量合并，支持 8 种转场特效、循环模式、不规则片段模式、背景音乐 |
| ✨ **图片合并成视频** | 将图片序列合成视频，支持动态特效（Ken Burns）、转场、背景音乐 |
| 🖼️ **图片批量裁剪** | 将任意尺寸图片批量裁剪为 9:16 竖屏格式 |

---

## 📥 下载与安装

### 直接下载（推荐）

前往 [Releases 页面](https://github.com/secure-artifacts/VideoTools/releases/latest) 下载最新版本：

```
VideoTools-vX.X.X-windows.zip
```

**安装步骤：**
1. 下载并解压 ZIP 文件到任意目录
2. 进入解压后的 `VideoTools\` 文件夹
3. 双击 `VideoTools.exe` 直接运行，**无需安装、无需 Python**
4. 首次运行无需配置，软件会自动记住上次的参数设置

**系统要求：**
- Windows 10 / 11（64位）
- 无需额外安装运行库

---

## 📖 功能详解

### 🚀 视频合并与转场

将多段视频素材按规则自动合并输出，适用于批量制作短视频内容。

#### 基本流程
1. **添加视频文件** — 点击「添加文件」或「添加文件夹」，或直接拖拽 `.mp4 / .avi / .mov / .mkv` 到文件列表
2. **配置参数** — 设置合并数量、输出数量、画幅、分辨率、转场特效、速度等
3. **选择输出目录** — 点击「选择输出目录」，输出文件自动按日期归类到子文件夹
4. **开始生成** — 点击「🚀 开始生成视频」

#### 合并参数说明

| 参数 | 说明 |
|------|------|
| **合并数量** | 每个输出视频由几个片段合并而成 |
| **输出数量** | 共生成几个视频文件 |
| **画幅（尺寸）** | 9:16 竖屏 / 16:9 横屏 / 3:4 小红书 / 4:5 Ins / 1:1 正方形 |
| **分辨率** | 720P / 1080P（推荐）/ 2K / 4K |
| **合并顺序** | 随机合并（均衡分配使用次数）/ 按顺序合并 |
| **转场特效** | 溶解 / 滑动 / 颜色擦去 / 直线擦去 / 对比并移动 / 流动 / 堆叠 / 叠加 / 无转场 |
| **视频速度** | 0.1× — 2.0×，支持滑条或直接输入 |
| **去掉声音** | 推荐勾选，防止多轨道音频合并崩溃 |

#### 三种合并模式

**① 普通模式**（默认）  
按「合并数量 × 输出数量」自动均衡分配素材，适合批量制作相同规格的视频。

**② 🔀 不规则片段合并**  
自定义每个输出视频的片段数，适合不同视频需要不同长度的场景。
- 勾选「🔀 不规则片段合并」→ 点击「📋 点击配置列表」
- 每行输入一个数字，代表该视频合并的片段数
- 支持从 Excel/WPS 表格直接复制粘贴

```
示例输入：
8
4
6
→ 输出 3 个视频，分别合并 8、4、6 个片段
```

**③ 🔁 循环模式**  
将单个视频素材重复循环 N 次合并成一个视频，适合制作循环素材。
- 勾选「🔁 循环模式」→ 点击「📋 点击配置循环」
- 第 1 行 → 第 1 个文件循环几次，第 2 行 → 第 2 个文件循环几次，依此类推
- 若行数超过文件数，多余行自动忽略
- 仍支持背景音乐、转场特效、尺寸/分辨率/速度

```
示例输入：
3
5
2
→ 第1个视频素材循环3次、第2个循环5次、第3个循环2次
  输出 3 个独立视频
```

> ⚠️ 不规则模式与循环模式互斥，开启一个会自动关闭另一个。

#### 背景音乐

勾选「去掉声音」后，背景音乐面板自动显示：

1. **音频库管理** — 添加 MP3/WAV/AAC/OGG 文件到音频库（永久保存，下次打开仍可用）
2. **选择背景音乐** — 点击选择栏打开选择器，可多选并排序
3. **音频分配模式**：
   - 随机分配：每个视频随机选一首
   - 按顺序补全：依次分配，不足时循环补全
   - 按顺序不补全：依次分配，不足时剩余视频无音频
4. **音频自动循环** — 音频时长不足时自动循环补齐
5. **音量调节** — 0%（静音）~ 200%（双倍）
6. **跳过开头 / 渐入时长** — 在音频库中选中音频后点击「🎧 编辑参数」设置

---

### ✨ 图片合并成视频

将图片序列（JPG/PNG/WebP 等）合成为带动效的视频，适合制作电子相册、短视频封面素材。

#### 配置参数

| 参数 | 说明 |
|------|------|
| **每个视频合并几张** | 每个输出视频包含的图片数量 |
| **输出几个视频** | 批量输出的视频数量 |
| **每张展示时长** | 每张图片在视频中显示的秒数（2 — 60 秒） |
| **转场特效** | 淡入淡出 / 滑动 / 擦除 / 圆形展开 / 马赛克 / 溶解 / 黑场等 15 种 |
| **动态特效** | Ken Burns 效果：中心放大、左上角放大、放大后缩小、向上平移、黑白老照片、色彩增强等 |
| **音频分配** | 与视频合并相同的音频库管理体系 |

---

### 🖼️ 图片批量裁剪

将任意比例的图片批量裁剪为 **9:16 竖屏** 格式，适合为短视频平台准备素材。

- 支持格式：JPG / PNG / WebP / BMP / TIFF
- 支持拖拽批量导入
- 输出文件自动保存到按日期命名的子文件夹

---

## 🔒 安全说明

### 构建可信度

VideoTools 的每一个 Release 均通过 **GitHub Actions（github-hosted runner）** 自动构建，并附带 [SLSA Level 2](https://slsa.dev/) 构建证明（Attestation），可独立验证：

```bash
# 使用 GitHub CLI 验证构建来源
gh attestation verify VideoTools-vX.X.X-windows.zip \
  --repo secure-artifacts/VideoTools
```

**Attestation 验证的五项指标：**
- ✅ Release asset 上传者为 `github-actions[bot]`（非人工上传）
- ✅ SLSA provenance 类型为 `https://slsa.dev/provenance/v1`
- ✅ `workflow.repository` 指向本仓库
- ✅ `runner_environment` 为 `github-hosted`（非自托管）
- ✅ `workflow.ref` 与 Release tag 一致

### 安全扫描

| 扫描类型 | 工具 | 状态 |
|----------|------|------|
| 代码漏洞扫描 | GitHub CodeQL (Python) | [![CodeQL](https://img.shields.io/github/actions/workflow/status/secure-artifacts/VideoTools/codeql.yml?style=flat-square&label=CodeQL)](https://github.com/secure-artifacts/VideoTools/actions/workflows/codeql.yml) |
| 密钥泄露检测 | GitHub Secret Scanning | 已启用 |
| 依赖漏洞检测 | GitHub Dependabot | 已启用（每周扫描）|

---

## 🛠️ 技术栈

| 组件 | 版本 |
|------|------|
| Python | 3.11 |
| PyQt6 | ≥ 6.4.0 |
| Pillow | ≥ 9.0.0 |
| FFmpeg | 随软件内置（来自 [BtbN/ffmpeg-builds](https://github.com/BtbN/ffmpeg-builds)）|
| PyInstaller | ≥ 5.0.0（打包工具，不含于发行版）|

---

## 🏗️ 本地开发

```bash
# 克隆仓库
git clone https://github.com/secure-artifacts/VideoTools.git
cd VideoTools

# 安装依赖
pip install -r requirements.txt

# 运行（需要本地有 ffmpeg/ffmpeg.exe 和 ffmpeg/ffprobe.exe）
python main/main.py
```

**本地运行前请确保：**  
将 `ffmpeg.exe` 和 `ffprobe.exe` 放置于项目根目录的 `ffmpeg\` 子目录下。

---

## 📋 更新日志

### v1.0.1
- ✨ 新增「🔁 循环模式」：对每个视频素材指定循环次数，单素材重复合并

### v1.0.0
- 🎉 首次发布
- 🚀 视频合并与转场（普通模式 / 不规则片段模式）
- ✨ 图片合并成视频（Ken Burns 动效 + 15 种转场）
- 🖼️ 图片批量裁剪（9:16）
- 🎵 内置音频库管理系统
- 💾 参数设置自动持久化

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

FFmpeg 遵循 [LGPL/GPL 许可证](https://ffmpeg.org/legal.html)，随本软件分发的 FFmpeg 二进制文件来自 [BtbN/ffmpeg-builds](https://github.com/BtbN/ffmpeg-builds)。
