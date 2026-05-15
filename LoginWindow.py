import sys
import os
from PyQt5.QtWidgets import (QDialog, QLabel, QLineEdit, QPushButton,
                             QVBoxLayout, QFormLayout, QMessageBox, QWidget, QFrame)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import (QPixmap, QPainter, QPen, QBrush,
                         QColor, QLinearGradient, QFont)


class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("首饰管理系统 - 登录")
        self.setWindowFlags(Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)

        # 16:9 窗口尺寸
        self.base_width = 960
        self.base_height = 540
        self.setFixedSize(self.base_width, self.base_height)

        # 加载背景（优先图片，其次自绘）
        self.background = self._load_background()
        self.bg_label = QLabel(self)
        self.bg_label.setPixmap(self.background)
        self.bg_label.setGeometry(0, 0, self.base_width, self.base_height)

        # 构建前景登录控件
        self._setup_ui()

    def _load_background(self) -> QPixmap:
        """优先使用 resources/login_bg_1.png，否则绘制高级浅色背景"""
        base_path = os.path.join(os.path.dirname(__file__), "resources", "login_bg_2.png")
        if os.path.isfile(base_path):
            pix = QPixmap(base_path)
            if not pix.isNull():
                return pix.scaled(self.base_width, self.base_height,
                                  Qt.KeepAspectRatioByExpanding,
                                  Qt.SmoothTransformation)
        # 自绘背景（备用）
        return self._draw_advanced_background()

    def _draw_advanced_background(self) -> QPixmap:
        pix = QPixmap(self.base_width, self.base_height)
        pix.fill(QColor(248, 248, 248))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)

        # 顶部金色装饰线
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(212, 175, 55))
        painter.drawRect(0, 0, self.base_width, 4)

        # 左侧淡金渐变
        left_grad = QLinearGradient(0, 0, 200, 0)
        left_grad.setColorAt(0.0, QColor(240, 230, 200, 80))
        left_grad.setColorAt(1.0, QColor(240, 230, 200, 0))
        painter.setBrush(left_grad)
        painter.drawRect(0, 0, 300, self.base_height)

        # 几何斜线
        painter.setPen(QPen(QColor(212, 175, 55, 140), 1))
        for i in range(1, 6):
            x = self.base_width - 100 - i * 20
            painter.drawLine(x, self.base_height, x + 180, 0)

        # 右下角光晕
        painter.setBrush(QColor(212, 175, 55, 20))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(self.base_width - 200, self.base_height - 200, 400, 400)

        painter.end()
        return pix

    def _setup_ui(self):
        """半透明卡片居中，包含标题、输入框和按钮"""
        # 半透明卡片容器
        card = QFrame(self)
        card_width = 360
        card_height = 280
        card_x = (self.width() - card_width) // 2
        card_y = (self.height() - card_height) // 2
        card.setGeometry(card_x, card_y, card_width, card_height)
        card.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.7);
                border-radius: 16px;
            }
        """)

        # 卡片内布局
        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(18)

        # 标题
        title = QLabel("管理员登录")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            color: #333333;
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 10px;
        """)
        layout.addWidget(title)

        # 用户名输入框
        self.user_input = QLineEdit()
        self.user_input.setText("admin")
        self.user_input.setPlaceholderText("用户名")
        self.user_input.setStyleSheet(self._input_style())
        layout.addWidget(self.user_input)

        # 密码输入框
        self.pass_input = QLineEdit()
        self.pass_input.setText("admin")
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setPlaceholderText("密码")
        self.pass_input.setStyleSheet(self._input_style())
        layout.addWidget(self.pass_input)

        # 登录按钮
        self.login_btn = QPushButton("登 录")
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #D4AF37;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 14px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #E5C158; }
            QPushButton:pressed { background-color: #B8942E; }
        """)
        self.login_btn.clicked.connect(self.check_login)
        layout.addWidget(self.login_btn)

    def _input_style(self) -> str:
        return """
            QLineEdit {
                border: 1px solid #D4AF37;
                border-radius: 8px;
                padding: 12px 16px;
                background-color: rgba(255, 255, 255, 0.5);
                color: #333333;
                font-size: 16px;
                font-weight: 500;
            }
            QLineEdit:focus {
                border-color: #B8942E;
                background-color: rgba(255, 255, 255, 0.8);
            }
            QLineEdit::placeholder {
                color: #999999;
            }
        """

    def check_login(self):
        if self.user_input.text() == "admin" and self.pass_input.text() == "admin":
            self.accept()
        else:
            QMessageBox.warning(self, "错误", "用户名或密码错误！(默认: admin/admin)")