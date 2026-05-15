# ================= 自建库 =================
from LoginWindow import LoginWindow
from AdminWindow import AdminWindow

import sys

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QTableWidget, QTableWidgetItem, QMessageBox,
                             QFileDialog, QHeaderView, QDialog, QFormLayout,
                             QGroupBox, QStackedWidget, QComboBox, QDateEdit)


# ================= 程序入口 =================#
if __name__ == '__main__':
    app = QApplication(sys.argv)
    # 1. 显示登录窗口
    login = LoginWindow()
    if login.exec_() == QDialog.Accepted:
    # 2. 登录成功后显示主窗口
        window = AdminWindow()
        window.show()
        sys.exit(app.exec_())