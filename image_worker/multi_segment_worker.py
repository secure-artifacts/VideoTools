"""
multi_segment_worker.py — 多片段合成引擎 QThread

每个片段：
  - 时长 ≥ 8s  → 只选图片 + 动态特效
  - 时长 < 8s  → 随机选图片或视频（视频截取前 N 秒）
合成方式：
  1. 每段生成临时视频（纯视频流，无音频）
  2. concat demuxer 拼接所有临时视频
  3. 加入配音音频（精准时长，音量可调），输出最终视频
"""
import os
import random
import subprocess
import tempfile
import sys

from PyQt6.QtCore import QThread, pyqtSignal

# 支持的图片和视频扩展名
_IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"}
_VID_EXT = {".mp4", ".avi", ".mov", ".mkv", ".m4v"}

# Ken Burns / 动态特效映射（与 image_merge_worker 一致）
_EFFECT_MAP = {
    "中心缓慢放大 (Zoom Center)":      "zoompan=z='min(max(zoom,1)+0.0015,1.5)':x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':d={frames}:s={w}x{h}",
    "左上角放大 (Zoom Top-Left)":       "zoompan=z='min(max(zoom,1)+0.0015,1.5)':x='0':y='0':d={frames}:s={w}x{h}",
    "右上角放大 (Zoom Top-Right)":      "zoompan=z='min(max(zoom,1)+0.0015,1.5)':x='iw-(iw/zoom)':y='0':d={frames}:s={w}x{h}",
    "左下角放大 (Zoom Bottom-Left)":    "zoompan=z='min(max(zoom,1)+0.0015,1.5)':x='0':y='ih-(ih/zoom)':d={frames}:s={w}x{h}",
    "右下角放大 (Zoom Bottom-Right)":   "zoompan=z='min(max(zoom,1)+0.0015,1.5)':x='iw-(iw/zoom)':y='ih-(ih/zoom)':d={frames}:s={w}x{h}",
    "缩小 (Zoom Out)":                  "zoompan=z='if(lt(on,15), 1+(on/15)*0.5, max(1.5-(on-15)*0.0008, 1))':x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':d={frames}:s={w}x{h}",
    "向上平移 (Pan Up)":                "zoompan=z='1.3':x='iw/2-(iw/zoom)/2':y='(ih-ih/zoom)*(1 - (on/{frames})*0.3)':d={frames}:s={w}x{h}",
    "黑白 (B&W)":                       "colorchannelmixer=.3:.4:.3:0:.3:.4:.3:0:.3:.4:.3:0",
    "增强对比 (EQ)":                    "eq=contrast=1.2:brightness=0.05:saturation=1.3",
    "随机":                             "__random__",
}

_ZOOM_EFFECTS = [k for k in _EFFECT_MAP if "Zoom" in k or "Pan" in k]

_TRANS_MAP = {
    "淡入淡出 (fade)":  "fade",
    "滑动 (slideleft)": "slideleft",
    "颜色擦去":         "colorwipe",
    "直线擦去":         "wipeleft",
    "无转场":           None,
}


def _get_files(folder: str, exts: set) -> list[str]:
    if not os.path.isdir(folder):
        return []
    result = []
    for f in os.listdir(folder):
        if os.path.splitext(f)[1].lower() in exts:
            result.append(os.path.join(folder, f))
    return result


def _get_target_dimensions(aspect_ratio: str, resolution: str):
    res_map = {"720P": (720, 1280), "1080P": (1080, 1920), "2K": (1440, 2560), "4K": (2160, 3840)}
    short_edge, long_edge = res_map.get(resolution, (1080, 1920))
    if aspect_ratio == "16:9":   return long_edge,  short_edge,             "16/9"
    elif aspect_ratio == "9:16": return short_edge, long_edge,              "9/16"
    elif aspect_ratio == "3:4":  return short_edge, int(short_edge * 4 / 3), "3/4"
    elif aspect_ratio == "4:5":  return short_edge, int(short_edge * 5 / 4), "4/5"
    elif aspect_ratio == "1:1":  return short_edge, short_edge,             "1/1"
    else:                        return short_edge, long_edge,              "9/16"


