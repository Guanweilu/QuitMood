---
name: quitmood-种草剪辑
description: 按照 QuitMood 种草视频模板剪辑视频。用户提供素材文件夹和音频，Claude 先看素材画面再制定剪辑方案，最后自动执行出片。当用户提到"种草视频"、"QuitMood 剪辑"、"按模板剪视频"、"帮我剪个带货视频"等需求时触发。
---

# QuitMood 种草剪辑 Skill v5.0

## 核心理念

**不要盲剪，先看素材再动手。** 自动场景检测只能找到画面变化点，不能判断画面好不好、放哪里合适。必须先抽帧预览，理解每条素材拍了什么，再制定剪辑方案。

## 工具位置

- 脚本: `~/QuitMood/种草剪辑.py`（自动模式，适合快速出片）
- 输出目录: `~/QuitMood/输出/`
- FFmpeg: `~/bin/ffmpeg`
- GitHub: https://github.com/Guanweilu/QuitMood

## 触发时的完整流程

### 第 1 步：收集信息

向用户要：
- 素材文件夹路径
- 音频路径（可选）
- 产品类型（外观型 A / 功能型 B，影响时长分配）
- 要几个成品
- 有无特殊要求（比如"搓手指的画面放最后"）

### 第 2 步：抽帧预览

对每条素材抽取缩略图，看懂每条拍了什么：

```bash
mkdir -p /tmp/qm_preview
for f in 素材文件夹/IMG_*.MOV; do
  name=$(basename "$f" .MOV)
  ~/bin/ffmpeg -y -i "$f" -vf "fps=1/2,scale=320:-1,tile=5x1" -frames:v 1 "/tmp/qm_preview/${name}.jpg" 2>/dev/null
done
```

然后用 Read 工具查看每张缩略图。

### 第 3 步：分析素材 & 制定方案

看完缩略图后，为每条素材标注：
- 内容类别（外包装 / 开箱 / 内部细节 / 使用过程 / 使用效果 / CTA手势）
- 最佳时间段（从第几秒开始截取最好看）
- 需要避开的部分（黑屏、模糊、手抖）

然后按叙事弧线制定剪辑方案。

### 叙事弧线模板

**模式 A · 外观型（润唇膏、香水等）— 外包装展示多：**
| 段落 | 时长 | 内容 |
|------|------|------|
| hook | 1.5s | 产品第一眼（最吸引人的画面）|
| exterior_1 | 3.0s | 外包装主体展示 |
| exterior_2 | 2.0s | 外包装换角度/细节 |
| open | 1.5s | 开箱动作 |
| interior | 2.0s | 内部细节 |
| use_1 | 2.0s | 使用上手 |
| use_2 | 2.0s | 使用效果 |
| cta | 1.0s | 收尾/CTA手势 |

**模式 B · 功能型（牙贴、清洁剂等）— 使用演示多：**
| 段落 | 时长 | 内容 |
|------|------|------|
| hook | 1.5s | 产品第一眼 |
| exterior | 2.0s | 外包装一眼 |
| open | 1.5s | 开箱/拆封 |
| interior | 2.0s | 内部/单品细节 |
| use_1 | 2.0s | 使用过程 |
| use_2 | 2.5s | 使用效果（重点，稍长）|
| use_3 | 2.0s | 效果特写/多色展示 |
| cta | 1.5s | 收尾/CTA手势 |

### 第 4 步：执行剪辑

用 FFmpeg 逐段截取 + 拼接 + 合音频：

```bash
FF=~/bin/ffmpeg
W=1080; H=1920; FPS=30
VF="scale=${W}:${H}:force_original_aspect_ratio=increase,crop=${W}:${H},fps=${FPS},setsar=1"

# 逐段截取
$FF -y -ss {开始时间} -i {素材路径} -t {时长} -vf "$VF" -an -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p {输出段落}.mp4

# 拼接
$FF -y -f concat -safe 0 -i filelist.txt -c copy tmp.mp4

# 合音频
$FF -y -i tmp.mp4 -i 音频.MP3 -c:v copy -c:a aac -shortest 成品.mp4
```

### 第 5 步：交付

告诉用户成品路径，让他们查看效果。如果不满意，根据反馈调整方案重新剪。

## 重要原则

1. **永远先看素材再剪** — 不要直接跑自动脚本，除非用户明确要求"快速出片不用看"
2. **叙事逻辑 > 画面质量** — 顺序要对（外→内→用），宁可画面普通也不要逻辑乱
3. **注意用户的特殊要求** — 比如"搓手指放最后"、"某个画面不要用"
4. **两个成品之间不要重复同一个时间点的画面** — 可以用同一条素材，但要选不同的时间段
5. **CTA 段永远放最后** — 引导点击的手势/画面不能出现在中间

## 关联资源

- Obsidian 原始模板笔记: `~/ObsidianVault/QuitMood视频剪辑.md`
- Obsidian 使用说明: `~/ObsidianVault/QuitMood剪辑工具.md`
- GitHub 仓库: https://github.com/Guanweilu/QuitMood
