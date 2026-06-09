"""
ui_multi_segment.py — 多片段合成主界面

用户流程：
  1. 在表格中手动输入或从 Excel 粘贴两列数据（文案片段 | 文件夹名）
  2. 上传配音音频 → Whisper 对齐 → 时间戳自动填入表格
  3. 选择素材根目录
  4. 配置合成参数（画幅 / 分辨率 / 动态特效 / 转场 / 音量）
  5. 开始合成 → 输出最终视频
"""
import json
import os
import sys
from datetime import datetime

from PyQt6.QtCore import Qt, QSettings, QEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QDoubleSpinBox, QSpinBox,
    QFileDialog, QProgressBar, QMessageBox, QFrame,
    QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractSpinBox, QSlider, QSizePolicy, QDialog, QPlainTextEdit,
    QAbstractItemView,
)
from PyQt6.QtGui import QColor, QFont, QKeySequence, QShortcut

from image_worker.whisper_worker import WhisperWorker
from image_worker.multi_segment_worker import MultiSegmentWorker


# ══════════════════════════════════════════════════════════════════════════════
#  MultiSegmentUI
# ══════════════════════════════════════════════════════════════════════════════

class MultiSegmentUI(QWidget):

    def __init__(self):
        super().__init__()

        # State
        self.audio_path: str = ""
        self.root_dir:   str = ""
        self.base_dir:   str = ""   # output base dir
        self.output_dir: str = ""
        self._whisper_worker  = None
        self._compose_worker  = None
        self.settings = QSettings("MyCompany", "VideoToolbox")

        self.setup_ui()
        self.bind_events()
        self.load_settings()

    # ── Settings ───────────────────────────────────────────────────────────

    def load_settings(self):
        self.combo_aspect_ratio.setCurrentText(
            self.settings.value("ms_aspect_ratio", "9:16 (竖屏/抖音)"))
        self.combo_resolution.setCurrentText(
            self.settings.value("ms_resolution", "1080P (1K/推荐)"))
        self.combo_effect.setCurrentText(
            self.settings.value("ms_effect", "中心缓慢放大 (Zoom Center)"))
        self.combo_transition.setCurrentText(
            self.settings.value("ms_transition", "淡入淡出 (fade)"))
        self.combo_whisper_model.setCurrentText(
            self.settings.value("ms_whisper_model", "medium"))
        self.spin_audio_volume.setValue(
            self.settings.value("ms_audio_volume", 100, type=int))
        self.slider_audio_volume.setValue(
            self.settings.value("ms_audio_volume", 100, type=int))

        saved_root = self.settings.value("ms_root_dir", "")
        if saved_root and os.path.exists(saved_root):
            self.root_dir = saved_root
            self.lbl_root_dir.setText(f"已选择: {saved_root}")
            self._refresh_folder_list()

        saved_base = self.settings.value("ms_base_dir", "")
        if saved_base and os.path.exists(saved_base):
            self.base_dir = saved_base
            self.lbl_out_path.setText(f"已选择: {saved_base}")

        saved_audio = self.settings.value("ms_audio_path", "")
        if saved_audio and os.path.exists(saved_audio):
            self.audio_path = saved_audio
            self.lbl_audio_path.setText(os.path.basename(saved_audio))

        # Restore table
        try:
            raw = self.settings.value("ms_table_data", "[]")
            rows = json.loads(raw) if raw else []
            if rows:
                self.table.setRowCount(0)
                for row in rows:
                    self._append_row(
                        row.get("text", ""),
                        row.get("folder", ""),
                        row.get("start", ""),
                        row.get("end", ""),
                    )
        except Exception:
            pass

    def save_settings(self):
        self.settings.setValue("ms_aspect_ratio", self.combo_aspect_ratio.currentText())
        self.settings.setValue("ms_resolution",   self.combo_resolution.currentText())
        self.settings.setValue("ms_effect",        self.combo_effect.currentText())
        self.settings.setValue("ms_transition",    self.combo_transition.currentText())
        self.settings.setValue("ms_whisper_model", self.combo_whisper_model.currentText())
        self.settings.setValue("ms_audio_volume",  self.spin_audio_volume.value())
        self.settings.setValue("ms_root_dir",      self.root_dir)
        self.settings.setValue("ms_base_dir",      self.base_dir)
        self.settings.setValue("ms_audio_path",    self.audio_path)

        rows = []
        for r in range(self.table.rowCount()):
            rows.append({
                "text":   self._cell(r, 1),
                "folder": self._cell(r, 2),
                "start":  self._cell(r, 3),
                "end":    self._cell(r, 4),
            })
        self.settings.setValue("ms_table_data", json.dumps(rows, ensure_ascii=False))

    # ── UI ─────────────────────────────────────────────────────────────────

    def create_card(self, title: str):
        card = QFrame()
        card.setProperty("class", "Card")
        lo = QVBoxLayout(card)
        lo.setContentsMargins(15, 15, 15, 15)
        lo.setSpacing(10)
        lbl = QLabel(title)
        lbl.setProperty("class", "CardTitle")
        lo.addWidget(lbl)
        return card, lo

    def setup_ui(self):
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
        main.setSpacing(2)

        # ── Card 1: 文案表格 ──────────────────────────────────────────────
        card1, lo1 = self.create_card("📋 文案片段与分类（手动粘贴或输入）")

        hint = QLabel(
            "💡  在表格中输入文案片段（A列）和对应文件夹名（B列）。\n"
            "支持直接从 Excel/WPS 复制两列数据后，点击表格任意单元格再按 Ctrl+V 粘贴。"
        )
        hint.setStyleSheet("color: #6b7280; font-size: 9pt;")
        hint.setWordWrap(True)
        lo1.addWidget(hint)

        # Table: 序号 | 文案片段 | 文件夹名 | 开始(秒) | 结束(秒)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "文案片段", "文件夹名", "开始(秒)", "结束(秒)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 80)
        self.table.setMinimumHeight(240)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        lo1.addWidget(self.table)

        # Table toolbar
        tbl_btn_row = QHBoxLayout()
        self.btn_add_row    = QPushButton("➕ 添加行")
        self.btn_del_row    = QPushButton("➖ 删除行")
        self.btn_clear_tbl  = QPushButton("🗑️ 清空表格")
        self.btn_paste_help = QPushButton("📋 粘贴说明")
        tbl_btn_row.addWidget(self.btn_add_row)
        tbl_btn_row.addWidget(self.btn_del_row)
        tbl_btn_row.addWidget(self.btn_clear_tbl)
        tbl_btn_row.addStretch()
        tbl_btn_row.addWidget(self.btn_paste_help)
        lo1.addLayout(tbl_btn_row)

        main.addWidget(card1)

        # ── Card 2: 配音音频 & Whisper 对齐 ──────────────────────────────
        card2, lo2 = self.create_card("🎵 配音音频与 Whisper 时间戳对齐")

        audio_row = QHBoxLayout()
        self.btn_select_audio = QPushButton("📂 选择配音音频")
        self.lbl_audio_path   = QLabel("未选择")
        self.lbl_audio_path.setStyleSheet("color: #6b7280;")
        audio_row.addWidget(self.btn_select_audio)
        audio_row.addWidget(self.lbl_audio_path, 1)
        lo2.addLayout(audio_row)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Whisper 模型:"))
        self.combo_whisper_model = QComboBox()
        self.combo_whisper_model.addItems(["tiny", "base", "small", "medium", "large"])
        self.combo_whisper_model.setCurrentText("medium")
        self.combo_whisper_model.setMaximumWidth(160)
        self.combo_whisper_model.setToolTip(
            "tiny: 39MB  |  base: 74MB  |  small: 244MB  |  medium: 769MB  |  large: 1.5GB\n"
            "首次使用会自动下载模型，保加利亚语推荐 medium 或 large。"
        )
        model_row.addWidget(self.combo_whisper_model)
        model_row.addSpacing(20)

        self.btn_start_align = QPushButton("🎯 开始对齐")
        self.btn_stop_align  = QPushButton("🛑 停止")
        self.btn_stop_align.setEnabled(False)
        model_row.addWidget(self.btn_start_align)
        model_row.addWidget(self.btn_stop_align)
        model_row.addStretch()
        lo2.addLayout(model_row)

        self.align_progress = QProgressBar()
        self.align_progress.setValue(0)
        lo2.addWidget(self.align_progress)

        self.lbl_align_status = QLabel("未开始")
        self.lbl_align_status.setStyleSheet("color: #6b7280; font-size: 9pt;")
        lo2.addWidget(self.lbl_align_status)

        warn = QLabel("⚠  首次使用 Whisper 会自动下载模型（medium ≈ 769MB），需要网络连接，请耐心等待。")
        warn.setStyleSheet("color: #f59e0b; font-size: 9pt;")
        warn.setWordWrap(True)
        lo2.addWidget(warn)

        # Volume control
        vol_sep = QFrame()
        vol_sep.setFrameShape(QFrame.Shape.HLine)
        vol_sep.setStyleSheet("color: #2b303b;")
        lo2.addWidget(vol_sep)

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("🔊 配音音量:"))
        self.slider_audio_volume = QSlider(Qt.Orientation.Horizontal)
        self.slider_audio_volume.setRange(0, 200)
        self.slider_audio_volume.setValue(100)
        self.slider_audio_volume.setFixedWidth(130)
        self.spin_audio_volume = QSpinBox()
        self.spin_audio_volume.setRange(0, 200)
        self.spin_audio_volume.setValue(100)
        self.spin_audio_volume.setSuffix(" %")
        self.spin_audio_volume.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin_audio_volume.setFixedWidth(72)
        self.spin_audio_volume.setToolTip("0% = 静音 / 100% = 原始音量 / 200% = 双倍音量")
        self.slider_audio_volume.valueChanged.connect(self.spin_audio_volume.setValue)
        self.spin_audio_volume.valueChanged.connect(self.slider_audio_volume.setValue)
        vol_row.addWidget(self.slider_audio_volume)
        vol_row.addWidget(self.spin_audio_volume)
        vol_row.addStretch()
        lo2.addLayout(vol_row)

        main.addWidget(card2)

        # ── Card 3: 素材根目录 ────────────────────────────────────────────
        card3, lo3 = self.create_card("📁 素材根目录")

        root_row = QHBoxLayout()
        self.btn_select_root = QPushButton("📂 选择根目录")
        self.lbl_root_dir    = QLabel("未选择（根目录下的子文件夹即分类文件夹）")
        self.lbl_root_dir.setStyleSheet("color: #6b7280;")
        root_row.addWidget(self.btn_select_root)
        root_row.addWidget(self.lbl_root_dir, 1)
        lo3.addLayout(root_row)

        self.lbl_folder_status = QLabel("")
        self.lbl_folder_status.setWordWrap(True)
        self.lbl_folder_status.setStyleSheet("font-size: 9pt; color: #6b7280;")
        lo3.addWidget(self.lbl_folder_status)

        main.addWidget(card3)

        # ── Card 4: 合成参数 ──────────────────────────────────────────────
        card4, lo4 = self.create_card("⚙️ 合成参数")

        grid = QGridLayout()
        grid.setVerticalSpacing(12)
        grid.setHorizontalSpacing(20)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 1)
        _W = 240

        grid.addWidget(QLabel("画幅(尺寸):"), 0, 0)
        self.combo_aspect_ratio = QComboBox()
        self.combo_aspect_ratio.addItems([
            "9:16 (竖屏/抖音)", "16:9 (横屏/西瓜)", "3:4 (小红书)", "4:5 (Ins)", "1:1 (正方形)"])
        self.combo_aspect_ratio.setMaximumWidth(_W)
        grid.addWidget(self.combo_aspect_ratio, 0, 1)

        grid.addWidget(QLabel("输出分辨率:"), 0, 2)
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems(["1080P (1K/推荐)", "720P (标清)", "2K (超清)", "4K (极清)"])
        self.combo_resolution.setMaximumWidth(_W)
        grid.addWidget(self.combo_resolution, 0, 3)

        grid.addWidget(QLabel("动态特效:"), 1, 0)
        self.combo_effect = QComboBox()
        self.combo_effect.addItems([
            "中心缓慢放大 (Zoom Center)",
            "左上角放大 (Zoom Top-Left)",
            "右上角放大 (Zoom Top-Right)",
            "左下角放大 (Zoom Bottom-Left)",
            "右下角放大 (Zoom Bottom-Right)",
            "缩小 (Zoom Out)",
            "向上平移 (Pan Up)",
            "黑白 (B&W)",
            "增强对比 (EQ)",
            "随机",
        ])
        self.combo_effect.setMaximumWidth(_W)
        grid.addWidget(self.combo_effect, 1, 1)

        grid.addWidget(QLabel("转场特效:"), 1, 2)
        self.combo_transition = QComboBox()
        self.combo_transition.addItems([
            "淡入淡出 (fade)", "滑动 (slideleft)", "颜色擦去", "直线擦去", "无转场"])
        self.combo_transition.setMaximumWidth(_W)
        grid.addWidget(self.combo_transition, 1, 3)

        lo4.addLayout(grid)
        main.addWidget(card4)

        # ── Card 5: 输出与执行 ────────────────────────────────────────────
        card5, lo5 = self.create_card("💾 输出与执行")

        out_row = QHBoxLayout()
        self.btn_out_path = QPushButton("选择输出目录")
        self.lbl_out_path = QLabel("默认: 未选择")
        self.lbl_out_path.setStyleSheet("color: #888;")
        out_row.addWidget(self.btn_out_path)
        out_row.addWidget(self.lbl_out_path, 1)
        out_row.addStretch()
        lo5.addLayout(out_row)

        self.compose_progress = QProgressBar()
        self.compose_progress.setValue(0)
        lo5.addWidget(self.compose_progress)

        self.lbl_compose_status = QLabel("准备就绪...")
        lo5.addWidget(self.lbl_compose_status)

        exec_row = QHBoxLayout()
        self.btn_start_compose = QPushButton("🚀 开始合成视频")
        self.btn_start_compose.setObjectName("PrimaryBtn")
        self.btn_start_compose.setFixedHeight(45)
        self.btn_stop_compose  = QPushButton("🛑 停止")
        self.btn_stop_compose.setEnabled(False)
        self.btn_stop_compose.setFixedHeight(45)
        exec_row.addWidget(self.btn_start_compose, 3)
        exec_row.addWidget(self.btn_stop_compose,  1)
        lo5.addLayout(exec_row)

        main.addWidget(card5)
        main.addStretch()

    # ── Events ─────────────────────────────────────────────────────────────

    def bind_events(self):
        # Table toolbar
        self.btn_add_row.clicked.connect(self._add_table_row)
        self.btn_del_row.clicked.connect(self._delete_selected_rows)
        self.btn_clear_tbl.clicked.connect(self._clear_table)
        self.btn_paste_help.clicked.connect(self._show_paste_help)

        # Ctrl+V on table
        shortcut = QShortcut(QKeySequence("Ctrl+V"), self.table)
        shortcut.activated.connect(self._paste_from_clipboard)

        # Audio
        self.btn_select_audio.clicked.connect(self._select_audio)

        # Whisper align
        self.btn_start_align.clicked.connect(self._start_align)
        self.btn_stop_align.clicked.connect(self._stop_align)

        # Root dir
        self.btn_select_root.clicked.connect(self._select_root_dir)

        # Table cell changed → refresh folder status
        self.table.cellChanged.connect(lambda r, c: self._refresh_folder_list() if c == 2 else None)

        # Output
        self.btn_out_path.clicked.connect(self._select_output_dir)

        # Compose
        self.btn_start_compose.clicked.connect(self._start_compose)
        self.btn_stop_compose.clicked.connect(self._stop_compose)

    # ── Table helpers ─────────────────────────────────────────────────────

    def _cell(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

    def _append_row(self, text: str = "", folder: str = "",
                    start: str = "", end: str = ""):
        r = self.table.rowCount()
        self.table.insertRow(r)

        # Col 0: row number (read-only)
        num_item = QTableWidgetItem(str(r + 1))
        num_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(r, 0, num_item)

        self.table.setItem(r, 1, QTableWidgetItem(text))
        self.table.setItem(r, 2, QTableWidgetItem(folder))

        for col, val in [(3, start), (4, end)]:
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, col, item)

    def _renumber_rows(self):
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                item.setText(str(r + 1))

    def _add_table_row(self):
        self._append_row()

    def _delete_selected_rows(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)
        self._renumber_rows()

    def _clear_table(self):
        reply = QMessageBox.question(self, "确认", "确定要清空所有行吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.table.setRowCount(0)

    def _show_paste_help(self):
        QMessageBox.information(
            self, "粘贴说明",
            "在 Excel / WPS 中选中两列数据（A列=文案片段，B列=文件夹名），复制后：\n\n"
            "1. 点击表格中的任意单元格\n"
            "2. 按 Ctrl+V\n\n"
            "数据将自动解析并追加到表格末尾。\n"
            "支持 Tab 分隔（Excel 默认复制格式）。"
        )

    def _paste_from_clipboard(self):
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return

        self.table.blockSignals(True)
        pasted = 0
        for line in text.splitlines():
            line = line.rstrip("\r")
            if not line.strip():
                continue
            parts = line.split("\t")
            seg_text = parts[0].strip() if len(parts) > 0 else ""
            folder   = parts[1].strip() if len(parts) > 1 else ""
            if seg_text or folder:
                self._append_row(seg_text, folder)
                pasted += 1
        self.table.blockSignals(False)

        if pasted > 0:
            self._renumber_rows()
            self._refresh_folder_list()

    # ── Audio ─────────────────────────────────────────────────────────────

    def _select_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择配音音频", "",
            "Audio Files (*.mp3 *.wav *.aac *.ogg *.m4a *.flac)")
        if path:
            self.audio_path = path
            self.lbl_audio_path.setText(os.path.basename(path))
            self.lbl_audio_path.setStyleSheet("color: #10b981; font-weight: bold;")

    # ── Whisper align ─────────────────────────────────────────────────────

    def _collect_user_texts(self) -> list[str]:
        texts = []
        for r in range(self.table.rowCount()):
            t = self._cell(r, 1)
            if t:
                texts.append(t)
        return texts

    def _start_align(self):
        if not self.audio_path or not os.path.isfile(self.audio_path):
            QMessageBox.warning(self, "警告", "请先选择配音音频文件。")
            return
        user_texts = self._collect_user_texts()
        if not user_texts:
            QMessageBox.warning(self, "警告", "表格中没有文案片段，请先填写文案列。")
            return

        self.btn_start_align.setEnabled(False)
        self.btn_stop_align.setEnabled(True)
        self.align_progress.setValue(0)
        self.lbl_align_status.setText("正在启动 Whisper...")

        self._whisper_worker = WhisperWorker(
            audio_path=self.audio_path,
            model=self.combo_whisper_model.currentText(),
            user_texts=user_texts,
        )
        self._whisper_worker.progress.connect(self._on_align_progress)
        self._whisper_worker.finished.connect(self._on_align_finished)
        self._whisper_worker.error.connect(self._on_align_error)
        self._whisper_worker.start()

    def _stop_align(self):
        if self._whisper_worker:
            self._whisper_worker.stop()

    def _on_align_progress(self, pct: int, msg: str):
        self.align_progress.setValue(pct)
        self.lbl_align_status.setText(msg)

    def _on_align_finished(self, aligned: list):
        self.btn_start_align.setEnabled(True)
        self.btn_stop_align.setEnabled(False)
        self.align_progress.setValue(100)
        self.lbl_align_status.setText(f"✅ 对齐完成，共 {len(aligned)} 段")

        # Fill timestamps back into table (only rows that have text)
        aligned_idx = 0
        for r in range(self.table.rowCount()):
            if self._cell(r, 1) and aligned_idx < len(aligned):
                seg = aligned[aligned_idx]
                start_item = QTableWidgetItem(f"{seg['start']:.2f}")
                end_item   = QTableWidgetItem(f"{seg['end']:.2f}")
                start_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                end_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                start_item.setForeground(QColor("#10b981"))
                end_item.setForeground(QColor("#10b981"))
                self.table.setItem(r, 3, start_item)
                self.table.setItem(r, 4, end_item)
                aligned_idx += 1

    def _on_align_error(self, msg: str):
        self.btn_start_align.setEnabled(True)
        self.btn_stop_align.setEnabled(False)
        self.lbl_align_status.setText(f"❌ 错误: {msg}")
        QMessageBox.critical(self, "对齐失败", msg)

    # ── Root dir ──────────────────────────────────────────────────────────

    def _select_root_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择素材根目录")
        if path:
            self.root_dir = path
            self.lbl_root_dir.setText(f"已选择: {path}")
            self._refresh_folder_list()

    def _refresh_folder_list(self):
        if not self.root_dir or not os.path.isdir(self.root_dir):
            self.lbl_folder_status.setText("")
            return

        # Folders used in table (B列)
        used_folders: set[str] = set()
        for r in range(self.table.rowCount()):
            f = self._cell(r, 2).strip()
            if f:
                used_folders.add(f)

        # Folders existing in root_dir
        try:
            existing = {
                name for name in os.listdir(self.root_dir)
                if os.path.isdir(os.path.join(self.root_dir, name))
            }
        except Exception:
            existing = set()

        ok_folders      = used_folders & existing
        missing_folders = used_folders - existing

        lines = []
        if ok_folders:
            lines.append("✅ 找到文件夹: " + "、".join(sorted(ok_folders)))
        if missing_folders:
            lines.append("⚠️ 缺少文件夹（表格中使用但根目录内不存在）: " +
                         "、".join(sorted(missing_folders)))
        if not used_folders:
            lines.append("（表格中尚未填写文件夹名）")

        self.lbl_folder_status.setText("\n".join(lines))
        if missing_folders:
            self.lbl_folder_status.setStyleSheet("font-size: 9pt; color: #f59e0b;")
        else:
            self.lbl_folder_status.setStyleSheet("font-size: 9pt; color: #10b981;")

    # ── Output dir ────────────────────────────────────────────────────────

    def _select_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.base_dir = path
            self.lbl_out_path.setText(f"已选择: {path}")

    # ── Compose ───────────────────────────────────────────────────────────

    def _collect_segments(self) -> list[dict] | None:
        """Collect and validate table data."""
        segments = []
        errors   = []
        for r in range(self.table.rowCount()):
            text   = self._cell(r, 1)
            folder = self._cell(r, 2)
            start  = self._cell(r, 3)
            end    = self._cell(r, 4)

            if not text and not folder:
                continue

            if not folder:
                errors.append(f"第 {r+1} 行：缺少文件夹名")
                continue

            try:
                s = float(start) if start else None
                e = float(end)   if end   else None
            except ValueError:
                errors.append(f"第 {r+1} 行：时间戳格式错误")
                continue

            if s is None or e is None:
                errors.append(f"第 {r+1} 行：缺少时间戳，请先执行 Whisper 对齐")
                continue

            if e <= s:
                errors.append(f"第 {r+1} 行：结束时间必须大于开始时间")
                continue

            segments.append({
                "text":   text,
                "folder": folder,
                "start":  s,
                "end":    e,
            })

        if errors:
            QMessageBox.warning(self, "数据错误", "\n".join(errors[:10]))
            return None
        return segments

    def _resolve_ffmpeg_paths(self):
        if getattr(sys, "frozen", False):
            root = os.path.dirname(sys.executable)
        else:
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ffmpeg  = os.path.join(root, "ffmpeg", "ffmpeg.exe")
        ffprobe = os.path.join(root, "ffmpeg", "ffprobe.exe")
        return ffmpeg, ffprobe

    def _start_compose(self):
        segments = self._collect_segments()
        if segments is None:
            return
        if not segments:
            QMessageBox.warning(self, "警告", "表格中没有有效的片段数据。")
            return
        if not self.root_dir or not os.path.isdir(self.root_dir):
            QMessageBox.warning(self, "警告", "请先选择素材根目录。")
            return
        if not self.base_dir:
            QMessageBox.warning(self, "警告", "请先选择输出目录。")
            return

        ffmpeg, ffprobe = self._resolve_ffmpeg_paths()
        if not os.path.isfile(ffmpeg) or not os.path.isfile(ffprobe):
            QMessageBox.critical(self, "错误",
                f"找不到 ffmpeg.exe 或 ffprobe.exe！\n期望路径：{os.path.dirname(ffmpeg)}")
            return

        prefix = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = os.path.join(self.base_dir, prefix)
        os.makedirs(out_dir, exist_ok=True)
        output_file = os.path.join(out_dir, f"multi_segment_{prefix}.mp4")

        aspect = self.combo_aspect_ratio.currentText().split(" ")[0]
        res    = self.combo_resolution.currentText().split(" ")[0]

        self.btn_start_compose.setEnabled(False)
        self.btn_stop_compose.setEnabled(True)
        self.compose_progress.setValue(0)
        self.lbl_compose_status.setText("正在初始化合成引擎...")

        self._compose_worker = MultiSegmentWorker(
            segments       = segments,
            root_dir       = self.root_dir,
            audio_path     = self.audio_path,
            output_file    = output_file,
            aspect_ratio   = aspect,
            resolution     = res,
            effect_name    = self.combo_effect.currentText(),
            transition_name= self.combo_transition.currentText(),
            audio_volume   = self.spin_audio_volume.value(),
            ffmpeg_path    = ffmpeg,
            ffprobe_path   = ffprobe,
        )
        self._compose_worker.progress.connect(self._on_compose_progress)
        self._compose_worker.finished.connect(self._on_compose_finished)
        self._compose_worker.start()

    def _stop_compose(self):
        if self._compose_worker:
            self._compose_worker.stop()

    def _on_compose_progress(self, pct: int, msg: str):
        self.compose_progress.setValue(pct)
        self.lbl_compose_status.setText(msg)

    def _on_compose_finished(self, success: bool, msg: str):
        self.btn_start_compose.setEnabled(True)
        self.btn_stop_compose.setEnabled(False)
        if success:
            self.compose_progress.setValue(100)
            self.lbl_compose_status.setText("✅ 合成完成！")
            QMessageBox.information(self, "完成", msg)
        else:
            self.lbl_compose_status.setText("❌ 合成失败")
            QMessageBox.critical(self, "错误", msg)
