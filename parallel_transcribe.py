#!/usr/bin/env python3
"""
并行语音转录模块 - 使用 faster-whisper 进行高效的音频转录
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from tqdm import tqdm


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def get_device_and_compute_type(config: dict) -> Tuple[str, str]:
    """根据配置获取设备和计算类型"""
    whisper_config = config.get("whisper", {})
    device = whisper_config.get("device", "auto")
    compute_type = whisper_config.get("compute_type", "int8")
    return device, compute_type


def transcribe_audio(
    input_path: str,
    output_dir: str,
    model_size: str = "small",
    language: str = "auto",
    device: str = "auto",
    compute_type: str = "int8",
) -> dict:
    """
    使用 faster-whisper 转录音频

    Args:
        input_path: 音频或视频文件路径
        output_dir: 输出目录
        model_size: 模型大小 (tiny, base, small, medium, large-v1, large-v2, large-v3)
        language: 语言代码 (auto 为自动检测)
        device: 计算设备 (cpu, cuda, auto)
        compute_type: 计算类型 (int8, float16, float32)

    Returns:
        dict: 转录结果
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "success": False,
        "transcript_file": None,
        "srt_file": None,
        "vtt_file": None,
        "segments": [],
        "detected_language": None,
        "error": None,
    }

    try:
        use_faster = True
        try:
            from faster_whisper import WhisperModel
        except Exception:
            use_faster = False
        segments_list = []
        detected_language = None
        if use_faster:
            print(f"加载 Whisper 模型: {model_size}")
            model = WhisperModel(model_size, device=device, compute_type=compute_type)
            print(f"开始转录: {input_path}")
            segments, info = model.transcribe(
                str(input_path),
                language=language if language != "auto" else None,
                beam_size=5,
                best_of=5,
                condition_on_previous_text=True,
            )
            detected_language = info.language
            for segment in tqdm(segments, desc="转录中"):
                segments_list.append({
                    "id": segment.id,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                })
        else:
            try:
                import whisper
            except Exception:
                result["error"] = "无法加载 faster-whisper，且未安装 openai-whisper"
                print("错误: 无法加载 faster-whisper，且未安装 openai-whisper")
                print("运行: pip install openai-whisper")
                return result
            print(f"加载 OpenAI Whisper 模型: {model_size}")
            model = whisper.load_model(model_size)
            print(f"开始转录: {input_path}")
            wres = model.transcribe(str(input_path), language=None if language == "auto" else language)
            detected_language = wres.get("language")
            for s in wres.get("segments", []):
                segments_list.append({
                    "id": s.get("id", len(segments_list)),
                    "start": float(s.get("start", 0.0)),
                    "end": float(s.get("end", 0.0)),
                    "text": (s.get("text") or "").strip(),
                })

        result["detected_language"] = detected_language
        if detected_language:
            print(f"检测到语言: {detected_language}")

        result["segments"] = segments_list

        transcript_text = "\n".join([s["text"] for s in segments_list])
        transcript_file = output_dir / "transcript.txt"
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(transcript_text)
        result["transcript_file"] = str(transcript_file)
        print(f"✅ 转录文本已保存: {transcript_file}")

        srt_file = output_dir / "subtitle_whisper.srt"
        srt_content = generate_srt(segments_list)
        with open(srt_file, "w", encoding="utf-8") as f:
            f.write(srt_content)
        result["srt_file"] = str(srt_file)
        print(f"✅ SRT 字幕已保存: {srt_file}")

        vtt_file = output_dir / "subtitle_whisper.vtt"
        vtt_content = generate_vtt(segments_list)
        with open(vtt_file, "w", encoding="utf-8") as f:
            f.write(vtt_content)
        result["vtt_file"] = str(vtt_file)
        print(f"✅ VTT 字幕已保存: {vtt_file}")

        json_file = output_dir / "transcript.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        result["success"] = True

    except Exception as e:
        result["error"] = str(e)
        print(f"❌ 转录失败: {e}")

    return result


