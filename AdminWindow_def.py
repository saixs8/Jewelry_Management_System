import os
import random
import sqlite3
from datetime import datetime
import cv2
import numpy as np

try:
    import pymysql
except ImportError:
    pymysql = None


class AdminUtils:
    """集中放置可复用的工具方法，包括数据库合并逻辑"""

    @staticmethod
    def compute_image_hash_from_path(img_path):
        """计算图片的感知哈希（64位二进制字符串）"""
        img = cv2.imread(img_path)
        if img is None:
            return ""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
        avg = np.mean(resized)
        hash_bits = (resized > avg).flatten()
        return ''.join(str(int(b)) for b in hash_bits)

    @staticmethod
    def generate_id():
        """生成商品编号：年月日+4位随机数"""
        date_str = datetime.now().strftime("%Y%m%d")
        random_str = str(random.randint(1000, 9999))
        return date_str + random_str

    @staticmethod
    def merge_sqlite_files_to_current_db(db, file_paths):
        """
        将多个 SQLite 文件合并到当前数据库连接中。
        db: Database 实例，内部 conn 可以是 sqlite3 或 pymysql 连接。
        file_paths: 要合并的 .db 文件路径列表。
        返回: (inserted, skipped, errors)
        """
        # 识别当前数据库类型并获取列信息
        if isinstance(db.conn, sqlite3.Connection):
            db.cursor.execute("PRAGMA table_info(products)")
            current_cols = [row[1] for row in db.cursor.fetchall()]
            use_mysql = False
        elif pymysql and isinstance(db.conn, pymysql.connections.Connection):
            db.cursor.execute("DESCRIBE products")
            current_cols = [row[0] for row in db.cursor.fetchall()]
            use_mysql = True
        else:
            raise Exception("不支持的数据库类型，仅支持 SQLite 或 MySQL（需安装 pymysql）")

        total_inserted = 0
        skipped = 0
        errors = []

        for file_path in file_paths:
            try:
                src_conn = sqlite3.connect(file_path)
                src_cur = src_conn.cursor()
                src_cur.execute("SELECT * FROM products")
                rows = src_cur.fetchall()
                src_cur.execute("PRAGMA table_info(products)")
                src_cols = [col[1] for col in src_cur.fetchall()]

                for row in rows:
                    try:
                        row_dict = dict(zip(src_cols, row))
                        values = []
                        for col in current_cols:
                            if col in row_dict:
                                values.append(row_dict[col])
                            else:
                                # 缺失列填充默认值
                                if col in ('selling_price', 'cost_price'):
                                    values.append(0.0)
                                elif col in ('is_sold',):
                                    values.append(0)
                                elif col in ('update_time', 'image_hash', 'platform', 'description',
                                            'sale_method', 'brand', 'category'):
                                    values.append('')
                                else:
                                    values.append('')

                        if use_mysql:
                            ph = ','.join(['%s'] * len(current_cols))
                            sql = f"INSERT IGNORE INTO products ({','.join(current_cols)}) VALUES ({ph})"
                        else:
                            ph = ','.join(['?'] * len(current_cols))
                            sql = f"INSERT OR IGNORE INTO products ({','.join(current_cols)}) VALUES ({ph})"

                        db.cursor.execute(sql, values)
                        if db.cursor.rowcount > 0:
                            total_inserted += 1
                        else:
                            skipped += 1
                    except Exception as e:
                        skipped += 1
                        errors.append(f"文件 {os.path.basename(file_path)} 中的一条记录失败: {str(e)}")
                src_conn.close()
            except Exception as e:
                errors.append(f"无法打开文件 {os.path.basename(file_path)}: {str(e)}")

        db.conn.commit()
        return total_inserted, skipped, errors