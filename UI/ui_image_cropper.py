import os
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QListWidget, 
                             QProgressBar, QMessageBox, QFrame)
from PyQt6.QtCore import Qt, QEvent, QSettings

from image_worker.image_worker import ImageWorker

class ImageCropperUI(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.base_dir = ""
        self.output_dir = ""
        self.settings = QSettings("MyCompany", "VideoToolbox")
        
        self.setup_ui()
        self.bind_events()
        self.load_settings()

    def load_settings(self):
        saved_dir = self.settings.value("c_base_dir", "")
        if saved_dir and os.path.exists(saved_dir):
            self.base_dir = saved_dir
            self.lbl_out_path.setText(f"已选择: {self.base_dir}")

    def save_settings(self):
        self.settings.setValue("c_base_dir", self.base_dir)

    def create_card(self, title):
        card = QFrame()
        card.setProperty("class", "Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        lbl_title = QLabel(title)
        lbl_title.setProperty("class", "CardTitle")
        layout.addWidget(lbl_title)
        return card, layout

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)

        card_upload, layout_upload = self.create_card("🖼️ 输入图片")
        self.file_list = QListWidget()
        self.file_list.setAcceptDrops(True)
        self.file_list.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        self.file_list.installEventFilter(self)
        self.file_list.setToolTip("将图片文件拖拽至此处")
        layout_upload.addWidget(self.file_list)

        btn_layout = QHBoxLayout()
        self.btn_add_files = QPushButton("添加图片")
        self.btn_add_folder = QPushButton("添加文件夹")
        self.btn_clear = QPushButton("清空列表")
        btn_layout.addWidget(self.btn_add_files)
        btn_layout.addWidget(self.btn_add_folder)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_clear)
        layout_upload.addLayout(btn_layout)
        main_layout.addWidget(card_upload)

        card_action, layout_action = self.create_card("💾 输出与执行")
        path_layout = QHBoxLayout()
        self.btn_out_path = QPushButton("选择输出目录")
        self.lbl_out_path = QLabel("默认: 未选择")
        self.lbl_out_path.setStyleSheet("color: #888;")
        path_layout.addWidget(self.btn_out_path)
        path_layout.addWidget(self.lbl_out_path)
        path_layout.addStretch()
        layout_action.addLayout(path_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout_action.addWidget(self.progress_bar)
        
        self.lbl_status = QLabel("准备就绪...")
        layout_action.addWidget(self.lbl_status)

        action_btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("🚀 开始批量裁剪 (9:16)")
        self.btn_start.setObjectName("PrimaryBtn") 
        self.btn_stop = QPushButton("🛑 停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setMinimumHeight(45)
        
        action_btn_layout.addWidget(self.btn_start, stretch=3)
        action_btn_layout.addWidget(self.btn_stop, stretch=1)
        layout_action.addLayout(action_btn_layout)

        main_layout.addWidget(card_action)
        main_layout.addStretch()

    def bind_events(self):
        self.btn_add_files.clicked.connect(self.add_files)
        self.btn_add_folder.clicked.connect(self.add_folder)
        self.btn_clear.clicked.connect(self.file_list.clear)
        self.btn_out_path.clicked.connect(self.select_output_dir)
        self.btn_start.clicked.connect(self.start_crop)
        self.btn_stop.clicked.connect(self.stop_crop)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)")
        for f in files:
            self.file_list.addItem(f)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            for root, _, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff')):
                        self.file_list.addItem(os.path.join(root, file))

    def select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择基础输出文件夹")
        if dir_path:
            self.base_dir = dir_path
            self.lbl_out_path.setText(f"已选择: {self.base_dir}")

    def start_crop(self):
        if self.file_list.count() == 0 or not self.base_dir:
            QMessageBox.warning(self, "警告", "请先上传图片并选择输出路径！")
            return

        prefix = datetime.now().strftime("%Y%m%d")
        self.output_dir = os.path.join(self.base_dir, f"图片批量裁剪_{prefix}")
        
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法创建输出文件夹，请检查是否被拦截！\n{str(e)}")
            return

        all_images = [self.file_list.item(i).text() for i in range(self.file_list.count())]
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)

        self.worker = ImageWorker(image_paths=all_images, output_dir=self.output_dir)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.task_finished)
        self.worker.start()

    def stop_crop(self):
        if self.worker:
            self.worker.stop()
            self.lbl_status.setText("正在停止...")

    def update_progress(self, percent, text):
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(text)

    def task_finished(self, success, message):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if success:
            QMessageBox.information(self, "完成", message)
            self.lbl_status.setText("全部完成！")
        else:
            QMessageBox.critical(self, "提示", message)
            self.lbl_status.setText("已停止或发生错误。")

    def eventFilter(self, source, event):
        if source is self.file_list:
            if event.type() == QEvent.Type.DragEnter or event.type() == QEvent.Type.DragMove:
                if event.mimeData().hasUrls():
                    event.accept()
                    return True
            elif event.type() == QEvent.Type.Drop:
                for url in event.mimeData().urls():
                    path = url.toLocalFile()
                    if path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff')):
                        self.file_list.addItem(path)
                event.accept()
                return True
        res = super().eventFilter(source, event)
        return bool(res)