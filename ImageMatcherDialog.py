import os
import cv2
import numpy as np
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QListWidget, QListWidgetItem, QMessageBox, QComboBox,
                             QProgressDialog, QFileDialog, QFrame)
from PyQt5.QtCore import Qt, QTimer, QRect, QPoint, QSize
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QIcon

from Database import IMAGE_FOLDER
from ProductEditWindow import ProductEditWindow

# ---------- ORB ----------
_orb = None
def _get_orb():
    global _orb
    if _orb is None:
        try:
            _orb = cv2.ORB_create(nfeatures=2000)
        except:
            _orb = False
    return _orb if _orb is not False else None

def preprocess(img, max_dim=800):
    if img is None:
        return None
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    h, w = gray.shape
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)))
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    return gray

def get_features(gray_img):
    if gray_img is None:
        return None, None
    orb = _get_orb()
    if orb is None:
        return None, None
    kp, des = orb.detectAndCompute(gray_img, None)
    return kp, des

def color_hist_similarity(color1, color2):
    try:
        hsv1 = cv2.cvtColor(color1, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(color2, cv2.COLOR_BGR2HSV)
        hist1 = cv2.calcHist([hsv1], [0,1,2], None, [8,8,8], [0,180,0,256,0,256])
        hist2 = cv2.calcHist([hsv2], [0,1,2], None, [8,8,8], [0,180,0,256,0,256])
        cv2.normalize(hist1, hist1)
        cv2.normalize(hist2, hist2)
        return cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
    except:
        return 0

def single_match(query_gray, db_gray, ratio=0.8, ransac_thresh=10.0):
    kp_db, des_db = get_features(db_gray)
    if des_db is None or len(des_db) < 4:
        return 0
    best_inliers = 0
    h, w = query_gray.shape[:2]
    for ang in [0, 90, 180, 270]:
        if ang == 0:
            rot = query_gray
        else:
            M = cv2.getRotationMatrix2D((w//2, h//2), ang, 1.0)
            rot = cv2.warpAffine(query_gray, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        kp_q, des_q = get_features(rot)
        if des_q is None or len(des_q) < 4:
            continue
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        try:
            matches = bf.knnMatch(des_q, des_db, k=2)
        except:
            continue
        good = [m for m, n in matches if m.distance < ratio * n.distance]
        if len(good) >= 4:
            src_pts = np.float32([kp_q[m.queryIdx].pt for m in good]).reshape(-1,2)
            dst_pts = np.float32([kp_db[m.trainIdx].pt for m in good]).reshape(-1,2)
            H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, ransac_thresh)
            if H is not None:
                inliers = int(mask.ravel().sum())
                if inliers > best_inliers:
                    best_inliers = inliers
    return best_inliers

def multi_scale_match(query_img_color, db_img_color):
    if query_img_color is None or db_img_color is None:
        return 0, 0
    query_gray = preprocess(query_img_color)
    db_gray = preprocess(db_img_color)
    if query_gray is None or db_gray is None:
        return 0, 0
    hsim = color_hist_similarity(query_img_color, db_img_color)
    best_inliers = 0
    for scale in [0.6, 0.8, 1.0, 1.2, 1.4]:
        if scale == 1.0:
            scaled_gray = query_gray
        else:
            new_w = max(8, int(query_gray.shape[1] * scale))
            new_h = max(8, int(query_gray.shape[0] * scale))
            scaled_gray = cv2.resize(query_gray, (new_w, new_h))
        inliers = single_match(scaled_gray, db_gray)
        if inliers > best_inliers:
            best_inliers = inliers
    return best_inliers, hsim

# ---------- 可框选标签 ----------
class CropLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.crop_rect = QRect()
        self.is_drawing = False
        self.setStyleSheet("background-color: #222; border: 2px solid #555; border-radius: 8px;")
    def mousePressEvent(self, event):
        self.is_drawing = True
        self.crop_rect.setTopLeft(event.pos())
        self.crop_rect.setBottomRight(event.pos())
        self.update()
    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.crop_rect.setBottomRight(event.pos())
            self.update()
    def mouseReleaseEvent(self, event):
        self.is_drawing = False
        self.crop_rect.setBottomRight(event.pos())
        self.update()
    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.crop_rect.isEmpty():
            painter = QPainter(self)
            pen = QPen(QColor(100, 200, 255), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(QColor(100, 200, 255, 30))
            painter.drawRect(self.crop_rect)
            painter.end()
    def clear_rect(self):
        self.crop_rect = QRect()
        self.update()

# ---------- 主对话框 ----------
class ImageMatcherDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("✨ 首饰图像匹配")
        self.setMinimumSize(950, 750)
        self.setModal(True)
        self.setStyleSheet(self._global_style())

        self.cap = None
        self.timer = None
        self.current_camera_index = 0
        self.current_frame = None
        self.available = []
        self.source_image = None
        self.cropped_image = None
        self.has_cropped = False
        self.mode = "camera"
        self.file_path = None
        self.photo_taken = False
        self.match_in_progress = False
        self.camera_initialized = False

        self.init_ui()
        self.scan_cameras()

    def _global_style(self):
        return """
            QDialog { background-color: #f0f2f5; }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
                color: #333333;
            }
            QPushButton:hover {
                background-color: #e8f0fe;
                border-color: #90c0ff;
            }
            QPushButton:pressed {
                background-color: #d0e0ff;
            }
            QPushButton#primaryBtn {
                background-color: #1890ff;
                color: white;
                border: none;
                font-weight: bold;
            }
            QPushButton#primaryBtn:hover { background-color: #40a9ff; }
            QPushButton#dangerBtn {
                background-color: #ff4d4f;
                color: white;
                border: none;
            }
            QPushButton#dangerBtn:hover { background-color: #ff7875; }
            QLabel#title {
                font-size: 18px;
                font-weight: bold;
                color: #1a1a2e;
                margin: 5px;
            }
            QComboBox {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 6px;
                min-width: 100px;
                background: white;
            }
            QComboBox:hover { border-color: #90c0ff; }
            QListWidget {
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                padding: 4px;
                background: white;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 6px;
                margin: 2px 0px;
                border-radius: 4px;
            }
            QListWidget::item:hover { background-color: #e6f7ff; }
            QListWidget::item:selected {
                background-color: #1890ff;
                color: white;
            }
            QFrame#card {
                background: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("🔍 首饰图像匹配")
        title.setObjectName("title")
        main_layout.addWidget(title)

        mode_card = QFrame()
        mode_card.setObjectName("card")
        mode_card.setFixedHeight(70)
        mode_layout = QHBoxLayout(mode_card)
        mode_layout.setContentsMargins(16, 8, 16, 8)

        self.btn_camera_mode = QPushButton("📷 摄像头")
        self.btn_camera_mode.setCheckable(True)
        self.btn_camera_mode.setChecked(True)
        self.btn_file_mode = QPushButton("📁 本地图片")
        self.btn_file_mode.setCheckable(True)

        self.btn_camera_mode.clicked.connect(lambda: self.switch_mode("camera"))
        self.btn_file_mode.clicked.connect(lambda: self.switch_mode("file"))

        mode_layout.addWidget(QLabel("输入方式:"))
        mode_layout.addWidget(self.btn_camera_mode)
        mode_layout.addWidget(self.btn_file_mode)
        mode_layout.addStretch()
        main_layout.addWidget(mode_card)

        control_card = QFrame()
        control_card.setObjectName("card")
        control_card.setFixedHeight(70)
        ctrl_layout = QHBoxLayout(control_card)
        ctrl_layout.setContentsMargins(16, 8, 16, 8)

        self.camera_combo = QComboBox()
        self.camera_combo.currentIndexChanged.connect(self.on_camera_changed)
        self.btn_refresh = QPushButton("🔄 扫描摄像头")
        self.btn_refresh.clicked.connect(self.scan_cameras)
        self.btn_capture = QPushButton("📸 拍照")
        self.btn_capture.clicked.connect(self.capture_photo)

        self.btn_file_select = QPushButton("📂 选择图片")
        self.btn_file_select.clicked.connect(self.select_file)
        self.file_label = QLabel("未选择文件")
        self.file_label.setStyleSheet("color: #888; margin-left: 8px;")

        ctrl_layout.addWidget(QLabel("摄像头:"))
        ctrl_layout.addWidget(self.camera_combo)
        ctrl_layout.addWidget(self.btn_refresh)
        ctrl_layout.addWidget(self.btn_capture)
        ctrl_layout.addWidget(self.btn_file_select)
        ctrl_layout.addWidget(self.file_label)
        ctrl_layout.addStretch()
        main_layout.addWidget(control_card)

        preview_card = QFrame()
        preview_card.setObjectName("card")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 12, 12, 12)

        self.video_label = CropLabel()
        self.video_label.setFixedSize(640, 480)
        self.video_label.setText("等待摄像头启动...")
        self.video_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.video_label, 0, Qt.AlignCenter)

        sel_layout = QHBoxLayout()
        self.btn_clear_crop = QPushButton("🗑️ 清除选区")
        self.btn_clear_crop.clicked.connect(self.clear_crop)
        self.btn_apply_crop = QPushButton("✅ 使用选区")
        self.btn_apply_crop.clicked.connect(self.apply_crop)
        sel_layout.addStretch()
        sel_layout.addWidget(self.btn_clear_crop)
        sel_layout.addWidget(self.btn_apply_crop)
        preview_layout.addLayout(sel_layout)

        main_layout.addWidget(preview_card)

        self.btn_match = QPushButton("🚀 开始匹配")
        self.btn_match.setObjectName("primaryBtn")
        self.btn_match.setFixedHeight(40)
        self.btn_match.clicked.connect(self.start_match)
        main_layout.addWidget(self.btn_match)

        result_label = QLabel("匹配结果 (双击编辑商品)")
        result_label.setStyleSheet("font-weight: bold; color: #333; margin-top: 4px;")
        main_layout.addWidget(result_label)

        self.result_list = QListWidget()
        self.result_list.setIconSize(QSize(60, 60))
        self.result_list.itemDoubleClicked.connect(self.open_edit)
        main_layout.addWidget(self.result_list, 1)

        self.setLayout(main_layout)
        self.switch_mode("camera")

    # ---------- 获取商品主图（用于显示） ----------
    def _get_main_image_for_product(self, prod):
        """返回商品主图的绝对路径，优先使用image_path字段，否则取文件夹第一张"""
        product_id = prod[0]
        image_field = prod[2] if len(prod) > 2 else ""
        if image_field:
            direct_path = os.path.normpath(os.path.join(IMAGE_FOLDER, image_field))
            if os.path.isfile(direct_path):
                return direct_path
        product_dir = os.path.join(IMAGE_FOLDER, product_id)
        if os.path.isdir(product_dir):
            for f in sorted(os.listdir(product_dir)):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    return os.path.join(product_dir, f)
        return ""

    # ---------- 获取商品所有图片（用于匹配） ----------
    def _find_all_images_for_product(self, prod):
        """返回该商品所有图片的绝对路径列表（去重）"""
        product_id = prod[0]
        image_field = prod[2] if len(prod) > 2 else ""
        paths = set()
        # 主图字段
        if image_field:
            direct = os.path.normpath(os.path.join(IMAGE_FOLDER, image_field))
            if os.path.isfile(direct):
                paths.add(direct)
        # 商品编号文件夹
        product_dir = os.path.join(IMAGE_FOLDER, product_id)
        if os.path.isdir(product_dir):
            for f in os.listdir(product_dir):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    paths.add(os.path.join(product_dir, f))
        return list(paths)

    def switch_mode(self, mode):
        self.mode = mode
        self.btn_camera_mode.setChecked(mode == "camera")
        self.btn_file_mode.setChecked(mode == "file")
        self.camera_combo.setVisible(mode == "camera")
        self.btn_refresh.setVisible(mode == "camera")
        self.btn_capture.setVisible(mode == "camera")
        self.btn_file_select.setVisible(mode == "file")
        self.file_label.setVisible(mode == "file")
        if mode == "camera":
            if self.available and not self.camera_initialized:
                self.current_camera_index = self.available[0]
                self.init_camera()
        else:
            self.stop_camera()
            self.video_label.setText("请选择本地图片")

    def scan_cameras(self):
        self.available = []
        self.camera_combo.blockSignals(True)
        for i in range(2):
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    self.available.append(i)
                cap.release()
            except:
                pass
        self.camera_combo.clear()
        if self.available:
            for idx in self.available:
                self.camera_combo.addItem(f"摄像头 {idx}", idx)
            self.camera_combo.setEnabled(True)
        else:
            self.camera_combo.addItem("无可用", -1)
            self.camera_combo.setEnabled(False)
        self.camera_combo.blockSignals(False)

        if self.mode == "camera" and self.available and not self.camera_initialized:
            self.current_camera_index = self.available[0]
            self.init_camera()

    def on_camera_changed(self, index):
        if not self.isVisible() or self.mode != "camera":
            return
        idx = self.camera_combo.itemData(index)
        if idx is None or idx < 0:
            return
        if idx != self.current_camera_index:
            self.current_camera_index = idx
            self.init_camera()

    def init_camera(self):
        self.stop_camera()
        if self.mode != "camera" or self.current_camera_index < 0:
            return
        try:
            self.cap = cv2.VideoCapture(self.current_camera_index)
            if not self.cap.isOpened():
                self.video_label.setText("无法打开摄像头")
                self.cap = None
                self.camera_initialized = False
                return
            self.photo_taken = False
            self.start_preview()
            self.camera_initialized = True
        except:
            self.video_label.setText("摄像头初始化失败")
            self.cap = None
            self.camera_initialized = False

    def start_preview(self):
        if self.timer is None:
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def stop_preview(self):
        if self.timer:
            self.timer.stop()

    def stop_camera(self):
        self.stop_preview()
        if self.timer:
            self.timer = None
        if self.cap:
            self.cap.release()
            self.cap = None
        self.camera_initialized = False

    def update_frame(self):
        if self.photo_taken or self.match_in_progress:
            return
        if self.cap is None or not self.cap.isOpened():
            return
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = frame
            self.show_frame(frame)

    def show_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(640, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.video_label.setPixmap(pix)

    def capture_photo(self):
        if self.mode != "camera":
            return
        if self.photo_taken:
            self.photo_taken = False
            self.btn_capture.setText("📸 拍照")
            self.clear_crop()
            self.start_preview()
            return
        if self.current_frame is None:
            QMessageBox.warning(self, "提示", "暂无画面")
            return
        self.source_image = self.current_frame.copy()
        self.photo_taken = True
        self.btn_capture.setText("📸 重新拍照")
        self.stop_preview()
        self.clear_crop()
        self.show_frame(self.source_image)

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择首饰图片", "", "图像 (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.file_label.setText(os.path.basename(path))
            img = cv2.imread(path)
            if img is None:
                QMessageBox.warning(self, "错误", "无法读取图片")
                return
            self.source_image = img
            self.clear_crop()
            self.show_frame(img)

    def clear_crop(self):
        self.video_label.clear_rect()
        self.has_cropped = False
        self.cropped_image = None
        if self.source_image is not None:
            self.show_frame(self.source_image)

    def apply_crop(self):
        rect = self.video_label.crop_rect
        if self.source_image is None or rect.isEmpty():
            QMessageBox.warning(self, "提示", "请先在图像上拖拽框选首饰区域")
            return
        lbl_w = self.video_label.width()
        lbl_h = self.video_label.height()
        img_h, img_w = self.source_image.shape[:2]
        scale_x = img_w / lbl_w
        scale_y = img_h / lbl_h
        x1 = max(0, int(rect.left() * scale_x))
        y1 = max(0, int(rect.top() * scale_y))
        x2 = min(img_w, int(rect.right() * scale_x))
        y2 = min(img_h, int(rect.bottom() * scale_y))
        if x2 - x1 < 10 or y2 - y1 < 10:
            QMessageBox.warning(self, "选区太小")
            return
        self.cropped_image = self.source_image[y1:y2, x1:x2].copy()
        self.has_cropped = True
        self.show_frame(self.cropped_image)
        self.video_label.clear_rect()

    # ---------- 匹配（核心修改） ----------
    def start_match(self):
        if self.match_in_progress:
            return
        self.match_in_progress = True
        self.btn_match.setEnabled(False)

        if self.has_cropped and self.cropped_image is not None:
            target_color = self.cropped_image
        elif self.source_image is not None:
            reply = QMessageBox.question(self, "建议框选主体",
                                        "您没有框选首饰主体，直接使用整张图片可能影响准确度。\n是否继续？",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                self.match_in_progress = False
                self.btn_match.setEnabled(True)
                return
            target_color = self.source_image
        else:
            QMessageBox.warning(self, "提示", "请先拍照或选择图片")
            self.match_in_progress = False
            self.btn_match.setEnabled(True)
            return

        self.stop_camera()

        try:
            query_gray = preprocess(target_color)
            if query_gray is None:
                QMessageBox.warning(self, "错误", "图像预处理失败")
                self.match_in_progress = False
                self.btn_match.setEnabled(True)
                return

            products = self.db.get_all_products()
            if not products:
                QMessageBox.information(self, "提示", "数据库无商品")
                self.match_in_progress = False
                self.btn_match.setEnabled(True)
                return

            progress = QProgressDialog("匹配中...", "取消", 0, len(products), self)
            progress.setWindowModality(Qt.WindowModal)
            normal_results = []
            missing_results = []

            for i, prod in enumerate(products):
                if progress.wasCanceled():
                    break
                progress.setValue(i)
                try:
                    all_images = self._find_all_images_for_product(prod)
                    if not all_images:
                        missing_results.append((prod[0], prod[1]))
                        continue

                    best_score = -1
                    best_inliers = 0
                    best_hsim = 0
                    for img_path in all_images:
                        db_img_color = cv2.imread(img_path)
                        if db_img_color is None:
                            continue
                        inliers, hsim = multi_scale_match(target_color, db_img_color)
                        score = inliers * 2.0 + max(0, hsim + 0.5) * 20
                        if score > best_score:
                            best_score = score
                            best_inliers = inliers
                            best_hsim = hsim
                    if best_score >= 0:
                        main_img = self._get_main_image_for_product(prod)
                        normal_results.append((prod[0], best_score, best_inliers, best_hsim, prod[1], main_img))
                    else:
                        missing_results.append((prod[0], prod[1]))
                except Exception as ex:
                    print(f"处理商品 {prod[0]} 失败: {ex}")
                    missing_results.append((prod[0], prod[1]))

            progress.setValue(len(products))
            normal_results.sort(key=lambda x: x[1], reverse=True)
            self.result_list.clear()

            for pid, score, inliers, hsim, name, img_path in normal_results:
                text = f"{pid} - {name}  [内点:{inliers} 色似:{hsim:.2f} 得分:{score:.1f}]"
                item = QListWidgetItem(text)
                item.setData(Qt.UserRole, pid)
                pix = QPixmap(img_path) if img_path else QPixmap()
                if not pix.isNull():
                    icon = QIcon(pix.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    item.setIcon(icon)
                self.result_list.addItem(item)

            if missing_results:
                self.result_list.addItem(QListWidgetItem("── 以下商品图片缺失，请重新上传 ──"))
                for pid, name in missing_results:
                    text = f"{pid} - {name}  [图片缺失]"
                    item = QListWidgetItem(text)
                    item.setData(Qt.UserRole, pid)
                    item.setForeground(QColor("red"))
                    self.result_list.addItem(item)

                missing_ids = [r[0] for r in missing_results]
                QMessageBox.information(self, "提示",
                    f"以下 {len(missing_ids)} 个商品缺少有效图片，已用红色标注：\n{', '.join(missing_ids)}\n\n双击这些商品可打开编辑窗口重新上传图片。")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"匹配过程异常: {str(e)}")
        finally:
            self.match_in_progress = False
            self.btn_match.setEnabled(True)
            if self.mode == "camera" and self.available:
                self.init_camera()
            else:
                self.video_label.setText("匹配完成")

    def open_edit(self, item):
        pid = item.data(Qt.UserRole)
        if pid:
            product = self.db.get_product(pid)
            if product:
                self.close()
                self.edit_win = ProductEditWindow(product, self.db, None)
                self.edit_win.show()

    def closeEvent(self, event):
        self.stop_camera()
        event.accept()