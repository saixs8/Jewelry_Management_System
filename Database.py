import os
import json
import sqlite3
from datetime import datetime

try:
    import pymysql
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

IMAGE_FOLDER = "Jewelry_images"

class Database:
    def __init__(self):
        if not os.path.exists(IMAGE_FOLDER):
            os.makedirs(IMAGE_FOLDER)

        self.use_mysql = False
        self.mysql_failed = False          # 新增：标记 MySQL 连接是否失败
        self.conn = None
        self.cursor = None

        # 尝试加载 MySQL 配置
        mysql_config = self._load_mysql_config()
        if mysql_config and PYMYSQL_AVAILABLE:
            try:
                self.conn = pymysql.connect(
                    host=mysql_config["host"],
                    user=mysql_config["user"],
                    password=mysql_config["password"],
                    database=mysql_config["database"],
                    charset='utf8mb4',
                    cursorclass=pymysql.cursors.Cursor
                )
                self.cursor = self.conn.cursor()
                self.use_mysql = True
                print("已连接到 MySQL 数据库")
            except Exception as e:
                self.mysql_failed = True
                print(f"MySQL 连接失败，已回退到本地 SQLite: {e}")
                self.conn = None

        # 回退到 SQLite
        if self.conn is None:
            self.conn = sqlite3.connect("Jewelry_Management_System.db")
            self.cursor = self.conn.cursor()
            print("使用本地 SQLite 数据库")

        self.create_table()
        self._build_column_map()
        self._fix_all_time_columns()
        self._fix_create_time_column()

    def _load_mysql_config(self):
        path = os.path.join(os.path.dirname(__file__), "mysql_config.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            if all(k in cfg for k in ("host", "user", "password", "database")):
                return cfg
        except:
            pass
        return None

    # ---------------- 自适应建表 ----------------
    def create_table(self):
        if self.use_mysql:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id VARCHAR(20) PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    image_path VARCHAR(500),
                    selling_price DECIMAL(10,2),
                    cost_price DECIMAL(10,2),
                    remark TEXT,
                    location VARCHAR(200),
                    create_time VARCHAR(30),
                    platform VARCHAR(200) DEFAULT '',
                    description TEXT,
                    is_sold TINYINT DEFAULT 0,
                    sale_method VARCHAR(200) DEFAULT '',
                    brand VARCHAR(100) DEFAULT '',
                    category VARCHAR(100) DEFAULT '',
                    update_time VARCHAR(30) DEFAULT '',
                    image_hash VARCHAR(64) DEFAULT ''
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ''')
        else:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    image_path TEXT,
                    selling_price REAL,
                    cost_price REAL,
                    remark TEXT,
                    location TEXT,
                    create_time TEXT,
                    platform TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    is_sold INTEGER DEFAULT 0,
                    sale_method TEXT DEFAULT '',
                    brand TEXT DEFAULT '',
                    category TEXT DEFAULT '',
                    update_time TEXT DEFAULT '',
                    image_hash TEXT DEFAULT ''
                )
            ''')
        self.conn.commit()

    # ---------------- 通用列映射与清洗 ----------------
    def _build_column_map(self):
        if self.use_mysql:
            self.cursor.execute("DESCRIBE products")
            cols = self.cursor.fetchall()
            self.col_map = {col[0]: idx for idx, col in enumerate(cols)}
        else:
            self.cursor.execute("PRAGMA table_info(products)")
            cols = self.cursor.fetchall()
            self.col_map = {col[1]: col[0] for col in cols}
        print(f"[列映射] 数据库实际列顺序: {list(self.col_map.keys())}")

    def _fix_all_time_columns(self):
        for col_name in ['brand', 'category']:
            if col_name not in self.col_map:
                continue
            try:
                placeholder = '%s' if self.use_mysql else '?'
                self.cursor.execute(f"SELECT id, {col_name} FROM products")
                rows = self.cursor.fetchall()
                updated = 0
                for pid, val in rows:
                    if val:
                        is_time = False
                        if ('-' in val or ':' in val) and len(val) >= 8:
                            is_time = True
                        if any(w in val for w in ['星期', '周', '上午', '下午']):
                            is_time = True
                        if is_time:
                            self.cursor.execute(f"UPDATE products SET {col_name} = '' WHERE id = {placeholder}", (pid,))
                            updated += 1
                if updated > 0:
                    print(f"[数据库修复] 已清空 {updated} 条记录中的错误{col_name}数据（时间格式）")
                self.conn.commit()
            except Exception as e:
                print(f"[数据库修复] 修复{col_name}失败: {e}")

    def _fix_create_time_column(self):
        if 'create_time' not in self.col_map:
            return
        try:
            placeholder = '%s' if self.use_mysql else '?'
            self.cursor.execute("SELECT id, create_time FROM products")
            rows = self.cursor.fetchall()
            updated = 0
            for pid, ct in rows:
                if ct:
                    if not ('-' in ct and len(ct) >= 10):
                        self.cursor.execute(f"UPDATE products SET create_time = '' WHERE id = {placeholder}", (pid,))
                        updated += 1
            if updated > 0:
                print(f"[数据库修复] 已清空 {updated} 条记录中的错误创建时间数据")
            self.conn.commit()
        except Exception as e:
            print(f"[数据库修复] 修复创建时间失败: {e}")

    # ---------------- 通用取值方法 ----------------
    def _get_col(self, row, col_name, default=""):
        idx = self.col_map.get(col_name)
        if idx is not None and idx < len(row):
            val = row[idx]
            return val if val is not None else default
        return default

    # ---------------- 增删改查 ----------------
    def insert_product(self, data):
        if len(data) < 14:
            print("警告：插入数据长度不足14")
            return False
        try:
            cols = ['id','name','image_path','selling_price','cost_price','remark',
                    'location','create_time','platform','description','is_sold',
                    'sale_method','brand','category']
            if self.use_mysql:
                ph = ','.join(['%s'] * len(cols))
                sql = f"INSERT INTO products ({','.join(cols)}) VALUES ({ph})"
            else:
                ph = ','.join(['?'] * len(cols))
                sql = f"INSERT INTO products ({','.join(cols)}) VALUES ({ph})"
            self.cursor.execute(sql, data)
            self.conn.commit()
            return True
        except Exception as e:
            print("数据库插入错误:", e)
            return False

    def get_product(self, product_id):
        placeholder = '%s' if self.use_mysql else '?'
        self.cursor.execute(f"SELECT * FROM products WHERE id={placeholder}", (product_id,))
        row = self.cursor.fetchone()
        return tuple(row) if row else None

    def get_all_products(self):
        self.cursor.execute("SELECT * FROM products")
        return [tuple(row) for row in self.cursor.fetchall()]

    def delete_product(self, product_id):
        placeholder = '%s' if self.use_mysql else '?'
        self.cursor.execute(f"SELECT image_path FROM products WHERE id={placeholder}", (product_id,))
        result = self.cursor.fetchone()
        if result and result[0]:
            try:
                if os.path.exists(result[0]):
                    os.remove(result[0])
            except Exception as e:
                print("删除图片文件失败:", e)
        self.cursor.execute(f"DELETE FROM products WHERE id={placeholder}", (product_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get_all_brands(self):
        self.cursor.execute("SELECT DISTINCT brand FROM products WHERE brand != ''")
        rows = self.cursor.fetchall()
        clean = []
        for r in rows:
            b = r[0]
            if not b: continue
            if ('-' in b or ':' in b) and len(b) >= 8: continue
            if any(w in b for w in ['星期', '周', '上午', '下午']): continue
            clean.append(b)
        return clean

    def get_all_categories(self):
        self.cursor.execute("SELECT DISTINCT category FROM products WHERE category != ''")
        rows = self.cursor.fetchall()
        clean = []
        for r in rows:
            c = r[0]
            if not c: continue
            if ('-' in c or ':' in c) and len(c) >= 8: continue
            if any(w in c for w in ['星期', '周', '上午', '下午']): continue
            clean.append(c)
        return clean

    def update_product(self, product_id, data):
        if len(data) != 13:
            print(f"数据长度应为13，实际为 {len(data)}")
            return False
        try:
            if self.use_mysql:
                sql = '''
                    UPDATE products
                    SET name=%s, image_path=%s, selling_price=%s, cost_price=%s,
                        location=%s, create_time=%s, remark=%s,
                        platform=%s, description=%s, is_sold=%s, sale_method=%s, brand=%s, category=%s
                    WHERE id=%s
                '''
                self.cursor.execute(sql, (*data, product_id))
            else:
                sql = '''
                    UPDATE products
                    SET name=?, image_path=?, selling_price=?, cost_price=?,
                        location=?, create_time=?, remark=?,
                        platform=?, description=?, is_sold=?, sale_method=?, brand=?, category=?
                    WHERE id=?
                '''
                self.cursor.execute(sql, (*data, product_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"更新商品失败: {e}")
            return False

    def update_image_hash(self, product_id, image_hash):
        placeholder = '%s' if self.use_mysql else '?'
        try:
            self.cursor.execute(f"UPDATE products SET image_hash={placeholder} WHERE id={placeholder}", (image_hash, product_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"更新图片哈希失败: {e}")
            return False

    def get_all_image_hashes(self):
        self.cursor.execute("SELECT id, image_hash FROM products WHERE image_hash != ''")
        return self.cursor.fetchall()

    def get_product_category(self, product_id):
        placeholder = '%s' if self.use_mysql else '?'
        self.cursor.execute(f"SELECT category FROM products WHERE id={placeholder}", (product_id,))
        row = self.cursor.fetchone()
        return row[0] if row else ""

    def get_product_brand(self, product_id):
        placeholder = '%s' if self.use_mysql else '?'
        self.cursor.execute(f"SELECT brand FROM products WHERE id={placeholder}", (product_id,))
        row = self.cursor.fetchone()
        return row[0] if row else ""

    def get_product_create_time(self, product_id):
        placeholder = '%s' if self.use_mysql else '?'
        self.cursor.execute(f"SELECT create_time FROM products WHERE id={placeholder}", (product_id,))
        row = self.cursor.fetchone()
        return row[0] if row else ""

    def close(self):
        self.conn.close()