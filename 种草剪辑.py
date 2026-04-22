#!/usr/bin/env python3
"""
QuitMood 种草模板自动剪辑工具 v4.0

全自动种草视频剪辑，支持：
  - 两种产品模式：A（外观型）/ B（功能型）
  - 智能跳过坏画面（过暗、过亮、过渡帧）
  - 自动字幕（提供音频即自动语音识别生成字幕）
  - 单视频或素材文件夹输入

使用方法：
  # 基础用法（无音频无字幕）
  python3 种草剪辑.py 素材文件夹/
  python3 种草剪辑.py 视频.MOV

  # 带音频 + 自动字幕
  python3 种草剪辑.py 素材文件夹/ --audio 音频.MP3
  python3 种草剪辑.py 素材文件夹/ --audio 音频.MP3 --no-subs  (不要字幕)

  # 完整用法
  python3 种草剪辑.py 素材文件夹/ --mode B --count 3 --audio 音频.MP3

  --mode A     外观型产品（润唇膏、香水等），外包装展示多
  --mode B     功能型产品（牙贴、清洁剂等），使用演示多（默认）
  --count N    生成 N 个成品（默认 3）
  --audio      配音音频（提供后自动生成字幕）
  --no-subs    有音频但不要字幕
"""

import subprocess
import os
import sys
import re
from datetime import datetime

FFMPEG = os.path.expanduser("~/bin/ffmpeg")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 确保 ~/bin 在 PATH 中（whisper 等库需要找到 ffmpeg）
_bin_dir = os.path.expanduser("~/bin")
if _bin_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _bin_dir + ":" + os.environ.get("PATH", "")
输出目录 = os.path.join(BASE_DIR, "输出")

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

# ========== 模式配置 ==========

# 模式 A：外观型产品 — 外包装 6.5s / 内部 3.5s / 使用 5s = 15s
MODE_A = {
    "name": "外观型（A）",
    "segments": [
        ("hook",       1.5, "exterior"),
        ("exterior_1", 3.0, "exterior"),
        ("exterior_2", 2.0, "exterior"),
        ("open",       1.5, "interior"),
        ("interior",   2.0, "interior"),
        ("use_1",      2.0, "usage"),
        ("use_2",      2.0, "usage"),
        ("cta",        1.0, "usage"),
    ],
    "stage_split": [0.40, 0.30, 0.30],  # 外包装素材多分一些
}

# 模式 B：功能型产品 — 外包装 3.5s / 内部 3.5s / 使用 8s = 15s
MODE_B = {
    "name": "功能型（B）",
    "segments": [
        ("hook",       1.5, "exterior"),
        ("exterior",   2.0, "exterior"),
        ("open",       1.5, "interior"),
        ("interior",   2.0, "interior"),
        ("use_1",      2.0, "usage"),
        ("use_2",      2.5, "usage"),
        ("use_3",      2.0, "usage"),
        ("cta",        1.5, "usage"),
    ],
    "stage_split": [0.25, 0.25, 0.50],  # 使用素材多分一些
}

MODES = {"A": MODE_A, "B": MODE_B}

# ========== 通用配置 ==========
CONFIG = {
    "scene_threshold": 0.05,
    "scene_offset": 0.5,      # 跳过过渡帧：场景检测点往后偏移 0.5 秒
    "brightness_min": 40,      # 亮度下限（0-255），低于此为过暗
    "brightness_max": 220,     # 亮度上限（0-255），高于此为过亮
    "output_width": 1080,
    "output_height": 1920,
    "output_fps": 30,
}


# ========== 工具函数 ==========

