# ImageViewerDialog.py
import os
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap


class ImageViewerDialog(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("商品图片预览")
        self.setMinimumSize(400, 300)
        # 模态或非模态都可，根据原调用习惯（一般是 exec_() 模态）
        self.setModal(True)

        layout = QVBoxLayout()
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)

        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # 缩放以适应窗口，保持比例
                scaled = pixmap.scaled(800, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_label.setPixmap(scaled)
            else:
                self.image_label.setText("图片无法加载")
        else:
            self.image_label.setText("暂无图片")

        layout.addWidget(self.image_label)
        self.setLayout(layout)