# QuitMood 种草模板自动剪辑工具 v4.0

丢素材进来 → 自动分析镜头 → 自动按种草模板 → 15 秒竖屏成品。

## 功能

- **两种产品模式**：A（外观型）/ B（功能型），节奏自动适配
- **叙事弧线**：每个视频自动走 外包装 → 内部展示 → 使用演示 完整流程
- **智能跳过坏画面**：自动过滤过暗、过亮、过渡帧
- **自动字幕**：提供音频即自动语音识别生成字幕（Whisper）
- **批量出片**：一个素材文件夹自动剪出多个不重复的成品

## 模式说明

### 模式 A · 外观型产品（润唇膏、香水、化妆品等）
外包装 6.5s / 内部 3.5s / 使用 5s = 15s

### 模式 B · 功能型产品（牙贴、清洁剂、工具等）
外包装 3.5s / 内部 3.5s / 使用 8s = 15s

## 安装

### 1. 安装 FFmpeg

**macOS（有 Homebrew）：**
```bash
brew install ffmpeg
```

**macOS（无 Homebrew / 无 sudo）：**
```bash
mkdir -p ~/bin
curl -L -o ~/ffmpeg.zip https://evermeet.cx/ffmpeg/ffmpeg-7.1.1.zip
unzip -o ~/ffmpeg.zip -d ~/bin/
chmod +x ~/bin/ffmpeg
rm ~/ffmpeg.zip
```

### 2. 安装 Whisper（自动字幕，可选）
```bash
pip3 install --user openai-whisper
```

### 3. 克隆仓库
```bash
git clone https://github.com/Guanweilu/QuitMood.git
cd QuitMood
```

### 4. 确认 Python 3
```bash
python3 --version  # 需要 3.9+
```

## 使用

### 单视频
```bash
python3 种草剪辑.py 视频.MOV
python3 种草剪辑.py 视频.MOV --audio 音频.MP3
```

### 素材文件夹（推荐）
```bash
# 功能型产品，出 3 个成品，带音频和自动字幕
python3 种草剪辑.py 素材文件夹/ --mode B --count 3 --audio 音频.MP3

# 外观型产品
python3 种草剪辑.py 素材文件夹/ --mode A --audio 音频.MP3

# 不要字幕
python3 种草剪辑.py 素材文件夹/ --audio 音频.MP3 --no-subs
```

成品自动输出到 `输出/` 文件夹。

## 参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `--mode A\|B` | 产品模式 | B（功能型）|
| `--count N` | 生成数量 | 3 |
| `--audio FILE` | 配音音频（提供后自动生成字幕）| 无 |
| `--no-subs` | 有音频但不要字幕 | 否 |

## 素材准备建议

把拍摄素材按拍摄顺序放到一个文件夹里。脚本会自动按文件名排序，将素材划分为三个叙事阶段：

```
文件夹/
├── IMG_001.MOV  ← 前 25~40% 自动归为「外包装」
├── IMG_002.MOV
├── ...
├── IMG_010.MOV  ← 中间 25~30% 自动归为「内部展示」
├── ...
├── IMG_015.MOV  ← 后 30~50% 自动归为「使用演示」
├── ...
└── IMG_022.MOV
```

## 输出规格

- 分辨率：1080 x 1920（竖屏 9:16）
- 帧率：30fps
- 编码：H.264 + AAC
- 时长：15 秒
- 字幕：自动语音识别（Whisper base 模型，中文）

## 工作原理

1. **场景检测**：FFmpeg 自动识别每条素材中的镜头切换点
2. **质量过滤**：跳过过暗、过亮、过渡帧（偏移 0.5s 避开切换瞬间）
3. **叙事分配**：按产品模式将镜头分配到外包装/内部/使用三个阶段
4. **节奏变化**：快-慢-快-慢交替，不是固定 2 秒一刀切
5. **语音识别**：Whisper 自动识别音频内容生成 SRT 字幕
6. **合成输出**：视频 + 音频 + 字幕一步到位
