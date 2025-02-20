class User:
    def __init__(self,
                 user_id: int = None,
                 wx_id: str = None,
                 nickname: str = None,
                 height: float = None,
                 weight: float = None,
                 gender: int = 0,
                 age: int = 22,
                 activity_level: str = '久坐不动'):
        """
        :param user_id: user表主键，自增
        :param wx_id: 微信用户ID
        :param nickname: 微信昵称
        :param height: 身高，单位cm
        :param weight: 体重，单位kg
        :param gender: 0=未知,1=男,2=女
        :param age: 年龄
        :param activity_level: 活动水平, 默认值为'久坐不动'
                                久坐不动（几乎不运动）：BMR × 1.2
                                轻度活动（轻度运动或运动1-3天/周）：BMR × 1.375
                                中度活动（中等强度运动或运动3-5天/周）：BMR × 1.55
                                高度活动（高强度运动或运动6-7天/周）：BMR × 1.725
                                极度活动（极高强度运动，体力劳动者）：BMR × 1.9
        """
        self.user_id = user_id
        self.wx_id = wx_id
        self.nickname = nickname
        self.height = height
        self.weight = weight
        self.gender = gender
        self.age = age
        self.activity_level = activity_level

    def __repr__(self):
        return (f"<User user_id={self.user_id}, wx_id={self.wx_id}, nickname={self.nickname}, "
                f"height={self.height}, weight={self.weight}, gender={self.gender}, age={self.age}, "
                f"activity_level={self.activity_level}>")

    @classmethod
    def from_row(cls, row: tuple):
        """
        根据数据库返回的tuple行来构造User对象。
        row的顺序应与SELECT时的字段顺序对应：
        e.g. SELECT user_id, wx_id, nickname, height, weight, gender, age, activity_level
        """
        if not row:
            return None
        return cls(
            user_id=row[0],
            wx_id=row[1],
            nickname=row[2],
            height=row[3],
            weight=row[4],
            gender=row[5],
            age=row[6],
            activity_level=row[7] if len(row) > 7 else '久坐不动'  # 加入活动水平字段
        )



class FoodRecord:
    def __init__(self,
                 food_record_id: int = None,
                 user_id: int = None,
                 total_calories: float = 0.0,
                 record_time: str = None):
        """
        :param food_record_id: 主键，自增
        :param user_id: 关联 user 表的ID
        :param total_calories: 该记录时段内的总热量
        :param record_time: 记录时间，字符串格式如 '2025-02-20 10:30:00'
        """
        self.food_record_id = food_record_id
        self.user_id = user_id
        self.total_calories = total_calories
        self.record_time = record_time

    def __repr__(self):
        return (f"<FoodRecord food_record_id={self.food_record_id}, user_id={self.user_id}, "
                f"total_calories={self.total_calories}, record_time={self.record_time}>")

    @classmethod
    def from_row(cls, row: tuple):
        """
        根据数据库返回的tuple行构造FoodRecord对象。
        e.g. SELECT food_record_id, user_id, total_calories, record_time
        """
        if not row:
            return None
        return cls(
            food_record_id=row[0],
            user_id=row[1],
            total_calories=row[2],
            record_time=row[3],
        )


class Food:
    def __init__(self,
                 food_id: int = None,
                 food_name: str = None,
                 calories: float = None,
                 food_record_id: int = None):
        """
        :param food_id: 主键，自增
        :param food_name: 食物名称，如"米饭"
        :param calories: 食物热量(可按实际摄入量或100g的热量)
        :param food_record_id: 关联到 food_record 的ID
        """
        self.food_id = food_id
        self.food_name = food_name
        self.calories = calories
        self.food_record_id = food_record_id

    def __repr__(self):
        return (f"<Food food_id={self.food_id}, food_name={self.food_name}, "
                f"calories={self.calories}, food_record_id={self.food_record_id}>")

    @classmethod
    def from_row(cls, row: tuple):
        """
        根据数据库返回的tuple行构造Food对象。
        e.g. SELECT food_id, food_name, calories, food_record_id
        """
        if not row:
            return None
        return cls(
            food_id=row[0],
            food_name=row[1],
            calories=row[2],
            food_record_id=row[3],
        )


class ExerciseRecord:
    def __init__(self,
                 exercise_id: int = None,
                 exercise_name: str = None,
                 exercise_time: str = None,
                 user_id: int = None,
                 burned_calories: float = 0.0):
        """
        :param exercise_id: 主键，自增
        :param exercise_name: 运动名称，如"跑步"
        :param exercise_time: 运动时间，SQLite下通常为TEXT
        :param user_id: 关联 user 表ID
        :param burned_calories: 本次运动消耗的总热量
        """
        self.exercise_id = exercise_id
        self.exercise_name = exercise_name
        self.exercise_time = exercise_time
        self.user_id = user_id
        self.burned_calories = burned_calories

    def __repr__(self):
        return (f"<ExerciseRecord exercise_id={self.exercise_id}, exercise_name={self.exercise_name}, "
                f"exercise_time={self.exercise_time}, user_id={self.user_id}, "
                f"burned_calories={self.burned_calories}>")

    @classmethod
    def from_row(cls, row: tuple):
        """
        根据数据库返回的tuple行构造ExerciseRecord对象。
        e.g. SELECT exercise_id, exercise_name, exercise_time, user_id, burned_calories
        """
        if not row:
            return None
        return cls(
            exercise_id=row[0],
            exercise_name=row[1],
            exercise_time=row[2],
            user_id=row[3],
            burned_calories=row[4],
        )
