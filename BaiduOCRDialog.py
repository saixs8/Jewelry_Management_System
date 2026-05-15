import os
import cv2
import re
import base64
import requests
import time
from difflib import SequenceMatcher
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QListWidget, QListWidgetItem, QMessageBox, QComboBox,
                             QLineEdit)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage
from ProductEditWindow import ProductEditWindow


class BaiduOCRDialog(QDialog):
    def __init__(self, db, parent=None, api_key="", secret_key=""):
        super().__init__(parent)
        self.db = db
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token = None
        self.token_expire_time = 0
        self.current_api_used = "未使用"
        self.setWindowTitle("手写编号识别（百度OCR）")
        self.setMinimumSize(800, 600)
        self.setModal(True)

        if not self.api_key or self.api_key == "你的真实API_Key":
            QMessageBox.critical(self, "配置错误",
                "请先在 AdminWindow.py 中设置正确的百度 API Key 和 Secret Key！\n"
                "获取方式：https://cloud.baidu.com/product/ocr/general")
            self.close()
            return

        self.cap = None
        self.camera_timer = None
        self.current_camera_index = 0
        self.current_frame = None

        self.init_ui()
        self.scan_available_cameras()
        if self.available_cameras:
            self.current_camera_index = self.available_cameras[0]
            self.init_camera()
        else:
            self.video_label.setText("未检测到任何摄像头")

        self.get_access_token()

    def get_access_token(self):
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }
        try:
            response = requests.post(url, params=params, timeout=10)
            data = response.json()
            if "access_token" in data:
                self.access_token = data["access_token"]
                self.token_expire_time = time.time() + data.get("expires_in", 2592000)
                print("百度OCR Token 获取成功")
                self.result_label.setText("识别就绪，点击「拍照识别」")
            else:
                error_msg = data.get("error_description", data.get("error", "未知错误"))
                print("获取Token失败:", data)
                QMessageBox.warning(self, "警告", f"百度OCR Token 获取失败：{error_msg}\n请检查 API Key 和 Secret Key 是否正确")
                self.result_label.setText("API Key 无效，请检查配置")
                self.manual_btn.setEnabled(False)
        except Exception as e:
            print("网络错误:", e)
            QMessageBox.warning(self, "警告", f"网络错误，无法获取Token：{e}")
            self.result_label.setText("网络异常，无法连接百度OCR")

    def init_ui(self):
        layout = QVBoxLayout()
        camera_layout = QHBoxLayout()
        camera_layout.addWidget(QLabel("选择摄像头:"))
        self.camera_combo = QComboBox()
        self.camera_combo.currentIndexChanged.connect(self.on_camera_changed)
        camera_layout.addWidget(self.camera_combo)
        camera_layout.addStretch()
        layout.addLayout(camera_layout)

        self.video_label = QLabel("等待摄像头启动...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setFixedSize(640, 480)
        self.video_label.setStyleSheet("background-color: black; border: 1px solid #ccc;")
        layout.addWidget(self.video_label)

        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 刷新摄像头")
        self.refresh_btn.clicked.connect(self.refresh_camera)
        btn_layout.addWidget(self.refresh_btn)

        self.manual_btn = QPushButton("📸 拍照识别")
        self.manual_btn.clicked.connect(self.manual_recognize)
        btn_layout.addWidget(self.manual_btn)

        layout.addLayout(btn_layout)

        manual_layout = QHBoxLayout()
        manual_layout.addWidget(QLabel("手动输入编号:"))
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("例如 202605043281")
        manual_layout.addWidget(self.manual_input)
        self.manual_search_btn = QPushButton("搜索并编辑")
        self.manual_search_btn.clicked.connect(self.search_by_manual_input)
        manual_layout.addWidget(self.manual_search_btn)
        layout.addLayout(manual_layout)

        self.result_label = QLabel("点击拍照识别手写数字，或直接输入编号")
        layout.addWidget(self.result_label)

        self.result_list = QListWidget()
        self.result_list.setSelectionMode(QListWidget.SingleSelection)
        self.result_list.itemDoubleClicked.connect(self.open_selected_product)
        layout.addWidget(self.result_list)

        self.setLayout(layout)

    def search_by_manual_input(self):
        number = self.manual_input.text().strip()
        if not number:
            QMessageBox.warning(self, "提示", "请输入编号")
            return
        product = self.db.get_product(number)
        if product:
            self.close()
            self.edit_window = ProductEditWindow(product, self.db, None)
            self.edit_window.show()
        else:
            QMessageBox.warning(self, "提示", f"未找到编号为 {number} 的商品")

    def scan_available_cameras(self):
        available = []
        for i in range(10):
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

    def refresh_camera(self):
        self.scan_available_cameras()
        if self.available_cameras:
            self.current_camera_index = self.available_cameras[0]
            self.camera_combo.setCurrentIndex(0)
            self.init_camera()
        else:
            self.cap = None
            self.video_label.setText("未检测到任何摄像头")

    def on_camera_changed(self, index):
        if index < 0:
            return
        self.current_camera_index = self.camera_combo.itemData(index)
        if self.current_camera_index >= 0:
            self.init_camera()

    def init_camera(self):
        if self.cap is not None:
            self.cap.release()
        if self.camera_timer is not None:
            self.camera_timer.stop()

        if self.current_camera_index < 0:
            self.video_label.setText("无可用摄像头")
            return

        try:
            self.cap = cv2.VideoCapture(self.current_camera_index)
            if not self.cap.isOpened():
                QMessageBox.warning(self, "警告", f"无法打开摄像头 {self.current_camera_index}")
                self.video_label.setText(f"摄像头 {self.current_camera_index} 不可用")
                return
            self.camera_timer = QTimer(self)
            self.camera_timer.timeout.connect(self.update_frame)
            self.camera_timer.start(30)
        except Exception as e:
            print("摄像头初始化错误:", e)
            QMessageBox.warning(self, "错误", f"摄像头初始化失败：{e}")

    def update_frame(self):
        if self.cap is None:
            return
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = frame
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.video_label.setPixmap(QPixmap.fromImage(q_img).scaled(640, 480, Qt.KeepAspectRatio))

    def baidu_ocr(self, image, api_type='handwriting'):
        if self.access_token is None:
            self.result_label.setText("百度OCR未就绪，请检查API配置")
            return []
        _, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 70])
        base64_img = base64.b64encode(encoded).decode('utf-8')

        endpoints = {
            'handwriting': 'https://aip.baidubce.com/rest/2.0/ocr/v1/handwriting',
            'accurate': 'https://aip.baidubce.com/rest/2.0/ocr/v1/accurate',
            'general_basic': 'https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic'
        }

        priority = ['handwriting', 'accurate', 'general_basic']
        start_index = priority.index(api_type) if api_type in priority else 0

        for api in priority[start_index:]:
            url = f"{endpoints[api]}?access_token={self.access_token}"
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            data = {'image': base64_img}
            try:
                resp = requests.post(url, headers=headers, data=data, timeout=10)
                result = resp.json()
                if 'words_result' in result:
                    all_text = ' '.join([w['words'] for w in result['words_result']])
                    numbers = re.findall(r'\d+', all_text)
                    print(f"[OCR] 使用 {api} 接口，识别结果: {numbers}")
                    self.current_api_used = api
                    return numbers
                else:
                    error_code = result.get('error_code')
                    error_msg = result.get('error_msg', '')
                    print(f"[OCR] {api} 接口失败: error_code={error_code}, msg={error_msg}")
                    if error_code in [17, 18, 19, 216100]:
                        continue
                    else:
                        return []
            except Exception as e:
                print(f"[OCR] {api} 请求异常: {e}")
                continue
        return []

    def manual_recognize(self):
        if self.current_frame is None:
            QMessageBox.warning(self, "提示", "没有画面，请检查摄像头")
            return
        if self.access_token is None:
            QMessageBox.warning(self, "提示", "百度OCR未准备就绪，请稍后重试")
            return
        numbers = self.baidu_ocr(self.current_frame, api_type='handwriting')
        if not numbers:
            QMessageBox.information(self, "提示", "未识别到数字，请调整角度或光线重试")
            self.result_label.setText("未识别到数字")
            return
        self.result_label.setText(f"识别到数字: {', '.join(numbers)} (接口: {self.current_api_used})")
        matches = self.match_with_database(numbers)
        if matches:
            self.show_match_dialog(matches)
        else:
            QMessageBox.information(self, "提示", f"未找到匹配的商品编号\n\n识别出的数字：{', '.join(numbers)}\n您可以在下方手动输入编号搜索。")
            if numbers:
                self.manual_input.setText(numbers[0])

    def match_with_database(self, numbers):
        """
        匹配数据库中的商品编号
        规则：
        1. 如果识别出的字符串长度 == 12 且全部为数字，则进行逐位精确匹配（相同位数比例）
        2. 否则使用子串包含、前缀匹配和序列相似度混合匹配（宽松）
        """
        all_ids = self.get_all_product_ids()
        suggestions = {}

        for num_str in numbers:
            # 检查是否为12位纯数字
            is_pure_digits = num_str.isdigit()
            if len(num_str) == 12 and is_pure_digits:
                # 逐位匹配
                for pid in all_ids:
                    # 确保 pid 也是数字（数据库中的编号是纯数字）
                    if not pid.isdigit():
                        continue
                    match_count = 0
                    for i in range(12):
                        if i < len(num_str) and i < len(pid) and num_str[i] == pid[i]:
                            match_count += 1
                    exact_ratio = match_count / 12.0
                    # 只要匹配率大于0（至少1位相同也考虑），但可设阈值为0.1
                    if exact_ratio > 0:
                        suggestions[pid] = max(suggestions.get(pid, 0), exact_ratio)
            else:
                # 模糊匹配（原逻辑）
                continue  # 稍后统一处理模糊匹配

        # 处理模糊匹配的识别结果（非12位或含非数字）
        for num_str in numbers:
            if len(num_str) == 12 and num_str.isdigit():
                # 已处理过，跳过
                continue
            if len(num_str) < 3:
                continue
            for pid in all_ids:
                # 1. 完全包含
                if num_str in pid:
                    len_ratio = len(num_str) / len(pid)
                    score = 0.95 + 0.05 * len_ratio
                    suggestions[pid] = max(suggestions.get(pid, 0), score)
                else:
                    # 2. 最长公共前缀
                    min_len = min(len(num_str), len(pid))
                    prefix_match = 0
                    for i in range(min_len):
                        if num_str[i] == pid[i]:
                            prefix_match += 1
                        else:
                            break
                    prefix_ratio = prefix_match / max(len(num_str), len(pid))
                    # 3. 整体相似度
                    ratio = SequenceMatcher(None, num_str, pid).ratio()
                    combined = 0.7 * prefix_ratio + 0.3 * ratio
                    if combined > 0.55:
                        suggestions[pid] = max(suggestions.get(pid, 0), combined)

        # 保底：如果没有任何匹配且 numbers 非空，显示所有编号的粗略相似度
        if not suggestions and numbers:
            first_num = numbers[0]
            for pid in all_ids:
                ratio = SequenceMatcher(None, first_num, pid).ratio()
                suggestions[pid] = ratio

        # 排序并展示前15个
        sorted_items = sorted(suggestions.items(), key=lambda x: x[1], reverse=True)[:15]
        result = []
        for pid, score in sorted_items:
            prod = self.db.get_product(pid)
            name = prod[1] if prod else "未知"
            result.append((pid, score, name))
        return result

    def show_match_dialog(self, matches):
        if not matches:
            return
        from PyQt5.QtWidgets import QDialog, QHBoxLayout, QListWidget, QPushButton
        dlg = QDialog(self)
        dlg.setWindowTitle("识别到商品编号，请选择")
        dlg.resize(450, 300)
        layout = QVBoxLayout()
        list_widget = QListWidget()
        for pid, score, name in matches:
            item = QListWidgetItem(f"{pid} (相似度: {score:.0%}) - {name}")
            item.setData(Qt.UserRole, pid)
            list_widget.addItem(item)
        layout.addWidget(list_widget)
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("打开编辑")
        cancel_btn = QPushButton("取消")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        dlg.setLayout(layout)

        def on_ok():
            cur = list_widget.currentItem()
            if cur:
                pid = cur.data(Qt.UserRole)
                dlg.accept()
                product = self.db.get_product(pid)
                if product:
                    self.close()
                    self.edit_window = ProductEditWindow(product, self.db, None)
                    self.edit_window.show()
            else:
                QMessageBox.warning(dlg, "提示", "请选择一个商品")
        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(dlg.reject)
        dlg.exec_()

    def get_all_product_ids(self):
        try:
            conn = self.db.conn if hasattr(self.db, 'conn') else self.db
            cur = conn.cursor()
            cur.execute("SELECT id FROM products")
            rows = cur.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            print("查询ID失败:", e)
            return []

    def open_selected_product(self, item):
        pid = item.data(Qt.UserRole)
        if pid:
            product = self.db.get_product(pid)
            if product:
                self.close()
                self.edit_window = ProductEditWindow(product, self.db, None)
                self.edit_window.show()

    def closeEvent(self, event):
        if self.cap:
            self.cap.release()
        if self.camera_timer:
            self.camera_timer.stop()
        event.accept()