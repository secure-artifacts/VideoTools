"""
whisper_worker.py — QThread 封装：调用 whisper_runner.py 并对齐文案时间戳

流程：
1. 用 subprocess.Popen 启动 whisper_runner.py
2. 实时读取 stdout，解析 PROGRESS: 行更新进度
3. 读取输出 JSON，用 difflib 将 Whisper segment 与用户文案片段对齐
4. 发出 finished(list) 信号，每项 {"start": float, "end": float}
"""
import difflib
import json
import os
import subprocess
import sys
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal


def _find_whisper_runner():
    """定位 whisper_runner.py 的路径。打包后在 exe 同级目录；开发时在项目根目录。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "whisper_runner.py")


def _normalize_text(text: str) -> str:
    """将文本转小写，去除多余空白，方便相似度比较。"""
    return " ".join(text.lower().split())


def align_segments(whisper_segments: list[dict], user_texts: list[str]) -> list[dict]:
    """
    将 Whisper 识别出的 segment 序列对齐到用户的文案片段序列。

    策略：
    - 将所有 Whisper segment 的文本按时间顺序拼接，形成全文。
    - 同时记录每个字符在全文中对应的 Whisper segment 索引。
    - 对每段用户文案，用 difflib 在全文中找最佳匹配位置。
    - 从匹配到的字符范围，反推对应的 start/end 时间戳。
    """
    if not whisper_segments:
        return [{"start": 0.0, "end": 0.0} for _ in user_texts]

    # 拼接全文，记录字符→segment 映射
    full_text = ""
    char_to_seg: list[int] = []   # 每个字符属于哪个 segment
    for seg_idx, seg in enumerate(whisper_segments):
        seg_text = seg["text"] + " "
        full_text += seg_text
        char_to_seg.extend([seg_idx] * len(seg_text))

    full_norm = _normalize_text(full_text)

    # 为每段用户文案找时间戳
    results: list[dict] = []
    search_start = 0  # 从上一次匹配结束处继续搜索（防止倒序匹配）

    for user_text in user_texts:
        user_norm = _normalize_text(user_text)
        if not user_norm:
            results.append({"start": 0.0, "end": 0.0})
            continue

        # 在 full_norm[search_start:] 中搜索最佳匹配
        search_window = full_norm[search_start:]
        matcher = difflib.SequenceMatcher(
            None, user_norm, search_window, autojunk=False
        )
        best_ratio = 0.0
        best_a, best_b, best_size = 0, 0, 0

        for block in matcher.get_matching_blocks():
            a, b, size = block
            if size == 0:
                continue
            ratio = size / max(len(user_norm), 1)
            if ratio > best_ratio:
                best_ratio = ratio
                best_a, best_b, best_size = a, b, size

        if best_ratio < 0.3 or best_size == 0:
            # 匹配度太低，用全文位置估算（按比例）
            frac = len(results) / max(len(user_texts), 1)
            total_dur = whisper_segments[-1]["end"]
            est_start = total_dur * frac
            est_end   = total_dur * (frac + 1.0 / max(len(user_texts), 1))
            results.append({"start": round(est_start, 3), "end": round(est_end, 3)})
            continue

        # 计算在原始 full_norm 中的绝对字符位置
        match_char_start = search_start + best_b
        match_char_end   = match_char_start + best_size

        # 更新搜索起点（让下一段从此处往后找）
        search_start = match_char_end

        # 反推 segment 索引（字符数可能与 whisper_segments 文本字符数有偏差，做安全 clamp）
        def char_to_time(char_pos: int, side: str) -> float:
            # char_pos 是在 full_norm 中的位置，但 char_to_seg 是基于原始 full_text 的
            # 两者长度可能不同（normalize 会改变空白）。做比例缩放。
            ratio = char_pos / max(len(full_norm), 1)
            raw_char = int(ratio * len(full_text))
            raw_char = max(0, min(raw_char, len(char_to_seg) - 1))
            seg_idx = char_to_seg[raw_char]
            seg = whisper_segments[seg_idx]
            return seg["start"] if side == "start" else seg["end"]

        t_start = char_to_time(match_char_start, "start")
        t_end   = char_to_time(match_char_end - 1, "end")

        if t_end <= t_start:
            t_end = t_start + 1.0

        results.append({"start": round(t_start, 3), "end": round(t_end, 3)})

    return results


class WhisperWorker(QThread):
    """
    signals:
        progress(int percent, str message)
        finished(list)   — list of {"start": float, "end": float}
        error(str)
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, audio_path: str, model: str, user_texts: list[str], parent=None):
        super().__init__(parent)
        self.audio_path  = audio_path
        self.model       = model
        self.user_texts  = user_texts
        self._stop_flag  = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        runner_path = _find_whisper_runner()
        if not os.path.isfile(runner_path):
            self.error.emit(f"找不到 whisper_runner.py，期望路径：{runner_path}")
            return

        # 临时 JSON 输出文件
        tmp_fd, tmp_json = tempfile.mkstemp(suffix=".json")
        os.close(tmp_fd)

        cmd = [
            sys.executable,
            runner_path,
            "--audio",    self.audio_path,
            "--model",    self.model,
            "--output",   tmp_json,
            "--language", "bg",
        ]

        self.progress.emit(0, "正在启动 Whisper 识别进程...")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )

            for line in proc.stdout:
                if self._stop_flag:
                    proc.terminate()
                    self.error.emit("用户取消了识别。")
                    return

                line = line.rstrip()
                if line.startswith("PROGRESS:"):
                    # 格式: PROGRESS:<percent>:<message>
                    parts = line.split(":", 2)
                    pct  = int(parts[1]) if len(parts) > 1 else 0
                    msg  = parts[2]       if len(parts) > 2 else ""
                    self.progress.emit(pct, msg)
                elif line.startswith("ERROR:"):
                    self.error.emit(line[6:])
                    return
                elif line.startswith("DONE:"):
                    pass  # 识别完成

            proc.wait()
            if proc.returncode != 0:
                self.error.emit("Whisper 进程异常退出，请检查是否已安装 openai-whisper 和 torch。")
                return

        except Exception as e:
            self.error.emit(f"启动识别进程失败: {e}")
            return

        # 读取 JSON 结果
        self.progress.emit(92, "正在对齐文案时间戳...")
        try:
            with open(tmp_json, "r", encoding="utf-8") as f:
                whisper_segments = json.load(f)
        except Exception as e:
            self.error.emit(f"读取识别结果失败: {e}")
            return
        finally:
            try:
                os.remove(tmp_json)
            except Exception:
                pass

        # 对齐
        try:
            aligned = align_segments(whisper_segments, self.user_texts)
        except Exception as e:
            self.error.emit(f"时间戳对齐失败: {e}")
            return

        self.progress.emit(100, f"对齐完成，共 {len(aligned)} 段")
        self.finished.emit(aligned)
