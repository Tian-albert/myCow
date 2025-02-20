# db_manager.py

import sqlite3
import os
from datetime import datetime
from common.log import logger


class DBManager:
    def __init__(self, db_path=None):
        """
        :param db_path: 数据库文件路径；可传入绝对或相对路径
        """
        # 如果不传db_path，就使用默认路径
        if db_path is None:
            cur_dir = os.path.dirname(__file__)
            db_path = os.path.join(cur_dir, "food_calories.db")

        self.db_path = db_path
        logger.info(f"[DBManager] 使用的数据库文件: {self.db_path}")

        # 在这里初始化数据库表
        self.init_database()

        self.conn = None

    def init_database(self):
        """初始化数据库表结构"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 创建用户信息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增长id
                    wx_id TEXT NOT NULL,  -- 微信用户的id
                    nickname TEXT,  -- 微信昵称
                    height REAL,  -- 身高，单位cm
                    weight REAL,  -- 体重，单位kg
                    gender INTEGER DEFAULT 0  -- 0=未知，1=男，2=女
                )
            ''')

            # 创建饮食记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS food_record (
                    food_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    total_calories REAL NOT NULL,
                    record_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建食物表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS food (
                    food_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    food_name TEXT NOT NULL,
                    calories REAL NOT NULL,
                    food_record_id INTEGER NOT NULL
                )
            ''')

            # 创建运动记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS exercise_record (
                    exercise_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise_name         TEXT NOT NULL,
                    exercise_time   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER NOT NULL,
                    burned_calories REAL NOT NULL -- 运动总消耗
                );

            ''')

            # 检查新增列是否存在
            cursor.execute("PRAGMA table_info(user)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'age' not in columns:
                cursor.execute('ALTER TABLE user ADD COLUMN age INTEGER DEFAULT 22')

            conn.commit()
            conn.close()
            logger.info("[DBManager] 数据库初始化完成")
        except Exception as e:
            logger.error(f"[DBManager] 初始化数据库失败: {e}")
            raise e

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        return conn
