#!/usr/bin/env python3
"""
QuitMood 种草模板自动剪辑工具 v2.0

全自动版：丢一条原始素材进来，自动分析镜头 → 自动挑选 → 自动按模板拼成 15 秒成品。

模板结构（15秒，8个镜头）：
  - hook     （2s）：1 个镜头，开头吸引注意力
  - demo     （8s）：4 个镜头，每个 2s，场景+演示
  - selling  （4s）：2 个镜头，每个 2s，卖点展示
  - cta      （1s）：1 个镜头，强CTA收尾
  合计：8 个镜头，15 秒

使用方法：
  # 纯视频（无音频）
  python3 种草剪辑.py /path/to/video.MOV

  # 视频 + 配音音频
  python3 种草剪辑.py /path/to/video.MOV /path/to/audio.MP3

  成品自动输出到 ~/QuitMood/输出/
"""

import subprocess
import os
import sys
import re
from datetime import datetime

FFMPEG = os.path.expanduser("~/bin/ffmpeg")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
输出目录 = os.path.join(BASE_DIR, "输出")

# ========== 配置区 ==========
CONFIG = {
    # 模板节奏：(名称, 时长秒, 镜头数)
    "segments": [
        ("hook", 2, 1),           # 2s, 1个镜头
        ("demo_1", 2, 1),         # 2s
        ("demo_2", 2, 1),         # 2s
        ("demo_3", 2, 1),         # 2s
        ("demo_4", 2, 1),         # 2s
        ("selling_1", 2, 1),      # 2s
        ("selling_2", 2, 1),      # 2s
        ("cta", 1, 1),            # 1s
    ],

    # 场景检测灵敏度（越低越敏感，检测出更多镜头）
    "scene_threshold": 0.05,

    # 最少需要的镜头数（检测到的不够时会用均匀切割兜底）
    "min_shots_needed": 8,

    # 输出设置
    "output_width": 1080,
    "output_height": 1920,  # 竖屏 9:16
    "output_fps": 30,
}
# ============================


