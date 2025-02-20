import re
from model import *
from dao import *
from common.log import logger


class HealthService:
    def __init__(self):
        self.user_dao = UserDAO()
        self.food_record_dao = FoodRecordDAO()
        self.food_dao = FoodDAO()
        self.exercise_dao = ExerciseDAO()

    def save_food_record(self, wx_id, nickname, content):
        """
        根据大模型返回的内容提取食物记录并保存到数据库中。
        """
        # 正则表达式提取总热量
        total_calories = self.extract_total_calories(content)

        # 根据食物和热量保存食物记录
        food_record_id = self.save_food_record_in_db(wx_id, nickname, total_calories, content)

        return food_record_id

    def extract_total_calories(self, content):
        """
        提取总热量值，使用正则表达式从内容中获取。
        整个表达式匹配的内容 是 完整匹配（group(0)）。
        第 1 组 (\d+(\.\d+)?)：
            这个括号内包含了 \d+(\.\d+)?，是第一个捕获组 group(1)。
            \d+：匹配整数部分（如 100）。
            (\.\d+)?：匹配可选的小数部分（如 .5）。
        第 2 组 (\.\d+)?：
            这个是 (\.\d+)? 的小数部分，是第二个捕获组 group(2)，用于匹配小数点和后面的数字（如 .5）。
        """
        match = re.search(r'总热量：?约?(\d+(\.\d+)?)千卡', content)
        if match:
            return float(match.group(1))
        return 0.0

    def save_food_record_in_db(self, wx_id, nickname, total_calories, content):
        """
        将食物记录保存到food_record表，并将食物名称和热量保存到food表中。
        """
        # 获取用户ID
        user = self.user_dao.get_user_by_wx_id(wx_id)
        if not user:
            res = self.save_user_info(wx_id=wx_id, nickname=nickname)
            if res:
                user = self.user_dao.get_user_by_wx_id(wx_id)
            else:
                return None

        # 保存食物记录到 food_record 表
        food_record_id = self.food_record_dao.insert_record(user.user_id, total_calories)

        # 提取食物信息并保存到 food 表
        food_items = self.extract_food_items(content)
        for food_item in food_items:
            self.food_dao.insert_food(food_item['food_name'], food_item['calories'], food_record_id)

        return food_record_id

    def extract_food_items(self, content):
        """
        提取食物名称和对应的热量
        ([^：:\n]+)      捕获组1：匹配食物名称，直到遇到冒号
        [：:]            匹配中文冒号 `：` 或 英文冒号 `:`
        (?:约)?	        非捕获组（?: 表示不存入匹配组），匹配可选的 "约"
        (\d+(\.\d+)?)	捕获组 2：匹配 卡路里数值（整数或小数）
        (\.\d+)?	    捕获组 3：匹配 小数部分（可选）
        千卡	            匹配 "千卡" 这个单位（不会被捕获
        """
        food_items = []
        food_pattern = r'([^：:\n]+)[：:](?:约)?(\d+(\.\d+)?)千卡'
        matches = re.finditer(food_pattern, content)
        for match in matches:
            food_name = match.group(1).strip()
            calories = float(match.group(2))
            if food_name == "总热量":
                continue
            food_items.append({'food_name': food_name, 'calories': calories})
        return food_items

    def get_user_today_food_report(self, wx_id, nickname):
        """
        查询用户当天的所有饮食记录并返回一个总结字符串。
        """
        user = self.user_dao.get_user_by_wx_id(wx_id)
        if not user:
            res = self.save_user_info(wx_id=wx_id, nickname=nickname)
            if res:
                user = self.user_dao.get_user_by_wx_id(wx_id)
            else:
                logger.error(f"[HealthService] 创建用户{wx_id}失败")
                return None

        # 获取当天的饮食记录
        food_records = self.food_record_dao.list_records_by_user(user.user_id,
                                                                 date_str=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        total_calories = 0
        report = "今日饮食记录：\n"


        count = 1
        for record in food_records:
            report += f"第 {count} 餐\n"
            count += 1
            foods = self.food_dao.list_foods_by_record(record.food_record_id)
            record_total = 0  # 总摄入热量
            for food in foods:
                record_total += food.calories
                report += f"- {food.food_name}: {food.calories}千卡\n"
            total_calories += record_total
            report += f"总热量：{record_total}千卡\n\n"  # 空行隔开每条记录

        # 获取用户今日运动消耗的热量
        # 获取当天所有运动记录
        exercise_records = self.exercise_dao.list_exercises_by_user(user.user_id, date_str=datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"))
        total_burned_calories = 0  # 今日运动总消耗的热量
        report += "今日运动记录：\n"

        for record in exercise_records:
            report += f"- {record.exercise_name}: {record.burned_calories}千卡\n"
            total_burned_calories += record.burned_calories
        report += f"总运动消耗：{total_burned_calories}千卡\n"
        # 获取用户的基础代谢率(BMR)和每日建议摄入热量
        bmr = self.calculate_bmr(user)
        recommended_calories = bmr * self.activity_level_factor(user.activity_level)

        remaining_calories = recommended_calories - total_calories + total_burned_calories

        report += f"\n今日总摄入：{total_calories:.1f}千卡\n"
        if(recommended_calories != 0):
            report += f"每日建议摄入：{recommended_calories:.1f}千卡\n"
            report += f"今日还可以摄入：{remaining_calories:.1f}千卡\n"
        else:
            report += f"提示：完善个人信息可获取推荐摄入热量"
        return report

    def calculate_bmr(self, user):
        """
        计算用户的基础代谢率（BMR），根据性别、身高和体重使用哈里斯-贝尼迪克特公式
        如果用户的个人信息不完善，因子为0，系统不会计算用户的每日推荐摄入热量
        """
        if not user.age or not user.gender or not user.height or not user.weight or not user.activity_level:
            return 0.0
        if user.gender == 1:  # 男性
            return 88.362 + (13.397 * user.weight) + (4.799 * user.height) - (5.677 * user.age)
        elif user.gender == 2:  # 女性
            return 447.593 + (9.247 * user.weight) + (3.098 * user.height) - (4.330 * user.age)
        else:  # 未知性别
            return 0.0

    def activity_level_factor(self, activity_level):
        """
        根据活动水平返回活动因子
        """
        activity_factors = {
            "久坐不动": 1.2,
            "轻度活动": 1.375,
            "中度活动": 1.55,
            "高度活动": 1.725,
            "极度活动": 1.9
        }
        return activity_factors.get(activity_level, 1.375)  # 默认为轻度活动

    def save_exercise_record(self, wx_id, nickname, exercise_name, burned_calories):
        """
        根据用户输入的运动记录，保存到运动记录表中。
        """
        user = self.user_dao.get_user_by_wx_id(wx_id)
        if not user:
            res = self.save_user_info(wx_id=wx_id, nickname=nickname)
            if res:
                user = self.user_dao.get_user_by_wx_id(wx_id)
            else:
                return None

        # 保存运动记录到 exercise_record 表
        exercise_id = self.exercise_dao.insert_exercise(exercise_name, user.user_id, burned_calories)
        return exercise_id

    def save_user_info(self, wx_id, nickname, height=None, weight=None, gender=0, age=None, activity_level=None):
        """
        根据用户输入的个人信息保存到用户信息表。
        """
        user = self.user_dao.get_user_by_wx_id(wx_id)
        if not user:
            self.user_dao.create_user(wx_id=wx_id, nickname=nickname, gender=gender, height=height, weight=weight,
                                      age=age, activity_level=activity_level)
            logger.info(f"[HealthService] 保存用户{wx_id}信息，昵称{nickname}")
            return True

        # 更新用户个人信息
        self.user_dao.update_user_info(wx_id=wx_id, height=height, weight=weight, age=age,
                                       activity_level=activity_level, gender=gender, nickname=nickname)
        return True
