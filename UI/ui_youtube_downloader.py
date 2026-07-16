import os
import sys
import subprocess
import re
import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QComboBox, QSpinBox, QFileDialog, QFrame,
    QProgressBar, QListWidget, QListWidgetItem, QAbstractSpinBox,
    QScrollArea, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QFont


# ─────────────────────────────────────────────────────────────────────────────
#  后台工作线程
# ─────────────────────────────────────────────────────────────────────────────

class YtdlpWorker(QThread):
    """在后台线程中逐条下载 YouTube 链接，实时回报进度。"""

    # (index, status_text, percent)
    item_progress = pyqtSignal(int, str, int)
    # (index, success, message)
    item_done = pyqtSignal(int, bool, str)
    # (total_percent, status_text)
    overall_progress = pyqtSignal(int, str)
    # (success, message)  整体完成
    all_done = pyqtSignal(bool, str)
    # 原始日志行（用于错误面板）
    log_line = pyqtSignal(str)

    def __init__(self, urls: list[str], fmt: str, quality: str,
                 threads: int, output_dir: str, ffmpeg_dir: str):
        super().__init__()
        self.urls = urls
        self.fmt = fmt
        self.quality = quality
        self.threads = threads
        self.output_dir = output_dir
        self.ffmpeg_dir = ffmpeg_dir
        self._stop_flag = False
        self._current_proc = None

    def stop(self):
        self._stop_flag = True
        if self._current_proc and self._current_proc.poll() is None:
            self._current_proc.terminate()

    # ------------------------------------------------------------------
    def _build_args(self) -> list[str]:
        """根据格式/画质设置构造 yt-dlp 命令行参数（不含 URL）。"""
        args = ["yt-dlp", "--newline", "--no-playlist"]

        # ffmpeg 路径
        if self.ffmpeg_dir and os.path.isdir(self.ffmpeg_dir):
            args += ["--ffmpeg-location", self.ffmpeg_dir]

        # 并发片段数（yt-dlp 内置分片下载）
        args += ["--concurrent-fragments", str(self.threads)]

        # 输出模板
        out_template = os.path.join(self.output_dir, "%(title)s.%(ext)s")
        args += ["-o", out_template]

        if self.fmt == "MP3（仅音频）":
            # 纯音频：提取最佳音质并转为 mp3
            args += [
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
            ]
        else:
            # ── 修复：不在视频流上指定 ext，由 ffmpeg 负责最终格式转换 ──
            # YouTube 的 DASH 流通常是 webm/mp4，直接限定 ext 会导致 code 1
            height_map = {
                "480p":       "480",
                "720p":       "720",
                "1080p":      "1080",
                "2K (1440p)": "1440",
                "4K (2160p)": "2160",
            }
            h = height_map.get(self.quality, "1080")

            # 格式优先级：
            #   1. 目标高度内最佳视频 + m4a 音频（最兼容）
            #   2. 目标高度内最佳视频 + 任意最佳音频
            #   3. 目标高度内合并流
            #   4. 任意最佳（兜底）
            fmt_sel = (
                f"bestvideo[height<={h}]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={h}]+bestaudio/"
                f"best[height<={h}]/best"
            )
            args += [
                "-f", fmt_sel,
                "--merge-output-format", self.fmt,
            ]

        return args

    # ------------------------------------------------------------------
    def _read_stderr(self, proc, stderr_lines: list):
        """在独立线程中持续读取 stderr，防止管道阻塞。"""
        try:
            for line in proc.stderr:
                line = line.strip()
                if line:
                    stderr_lines.append(line)
                    self.log_line.emit(f"[ERR] {line}")
        except Exception:
            pass

    def run(self):
        total = len(self.urls)
        base_args = self._build_args()
        succeeded = 0
        failed = 0

        for idx, url in enumerate(self.urls):
            if self._stop_flag:
                break

            self.item_progress.emit(idx, "⏳ 正在连接...", 0)
            overall_pct = int(idx / total * 100)
            self.overall_progress.emit(overall_pct, f"正在下载第 {idx+1}/{total} 个...")
            self.log_line.emit(f"\n{'─'*60}")
            self.log_line.emit(f"[{idx+1}/{total}] 开始下载: {url}")

            cmd = base_args + [url]
            self.log_line.emit(f"[CMD] {' '.join(cmd)}")

            try:
                self._current_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,   # ← 修复：单独捕获 stderr
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )

                stderr_lines: list[str] = []
                # 用独立线程读 stderr，防止死锁
                stderr_thread = threading.Thread(
                    target=self._read_stderr,
                    args=(self._current_proc, stderr_lines),
                    daemon=True,
                )
                stderr_thread.start()

                last_pct = 0
                for line in self._current_proc.stdout:
                    if self._stop_flag:
                        self._current_proc.terminate()
                        break

                    line = line.strip()
                    if not line:
                        continue

                    self.log_line.emit(f"[OUT] {line}")

                    # 解析进度行，例如: [download]  45.3% of ...
                    m = re.search(r"\[download\]\s+([\d.]+)%", line)
                    if m:
                        pct = int(float(m.group(1)))
                        last_pct = pct
                        self.item_progress.emit(idx, f"⏳ 下载中 {pct}%", pct)
                        fine = (idx + pct / 100) / total * 100
                        self.overall_progress.emit(int(fine),
                            f"正在下载第 {idx+1}/{total} 个 ({pct}%)")
                    elif "[Merger]" in line or "Merging" in line:
                        self.item_progress.emit(idx, "🔧 合并中...", last_pct)
                    elif "[ExtractAudio]" in line or "Destination:" in line:
                        self.item_progress.emit(idx, "🎵 转码中...", last_pct)

                stderr_thread.join(timeout=5)
                self._current_proc.wait()
                retcode = self._current_proc.returncode

                if self._stop_flag:
                    self.item_done.emit(idx, False, "已停止")
                    break
                elif retcode == 0:
                    succeeded += 1
                    self.item_done.emit(idx, True, "✅ 下载完成")
                    self.log_line.emit(f"[OK] 第 {idx+1} 个下载成功")
                else:
                    failed += 1
                    # 将 stderr 最后几行作为错误摘要显示
                    err_summary = " | ".join(stderr_lines[-3:]) if stderr_lines else f"code {retcode}"
                    # 截断过长的错误摘要
                    if len(err_summary) > 120:
                        err_summary = err_summary[:117] + "..."
                    self.item_done.emit(idx, False, f"❌ 失败: {err_summary}")
                    self.log_line.emit(f"[FAIL] code={retcode}, 原因: {err_summary}")

            except FileNotFoundError:
                failed += 1
                msg = "❌ 找不到 yt-dlp，请先执行: pip install yt-dlp"
                self.item_done.emit(idx, False, msg)
                self.log_line.emit(f"[FAIL] {msg}")
                break
            except Exception as e:
                failed += 1
                self.item_done.emit(idx, False, f"❌ 异常: {e}")
                self.log_line.emit(f"[FAIL] 异常: {e}")

        if self._stop_flag:
            self.all_done.emit(False, f"已停止。完成 {succeeded} 个，失败 {failed} 个。")
        else:
            self.overall_progress.emit(100, "全部完成！")
            ok = (failed == 0)
            msg = f"全部下载完成！共 {succeeded} 个成功，{failed} 个失败。"
            self.all_done.emit(ok, msg)


