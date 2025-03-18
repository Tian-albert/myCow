import re
from .dao import *
from common.log import logger


class HealthService:
    def __init__(self):
        self.user_dao = UserDAO()
        self.food_record_dao = FoodRecordDAO()
        self.food_dao = FoodDAO()
        self.exercise_dao = ExerciseDAO()

    def save_food_record(self, wx_id, nickname, content, img_path=None):
        """
        根据大模型返回的内容提取食物记录并保存到数据库中。
        """
        # 正则表达式提取总热量
        total_calories = self._extract_total_calories(content)
        logger.info(f"提取到的总热量为: {total_calories}")
        # if total_calories == 0.0:
        #     logger.error(f"[HealthService] 未提取到总热量，原文为：[{content}]")
        #     return None

        # 根据食物和热量保存食物记录
        food_record_id = self._save_food_record_in_db(wx_id, nickname, total_calories, content, img_path)

        return food_record_id

    def _extract_total_calories(self, content):
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

    def _save_food_record_in_db(self, wx_id, nickname, total_calories, content, img_path=None):
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
                logger.error(f"[HealthService] 创建用户{wx_id}失败")
                return None

        food_items = self._extract_food_items(content)
        if not food_items:
            logger.error(f"[HealthService] 未提取到食物记录，原文为[{content}]")
            return None

        # 保存食物记录到 food_record 表
        food_record_id = self.food_record_dao.insert_record(user_id=user.user_id, img_path=img_path, total_calories=total_calories)
        logger.info(f"保存食物记录到 food_record 表，food_record_id: {food_record_id}")

        # 提取食物信息并保存到 food 表
        calories = 0.0
        for food_item in food_items:
            self.food_dao.insert_food(food_item['food_name'], food_item['calories'], food_record_id)
            calories += food_item['calories']
        logger.info(f"保存{len(food_items)}个食物记录到 food 表")

        if total_calories == 0.0:
            self.food_record_dao.update_total_calories(food_record_id, calories)

        return food_record_id

    def _extract_food_items(self, content):
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
        food_pattern = r'([^：:\n]+)[：:](?:约)?\s*(\d+(\.\d+)?)\s*千卡'
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
                return f"创建用户{wx_id}失败"

        # 获取当天的饮食记录
        food_records = self.food_record_dao.list_records_by_user(user.user_id,
                                                                 date_str=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        report = ""
        total_calories = 0
        if not food_records:
            # 处理空记录的情况
            report += "今日暂无饮食记录\n"
        else:
            report += "今日饮食记录：\n"
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
                report += f"总热量：{record_total}千卡\n"  # 空行隔开每条记录
                report += f"图片：{record.img_path}\n\n"  # 空行隔开每条记录

        # 获取用户今日运动消耗的热量
        # 获取当天所有运动记录
        exercise_records = self.exercise_dao.list_exercises_by_user(user.user_id, date_str=datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"))
        total_burned_calories = 0  # 今日运动总消耗的热量
        if not exercise_records:
            # 处理空记录的情况
            report += "今日暂无运动记录\n"
        else:

            report += "今日运动记录：\n"
            for record in exercise_records:
                report += f"- {record.exercise_name}: {record.burned_calories}千卡\n"
                total_burned_calories += record.burned_calories
            report += f"总运动消耗：{total_burned_calories}千卡\n"

        # 获取用户的基础代谢率(BMR)和每日建议摄入热量
        bmr = self._calculate_bmr(user)
        recommended_calories = bmr * self._activity_level_factor(user.activity_level)

        remaining_calories = recommended_calories - total_calories + total_burned_calories

        report += f"\n今日总摄入：{total_calories:.1f}千卡\n"
        if recommended_calories != 0:
            report += f"每日建议摄入：{recommended_calories:.1f}千卡\n"
            report += f"今日还可以摄入：{remaining_calories:.1f}千卡\n"
        else:
            report += f"提示：完善个人信息可获取推荐摄入热量"
        return report

    def _calculate_bmr(self, user):
        """
        使用Mifflin-St Jeor公式计算用户的基础代谢率（BMR）
        如果用户的个人信息不完善，因子为0，系统不会计算用户的每日推荐摄入热量
        """
        if not user.age or not user.gender or not user.height or not user.weight or not user.activity_level:
            return 0.0
        if user.gender == 1:  # 男性
            return (10 * user.weight) + (6.25 * user.height) - (5 * user.age) + 5
        elif user.gender == 2:  # 女性
            return (10 * user.weight) + (6.25 * user.height) - (5 * user.age) - 161
        else:  # 未知性别
            return 0.0

    def _activity_level_factor(self, activity_level):
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

    # 新版
    def save_exercise_record(self, wx_id, nickname, content):
        """
        根据用户输入的运动记录字符串，例如：
         "记录运动 跑步 消耗150千卡"
        来识别出 exercise_name 和 burned_calories，然后保存到数据库。
        """
        # 通过正则表达式匹配 "记录运动 XXX 消耗YYY千卡"
        # 假设用户输入大致固定格式，如：
        #   记录运动 跑步 消耗150千卡
        #   记录运动 游泳 消耗300千卡
        # 如有更多变种格式，需要修改或添加匹配模式。
        pattern = r"记录运动\s+(\S+)\s+消耗(\d+)\s*千卡"
        match = re.search(pattern, content)
        if not match:
            logger.error(f"[HealthService] save_exercise_record: 无法从'{content}'中识别到运动信息")
            return None

        exercise_name = match.group(1)
        burned_calories_str = match.group(2)
        if not burned_calories_str or not burned_calories_str.isdigit():
            return None
        burned_calories = float(burned_calories_str)

        # 获取/创建用户
        user = self.user_dao.get_user_by_wx_id(wx_id)
        if not user:
            # 如果用户不存在，则简单调用 save_user_info 创建用户信息（仅含wx_id, nickname）
            # 具体逻辑可依业务需求决定
            created = self.save_user_info(wx_id, nickname, content=None)
            if created:
                user = self.user_dao.get_user_by_wx_id(wx_id)
            else:
                logger.error(f"[HealthService] 创建用户失败 wx_id={wx_id}")
                return None

        # 保存运动记录到 exercise_record 表
        exercise_id = self.exercise_dao.insert_exercise(exercise_name, user.user_id, burned_calories)
        logger.info(f"[HealthService] 已保存运动记录: {exercise_name}, 消耗{burned_calories}千卡")
        return exercise_id

    # 旧版
    # def save_exercise_record(self, wx_id, nickname, exercise_name, burned_calories):
    #     """
    #     根据用户输入的运动记录，保存到运动记录表中。
    #     """
    #     user = self.user_dao.get_user_by_wx_id(wx_id)
    #     if not user:
    #         res = self.save_user_info(wx_id=wx_id, nickname=nickname)
    #         if res:
    #             user = self.user_dao.get_user_by_wx_id(wx_id)
    #         else:
    #             return None
    #
    #     # 保存运动记录到 exercise_record 表
    #     exercise_id = self.exercise_dao.insert_exercise(exercise_name, user.user_id, burned_calories)
    #     return exercise_id

    # 旧版
    # def save_user_info(self, wx_id, nickname, height=None, weight=None, gender=0, age=None, activity_level=None):
    #     """
    #     根据用户输入的个人信息保存到用户信息表。
    #     """
    #     user = self.user_dao.get_user_by_wx_id(wx_id)
    #     if not user:
    #         self.user_dao.create_user(wx_id=wx_id, nickname=nickname, gender=gender, height=height, weight=weight,
    #                                   age=age, activity_level=activity_level)
    #         logger.info(f"[HealthService] 保存用户{wx_id}信息，昵称{nickname}")
    #         return True
    #
    #     # 更新用户个人信息
    #     self.user_dao.update_user_info(wx_id=wx_id, height=height, weight=weight, age=age,
    #                                    activity_level=activity_level, gender=gender, nickname=nickname)
    #     return True

    def save_user_info(self, wx_id, nickname, content=None):
        """
        根据用户输入的个人信息字符串，格式必须为：
          "设置个人信息 身高：170cm，体重：66kg，性别：男，年龄：21岁，活动水平：轻度活动"
        来识别出 height, weight, gender, age, activity_level 并保存到 user 表中。

        若未检测到某些字段，可根据业务需求决定默认值。
        其中 gender: 男 -> 1, 女 -> 2, 未知->0

        活动水平有 "久坐不动","轻度活动","中度活动","高度活动","极度活动"五个
        """

        # 如果content为空，仅创建一个空的用户信息 (只含 wx_id, nickname)
        if not content:
            logger.warning("[HealthService] save_user_info: 未提供content，仅创建空的用户信息。")
            self._create_or_update_user_base(wx_id, nickname)
            return True

        # 1. 使用正则分别提取身高、体重、性别、年龄、活动水平
        #   假设用户输入格式相对固定，如 "身高：170cm，体重：66kg，性别：男，年龄：21岁，活动水平：轻度活动"
        height_pattern = r'身高[:：]\s*(\d+)\s*cm'
        weight_pattern = r'体重[:：]\s*(\d+)\s*kg'
        gender_pattern = r'性别[:：]\s*(男|女)'
        age_pattern = r'年龄[:：]\s*(\d+)\s*岁'
        activity_pattern = r'活动水平[:：]\s*([\u4E00-\u9FA5]+)'

        height = None
        weight = None
        gender = 0
        age = None
        activity_level = None

        # (1) 身高
        match_height = re.search(height_pattern, content)
        if match_height:
            height = float(match_height.group(1))

        # (2) 体重
        match_weight = re.search(weight_pattern, content)
        if match_weight:
            weight = float(match_weight.group(1))

        # (3) 性别
        match_gender = re.search(gender_pattern, content)
        if match_gender:
            gender_str = match_gender.group(1)
            if gender_str == '男':
                gender = 1
            elif gender_str == '女':
                gender = 2
            else:
                gender = 0

        # (4) 年龄
        match_age = re.search(age_pattern, content)
        if match_age:
            age = int(match_age.group(1))

        # (5) 活动水平
        match_activity = re.search(activity_pattern, content)
        if match_activity:
            activity_level = match_activity.group(1).strip()  # 例如 "轻度活动"

        logger.info(f"[HealthService] save_user_info 解析结果: height={height}, weight={weight}, "
                    f"gender={gender}, age={age}, activity_level={activity_level}")

        # 识别检测
        if not height or not weight or not gender or not age or not activity_level:
            logger.error(f"[HealthService] save_user_info: 无法从'{content}'中识别全用户的个人信息")
            return False
        activity_levels = [
            "久坐不动",
            "轻度活动",
            "中度活动",
            "高度活动",
            "极度活动"
        ]
        if activity_level not in activity_levels:
            return False

        # 2. 获取数据库中的用户
        user = self.user_dao.get_user_by_wx_id(wx_id)
        if not user:
            # 不存在则新建
            self.user_dao.create_user(
                wx_id=wx_id,
                nickname=nickname,
                gender=gender,
                height=height,
                weight=weight,
                age=age,
                activity_level=activity_level
            )
            logger.info(f"[HealthService] 创建用户{wx_id}成功: {nickname}")
            return True
        else:
            # 已存在则更新
            updated = self.user_dao.update_user_info(
                wx_id=wx_id,
                nickname=nickname,
                gender=gender,
                height=height,
                weight=weight,
                age=age,
                activity_level=activity_level
            )
            logger.info(f"[HealthService] 更新用户{wx_id}成功: updated={updated}")
            return updated

    def _create_or_update_user_base(self, wx_id, nickname):
        """
        如果用户不存在则创建一个仅含wx_id和nickname的用户信息，
        若已存在则只更新nickname。
        """
        user = self.user_dao.get_user_by_wx_id(wx_id)
        if not user:
            self.user_dao.create_user(wx_id=wx_id, nickname=nickname)
            logger.info(f"[HealthService] 创建只含基础信息的用户: wx_id={wx_id}, nickname={nickname}")
        else:
            # 简单更新昵称（如果需要）
            self.user_dao.update_user_info(wx_id=wx_id, nickname=nickname)

    def get_user_info(self, wx_id):
        return self.user_dao.get_user_by_wx_id(wx_id)

    def get_exercise_info(self, exercise_id):
        return self.exercise_dao.get_exercise_by_id(exercise_id)