def get_video_duration(input_path):
    """获取视频总时长（秒）"""
    cmd = [FFMPEG, "-i", input_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if match:
        h, m, s = float(match.group(1)), float(match.group(2)), float(match.group(3))
        return h * 3600 + m * 60 + s
    return 0


def detect_scenes(input_path, threshold):
    """用 FFmpeg 场景检测找出所有镜头切换的时间点"""
    print(f"  分析素材中（灵敏度 {threshold}）...", end=" ", flush=True)

    tmp_file = "/tmp/qm_scenes.txt"
    cmd = [
        FFMPEG, "-y",
        "-i", input_path,
        "-vf", f"select='gt(scene,{threshold})',metadata=print:file={tmp_file}",
        "-vsync", "vfr",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    scene_times = [0.0]  # 第一个镜头从 0 秒开始
    if os.path.isfile(tmp_file):
        with open(tmp_file, "r") as f:
            for line in f:
                match = re.search(r"pts_time:(\d+\.?\d*)", line)
                if match:
                    t = float(match.group(1))
                    # 去重：和上一个时间点太近的（< 1秒）跳过
                    if t - scene_times[-1] >= 1.0:
                        scene_times.append(t)
        os.remove(tmp_file)

    print(f"检测到 {len(scene_times)} 个镜头")
    return scene_times


def uniform_split(duration, num_shots):
    """均匀切割：当场景检测镜头不够时的兜底方案"""
    interval = duration / num_shots
    return [i * interval for i in range(num_shots)]


def select_shots(scene_times, total_duration, num_needed):
    """
    从检测到的镜头中挑选 num_needed 个，尽量分散、覆盖全片。
    策略：把视频分成 num_needed 个时间段，每段里挑一个镜头。
    """
    if len(scene_times) < num_needed:
        print(f"  检测到的镜头（{len(scene_times)}）不够 {num_needed} 个，用均匀切割兜底")
        return uniform_split(total_duration, num_needed)

    # 把时间线均匀分成 num_needed 个区间
    interval = total_duration / num_needed
    selected = []
    for i in range(num_needed):
        zone_start = i * interval
        zone_end = (i + 1) * interval
        # 在这个区间里找一个镜头（优先选最靠近区间中点的）
        zone_mid = (zone_start + zone_end) / 2
        best = None
        best_dist = float("inf")
        for t in scene_times:
            if zone_start <= t < zone_end:
                dist = abs(t - zone_mid)
                if dist < best_dist:
                    best = t
                    best_dist = dist
        if best is not None:
            selected.append(best)
        else:
            # 这个区间没有镜头，用区间起点
            selected.append(zone_start)

    return selected


def extract_clip(input_path, start_time, duration, output_path, width, height, fps):
    """从原始素材中截取一段，缩放裁切到目标尺寸"""
    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        f"fps={fps}",
        f"setsar=1",
    ]
    filter_str = ",".join(filters)

    cmd = [
        FFMPEG, "-y",
        "-ss", str(start_time),
        "-i", input_path,
        "-t", str(duration),
        "-vf", filter_str,
        "-an",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\n  [错误] 截取 {start_time}s 失败:")
        print(result.stderr[-300:])
        return False
    return True


def concat_clips(clip_files, output_path):
    """拼接所有片段"""
    list_file = os.path.join(输出目录, "_filelist.txt")
    with open(list_file, "w") as f:
        for cf in clip_files:
            f.write(f"file '{cf}'\n")

    cmd = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(list_file)

    if result.returncode != 0:
        print(f"[错误] 拼接失败:")
        print(result.stderr[-300:])
        return False
    return True


def merge_audio(video_path, audio_path, output_path):
    """把音频合并到视频中"""
    cmd = [
        FFMPEG, "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[错误] 音频合并失败:")
        print(result.stderr[-300:])
        return False
    return True


def main():
    print("=" * 44)
    print("  QuitMood 种草模板 v2.0 - 全自动剪辑")
    print("=" * 44)

    # 检查参数
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 种草剪辑.py 视频.MOV")
        print("  python3 种草剪辑.py 视频.MOV 音频.MP3")
        sys.exit(1)

    input_path = sys.argv[1]
    audio_path = sys.argv[2] if len(sys.argv) >= 3 else None

    if not os.path.isfile(input_path):
        print(f"[错误] 视频文件不存在: {input_path}")
        sys.exit(1)

    if audio_path and not os.path.isfile(audio_path):
        print(f"[错误] 音频文件不存在: {audio_path}")
        sys.exit(1)

    # 检查 ffmpeg
    if not os.path.isfile(FFMPEG):
        print(f"[错误] 找不到 ffmpeg: {FFMPEG}")
        sys.exit(1)

    os.makedirs(输出目录, exist_ok=True)

    # 1. 获取视频信息
    total_duration = get_video_duration(input_path)
    print(f"\n素材: {os.path.basename(input_path)}")
    print(f"时长: {total_duration:.1f}s")
    if audio_path:
        audio_duration = get_video_duration(audio_path)
        print(f"音频: {os.path.basename(audio_path)} ({audio_duration:.1f}s)")

    # 2. 场景检测
    scene_times = detect_scenes(input_path, CONFIG["scene_threshold"])
    for i, t in enumerate(scene_times):
        print(f"    镜头 {i+1}: {t:.1f}s")

    # 3. 挑选镜头
    segments = CONFIG["segments"]
    num_needed = len(segments)
    selected = select_shots(scene_times, total_duration, num_needed)

    print(f"\n模板分配（{num_needed} 个镜头）:")
    for i, (name, dur, _) in enumerate(segments):
        print(f"  {name:12s} → 从 {selected[i]:.1f}s 开始，截取 {dur}s")

    # 4. 逐段截取
    print("\n开始截取...")
    width = CONFIG["output_width"]
    height = CONFIG["output_height"]
    fps = CONFIG["output_fps"]

    clip_files = []
    for i, (name, dur, _) in enumerate(segments):
        out_clip = os.path.join(输出目录, f"_clip_{i:02d}_{name}.mp4")
        print(f"  {name} ({dur}s, 从 {selected[i]:.1f}s)...", end=" ", flush=True)
        if extract_clip(input_path, selected[i], dur, out_clip, width, height, fps):
            clip_files.append(out_clip)
            print("OK")
        else:
            print("失败")
            sys.exit(1)

    # 5. 拼接成片
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if audio_path:
        # 先拼视频，再合音频
        tmp_video = os.path.join(输出目录, f"_tmp_video.mp4")
        output_file = os.path.join(输出目录, f"种草_{timestamp}.mp4")

        print(f"\n拼接视频...", end=" ", flush=True)
        if not concat_clips(clip_files, tmp_video):
            sys.exit(1)
        print("OK")

        print(f"合并音频...", end=" ", flush=True)
        if merge_audio(tmp_video, audio_path, output_file):
            print("OK")
        else:
            sys.exit(1)
        os.remove(tmp_video)
    else:
        output_file = os.path.join(输出目录, f"种草_{timestamp}.mp4")
        print(f"\n拼接成片...", end=" ", flush=True)
        if not concat_clips(clip_files, output_file):
            sys.exit(1)
        print("OK")

    # 6. 清理临时文件
    for cf in clip_files:
        os.remove(cf)

    total_time = sum(dur for _, dur, _ in segments)
    print(f"\n完成!")
    print(f"  镜头数: {num_needed}")
    print(f"  总时长: {total_time}s")
    if audio_path:
        print(f"  音频:   已合并")
    print(f"  输出:   {output_file}")


if __name__ == "__main__":
    main()
