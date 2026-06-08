import os
from PyQt6.QtCore import QThread, pyqtSignal
from PIL import Image

class ImageWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, image_paths, output_dir):
        super().__init__()
        self.image_paths = image_paths
        self.output_dir = output_dir
        self.is_stopped = False

    def run(self):
        total = len(self.image_paths)
        if total == 0:
            self.finished.emit(False, "没有需要处理的图片。")
            return

        success_count = 0
        for i, img_path in enumerate(self.image_paths):
            if self.is_stopped:
                self.finished.emit(False, "用户手动停止了任务。")
                return

            try:
                self.progress.emit(int((i / total) * 100), f"正在处理 ({i+1}/{total}): {os.path.basename(img_path)}")
                
                # 打开图片
                with Image.open(img_path) as img:
                    # 转换为 RGB 模式（防止 RGBA/P 模式保存为 JPG 时报错）
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                        
                    w, h = img.size
                    # 计算 9:16 的目标宽度 (基于高度)
                    target_w = int(h * 9 / 16)
                    
                    if w > target_w:
                        # 如果原图较宽，居中裁剪宽度
                        left = (w - target_w) / 2
                        right = (w + target_w) / 2
                        img_cropped = img.crop((left, 0, right, h))
                    else:
                        # 如果原图已经是 9:16 或者更窄，保持原样（或根据你需要补黑边，这里选择保持）
                        img_cropped = img

                    # 保存结果
                    filename = os.path.basename(img_path)
                    out_path = os.path.join(self.output_dir, filename)
                    img_cropped.save(out_path, quality=95)
                    success_count += 1
                    
            except Exception as e:
                print(f"处理 {img_path} 时出错: {e}")
                continue

        self.progress.emit(100, f"处理完成！成功裁剪 {success_count} 张图片。")
        self.finished.emit(True, f"共成功处理了 {success_count} 张图片。")

    def stop(self):
        self.is_stopped = True