def generate_srt(segments: List[dict]) -> str:
    """生成 SRT 格式的字幕"""
    srt_lines = []
    for segment in segments:
        start = format_time_srt(segment["start"])
        end = format_time_srt(segment["end"])
        srt_lines.append(f"{segment['id'] + 1}")
        srt_lines.append(f"{start} --> {end}")
        srt_lines.append(segment["text"])
        srt_lines.append("")
    return "\n".join(srt_lines)


def generate_vtt(segments: List[dict]) -> str:
    """生成 VTT 格式的字幕"""
    vtt_lines = ["WEBVTT", ""]
    for segment in segments:
        start = format_time_vtt(segment["start"])
        end = format_time_vtt(segment["end"])
        vtt_lines.append(f"{start} --> {end}")
        vtt_lines.append(segment["text"])
        vtt_lines.append("")
    return "\n".join(vtt_lines)


def format_time_srt(seconds: float) -> str:
    """将秒数转换为 SRT 时间格式 HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_time_vtt(seconds: float) -> str:
    """将秒数转换为 VTT 时间格式 HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def extract_audio_from_video(video_path: str, temp_dir: str = "./temp") -> Optional[str]:
    """从视频文件提取音频"""
    try:
        import ffmpeg
        try:
            import imageio_ffmpeg as i_ffmpeg
            os.environ.setdefault("FFMPEG_BINARY", i_ffmpeg.get_ffmpeg_exe())
        except Exception:
            pass

        video_path = Path(video_path)
        temp_dir = Path(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        audio_path = temp_dir / f"{video_path.stem}.mp3"

        if audio_path.exists():
            return str(audio_path)

        print(f"从视频中提取音频...")
        process = (
            ffmpeg.input(str(video_path))
            .output(str(audio_path), vn=True, acodec="libmp3lame", q="2")
            .overwrite_output()
        )
        process.run(quiet=True)

        return str(audio_path) if audio_path.exists() else None

    except Exception as e:
        print(f"提取音频失败: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Whisper语音转录工具")
    parser.add_argument(
        "--input", "-i", required=True, help="输入音频或视频文件路径"
    )
    parser.add_argument(
        "--output-dir", "-o", default=None, help="输出目录 (默认: 输入文件所在目录)"
    )
    parser.add_argument(
        "--model", "-m", default="small", help="模型大小 (默认: small)"
    )
    parser.add_argument(
        "--language", "-l", default="auto", help="语言代码 (默认: auto)"
    )
    parser.add_argument(
        "--device", "-d", default="auto", help="计算设备 (cpu/cuda/auto)"
    )
    parser.add_argument(
        "--compute-type", "-c", default="int8", help="计算类型 (int8/float16/float32)"
    )
    parser.add_argument(
        "--json", "-j", action="store_true", help="输出JSON格式"
    )

    args = parser.parse_args()

    # 加载配置
    config = load_config()
    whisper_config = config.get("whisper", {})

    # 使用命令行参数或配置
    model_size = args.model or whisper_config.get("model", "small")
    language = args.language or whisper_config.get("language", "auto")

    if args.device == "auto" and whisper_config.get("device"):
        device = whisper_config.get("device")
    else:
        device = args.device

    if args.compute_type == "int8" and whisper_config.get("compute_type"):
        compute_type = whisper_config.get("compute_type")
    else:
        compute_type = args.compute_type

    # 确定输出目录
    input_path = Path(args.input)
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = input_path.parent

    # 检查输入文件类型
    audio_extensions = {".mp3", ".wav", "flac", ".m4a", ".aac", ".ogg", ".wma"}
    video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm"}

    if input_path.suffix.lower() in video_extensions:
        print(f"检测到视频文件，正在提取音频...")
        audio_path = extract_audio_from_video(str(input_path))
        if not audio_path:
            print("❌ 音频提取失败")
            sys.exit(1)
    else:
        audio_path = str(input_path)

    print(f"\n开始转录: {audio_path}")
    print(f"模型: {model_size} | 语言: {language} | 设备: {device}")

    result = transcribe_audio(
        input_path=audio_path,
        output_dir=output_dir,
        model_size=model_size,
        language=language,
        device=device,
        compute_type=compute_type,
    )

    if args.json:
        print("\n" + json.dumps(result, indent=2, ensure_ascii=False))

    if not result["success"]:
        sys.exit(1)

    return result


if __name__ == "__main__":
    main()
