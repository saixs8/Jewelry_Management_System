"""
数据库迁移 / 合并工具类
支持：
- SQLite → MySQL 迁移
- SQLite → 当前数据库（自动识别 SQLite / MySQL）合并
"""

import os
import sqlite3
import pymysql


class DatabaseMigrator:
    """
    数据库迁移类
    可通过实例化并传入配置执行迁移，也可使用静态方法快速调用
    """

    def __init__(self, mysql_host=None, mysql_user=None, mysql_password=None, mysql_db=None):
        self.mysql_host = mysql_host
        self.mysql_user = mysql_user
        self.mysql_password = mysql_password
        self.mysql_db = mysql_db

    # ---------- 公共：合并 SQLite 文件到当前数据库 ----------
    @staticmethod
    def merge_sqlite_to_current(db_manager, file_paths):
        """
        将 SQLite 文件合并到当前已打开的数据库连接
        db_manager: 当前系统的 Database 实例
        file_paths: 要合并的 .db 文件路径列表
        返回 (inserted, skipped, errors)
        """
        # 获取当前数据库的列信息
        db_manager.cursor.execute("PRAGMA table_info(products)" if isinstance(db_manager.conn, sqlite3.Connection)
                                  else "DESCRIBE products")
        current_cols = [row[1] if isinstance(row, tuple) else row[0] for row in db_manager.cursor.fetchall()]

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
                        # 构建 SQL
                        if isinstance(db_manager.conn, sqlite3.Connection):
                            ph = ','.join(['?'] * len(current_cols))
                            sql = f"INSERT OR IGNORE INTO products ({','.join(current_cols)}) VALUES ({ph})"
                        else:  # MySQL
                            ph = ','.join(['%s'] * len(current_cols))
                            sql = f"INSERT IGNORE INTO products ({','.join(current_cols)}) VALUES ({ph})"
                        db_manager.cursor.execute(sql, values)
                        if db_manager.cursor.rowcount > 0:
                            total_inserted += 1
                        else:
                            skipped += 1
                    except Exception as e:
                        skipped += 1
                        errors.append(f"文件 {os.path.basename(file_path)} 中的一条记录失败: {str(e)}")
                src_conn.close()
            except Exception as e:
                errors.append(f"无法打开文件 {os.path.basename(file_path)}: {str(e)}")

        db_manager.conn.commit()
        return total_inserted, skipped, errors

    # ---------- SQLite → MySQL 迁移（独立于当前程序）----------
    def migrate_sqlite_to_mysql(self, sqlite_path):
        """将指定的 SQLite 文件迁移到配置的 MySQL 数据库"""
        if not os.path.exists(sqlite_path):
            return f"文件不存在: {sqlite_path}"

        try:
            sqlite_conn = sqlite3.connect(sqlite_path)
            sqlite_cur = sqlite_conn.cursor()
            sqlite_cur.execute("SELECT * FROM products")
            rows = sqlite_cur.fetchall()
            sqlite_cur.execute("PRAGMA table_info(products)")
            old_cols = [col[1] for col in sqlite_cur.fetchall()]

            mysql_conn = pymysql.connect(
                host=self.mysql_host,
                user=self.mysql_user,
                password=self.mysql_password,
                database=self.mysql_db,
                charset='utf8mb4'
            )
            mysql_cur = mysql_conn.cursor()

            # 目标列（与 MySQL 表结构一致）
            target_cols = [
                'id', 'name', 'image_path', 'selling_price', 'cost_price',
                'remark', 'location', 'create_time', 'platform', 'description',
                'is_sold', 'sale_method', 'brand', 'category', 'update_time', 'image_hash'
            ]
            defaults = {c: '' for c in target_cols}
            for c in ('selling_price', 'cost_price'): defaults[c] = 0.0
            defaults['is_sold'] = 0

            inserted, skipped = 0, 0
            for row in rows:
                row_dict = dict(zip(old_cols, row))
                vals = []
                for col in target_cols:
                    v = row_dict.get(col)
                    if v is None:
                        v = defaults[col]
                    vals.append(v)
                try:
                    ph = ','.join(['%s'] * len(target_cols))
                    sql = f"INSERT IGNORE INTO products ({','.join(target_cols)}) VALUES ({ph})"
                    mysql_cur.execute(sql, vals)
                    if mysql_cur.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1
                except Exception as e:
                    mysql_conn.rollback()
                    return f"插入失败: {str(e)}"
            mysql_conn.commit()
            mysql_cur.close()
            mysql_conn.close()
            sqlite_conn.close()
            return f"迁移完成：成功 {inserted} 条，跳过 {skipped} 条"
        except Exception as e:
            return f"迁移出错: {str(e)}"