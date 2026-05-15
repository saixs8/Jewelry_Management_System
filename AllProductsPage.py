# AllProductsPage.py
import os
import re
import shutil
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTableWidget,
                             QTableWidgetItem, QHeaderView, QHBoxLayout, QPushButton, QComboBox, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from Database import IMAGE_FOLDER
from ProductEditWindow import ProductEditWindow


class AllProductsPage(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_product_id = None
        self.all_products = []               # 缓存所有商品数据
        self.current_brand_filter = ""       # 当前筛选的品牌
        self.current_category_filter = ""    # 当前筛选的品类
        self.sort_col = None                 # 当前排序的列 (0:编号, 3:售价, 4:进价)
        self.sort_asc = True                 # 升序/降序
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout()

        title = QLabel("所有商品列表")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)

        # 筛选和排序栏
        filter_layout = QHBoxLayout()

        # 品类筛选 + 删除品类按钮
        filter_layout.addWidget(QLabel("品类:"))
        self.category_combo = QComboBox()
        self.category_combo.setEditable(False)
        self.category_combo.currentTextChanged.connect(self.on_category_filter_changed)
        filter_layout.addWidget(self.category_combo)

        self.del_category_btn = QPushButton("🗑️ 删除品类(所有商品)")
        self.del_category_btn.clicked.connect(self.delete_category)
        filter_layout.addWidget(self.del_category_btn)

        # 品牌筛选 + 删除品牌按钮
        filter_layout.addWidget(QLabel("品牌:"))
        self.brand_combo = QComboBox()
        self.brand_combo.setEditable(False)
        self.brand_combo.currentTextChanged.connect(self.on_brand_filter_changed)
        filter_layout.addWidget(self.brand_combo)

        self.del_brand_btn = QPushButton("🗑️ 删除品牌(所有商品)")
        self.del_brand_btn.clicked.connect(self.delete_brand)
        filter_layout.addWidget(self.del_brand_btn)

        # 删除选中商品按钮
        self.del_selected_btn = QPushButton("🗑️ 删除选中商品")
        self.del_selected_btn.clicked.connect(self.delete_selected_product)
        filter_layout.addWidget(self.del_selected_btn)

        # 排序按钮
        filter_layout.addWidget(QLabel("   编号排序:"))
        self.sort_id_asc_btn = QPushButton("升序")
        self.sort_id_asc_btn.clicked.connect(lambda: self.on_sort(0, True))
        filter_layout.addWidget(self.sort_id_asc_btn)
        self.sort_id_desc_btn = QPushButton("降序")
        self.sort_id_desc_btn.clicked.connect(lambda: self.on_sort(0, False))
        filter_layout.addWidget(self.sort_id_desc_btn)

        filter_layout.addWidget(QLabel("   售价排序:"))
        self.sort_sell_asc_btn = QPushButton("升序")
        self.sort_sell_asc_btn.clicked.connect(lambda: self.on_sort(3, True))
        filter_layout.addWidget(self.sort_sell_asc_btn)
        self.sort_sell_desc_btn = QPushButton("降序")
        self.sort_sell_desc_btn.clicked.connect(lambda: self.on_sort(3, False))
        filter_layout.addWidget(self.sort_sell_desc_btn)

        filter_layout.addWidget(QLabel("   进价排序:"))
        self.sort_cost_asc_btn = QPushButton("升序")
        self.sort_cost_asc_btn.clicked.connect(lambda: self.on_sort(4, True))
        filter_layout.addWidget(self.sort_cost_asc_btn)
        self.sort_cost_desc_btn = QPushButton("降序")
        self.sort_cost_desc_btn.clicked.connect(lambda: self.on_sort(4, False))
        filter_layout.addWidget(self.sort_cost_desc_btn)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # 表格（品类、品牌、售价、进价 共7列）
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["编号", "图片", "名称", "品类", "品牌", "售价", "进价"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 80)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)  # 单选
        self.table.cellDoubleClicked.connect(self.open_edit_window)

        layout.addWidget(self.table)
        self.setLayout(layout)

    def load_data(self):
        """从数据库加载所有商品，并刷新下拉框和表格"""
        old_brand_filter = self.current_brand_filter
        old_category_filter = self.current_category_filter

        self.all_products = self.db.get_all_products()

        # 提取所有品牌和品类（利用已有方法自动过滤脏数据）
        brands = set()
        categories = set()
        for prod in self.all_products:
            b = self.db._get_col(prod, 'brand', '')
            if b and ('-' in b or ':' in b) and len(b) > 10:
                b = ''
            if b:
                brands.add(b)
            c = self.db._get_col(prod, 'category', '')
            if c:
                categories.add(c)

        # 更新品牌下拉框
        brand_list = sorted(brands)
        self.brand_combo.blockSignals(True)
        self.brand_combo.clear()
        self.brand_combo.addItem("全部")
        self.brand_combo.addItems(brand_list)
        if old_brand_filter and old_brand_filter in brand_list:
            self.brand_combo.setCurrentText(old_brand_filter)
            self.current_brand_filter = old_brand_filter
        else:
            self.current_brand_filter = ""
            self.brand_combo.setCurrentIndex(0)
        self.brand_combo.blockSignals(False)

        # 更新品类下拉框
        category_list = sorted(categories)
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("全部")
        self.category_combo.addItems(category_list)
        if old_category_filter and old_category_filter in category_list:
            self.category_combo.setCurrentText(old_category_filter)
            self.current_category_filter = old_category_filter
        else:
            self.current_category_filter = ""
            self.category_combo.setCurrentIndex(0)
        self.category_combo.blockSignals(False)

        self.apply_filter_and_sort()

    def on_brand_filter_changed(self, brand):
        self.current_brand_filter = brand if brand != "全部" else ""
        self.apply_filter_and_sort()

    def on_category_filter_changed(self, category):
        self.current_category_filter = category if category != "全部" else ""
        self.apply_filter_and_sort()

    def on_sort(self, col, ascending):
        self.sort_col = col
        self.sort_asc = ascending
        self.apply_filter_and_sort()

    def apply_filter_and_sort(self):
        """根据当前筛选和排序刷新表格（使用列名自适应获取值）"""
        filtered = []
        for prod in self.all_products:
            b = self.db._get_col(prod, 'brand', '') or ''
            if b and ('-' in b or ':' in b) and len(b) > 10:
                b = ''
            c = self.db._get_col(prod, 'category', '') or ''
            if self.current_brand_filter and b != self.current_brand_filter:
                continue
            if self.current_category_filter and c != self.current_category_filter:
                continue
            filtered.append(prod)

        if self.sort_col is not None:
            if self.sort_col == 0:  # 编号
                filtered.sort(key=lambda x: str(x[0]), reverse=not self.sort_asc)
            else:
                filtered.sort(key=lambda x: float(x[self.sort_col]) if x[self.sort_col] is not None else 0.0,
                              reverse=not self.sort_asc)

        self.table.setRowCount(0)
        for row_idx, prod in enumerate(filtered):
            p_id = self.db._get_col(prod, 'id', '')
            p_name = self.db._get_col(prod, 'name', '')
            p_image = self.db._get_col(prod, 'image_path', '')
            p_category = self.db._get_col(prod, 'category', '')
            p_brand = self.db._get_col(prod, 'brand', '')
            if p_brand and ('-' in p_brand or ':' in p_brand) and len(p_brand) > 10:
                p_brand = ''
            p_sell = self.db._get_col(prod, 'selling_price', '0.00')
            p_cost = self.db._get_col(prod, 'cost_price', '0.00')

            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(p_id)))

            img_label = QLabel()
            img_label.setAlignment(Qt.AlignCenter)
            if p_image:
                full_path = os.path.join(IMAGE_FOLDER, p_image)
                if os.path.exists(full_path):
                    pixmap = QPixmap(full_path).scaled(60, 60, Qt.KeepAspectRatio)
                    img_label.setPixmap(pixmap)
                else:
                    img_label.setText("无图")
            else:
                img_label.setText("无图")
            self.table.setCellWidget(row_idx, 1, img_label)

            self.table.setItem(row_idx, 2, QTableWidgetItem(str(p_name)))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(p_category)))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(p_brand)))
            self.table.setItem(row_idx, 5, QTableWidgetItem(str(p_sell)))
            self.table.setItem(row_idx, 6, QTableWidgetItem(str(p_cost)))

        self.table.viewport().update()

    def delete_selected_product(self):
        """删除当前选中行的商品（包含编号文件夹和品牌名称图片）"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请先在表格中选中一个商品")
            return

        item_id = self.table.item(current_row, 0)
        if not item_id:
            return
        product_id = item_id.text()
        product = self.db.get_product(product_id)
        if not product:
            QMessageBox.warning(self, "错误", "商品数据不存在")
            return

        reply = QMessageBox.question(
            self, '确认删除',
            f'确定要删除商品 [编号: {product_id}] 吗？\n此操作无法撤销！',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # 删除编号文件夹
            product_dir = os.path.join(IMAGE_FOLDER, product_id)
            if os.path.isdir(product_dir):
                shutil.rmtree(product_dir, ignore_errors=True)
            # 删除品牌名称图片
            if product:
                brand = self.db._get_col(product, 'brand', '')
                name = self.db._get_col(product, 'name', '')
                safe_brand = re.sub(r'[\\/*?:"<>|]', '', brand) if brand else "无品牌"
                safe_name = re.sub(r'[\\/*?:"<>|]', '', name) if name else "无名称"
                base = f"{safe_brand}-{safe_name}"
                for f in os.listdir(IMAGE_FOLDER):
                    if f.startswith(base) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                        try:
                            os.remove(os.path.join(IMAGE_FOLDER, f))
                        except Exception as e:
                            print(f"删除品牌图片失败: {e}")
            # 删除数据库记录
            self.db.delete_product(product_id)
            QMessageBox.information(self, "成功", "商品删除成功！")
            self.load_data()

    def delete_brand(self):
        brand = self.brand_combo.currentText()
        if brand == "全部" or not brand:
            QMessageBox.warning(self, "警告", "请先选择一个品牌进行删除")
            return
        reply = QMessageBox.question(self, "确认删除",
                                     f"确定要删除品牌【{brand}】下的所有商品吗？\n此操作无法撤销！",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            products_to_delete = [p for p in self.all_products if self.db._get_col(p, 'brand', '') == brand]
            if not products_to_delete:
                QMessageBox.information(self, "提示", f"没有找到品牌为【{brand}】的商品")
                return
            for prod in products_to_delete:
                product_dir = os.path.join(IMAGE_FOLDER, prod[0])
                if os.path.isdir(product_dir):
                    shutil.rmtree(product_dir, ignore_errors=True)
                b = self.db._get_col(prod, 'brand', '')
                n = self.db._get_col(prod, 'name', '')
                safe_brand = re.sub(r'[\\/*?:"<>|]', '', b) if b else "无品牌"
                safe_name = re.sub(r'[\\/*?:"<>|]', '', n) if n else "无名称"
                base = f"{safe_brand}-{safe_name}"
                for f in os.listdir(IMAGE_FOLDER):
                    if f.startswith(base) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                        try:
                            os.remove(os.path.join(IMAGE_FOLDER, f))
                        except Exception as e:
                            print(f"删除品牌图片失败: {e}")
                self.db.delete_product(prod[0])
            QMessageBox.information(self, "成功", f"已删除品牌【{brand}】下的 {len(products_to_delete)} 个商品")
            self.load_data()

    # 新增：删除品类
    def delete_category(self):
        category = self.category_combo.currentText()
        if category == "全部" or not category:
            QMessageBox.warning(self, "警告", "请先选择一个品类进行删除")
            return
        reply = QMessageBox.question(self, "确认删除",
                                     f"确定要删除品类【{category}】下的所有商品吗？\n此操作无法撤销！",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            products_to_delete = [p for p in self.all_products if self.db._get_col(p, 'category', '') == category]
            if not products_to_delete:
                QMessageBox.information(self, "提示", f"没有找到品类为【{category}】的商品")
                return
            for prod in products_to_delete:
                product_dir = os.path.join(IMAGE_FOLDER, prod[0])
                if os.path.isdir(product_dir):
                    shutil.rmtree(product_dir, ignore_errors=True)
                # 删除品牌名称图片（与品牌删除逻辑一致）
                b = self.db._get_col(prod, 'brand', '')
                n = self.db._get_col(prod, 'name', '')
                safe_brand = re.sub(r'[\\/*?:"<>|]', '', b) if b else "无品牌"
                safe_name = re.sub(r'[\\/*?:"<>|]', '', n) if n else "无名称"
                base = f"{safe_brand}-{safe_name}"
                for f in os.listdir(IMAGE_FOLDER):
                    if f.startswith(base) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                        try:
                            os.remove(os.path.join(IMAGE_FOLDER, f))
                        except Exception as e:
                            print(f"删除品牌图片失败: {e}")
                self.db.delete_product(prod[0])
            QMessageBox.information(self, "成功", f"已删除品类【{category}】下的 {len(products_to_delete)} 个商品")
            self.load_data()

    def open_edit_window(self, row, column):
        item = self.table.item(row, 0)
        if item is None:
            return
        product_id = item.text()
        product = self.db.get_product(product_id)
        if product:
            dialog = ProductEditWindow(product, self.db, None)
            dialog.data_saved.connect(self.refresh_after_edit)
            dialog.show()

    def refresh_after_edit(self):
        """编辑保存后刷新当前页面"""
        self.load_data()