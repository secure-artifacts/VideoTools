# ui_auto_screenshot.py
"""
「📸 链接截图」标签页 UI
功能：批量输入视频链接 → 下载 → 分帧截图
可选：保存视频 / 保存音频
"""

import os
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QSpinBox, QDoubleSpinBox, QLineEdit,
    QFileDialog, QFrame, QProgressBar, QAbstractSpinBox,
    QScrollArea, QSizePolicy, QMessageBox, QCheckBox,
    QGridLayout,
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QFont

from image_worker.screenshot_worker import ScreenshotWorker


class AutoScreenshotUI(QWidget):
    """链接批量截图页面"""

    def __init__(self):
        super().__init__()
        self.worker: ScreenshotWorker | None = None
        self.output_dir = ""
        self.settings = QSettings("MyCompany", "VideoToolbox")

        self._setup_ui()
        self._bind_events()
        self.load_settings()

    # ── 持久化设置 ────────────────────────────────────────────────────────

    def load_settings(self):
        self.spin_count.setValue(
            self.settings.value("ss_count", 10, type=int))
        self.spin_interval.setValue(
            self.settings.value("ss_interval", 0.5, type=float))
        self.edit_name.setText(
            self.settings.value("ss_name", "截图项目", type=str))
        self.chk_save_video.setChecked(
            self.settings.value("ss_save_video", False, type=bool))
        self.chk_save_audio.setChecked(
            self.settings.value("ss_save_audio", False, type=bool))
        saved_dir = self.settings.value("ss_output_dir", "")
        if saved_dir and os.path.isdir(saved_dir):
            self.output_dir = saved_dir
            self.lbl_out_path.setText(f"已选择: {saved_dir}")

    def save_settings(self):
        self.settings.setValue("ss_count",      self.spin_count.value())
        self.settings.setValue("ss_interval",   self.spin_interval.value())
        self.settings.setValue("ss_name",       self.edit_name.text().strip())
        self.settings.setValue("ss_save_video", self.chk_save_video.isChecked())
        self.settings.setValue("ss_save_audio", self.chk_save_audio.isChecked())
        self.settings.setValue("ss_output_dir", self.output_dir)

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
        # 外层滚动容器（与其他标签页完全一致）
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

        # ═══════════════════════════════════════════════════════════════════
        # 板块一：链接输入
        # ═══════════════════════════════════════════════════════════════════
        card1, lay1 = self._create_card("🔗 板块一 · 输入视频链接（每行一个）")

        hint1 = QLabel(
            "支持 YouTube、B站、抖音等主流平台链接，批量粘贴，每行一个"
        )
        hint1.setStyleSheet("color: #6b7280; font-size: 9pt;")
        lay1.addWidget(hint1)

        self.text_urls = QPlainTextEdit()
        self.text_urls.setPlaceholderText(
            "https://www.youtube.com/watch?v=xxxxxxx\n"
            "https://www.bilibili.com/video/BVxxxxxxx\n"
            "..."
        )
        self.text_urls.setMinimumHeight(140)
        self.text_urls.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        lay1.addWidget(self.text_urls)

        url_btn_row = QHBoxLayout()
        url_btn_row.addStretch()
        self.btn_clear_urls = QPushButton("🗑 清空链接")
        url_btn_row.addWidget(self.btn_clear_urls)
        lay1.addLayout(url_btn_row)

        main.addWidget(card1)

        # ═══════════════════════════════════════════════════════════════════
        # 板块二：参数设置
        # ═══════════════════════════════════════════════════════════════════
        card2, lay2 = self._create_card("⚙️ 板块二 · 截图参数设置")

        # 参数网格
        grid = QGridLayout()
        grid.setVerticalSpacing(14)
        grid.setHorizontalSpacing(20)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 1)
        _W = 200   # 输入控件最大宽度

        # Row 0 — 截取数量 / 间隔秒数
        grid.addWidget(QLabel("截取数量（张）:"), 0, 0)
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 9999)
        self.spin_count.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin_count.setMaximumWidth(_W)
        self.spin_count.setToolTip("每个视频最多截取多少帧图片")
        grid.addWidget(self.spin_count, 0, 1)

        grid.addWidget(QLabel("截图间隔（秒）:"), 0, 2)
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.1, 60.0)
        self.spin_interval.setSingleStep(0.1)
        self.spin_interval.setDecimals(1)
        self.spin_interval.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin_interval.setMaximumWidth(_W)
        self.spin_interval.setToolTip("相邻两帧之间的时间间隔（秒）")
        grid.addWidget(self.spin_interval, 0, 3)

        # Row 1 — 项目名称
        grid.addWidget(QLabel("项目名称:"), 1, 0)
        self.edit_name = QLineEdit()
        self.edit_name.setMaximumWidth(_W)
        self.edit_name.setToolTip('生成的输出文件夹前缀，如"截图项目_001"')
        grid.addWidget(self.edit_name, 1, 1)

        lay2.addLayout(grid)

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

        # ── 保存开关 ────────────────────────────────────────────────────
        save_row = QHBoxLayout()
        save_row.setSpacing(30)

        # 保存视频 开关
        self.chk_save_video = QCheckBox("🎬  保存视频")
        self.chk_save_video.setToolTip(
            "勾选后：下载的视频文件将一并保存到对应输出目录中"
        )
        save_row.addWidget(self.chk_save_video)

        # 保存音频 开关
        self.chk_save_audio = QCheckBox("🎵  保存音频")
        self.chk_save_audio.setToolTip(
            "勾选后：从视频中提取音频（mp3），保存到对应输出目录中"
        )
        save_row.addWidget(self.chk_save_audio)

        save_row.addStretch()

        # 开关容器 Frame（加个背景让开关区更突出）
        save_frame = QFrame()
        save_frame.setObjectName("SaveToggleFrame")
        save_frame.setStyleSheet("""
            QFrame#SaveToggleFrame {
                border: 1px dashed #374151;
                border-radius: 8px;
                padding: 4px 8px;
            }
        """)
        save_frame.setLayout(save_row)
        lay2.addWidget(save_frame)

        main.addWidget(card2)

        # ═══════════════════════════════════════════════════════════════════
        # 板块三：进度与日志
        # ═══════════════════════════════════════════════════════════════════
        card3, lay3 = self._create_card("📊 板块三 · 进度与运行日志")

        # 总进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setTextVisible(True)
        lay3.addWidget(self.progress_bar)

        # 状态文字
        self.lbl_status = QLabel("就绪 — 请输入链接并点击「开始执行」")
        self.lbl_status.setStyleSheet("color: #6b7280; font-size: 9pt;")
        lay3.addWidget(self.lbl_status)

        # 实时日志区
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(220)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setPlaceholderText("运行日志将在此处实时显示...")
        lay3.addWidget(self.log_text)

        # 操作按钮
        btn_row = QHBoxLayout()
        self.btn_clear_log = QPushButton("🗑 清空日志")
        self.btn_clear_log.setFixedWidth(110)
        btn_row.addWidget(self.btn_clear_log)
        btn_row.addStretch()

        self.btn_start = QPushButton("🚀 开始执行任务")
        self.btn_start.setObjectName("PrimaryBtn")
        self.btn_start.setFixedHeight(46)

        self.btn_stop = QPushButton("🛑 停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setFixedHeight(46)

        btn_row.addWidget(self.btn_start, stretch=3)
        btn_row.addWidget(self.btn_stop, stretch=1)
        lay3.addLayout(btn_row)

        main.addWidget(card3)
        main.addStretch()

    # ── 事件绑定 ──────────────────────────────────────────────────────────

    def _bind_events(self):
        self.btn_clear_urls.clicked.connect(self.text_urls.clear)
        self.btn_clear_log.clicked.connect(self.log_text.clear)
        self.btn_out_path.clicked.connect(self._select_output_dir)
        self.btn_start.clicked.connect(self._start_task)
        self.btn_stop.clicked.connect(self._stop_task)

    # ── 槽函数 ────────────────────────────────────────────────────────────

    def _select_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.output_dir = d
            self.lbl_out_path.setText(f"已选择: {d}")
            self.lbl_out_path.setStyleSheet("")

    def _get_urls(self) -> list:
        raw = self.text_urls.toPlainText().strip()
        return [u.strip() for u in raw.splitlines() if u.strip()]

    def _append_log(self, msg: str):
        self.log_text.appendPlainText(msg)
        # 自动滚动到底部
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ── 开始任务 ──────────────────────────────────────────────────────────

    def _start_task(self):
        urls = self._get_urls()
        if not urls:
            QMessageBox.warning(self, "提示", "请先输入至少一个视频链接！")
            return
        if not self.output_dir:
            QMessageBox.warning(self, "提示", "请先选择输出目录！")
            return
        if not self.edit_name.text().strip():
            QMessageBox.warning(self, "提示", "请填写项目名称！")
            return

        # 定位 ffmpeg 目录
        if getattr(sys, "frozen", False):
            _root = os.path.dirname(sys.executable)
        else:
            _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ffmpeg_dir = os.path.join(_root, "ffmpeg")
        if not os.path.isdir(ffmpeg_dir):
            ffmpeg_dir = ""

        # 初始化 UI 状态
        self.log_text.clear()
        self.progress_bar.setValue(0)
        self.lbl_status.setText(f"准备处理 {len(urls)} 个链接...")
        self._set_running(True)

        self.worker = ScreenshotWorker(
            urls             = urls,
            max_count        = self.spin_count.value(),
            interval         = self.spin_interval.value(),
            base_path        = self.output_dir,
            base_folder_name = self.edit_name.text().strip(),
            save_video       = self.chk_save_video.isChecked(),
            save_audio       = self.chk_save_audio.isChecked(),
            ffmpeg_dir       = ffmpeg_dir,
        )
        self.worker.log_signal.connect(self._append_log)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _stop_task(self):
        if self.worker:
            self.worker.stop()
            self.lbl_status.setText("正在停止，请稍候...")
            self.btn_stop.setEnabled(False)

    def _set_running(self, running: bool):
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)

    # ── Worker 信号槽 ─────────────────────────────────────────────────────

    def _on_progress(self, pct: int, text: str):
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(text)

    def _on_finished(self, success: bool, message: str):
        self._set_running(False)
        self.progress_bar.setValue(100 if success else self.progress_bar.value())
        self.lbl_status.setText(message)
        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.warning(self, "任务结束", message)
