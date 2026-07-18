import os, sys

root = os.path.dirname(os.path.abspath(__file__))
os.chdir(root)
sys.path.insert(0, root)

marker = os.path.join(root, "python_alive.txt")

def log(msg):
    with open(marker, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

with open(marker, "w", encoding="utf-8") as f:
    f.write("")  # reset

log("Python running OK")

try:
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    log("QApplication OK")

    log("Testing VideoMergerUI...")
    from UI.ui import VideoMergerUI
    VideoMergerUI()
    log("VideoMergerUI OK")

    log("Testing ImageMergerUI...")
    from UI.ui_image_merger import ImageMergerUI
    ImageMergerUI()
    log("ImageMergerUI OK")

    log("Testing ImageCropperUI...")
    from UI.ui_image_cropper import ImageCropperUI
    ImageCropperUI()
    log("ImageCropperUI OK")

    log("Testing MultiSegmentUI...")
    from UI.ui_multi_segment import MultiSegmentUI
    MultiSegmentUI()
    log("MultiSegmentUI OK")

    log("Testing YouTubeDownloaderUI...")
    from UI.ui_youtube_downloader import YouTubeDownloaderUI
    YouTubeDownloaderUI()
    log("YouTubeDownloaderUI OK")

    log("Testing AutoScreenshotUI...")
    from UI.ui_auto_screenshot import AutoScreenshotUI
    AutoScreenshotUI()
    log("AutoScreenshotUI OK")

    log("ALL WIDGETS OK - launching main app...")
    from main.main import ToolboxApp
    window = ToolboxApp()
    screen = app.primaryScreen().availableGeometry()
    w, h = 1200, 800
    x = screen.x() + (screen.width() - w) // 2
    y = screen.y() + (screen.height() - h) // 2
    window.setGeometry(x, y, w, h)
    window.show()
    window.raise_()
    window.activateWindow()
    log("window.show() OK")
    sys.exit(app.exec())

except Exception as e:
    import traceback
    err = traceback.format_exc()
    log(f"CRASH:\n{err}")
    input("Press Enter to exit...")
