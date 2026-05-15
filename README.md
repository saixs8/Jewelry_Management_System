\# 首饰管理系统



基于 PyQt5 的桌面首饰进销存管理系统，支持商品管理、图片管理、手写编号识别（百度OCR）、图像特征匹配、销售统计与数据库（SQLite / MySQL）切换。



\## 主要功能



\- \*\*管理员登录\*\*（默认 admin/admin）

\- \*\*商品录入\*\*：支持拍照、本地图片上传，自动生成编号，品牌/品类动态扩展。

\- \*\*所有商品列表\*\*：筛选、排序、批量删除、导出 Excel。

\- \*\*编辑/删除商品\*\*：按编号/名称/时间范围搜索，支持多图片管理、设置主图、同步品牌封面。

\- \*\*手写编号识别\*\*：调用百度 OCR 识别摄像头画面中的手写数字，自动匹配商品。

\- \*\*图像匹配\*\*：基于 ORB 特征 + 颜色直方图，从数据库中匹配相似首饰图片。

\- \*\*统计报表\*\*：全时段/自定义时间段的售出数量、收入、成本、利润，并生成销售额趋势图。

\- \*\*数据库管理\*\*：在 MySQL 和 SQLite 之间切换，支持 SQLite 数据合并到当前数据库。

\- \*\*跨数据库兼容\*\*：自动适配 MySQL / SQLite 的 SQL 语法。



\## 技术栈



\- \*\*界面\*\*：PyQt5

\- \*\*图像处理\*\*：OpenCV、NumPy

\- \*\*数据库\*\*：SQLite（内置）、MySQL（可选，需 pymysql）

\- \*\*OCR\*\*：百度通用文字识别 API

\- \*\*图表\*\*：Matplotlib

\- \*\*Excel 导出\*\*：pandas、openpyxl



\## 环境要求



\- Python 3.8+

\- 建议使用虚拟环境



\## 安装与运行



```bash

\# 1. 克隆或下载项目代码

cd JewelryManagementSystem



\# 2. 安装依赖

pip install -r requirements.txt

\# 3. 设置百度OCR识别秘钥
在AdminWindows中open_baidu_ocr用法中设置：
    def open_baidu_ocr(self):
        try:
            dialog = BaiduOCRDialog(self.db, self, api_key="你的真实API_Key",#这里要添加你的真实API_Key
                                   secret_key="秘钥")
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "功能暂时不可用", f"匹配模块加载失败，已禁用。\n错误: {e}")
            self.btn_match_image.setEnabled(False)
            self.btn_match_image.setText("📷 匹配(已禁用)")



\# 3. 运行程序

python Jewelry\_Management\_System.py

