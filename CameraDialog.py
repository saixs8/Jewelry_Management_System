import sys
import os
import cv2
from datetime import datetime
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QMessageBox, QComboBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage


class CameraDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("摄像头拍照 - 可选择摄像头")
        self.setMinimumSize(640, 560)  # 比画面稍高，留出控件空间
        self.setModal(True)

        self.cap = None
        self.timer = None
        self.current_camera_index = 0
        self.available_cameras = []

        self.init_ui()
        self.scan_available_cameras()
        if self.available_cameras:
            self.current_camera_index = self.available_cameras[0]
            self.init_camera()
        else:
            self.video_label.setText("未检测到任何摄像头")

    def init_ui(self):
        layout = QVBoxLayout()

        # 摄像头选择栏
        camera_layout = QHBoxLayout()
        camera_layout.addWidget(QLabel("选择摄像头:"))
        self.camera_combo = QComboBox()
        self.camera_combo.currentIndexChanged.connect(self.on_camera_changed)
        camera_layout.addWidget(self.camera_combo)
        camera_layout.addStretch()
        layout.addLayout(camera_layout)

        # 视频画面
        self.video_label = QLabel("等待摄像头启动...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setFixedSize(640, 480)
        self.video_label.setStyleSheet("background-color: black; border: 1px solid #ccc;")
        layout.addWidget(self.video_label)

        # 按钮栏
        btn_layout = QHBoxLayout()
        self.capture_btn = QPushButton("📸 拍照")
        self.capture_btn.clicked.connect(self.capture_image)
        self.refresh_btn = QPushButton("🔄 刷新摄像头")
        self.refresh_btn.clicked.connect(self.refresh_camera)
        self.close_btn = QPushButton("❌ 关闭")
        self.close_btn.clicked.connect(self.close_camera)
        btn_layout.addWidget(self.capture_btn)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def scan_available_cameras(self):
        """检测可用摄像头索引"""
        available = []
        for i in range(10):  # 最多检测10个
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    available.append(i)
                    cap.release()
            except:
                pass
        self.available_cameras = available
        self.camera_combo.clear()
        for idx in available:
            self.camera_combo.addItem(f"摄像头 {idx}", idx)
        if not available:
            self.camera_combo.addItem("无可用摄像头", -1)
            self.capture_btn.setEnabled(False)

    def refresh_camera(self):
        """刷新摄像头列表并重新打开当前选中的摄像头"""
        # 记住当前选中的索引
        old_index = self.current_camera_index
        self.scan_available_cameras()
        if self.available_cameras:
            # 如果之前的索引还存在，则保持；否则选择第一个
            if old_index in self.available_cameras:
                self.current_camera_index = old_index
            else:
                self.current_camera_index = self.available_cameras[0]
            # 在下拉框中选中对应的项
            index_in_combo = self.camera_combo.findData(self.current_camera_index)
            if index_in_combo >= 0:
                self.camera_combo.setCurrentIndex(index_in_combo)
            self.init_camera()
        else:
            self.cap = None
            self.video_label.setText("未检测到任何摄像头")
            self.capture_btn.setEnabled(False)

    def on_camera_changed(self, index):
        if index < 0:
            return
        idx = self.camera_combo.itemData(index)
        if idx >= 0 and idx != self.current_camera_index:
            self.current_camera_index = idx
            self.init_camera()

    def init_camera(self):
        if self.cap is not None:
            self.cap.release()
        if self.timer is not None:
            self.timer.stop()

        if self.current_camera_index < 0:
            self.video_label.setText("无可用摄像头")
            return

        self.cap = cv2.VideoCapture(self.current_camera_index)
        if not self.cap.isOpened():
            QMessageBox.warning(self, "警告", f"无法打开摄像头 {self.current_camera_index}")
            self.video_label.setText(f"摄像头 {self.current_camera_index} 不可用")
            self.capture_btn.setEnabled(False)
            return

        self.capture_btn.setEnabled(True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = frame
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.video_label.setPixmap(QPixmap.fromImage(q_img).scaled(640, 480, Qt.KeepAspectRatio))

    def capture_image(self):
        if not hasattr(self, 'current_frame') or self.current_frame is None:
            QMessageBox.warning(self, "提示", "没有画面，请检查摄像头")
            return

        # 生成临时文件名
        temp_filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        temp_path = os.path.join("product_images", temp_filename)
        os.makedirs("product_images", exist_ok=True)
        cv2.imwrite(temp_path, self.current_frame)

        # 调用父窗口的回调函数（AdminWindow 中的 set_image_from_camera）
        if self.parent():
            self.parent().set_image_from_camera(temp_path)
        self.close()

    def close_camera(self):
        if self.timer is not None:
            self.timer.stop()
        if self.cap is not None:
            self.cap.release()
        self.close()

    def closeEvent(self, event):
        self.close_camera()
        event.accept()