def get_video_duration(input_path):
    cmd = [FFMPEG, "-i", input_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if match:
        h, m, s = float(match.group(1)), float(match.group(2)), float(match.group(3))
        return h * 3600 + m * 60 + s
    return 0


def detect_scenes(input_path, threshold):
    tmp_file = "/tmp/qm_scenes.txt"
    cmd = [
        FFMPEG, "-y", "-i", input_path,
        "-vf", f"select='gt(scene,{threshold})',metadata=print:file={tmp_file}",
        "-vsync", "vfr", "-f", "null", "-",
    ]
    subprocess.run(cmd, capture_output=True, text=True)

    scene_times = [0.0]
    if os.path.isfile(tmp_file):
        with open(tmp_file, "r") as f:
            for line in f:
                match = re.search(r"pts_time:(\d+\.?\d*)", line)
                if match:
                    t = float(match.group(1))
                    if t - scene_times[-1] >= 1.0:
                        scene_times.append(t)
        os.remove(tmp_file)
    return scene_times


def probe_brightness(input_path, time_pos):
    """探测某个时间点的画面亮度（0-255）"""
    cmd = [
        FFMPEG, "-ss", str(time_pos), "-i", input_path,
        "-vframes", "1",
        "-vf", "signalstats",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    match = re.search(r"YAVG:(\d+\.?\d*)", result.stderr)
    if match:
        return float(match.group(1))
    return 128  # 默认中间值，不影响判断


def is_good_shot(input_path, time_pos):
    """判断某个时间点的画面是否可用（不过暗、不过亮）"""
    brightness = probe_brightness(input_path, time_pos)
    if brightness < CONFIG["brightness_min"]:
        return False, f"过暗({brightness:.0f})"
    if brightness > CONFIG["brightness_max"]:
        return False, f"过亮({brightness:.0f})"
    return True, f"OK({brightness:.0f})"


def find_videos_in_folder(folder):
    videos = []
    for f in sorted(os.listdir(folder)):
        if os.path.splitext(f)[1].lower() in VIDEO_EXTS:
            videos.append(os.path.join(folder, f))
    return videos


def extract_clip(input_path, start_time, duration, output_path, width, height, fps):
    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        f"fps={fps}",
        f"setsar=1",
    ]
    cmd = [
        FFMPEG, "-y", "-ss", str(start_time), "-i", input_path,
        "-t", str(duration), "-vf", ",".join(filters),
        "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0



def concat_clips(clip_files, output_path):
    list_file = os.path.join(输出目录, "_filelist.txt")
    with open(list_file, "w") as f:
        for cf in clip_files:
            f.write(f"file '{cf}'\n")
    cmd = [
        FFMPEG, "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(list_file)
    return result.returncode == 0


def merge_audio(video_path, audio_path, output_path):
    cmd = [
        FFMPEG, "-y", "-i", video_path, "-i", audio_path,
        "-c:v", "copy", "-c:a", "aac", "-shortest", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def generate_srt_from_audio(audio_path, output_srt_path):
    """用 Whisper 语音识别生成 SRT 字幕文件"""
    print(f"  语音识别中（首次可能需要下载模型）...", flush=True)
    try:
        import whisper
    except ImportError:
        print("  [警告] whisper 未安装，跳过字幕生成")
        print("  安装: pip3 install --user openai-whisper")
        return None

    model = whisper.load_model("base")
    result = model.transcribe(audio_path, language="zh")

    # 生成 SRT 格式
    with open(output_srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(result["segments"]):
            start = seg["start"]
            end = seg["end"]
            text = seg["text"].strip()
            if not text:
                continue
            f.write(f"{i + 1}\n")
            f.write(f"{_format_srt_time(start)} --> {_format_srt_time(end)}\n")
            f.write(f"{text}\n\n")

    n_segs = len(result["segments"])
    print(f"  语音识别完成，生成 {n_segs} 条字幕 → {output_srt_path}")
    return output_srt_path


def _format_srt_time(seconds):
    """秒数转 SRT 时间格式 00:00:00,000"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ========== 镜头池构建（含质量过滤）==========

def build_shot_pool(videos, threshold):
    """为一组视频建立镜头池，跳过坏画面"""
    offset = CONFIG["scene_offset"]
    pool = []
    skipped = 0

    for v in videos:
        dur = get_video_duration(v)
        scenes = detect_scenes(v, threshold)

        for i, t in enumerate(scenes):
            # 偏移：跳过过渡帧
            actual_t = min(t + offset, dur - 0.5)
            if actual_t < 0:
                actual_t = t

            # 可用时长
            if i + 1 < len(scenes):
                available = scenes[i + 1] - actual_t
            else:
                available = dur - actual_t

            if available < 1.0:
                continue

            # 质量检查
            good, reason = is_good_shot(v, actual_t)
            if not good:
                skipped += 1
                continue

            pool.append((v, actual_t, available))

    if skipped > 0:
        print(f"    （跳过 {skipped} 个坏画面）")

    return pool


# ========== 渲染 ==========

def merge_audio_and_subs(video_path, audio_path, srt_path, output_path):
    """把音频和 SRT 字幕同时合并到视频中"""
    if srt_path and os.path.isfile(srt_path):
        # 音频 + 字幕
        safe_srt = srt_path.replace("'", "'\\''").replace(":", "\\:")
        cmd = [
            FFMPEG, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-vf", f"subtitles='{safe_srt}':force_style='FontSize=20,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Alignment=2,MarginV=80'",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac",
            "-shortest",
            output_path,
        ]
    else:
        # 只有音频
        cmd = [
            FFMPEG, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            output_path,
        ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # 字幕渲染可能失败（字体问题等），fallback 到纯音频
        if srt_path:
            print("\n  [警告] 字幕渲染失败，尝试不带字幕...", end=" ", flush=True)
            cmd_fallback = [
                FFMPEG, "-y",
                "-i", video_path, "-i", audio_path,
                "-c:v", "copy", "-c:a", "aac", "-shortest",
                output_path,
            ]
            result = subprocess.run(cmd_fallback, capture_output=True, text=True)
    return result.returncode == 0


def _render_video(selected, segments, audio_path=None, srt_path=None, suffix=""):
    """渲染一个成品视频"""
    width = CONFIG["output_width"]
    height = CONFIG["output_height"]
    fps = CONFIG["output_fps"]

    print(f"\n  截取镜头...")
    clip_files = []
    for i, (name, dur, *_) in enumerate(segments):
        if i >= len(selected):
            break
        src, start_time = selected[i]
        out_clip = os.path.join(输出目录, f"_clip_{i:02d}_{name}.mp4")
        print(f"    {name} ({dur}s)...", end=" ", flush=True)

        if extract_clip(src, start_time, dur, out_clip, width, height, fps):
            clip_files.append(out_clip)
            print("OK")
        else:
            print("失败")
            return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if audio_path:
        tmp_video = os.path.join(输出目录, f"_tmp_video.mp4")
        output_file = os.path.join(输出目录, f"种草_{timestamp}{suffix}.mp4")

        print(f"  拼接视频...", end=" ", flush=True)
        if not concat_clips(clip_files, tmp_video):
            return None
        print("OK")

        sub_label = " + 字幕" if srt_path else ""
        print(f"  合并音频{sub_label}...", end=" ", flush=True)
        if merge_audio_and_subs(tmp_video, audio_path, srt_path, output_file):
            print("OK")
        else:
            return None
        os.remove(tmp_video)
    else:
        output_file = os.path.join(输出目录, f"种草_{timestamp}{suffix}.mp4")
        print(f"  拼接成片...", end=" ", flush=True)
        if not concat_clips(clip_files, output_file):
            return None
        print("OK")

    for cf in clip_files:
        os.remove(cf)

    total_time = sum(dur for _, dur, *_ in segments)
    print(f"  完成! {total_time}s → {output_file}")
    return output_file


# ========== 模式 1：单视频 ==========

def run_single_video(input_path, mode_config, audio_path=None, srt_path=None):
    total_duration = get_video_duration(input_path)
    print(f"\n素材: {os.path.basename(input_path)}")
    print(f"时长: {total_duration:.1f}s")

    print(f"  分析镜头...", end=" ", flush=True)
    scene_times = detect_scenes(input_path, CONFIG["scene_threshold"])
    print(f"{len(scene_times)} 个镜头")

    segments = mode_config["segments"]
    num_needed = len(segments)
    offset = CONFIG["scene_offset"]

    if len(scene_times) < num_needed:
        interval = total_duration / num_needed
        selected = [(input_path, i * interval) for i in range(num_needed)]
    else:
        interval = total_duration / num_needed
        selected = []
        for i in range(num_needed):
            zone_start = i * interval
            zone_end = (i + 1) * interval
            zone_mid = (zone_start + zone_end) / 2
            best = None
            best_dist = float("inf")
            for t in scene_times:
                actual_t = min(t + offset, total_duration - 0.5)
                if zone_start <= actual_t < zone_end:
                    dist = abs(actual_t - zone_mid)
                    if dist < best_dist:
                        best = actual_t
                        best_dist = dist
            selected.append((input_path, best if best is not None else zone_start))

    return _render_video(selected, segments, audio_path, srt_path)


# ========== 模式 2：素材文件夹 ==========

def run_folder(folder, mode_config, count=3, audio_path=None, srt_path=None):
    videos = find_videos_in_folder(folder)
    if not videos:
        print(f"[错误] 文件夹里没有视频: {folder}")
        sys.exit(1)

    segments = mode_config["segments"]
    split = mode_config["stage_split"]

    print(f"\n素材文件夹: {folder}")
    print(f"视频数量: {len(videos)}")
    print(f"模式: {mode_config['name']}")
    print(f"目标输出: {count} 个成品")

    n = len(videos)
    n_ext = max(1, int(n * split[0]))
    n_int = max(1, int(n * split[1]))
    ext_videos = videos[:n_ext]
    int_videos = videos[n_ext:n_ext + n_int]
    use_videos = videos[n_ext + n_int:]

    if not use_videos:
        use_videos = int_videos[len(int_videos)//2:]
        int_videos = int_videos[:len(int_videos)//2]

    print(f"\n阶段划分:")
    print(f"  外包装（{len(ext_videos)} 条）: {', '.join(os.path.basename(v) for v in ext_videos)}")
    print(f"  内部展示（{len(int_videos)} 条）: {', '.join(os.path.basename(v) for v in int_videos)}")
    print(f"  使用演示（{len(use_videos)} 条）: {', '.join(os.path.basename(v) for v in use_videos)}")

    print(f"\n分析所有素材镜头（含质量过滤）...")
    threshold = CONFIG["scene_threshold"]

    print(f"  外包装:", end=" ", flush=True)
    ext_pool = build_shot_pool(ext_videos, threshold)
    print(f"  {len(ext_pool)} 个可用镜头")

    print(f"  内部展示:", end=" ", flush=True)
    int_pool = build_shot_pool(int_videos, threshold)
    print(f"  {len(int_pool)} 个可用镜头")

    print(f"  使用演示:", end=" ", flush=True)
    use_pool = build_shot_pool(use_videos, threshold)
    print(f"  {len(use_pool)} 个可用镜头")

    ext_needed = sum(1 for _, _, stage in segments if stage == "exterior")
    int_needed = sum(1 for _, _, stage in segments if stage == "interior")
    use_needed = sum(1 for _, _, stage in segments if stage == "usage")

    output_files = []
    ext_offset = 0
    int_offset = 0
    use_offset = 0

    for vid_idx in range(count):
        print(f"\n{'='*44}")
        print(f"  生成第 {vid_idx + 1}/{count} 个成品")
        print(f"{'='*44}")

        ext_shots = []
        for i in range(ext_needed):
            idx = (ext_offset + i) % len(ext_pool) if ext_pool else 0
            if ext_pool:
                ext_shots.append(ext_pool[idx])
        ext_offset += ext_needed

        int_shots = []
        for i in range(int_needed):
            idx = (int_offset + i) % len(int_pool) if int_pool else 0
            if int_pool:
                int_shots.append(int_pool[idx])
        int_offset += int_needed

        use_shots = []
        for i in range(use_needed):
            idx = (use_offset + i) % len(use_pool) if use_pool else 0
            if use_pool:
                use_shots.append(use_pool[idx])
        use_offset += use_needed

        shot_queues = {
            "exterior": list(ext_shots),
            "interior": list(int_shots),
            "usage": list(use_shots),
        }

        selected = []
        for name, dur, stage in segments:
            if shot_queues[stage]:
                shot = shot_queues[stage].pop(0)
                selected.append((shot[0], shot[1]))
            else:
                for s in ["exterior", "interior", "usage"]:
                    if shot_queues[s]:
                        shot = shot_queues[s].pop(0)
                        selected.append((shot[0], shot[1]))
                        break

        for i, (name, dur, stage) in enumerate(segments):
            if i < len(selected):
                src, t = selected[i]
                print(f"  {name:14s} [{stage:8s}] {dur}s → {os.path.basename(src)} @ {t:.1f}s")

        output_file = _render_video(selected, segments, audio_path, srt_path,
                                     suffix=f"_{vid_idx + 1}")
        if output_file:
            output_files.append(output_file)

    return output_files


# ========== 主入口 ==========

def main():
    print("=" * 48)
    print("  QuitMood 种草模板 v4.0 - 全自动剪辑")
    print("=" * 48)

    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 种草剪辑.py 素材文件夹/ [选项]")
        print("  python3 种草剪辑.py 视频.MOV [选项]")
        print()
        print("选项:")
        print("  --mode A|B    产品模式（A=外观型, B=功能型, 默认B）")
        print("  --count N     生成数量（默认3）")
        print("  --audio FILE  配音音频")
        print("  --text FILE   字幕文案（一行一句）")
        sys.exit(1)

    if not os.path.isfile(FFMPEG):
        print(f"[错误] 找不到 ffmpeg: {FFMPEG}")
        sys.exit(1)

    os.makedirs(输出目录, exist_ok=True)

    input_path = sys.argv[1]

    # 解析参数
    mode_key = "B"
    count = 3
    audio_path = None
    no_subs = False
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--mode" and i + 1 < len(sys.argv):
            mode_key = sys.argv[i + 1].upper()
            i += 2
        elif sys.argv[i] == "--count" and i + 1 < len(sys.argv):
            count = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--audio" and i + 1 < len(sys.argv):
            audio_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--no-subs":
            no_subs = True
            i += 1
        else:
            # 兼容旧用法
            audio_path = sys.argv[i]
            i += 1

    if mode_key not in MODES:
        print(f"[错误] 未知模式: {mode_key}，可选 A 或 B")
        sys.exit(1)

    mode_config = MODES[mode_key]
    print(f"模式: {mode_config['name']}")

    # 字幕默认关闭，手动加更好控制
    srt_path = None

    if os.path.isdir(input_path):
        results = run_folder(input_path, mode_config, count=count,
                             audio_path=audio_path, srt_path=srt_path)
        print(f"\n{'='*48}")
        print(f"  全部完成! 共 {len(results)} 个成品")
        print(f"{'='*48}")
        for r in results:
            print(f"  {r}")
    else:
        run_single_video(input_path, mode_config,
                         audio_path=audio_path, srt_path=srt_path)

    # 清理临时字幕文件
    if srt_path and os.path.isfile(srt_path):
        os.remove(srt_path)


if __name__ == "__main__":
    main()