class MultiSegmentWorker(QThread):
    """
    Signals:
        progress(int percent, str message)
        finished(bool success, str message)
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(
        self,
        segments: list[dict],   # [{"text": str, "folder": str, "start": float, "end": float}, ...]
        root_dir: str,
        audio_path: str,
        output_file: str,
        aspect_ratio: str,
        resolution: str,
        effect_name: str,
        transition_name: str,
        audio_volume: int,      # 0-200
        ffmpeg_path: str,
        ffprobe_path: str,
        parent=None,
    ):
        super().__init__(parent)
        self.segments       = segments
        self.root_dir       = root_dir
        self.audio_path     = audio_path
        self.output_file    = output_file
        self.aspect_ratio   = aspect_ratio
        self.resolution     = resolution
        self.effect_name    = effect_name
        self.transition_name = transition_name
        self.audio_volume   = audio_volume
        self.ffmpeg_path    = ffmpeg_path
        self.ffprobe_path   = ffprobe_path
        self._stop_flag     = False

    def stop(self):
        self._stop_flag = True

    # ── helpers ──────────────────────────────────────────────────────────────

    def _run_ffmpeg(self, cmd: list) -> tuple[bool, str]:
        """Run an ffmpeg command. Returns (success, stderr_tail)."""
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            _out, stderr = proc.communicate()
            if proc.returncode != 0:
                tail = "\n".join(stderr.strip().split("\n")[-5:])
                return False, tail
            return True, ""
        except Exception as e:
            return False, str(e)

    def _get_video_duration(self, path: str) -> float:
        cmd = [
            self.ffprobe_path, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return float(res.stdout.strip())
        except Exception:
            return 0.0

    def _get_audio_bitrate(self, audio_path: str) -> str:
        try:
            cmd = [
                self.ffprobe_path, "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=bit_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ]
            res = subprocess.run(
                cmd, capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            raw = res.stdout.strip()
            if raw and raw.isdigit():
                kbps = max(96, min(320, int(raw) // 1000))
                return f"{kbps}k"
        except Exception:
            pass
        return "192k"

    def _resolve_effect(self, w: int, h: int, frames: int) -> str:
        name = self.effect_name
        if name == "随机":
            name = random.choice(_ZOOM_EFFECTS)
        tpl = _EFFECT_MAP.get(name, "")
        if not tpl or tpl == "__random__":
            return ""
        return tpl.format(w=w, h=h, frames=frames)

    def _build_image_segment(self, img_path: str, duration: float,
                              w: int, h: int, out_path: str) -> tuple[bool, str]:
        """Convert a single image to a video clip with optional Ken-Burns effect."""
        fps = 25
        frames = max(1, int(duration * fps))

        is_zoom = "Zoom" in self.effect_name or "Pan" in self.effect_name or self.effect_name == "随机"
        scale_w, scale_h = (w * 2, h * 2) if is_zoom else (w, h)

        eff = self._resolve_effect(w, h, frames)

        # Build filter chain
        chain = (
            f"[0:v]fps={fps},"
            f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=decrease,"
            f"pad={scale_w}:{scale_h}:(ow-iw)/2:(oh-ih)/2"
        )
        if eff:
            chain += f",{eff}"
        chain += f",scale={w}:{h}:force_original_aspect_ratio=decrease,"
        chain += f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
        chain += "setpts=PTS-STARTPTS,setsar=1,format=yuv420p[outv]"

        cmd = [
            self.ffmpeg_path, "-y",
            "-loop", "1", "-t", f"{duration:.3f}", "-i", img_path,
            "-filter_complex", chain,
            "-map", "[outv]",
            "-an",
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-t", f"{duration:.3f}",
            out_path,
        ]
        return self._run_ffmpeg(cmd)

    def _build_video_segment(self, vid_path: str, duration: float,
                              w: int, h: int, out_path: str) -> tuple[bool, str]:
        """Trim + scale a video clip to exact duration."""
        chain = (
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
            "setsar=1,fps=25,format=yuv420p[outv]"
        )
        cmd = [
            self.ffmpeg_path, "-y",
            "-t", f"{duration:.3f}", "-i", vid_path,
            "-filter_complex", chain,
            "-map", "[outv]",
            "-an",
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-t", f"{duration:.3f}",
            out_path,
        ]
        return self._run_ffmpeg(cmd)

    def _concat_segments(self, clip_paths: list[str], out_path: str) -> tuple[bool, str]:
        """Use concat demuxer to join all clips."""
        # Write a temp list file
        tmp_list_fd, tmp_list = tempfile.mkstemp(suffix=".txt")
        try:
            with os.fdopen(tmp_list_fd, "w", encoding="utf-8") as f:
                for p in clip_paths:
                    f.write(f"file '{p.replace(chr(39), chr(39)+chr(39))}'\n")

            cmd = [
                self.ffmpeg_path, "-y",
                "-f", "concat", "-safe", "0",
                "-i", tmp_list,
                "-c", "copy",
                "-an",
                out_path,
            ]
            return self._run_ffmpeg(cmd)
        finally:
            try:
                os.remove(tmp_list)
            except Exception:
                pass

    def _concat_segments_with_transition(
        self, clip_paths: list[str], durations: list[float],
        out_path: str, w: int, h: int
    ) -> tuple[bool, str]:
        """Concat clips with xfade transitions."""
        trans = _TRANS_MAP.get(self.transition_name)
        if trans is None or len(clip_paths) == 1:
            return self._concat_segments(clip_paths, out_path)

        fade_dur = 0.5  # seconds
        inputs = []
        for p in clip_paths:
            inputs.extend(["-i", p])

        filter_parts = []
        v_labels = []
        for idx in range(len(clip_paths)):
            lbl = f"[v{idx}]"
            filter_parts.append(f"[{idx}:v]setpts=PTS-STARTPTS{lbl}")
            v_labels.append(lbl)

        current = v_labels[0]
        running_offset = durations[0] - fade_dur
        for idx in range(1, len(clip_paths)):
            nxt = v_labels[idx]
            out_lbl = f"[xf{idx}]" if idx < len(clip_paths) - 1 else "[outv]"
            safe_offset = max(0.0, running_offset)
            filter_parts.append(
                f"{current}{nxt}xfade=transition={trans}:"
                f"duration={fade_dur}:offset={safe_offset:.3f}{out_lbl}"
            )
            current = out_lbl
            running_offset += durations[idx] - fade_dur

        if len(clip_paths) == 1:
            # Only one clip — just rename stream
            filter_parts = [f"[0:v]setpts=PTS-STARTPTS[outv]"]

        filter_complex = ";".join(filter_parts)

        cmd = [
            self.ffmpeg_path, "-y",
        ] + inputs + [
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-an",
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            out_path,
        ]
        return self._run_ffmpeg(cmd)

    def _add_audio(self, video_path: str, audio_path: str,
                   total_duration: float, out_path: str) -> tuple[bool, str]:
        """Mix the voiceover audio into the video (trim to total_duration, apply volume)."""
        vol = self.audio_volume / 100.0
        bitrate = self._get_audio_bitrate(audio_path)

        a_filters = [f"volume={vol:.3f}"]
        a_filters.extend([
            f"atrim=duration={total_duration:.3f}",
            "asetpts=PTS-STARTPTS",
            "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo",
        ])
        filter_complex = f"[1:a]{','.join(a_filters)}[outa]"

        cmd = [
            self.ffmpeg_path, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[outa]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", bitrate,
            "-t", f"{total_duration:.3f}",
            out_path,
        ]
        return self._run_ffmpeg(cmd)

    # ── main ─────────────────────────────────────────────────────────────────

    def run(self):
        target_w, target_h, _ = _get_target_dimensions(self.aspect_ratio, self.resolution)
        total_segs = len(self.segments)
        if total_segs == 0:
            self.finished.emit(False, "没有可合成的片段。")
            return

        tmp_dir = tempfile.mkdtemp(prefix="multiseg_")
        clip_paths: list[str] = []
        clip_durations: list[float] = []
        skipped: list[int] = []

        try:
            for i, seg in enumerate(self.segments):
                if self._stop_flag:
                    self.finished.emit(False, "用户手动停止了任务。")
                    return

                pct = int((i / total_segs) * 80)
                self.progress.emit(pct, f"正在处理第 {i+1}/{total_segs} 片段...")

                duration = seg.get("end", 0.0) - seg.get("start", 0.0)
                if duration <= 0:
                    skipped.append(i + 1)
                    continue

                folder_name = seg.get("folder", "").strip()
                folder_path = os.path.join(self.root_dir, folder_name)

                images = _get_files(folder_path, _IMG_EXT)
                videos = _get_files(folder_path, _VID_EXT)

                if not images and not videos:
                    skipped.append(i + 1)
                    continue

                use_video = (duration < 8.0) and bool(videos) and (random.random() < 0.5)

                clip_out = os.path.join(tmp_dir, f"clip_{i:04d}.mp4")

                if use_video:
                    asset = random.choice(videos)
                    ok, err = self._build_video_segment(asset, duration, target_w, target_h, clip_out)
                else:
                    if not images:
                        # No images fallback — use video if available
                        if videos:
                            asset = random.choice(videos)
                            ok, err = self._build_video_segment(asset, duration, target_w, target_h, clip_out)
                        else:
                            skipped.append(i + 1)
                            continue
                    else:
                        asset = random.choice(images)
                        ok, err = self._build_image_segment(asset, duration, target_w, target_h, clip_out)

                if not ok:
                    self.finished.emit(False, f"第 {i+1} 段合成失败：\n{err}")
                    return

                clip_paths.append(clip_out)
                clip_durations.append(duration)

            if not clip_paths:
                self.finished.emit(False, "所有片段都被跳过（文件夹不存在或无素材），无法生成视频。")
                return

            # ── Step 2: Concat all clips ──────────────────────────────────
            self.progress.emit(82, "正在拼接所有片段...")
            concat_out = os.path.join(tmp_dir, "concat.mp4")
            ok, err = self._concat_segments_with_transition(
                clip_paths, clip_durations, concat_out, target_w, target_h
            )
            if not ok:
                self.finished.emit(False, f"片段拼接失败：\n{err}")
                return

            # ── Step 3: Add audio ─────────────────────────────────────────
            total_duration = sum(clip_durations)
            has_audio = bool(self.audio_path and os.path.isfile(self.audio_path))

            self.progress.emit(92, "正在合入配音音频...")
            if has_audio:
                ok, err = self._add_audio(concat_out, self.audio_path, total_duration, self.output_file)
                if not ok:
                    self.finished.emit(False, f"添加配音失败：\n{err}")
                    return
            else:
                # No audio — just copy concat result
                import shutil
                shutil.copy2(concat_out, self.output_file)

            self.progress.emit(100, "完成！")

            skip_info = f"\n（第 {', '.join(str(s) for s in skipped)} 段因无素材被跳过）" if skipped else ""
            self.finished.emit(True, f"视频已生成：\n{self.output_file}{skip_info}")

        finally:
            # Clean up temp files
            import shutil
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass
