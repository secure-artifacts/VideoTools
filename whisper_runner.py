"""
whisper_runner.py — 独立 Whisper 音频识别脚本
用法: python whisper_runner.py --audio <path> --model <model> --output <json_path>

主程序通过 subprocess.Popen 调用此脚本。
进度通过 stdout 实时输出（每行一条状态消息），结果写入 JSON 文件。
"""
import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Whisper 音频识别脚本")
    parser.add_argument("--audio",  required=True,  help="输入音频文件路径")
    parser.add_argument("--model",  default="medium", help="Whisper 模型大小 (tiny/base/small/medium/large)")
    parser.add_argument("--output", required=True,  help="输出 JSON 文件路径")
    parser.add_argument("--language", default="bg", help="识别语言代码，默认 bg（保加利亚语）")
    args = parser.parse_args()

    if not os.path.isfile(args.audio):
        print(f"ERROR: 找不到音频文件: {args.audio}", flush=True)
        sys.exit(1)

    print(f"PROGRESS:5:正在加载 Whisper {args.model} 模型（首次使用需下载）...", flush=True)

    try:
        import whisper
    except ImportError:
        print("ERROR: 未安装 openai-whisper，请运行: pip install openai-whisper", flush=True)
        sys.exit(1)

    try:
        model = whisper.load_model(args.model)
    except Exception as e:
        print(f"ERROR: 加载模型失败: {e}", flush=True)
        sys.exit(1)

    print(f"PROGRESS:20:模型加载完成，开始识别音频...", flush=True)

    try:
        result = model.transcribe(
            args.audio,
            language=args.language,
            word_timestamps=False,  # segment 级别已足够
            verbose=False,
        )
    except Exception as e:
        print(f"ERROR: 识别失败: {e}", flush=True)
        sys.exit(1)

    print("PROGRESS:90:识别完成，正在写入结果...", flush=True)

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": round(float(seg["start"]), 3),
            "end":   round(float(seg["end"]),   3),
            "text":  seg["text"].strip(),
        })

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"ERROR: 写入 JSON 失败: {e}", flush=True)
        sys.exit(1)

    print(f"PROGRESS:100:完成，共识别 {len(segments)} 段", flush=True)
    print(f"DONE:{args.output}", flush=True)


if __name__ == "__main__":
    main()