# ─────────────────────────────────────────────────────────────────────────────
#  主 UI 类
# ─────────────────────────────────────────────────────────────────────────────

class YouTubeDownloaderUI(QWidget):
    """YouTube 视频/音频批量下载界面。"""

    def __init__(self):
        super().__init__()
        self.worker: YtdlpWorker | None = None
        self.output_dir = ""
        self.settings = QSettings("MyCompany", "VideoToolbox")
        self._item_widgets: dict[int, QListWidgetItem] = {}

        self._setup_ui()
        self._bind_events()
        self.load_settings()

    # ── 设置持久化 ────────────────────────────────────────────────────────

    def load_settings(self):
        self.combo_format.setCurrentText(
            self.settings.value("yt_format", "mp4"))
        self.combo_quality.setCurrentText(
            self.settings.value("yt_quality", "1080p"))
        self.spin_threads.setValue(
            self.settings.value("yt_threads", 4, type=int))
        saved_dir = self.settings.value("yt_output_dir", "")
        if saved_dir and os.path.isdir(saved_dir):
            self.output_dir = saved_dir
            self.lbl_out_path.setText(f"已选择: {saved_dir}")
        self._on_format_changed()

    def save_settings(self):
        self.settings.setValue("yt_format", self.combo_format.currentText())
        self.settings.setValue("yt_quality", self.combo_quality.currentText())
        self.settings.setValue("yt_threads", self.spin_threads.value())
        self.settings.setValue("yt_output_dir", self.output_dir)

    # ── UI 构建 ───────────────────────────────────────────────────────────

    def _create_card(self, title: str):
        card = QFrame()
        card.setProperty("class", "Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        lbl = QLabel(title)
        lbl.setProperty("class", "CardTitle")
        layout.addWidget(lbl)
        return card, layout

    def _setup_ui(self):
        # 外层滚动区域，与其他标签页完全一致
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        outer.addWidget(scroll)

        inner = QWidget()
        inner.setAutoFillBackground(False)
        scroll.setWidget(inner)
        main = QVBoxLayout(inner)
        main.setContentsMargins(0, 0, 1, 0)
        main.setSpacing(10)

        # ── 板块一：链接输入 ──────────────────────────────────────────────
        card1, lay1 = self._create_card("🔗 板块一 · 输入 YouTube 链接（每行一个）")

        hint = QLabel("支持批量粘贴，每行对应一个视频链接。含播放列表参数（&list=...）的链接自动只下载单个视频。")
        hint.setStyleSheet("color: #6b7280; font-size: 9pt;")
        hint.setWordWrap(True)
        lay1.addWidget(hint)

        self.text_urls = QPlainTextEdit()
        self.text_urls.setPlaceholderText(
            "https://www.youtube.com/watch?v=xxxxxxx\n"
            "https://www.youtube.com/watch?v=yyyyyyy\n"
            "..."
        )
        self.text_urls.setMinimumHeight(140)
        self.text_urls.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay1.addWidget(self.text_urls)

        url_btn_row = QHBoxLayout()
        url_btn_row.addStretch()
        self.btn_clear_urls = QPushButton("🗑 清空链接")
        url_btn_row.addWidget(self.btn_clear_urls)
        lay1.addLayout(url_btn_row)

        main.addWidget(card1)

        # ── 板块二：参数设置 ──────────────────────────────────────────────
        card2, lay2 = self._create_card("⚙️ 板块二 · 下载参数设置")

        params_row1 = QHBoxLayout()
        params_row1.setSpacing(20)

        # 格式
        fmt_col = QVBoxLayout()
        fmt_col.setSpacing(4)
        fmt_col.addWidget(QLabel("输出格式："))
        self.combo_format = QComboBox()
        self.combo_format.addItems(["mp4", "mkv", "webm", "MP3（仅音频）"])
        self.combo_format.setMinimumWidth(160)
        fmt_col.addWidget(self.combo_format)
        params_row1.addLayout(fmt_col)

        # 画质
        qual_col = QVBoxLayout()
        qual_col.setSpacing(4)
        self.lbl_quality = QLabel("视频画质：")
        qual_col.addWidget(self.lbl_quality)
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(["480p", "720p", "1080p", "2K (1440p)", "4K (2160p)"])
        self.combo_quality.setMinimumWidth(160)
        qual_col.addWidget(self.combo_quality)
        params_row1.addLayout(qual_col)

        # 线程数
        thread_col = QVBoxLayout()
        thread_col.setSpacing(4)
        thread_col.addWidget(QLabel("并发线程数（分片下载）："))
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 32)
        self.spin_threads.setValue(4)
        self.spin_threads.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self.spin_threads.setMinimumWidth(100)
        self.spin_threads.setToolTip(
            "控制单个视频的并发分片下载数量。\n"
            "建议值：4~8（线程越多对服务器压力越大）"
        )
        thread_col.addWidget(self.spin_threads)
        params_row1.addLayout(thread_col)

        params_row1.addStretch()
        lay2.addLayout(params_row1)

        # 输出目录
        out_row = QHBoxLayout()
        out_row.setSpacing(10)
        self.btn_out_path = QPushButton("📁 选择输出目录")
        self.btn_out_path.setFixedWidth(150)
        self.lbl_out_path = QLabel("尚未选择输出目录")
        self.lbl_out_path.setStyleSheet("color: #6b7280;")
        out_row.addWidget(self.btn_out_path)
        out_row.addWidget(self.lbl_out_path, 1)
        lay2.addLayout(out_row)

        main.addWidget(card2)

        # ── 板块三：进度面板 ──────────────────────────────────────────────
        card3, lay3 = self._create_card("📊 板块三 · 下载进度")

        # 每条链接的状态列表
        self.list_progress = QListWidget()
        self.list_progress.setMinimumHeight(160)
        self.list_progress.setAlternatingRowColors(False)
        self.list_progress.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list_progress.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lay3.addWidget(self.list_progress)

        # 总体进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setTextVisible(True)
        lay3.addWidget(self.progress_bar)

        # 状态文本
        self.lbl_status = QLabel("就绪 — 请输入链接并点击「开始下载」")
        self.lbl_status.setStyleSheet("color: #6b7280; font-size: 9pt;")
        lay3.addWidget(self.lbl_status)

        # 操作按钮行
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("🚀 开始下载")
        self.btn_start.setObjectName("PrimaryBtn")
        self.btn_start.setFixedHeight(46)

        self.btn_stop = QPushButton("🛑 停止下载")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setFixedHeight(46)

        self.btn_clear_log = QPushButton("🗑 清空日志")
        self.btn_clear_log.setFixedHeight(46)
        self.btn_clear_log.setFixedWidth(110)

        btn_row.addWidget(self.btn_start, stretch=3)
        btn_row.addWidget(self.btn_stop, stretch=1)
        btn_row.addWidget(self.btn_clear_log)
        lay3.addLayout(btn_row)

        main.addWidget(card3)

        # ── 板块四：错误日志 ──────────────────────────────────────────────
        card4, lay4 = self._create_card("🔍 板块四 · 详细日志（可用于排查失败原因）")

        log_hint = QLabel("下载过程中的所有输出实时显示在此，失败时可查看具体错误信息。")
        log_hint.setStyleSheet("color: #6b7280; font-size: 9pt;")
        lay4.addWidget(log_hint)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(180)
        self.log_view.setFont(QFont("Consolas", 9))
        self.log_view.setPlaceholderText("日志将在下载开始后显示...")
        self.log_view.setStyleSheet(
            "QPlainTextEdit { background-color: #0d1117; color: #c9d1d9; "
            "border: 1px solid #30363d; border-radius: 6px; padding: 6px; }"
        )
        lay4.addWidget(self.log_view)

        main.addWidget(card4)
        main.addStretch()

    # ── 事件绑定 ──────────────────────────────────────────────────────────

    def _bind_events(self):
        self.btn_clear_urls.clicked.connect(self.text_urls.clear)
        self.btn_out_path.clicked.connect(self._select_output_dir)
        self.btn_start.clicked.connect(self._start_download)
        self.btn_stop.clicked.connect(self._stop_download)
        self.btn_clear_log.clicked.connect(self.log_view.clear)
        self.combo_format.currentTextChanged.connect(self._on_format_changed)

    # ── 槽函数 ────────────────────────────────────────────────────────────

    def _on_format_changed(self, _=None):
        is_audio = self.combo_format.currentText() == "MP3（仅音频）"
        self.combo_quality.setEnabled(not is_audio)
        self.lbl_quality.setEnabled(not is_audio)
        if is_audio:
            self.combo_quality.setToolTip("音频模式下无需设置画质")
        else:
            self.combo_quality.setToolTip("")

    def _select_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.output_dir = d
            self.lbl_out_path.setText(f"已选择: {d}")
            self.lbl_out_path.setStyleSheet("")

    def _get_urls(self) -> list[str]:
        raw = self.text_urls.toPlainText().strip()
        urls = [u.strip() for u in raw.splitlines() if u.strip()]
        return urls

    # ── 开始下载 ──────────────────────────────────────────────────────────

    def _start_download(self):
        urls = self._get_urls()
        if not urls:
            QMessageBox.warning(self, "提示", "请先输入至少一个 YouTube 链接！")
            return
        if not self.output_dir:
            QMessageBox.warning(self, "提示", "请先选择输出目录！")
            return

        # 初始化进度列表
        self.list_progress.clear()
        self._item_widgets.clear()
        self.log_view.clear()
        for idx, url in enumerate(urls):
            short = url if len(url) <= 60 else url[:57] + "..."
            item = QListWidgetItem(f"  [{idx+1:02d}]  {short}  —  ⏳ 等待中")
            item.setFont(QFont("Consolas", 9))
            self.list_progress.addItem(item)
            self._item_widgets[idx] = item

        self.progress_bar.setValue(0)
        self.lbl_status.setText(f"准备下载 {len(urls)} 个视频...")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

        # 找 ffmpeg 目录
        if getattr(sys, 'frozen', False):
            _root = os.path.dirname(sys.executable)
        else:
            _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ffmpeg_dir = os.path.join(_root, "ffmpeg")
        if not os.path.isdir(ffmpeg_dir):
            ffmpeg_dir = ""

        self.worker = YtdlpWorker(
            urls=urls,
            fmt=self.combo_format.currentText(),
            quality=self.combo_quality.currentText(),
            threads=self.spin_threads.value(),
            output_dir=self.output_dir,
            ffmpeg_dir=ffmpeg_dir,
        )
        self.worker.item_progress.connect(self._on_item_progress)
        self.worker.item_done.connect(self._on_item_done)
        self.worker.overall_progress.connect(self._on_overall_progress)
        self.worker.all_done.connect(self._on_all_done)
        self.worker.log_line.connect(self._on_log_line)
        self.worker.start()

    def _stop_download(self):
        if self.worker:
            self.worker.stop()
            self.lbl_status.setText("正在停止，请稍候...")
            self.btn_stop.setEnabled(False)

    # ── Worker 信号槽 ─────────────────────────────────────────────────────

    def _on_item_progress(self, idx: int, text: str, pct: int):
        item = self._item_widgets.get(idx)
        if not item:
            return
        urls = self._get_urls()
        url = urls[idx] if idx < len(urls) else ""
        short = url if len(url) <= 55 else url[:52] + "..."
        item.setText(f"  [{idx+1:02d}]  {short}  —  {text}")

    def _on_item_done(self, idx: int, success: bool, msg: str):
        item = self._item_widgets.get(idx)
        if not item:
            return
        urls = self._get_urls()
        url = urls[idx] if idx < len(urls) else ""
        short = url if len(url) <= 55 else url[:52] + "..."
        item.setText(f"  [{idx+1:02d}]  {short}  —  {msg}")
        if success:
            item.setForeground(Qt.GlobalColor.green)
        else:
            item.setForeground(Qt.GlobalColor.red)
        self.list_progress.scrollToItem(item)

    def _on_overall_progress(self, pct: int, text: str):
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(text)

    def _on_log_line(self, line: str):
        """将日志追加到日志面板，自动滚动到底部。"""
        self.log_view.appendPlainText(line)
        # 滚动到最新行
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_all_done(self, success: bool, message: str):
        self.progress_bar.setValue(100 if success else self.progress_bar.value())
        self.lbl_status.setText(message)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.warning(self, "下载结束", message)
