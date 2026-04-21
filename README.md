# QuitMood 种草模板自动剪辑工具

丢一条原始拍摄素材 → 自动分析镜头 → 自动按种草模板拼成 15 秒竖屏成品。

## 模板结构（15秒 × 8个镜头）

| 段落 | 时长 | 镜头数 | 作用 |
|------|------|--------|------|
| hook | 2s | 1 | 开头钩子，吸引注意力 |
| demo | 8s | 4 | 场景+演示，快速切换 |
| selling | 4s | 2 | 卖点展示 |
| cta | 1s | 1 | 强CTA收尾 |

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

### 2. 克隆仓库
```bash
git clone https://github.com/Guanweilu/QuitMood.git
cd QuitMood
```

### 3. 确认 Python 3
```bash
python3 --version  # 需要 3.6+
```

## 使用

### 纯视频（无配音）
```bash
python3 种草剪辑.py /path/to/video.MOV
```

### 视频 + 配音音频
```bash
python3 种草剪辑.py /path/to/video.MOV /path/to/audio.MP3
```

成品自动输出到 `输出/` 文件夹，文件名格式：`种草_YYYYMMDD_HHMMSS.mp4`

## 输出规格

- 分辨率：1080 × 1920（竖屏 9:16）
- 帧率：30fps
- 编码：H.264 + AAC
- 时长：15秒

## 工作原理

1. FFmpeg 场景检测，自动识别原始素材中的镜头切换点
2. 把视频时间线均匀分成 8 个区间，每个区间挑一个镜头
3. 按模板节奏截取对应时长，缩放裁切到竖屏尺寸
4. 拼接所有片段，合并音频（如有），输出成品

## 自定义配置

编辑 `种草剪辑.py` 顶部的 `CONFIG`：

- `scene_threshold`：场景检测灵敏度（默认 0.05，越低越敏感）
- `output_width / output_height`：输出尺寸（默认竖屏 1080×1920）
- `output_fps`：帧率（默认 30）
- `segments`：模板节奏，可调整每段时长和镜头数
