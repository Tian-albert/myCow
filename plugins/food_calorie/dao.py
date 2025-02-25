# dao.py

from .model import *
import sqlite3
import os
from datetime import datetime
from common.log import logger


class DBManager:
    _instance = None  # 用于保存单例实例

    def __new__(cls, db_path=None):
        if cls._instance is None:
            cls._instance = super(DBManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path=None):
        """
        :param db_path: 数据库文件路径；可传入绝对或相对路径
        """
        # 如果已有实例初始化过，就不重复执行 init_database()
        # 因为 Python __init__ 在单例模式下会被多次调用
        if hasattr(self, "_inited") and self._inited:
            return

        # 如果不传db_path，就使用默认路径
        if db_path is None:
            cur_dir = os.path.dirname(__file__)
            db_path = os.path.join(cur_dir, "food_calorie.db")

        self.db_path = db_path
        logger.info(f"[DBManager] 使用的数据库文件: {self.db_path}")

        # 初始化数据库表
        self.init_database()
        self.conn = None

        # 标记已经初始化过
        self._inited = True

    def init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        try:
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
                    record_time TIMESTAMP DEFAULT (datetime('now','localtime'))
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
                    exercise_name     TEXT NOT NULL,
                    exercise_time     TIMESTAMP DEFAULT (datetime('now','localtime')),
                    user_id           INTEGER NOT NULL,
                    burned_calories   REAL NOT NULL -- 运动总消耗
                );
            ''')

            # 检查新增列是否存在
            # 检查user表
            cursor.execute("PRAGMA table_info(user)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'age' not in columns:
                cursor.execute('ALTER TABLE user ADD COLUMN age INTEGER DEFAULT 22')
            if 'activity_level' not in columns:
                cursor.execute('ALTER TABLE user ADD COLUMN activity_level TEXT')

            # 检查food_record表
            cursor.execute("PRAGMA table_info(food_record)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'img_path' not in columns:
                cursor.execute('ALTER TABLE food_record ADD COLUMN img_path TEXT')

            conn.commit()
            conn.close()
            logger.info("[DBManager] 数据库初始化完成")
        except Exception as e:
            logger.error(f"[DBManager] 初始化数据库失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            raise e

    def get_conn(self):
        return sqlite3.connect(self.db_path)


class UserDAO:
    def __init__(self):
        self.db_manager = DBManager()

    def create_user(self, wx_id: str, nickname: str = None, gender: int = 0,
                    height: float = None, weight: float = None, age: int = 22,
                    activity_level: str = '轻度活动') -> int:
        """
        在user表插入新记录，并返回新用户的user_id
        """
        conn = self.db_manager.get_conn()
        new_user_id = None
        try:
            cur = conn.cursor()

            sql = """
                INSERT INTO user (wx_id, nickname, gender, height, weight, age, activity_level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            cur.execute(sql, (wx_id, nickname, gender, height, weight, age, activity_level))
            new_user_id = cur.lastrowid
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[UserDAO] 创建用户失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()

        return new_user_id

    def get_user_by_wx_id(self, wx_id: str) -> User:
        """
        通过wx_id获取用户记录；若存在则返回User对象，否则返回None
        """
        conn = self.db_manager.get_conn()
        row = None
        try:
            cur = conn.cursor()

            sql = """
                SELECT user_id, wx_id, nickname, height, weight, gender, age, activity_level
                FROM user
                WHERE wx_id = ?
            """
            cur.execute(sql, (wx_id,))
            row = cur.fetchone()

            conn.close()
        except Exception as e:
            logger.error(f"[UserDAO] 获取用户失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()

        # 使用Model的from_row构造User对象
        return User.from_row(row) if row else None

    def update_user_info(self, wx_id: str, nickname: str = None,
                         gender: int = None, height: float = None,
                         weight: float = None, age: int = None,
                         activity_level: str = None) -> bool:
        """
        更新用户信息；返回是否有行受到影响
        """
        conn = self.db_manager.get_conn()
        affected = 0
        try:
            cur = conn.cursor()

            set_parts = []
            params = []
            if nickname is not None:
                set_parts.append("nickname = ?")
                params.append(nickname)
            if gender is not None:
                set_parts.append("gender = ?")
                params.append(gender)
            if height is not None:
                set_parts.append("height = ?")
                params.append(height)
            if weight is not None:
                set_parts.append("weight = ?")
                params.append(weight)
            if age is not None:
                set_parts.append("age = ?")
                params.append(age)
            if activity_level is not None:
                set_parts.append("activity_level = ?")
                params.append(activity_level)

            if not set_parts:
                conn.close()
                return False  # 无任何字段更新

            set_clause = ", ".join(set_parts)
            params.append(wx_id)
            sql = f"UPDATE user SET {set_clause} WHERE wx_id = ?"

            cur.execute(sql, params)
            conn.commit()
            affected = cur.rowcount
            conn.close()
        except Exception as e:
            logger.error(f"[UserDAO] 更新用户信息失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()

        return affected > 0

    def delete_user_by_wx_id(self, wx_id: str) -> bool:
        """
        根据wx_id删除用户；返回是否有行被删
        """
        rowcount = 0
        conn = self.db_manager.get_conn()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM user WHERE wx_id = ?", (wx_id,))
            conn.commit()
            rowcount = cur.rowcount
            conn.close()
        except Exception as e:
            logger.error(f"[UserDAO] 删除用户失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
        return rowcount > 0


class ExerciseDAO:
    def __init__(self):
        self.db_manager = DBManager()

    def insert_exercise(self, exercise_name: str, user_id: int, burned_calories: float) -> int:
        """
        向 exercise_record 表插入一条新的运动记录，并返回新插入记录的 exercise_id
        """
        conn = self.db_manager.get_conn()
        new_exercise_id = -1
        try:
            cur = conn.cursor()

            sql = """
                INSERT INTO exercise_record (exercise_name, user_id, burned_calories)
                VALUES (?, ?, ?)
            """
            cur.execute(sql, (exercise_name, user_id, burned_calories))
            new_exercise_id = cur.lastrowid

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[ExerciseDAO] 插入运动记录失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
        return new_exercise_id if new_exercise_id != -1 else None

    def get_exercise_by_id(self, exercise_id: int) -> ExerciseRecord:
        """
        根据ID获取运动记录, 返回ExerciseRecord对象或None
        """
        conn = self.db_manager.get_conn()
        row = None
        try:
            cur = conn.cursor()

            sql = """
                SELECT exercise_id, exercise_name, exercise_time, user_id, burned_calories
                FROM exercise_record
                WHERE exercise_id = ?
            """
            cur.execute(sql, (exercise_id,))
            row = cur.fetchone()
            conn.close()
        except Exception as e:
            logger.error(f"[ExerciseDAO] 获取运动记录失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()

        return ExerciseRecord.from_row(row) if row else None

    def list_exercises_by_user(self, user_id: int, date_str: str = None) -> list:
        """
        查询某个用户的所有运动记录, 返回ExerciseRecord对象列表
        """
        conn = self.db_manager.get_conn()
        rows = []
        try:
            cur = conn.cursor()

            # select的顺序要与model打印的顺序一致！！
            if date_str:
                sql = """
                SELECT exercise_id, exercise_name, exercise_time, user_id, burned_calories
                FROM exercise_record
                WHERE user_id = ?
                    AND DATE(exercise_time) = DATE(?)
                ORDER BY exercise_time DESC
                """
                cur.execute(sql, (user_id, date_str))
            else:
                sql = """
                    SELECT exercise_id, exercise_name, exercise_time, user_id, burned_calories
                    FROM exercise_record
                    WHERE user_id = ?
                    ORDER BY exercise_time DESC
                """
                cur.execute(sql, (user_id,))
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            logger.error(f"[ExerciseDAO] 查询运动记录失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()

        return [ExerciseRecord.from_row(r) for r in rows]

    def delete_exercise(self, exercise_id: int) -> bool:
        """
        删除运动记录
        """
        conn = self.db_manager.get_conn()
        deleted = 0
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM exercise_record WHERE exercise_id = ?", (exercise_id,))
            conn.commit()
            deleted = cur.rowcount
            conn.close()
        except Exception as e:
            logger.error(f"[ExerciseDAO] 删除运动记录失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
        return deleted > 0

    def update_burned_calories(self, exercise_id: int, new_calories: float) -> bool:
        """
        更新运动记录的消耗热量
        """
        conn = self.db_manager.get_conn()
        updated = 0
        try:
            cur = conn.cursor()
            sql = """
                UPDATE exercise_record
                SET burned_calories = ?
                WHERE exercise_id = ?
            """
            cur.execute(sql, (new_calories, exercise_id))
            conn.commit()
            updated = cur.rowcount
            conn.close()
        except Exception as e:
            logger.error(f"[ExerciseDAO] 更新运动记录失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
        return updated > 0


class FoodDAO:
    def __init__(self):
        self.db_manager = DBManager()

    def insert_food(self, food_name: str, calories: float, food_record_id: int) -> int:
        """
        向 food 表插入一条新的食物记录，并返回新插入记录的 food_id
        """
        conn = self.db_manager.get_conn()
        new_food_id = None
        try:
            cur = conn.cursor()

            sql = """
                INSERT INTO food (food_name, calories, food_record_id)
                VALUES (?, ?, ?)
            """
            cur.execute(sql, (food_name, calories, food_record_id))
            new_food_id = cur.lastrowid

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[FoodDAO] 插入食物失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
        return new_food_id

    def get_food_by_id(self, food_id: int) -> Food:
        """
        根据ID获取食物明细，返回Food对象或None
        """
        conn = self.db_manager.get_conn()
        row = None
        try:
            cur = conn.cursor()

            sql = """
                SELECT food_id, food_name, calories, food_record_id
                FROM food
                WHERE food_id = ?
            """
            cur.execute(sql, (food_id,))
            row = cur.fetchone()
            conn.close()
        except Exception as e:
            logger.error(f"[FoodDAO] 获取食物失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()

        return Food.from_row(row) if row else None

    def list_foods_by_record(self, food_record_id: int) -> list:
        """
        查询某条饮食记录下的所有食物，并返回Food对象列表
        """
        conn = self.db_manager.get_conn()
        rows = []
        try:
            cur = conn.cursor()

            sql = """
                SELECT food_id, food_name, calories, food_record_id
                FROM food
                WHERE food_record_id = ?
            """
            cur.execute(sql, (food_record_id,))
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            logger.error(f"[FoodDAO] 查询食物失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()

        return [Food.from_row(r) for r in rows]

    def delete_food(self, food_id: int) -> bool:
        """
        删除某条食物记录
        """
        conn = self.db_manager.get_conn()
        deleted = 0
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM food WHERE food_id = ?", (food_id,))
            conn.commit()
            deleted = cur.rowcount
            conn.close()
        except Exception as e:
            logger.error(f"[FoodDAO] 删除食物失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
        return deleted > 0

    def update_food_calories(self, food_id: int, new_calories: float) -> bool:
        """
        更新某条食物的热量值
        """
        conn = self.db_manager.get_conn()
        updated = 0
        try:
            cur = conn.cursor()
            sql = """
                UPDATE food
                SET calories = ?
                WHERE food_id = ?
            """
            cur.execute(sql, (new_calories, food_id))
            conn.commit()
            updated = cur.rowcount
            conn.close()
        except Exception as e:
            logger.error(f"[FoodDAO] 更新食物失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
        return updated > 0


class FoodRecordDAO:
    def __init__(self):
        self.db_manager = DBManager()

    def insert_record(self, user_id: int, img_path: str, total_calories: float = 0.0,
                      record_time: str = None) -> int:
        """
        向 food_record 表插入一条记录，并返回新插入记录的 food_record_id
        :param user_id: user表的主键ID
        :param img_path:
        :param total_calories: 当时记录的总热量
        :param record_time: 如果为None，可用默认CURRENT_TIMESTAMP
        """
        conn = self.db_manager.get_conn()
        new_record_id = None
        try:
            cur = conn.cursor()

            if record_time is None:
                # 直接在 SQL 里使用CURRENT_TIMESTAMP
                sql = """
                    INSERT INTO food_record (user_id, total_calories, img_path)
                    VALUES (?, ?, ?)
                """
                cur.execute(sql, (user_id, total_calories, img_path))
            else:
                sql = """
                    INSERT INTO food_record (user_id, total_calories, record_time, img_path)
                    VALUES (?, ?, ?, ?)
                """
                cur.execute(sql, (user_id, total_calories, record_time, img_path))

            new_record_id = cur.lastrowid

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[FoodRecordDAO] 插入食物记录失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
        return new_record_id

    def update_total_calories(self, food_record_id: int, new_calories: float) -> bool:
        """
        更新饮食记录表中的total_calories字段
        """
        conn = self.db_manager.get_conn()
        updated = 0
        try:
            cur = conn.cursor()

            sql = """
                UPDATE food_record
                SET total_calories = ?
                WHERE food_record_id = ?
            """
            cur.execute(sql, (new_calories, food_record_id))
            conn.commit()
            updated = cur.rowcount
            conn.close()
        except Exception as e:
            logger.error(f"[FoodRecordDAO] 更新食物记录失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()

        return updated > 0

    def get_record_by_id(self, food_record_id: int) -> FoodRecord:
        """
        根据ID获取饮食记录，返回FoodRecord对象或None
        """
        conn = self.db_manager.get_conn()
        row = None
        try:
            cur = conn.cursor()

            sql = """
                SELECT food_record_id, user_id, total_calories, record_time, img_path
                FROM food_record
                WHERE food_record_id = ?
            """
            cur.execute(sql, (food_record_id,))
            row = cur.fetchone()
            conn.close()
        except Exception as e:
            logger.error(f"[FoodRecordDAO] 获取食物记录失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()

        return FoodRecord.from_row(row) if row else None

    def list_records_by_user(self, user_id: int, date_str: str = None) -> list:
        """
        获取指定用户的所有饮食记录；可根据日期筛选
        返回包含多个FoodRecord对象的列表
        """
        conn = self.db_manager.get_conn()
        rows = []
        try:
            cur = conn.cursor()

            if date_str:
                sql = """
                    SELECT food_record_id, user_id, total_calories, record_time, img_path
                    FROM food_record
                    WHERE user_id = ?
                      AND DATE(record_time) = DATE(?)
                    ORDER BY record_time DESC
                """
                cur.execute(sql, (user_id, date_str))
            else:
                sql = """
                    SELECT food_record_id, user_id, total_calories, record_time, img_path
                    FROM food_record
                    WHERE user_id = ?
                    ORDER BY record_time DESC
                """
                cur.execute(sql, (user_id,))

            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            logger.error(f"[FoodRecordDAO] 查询食物记录失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()

        # 将每条记录转换为FoodRecord对象
        return [FoodRecord.from_row(r) for r in rows]

    def delete_record(self, food_record_id: int) -> bool:
        """
        删除饮食记录
        """
        conn = self.db_manager.get_conn()
        deleted = 0
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM food_record WHERE food_record_id = ?", (food_record_id,))
            conn.commit()
            deleted = cur.rowcount
            conn.close()
        except Exception as e:
            logger.error(f"[FoodRecordDAO] 删除食物记录失败: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
        return deleted > 0
