import re
import unittest

from dao import *
from HealthService import HealthService


class MyTestCase(unittest.TestCase):
    def test_UserDAO(self):
        userDAO = UserDAO()
        # res = userDAO.create_user("333", "Jack", 2, 180, 60, 21, "轻度活动")
        user = userDAO.get_user_by_wx_id("333")
        print(user)
        self.assertEqual(not user, False, "结果应该是 False")  # add assertion here

    def test_ExerciseDAO(self):
        exerciseDAO = ExerciseDAO()
        # exerciseDAO.insert_exercise("羽毛球", 2, 650)
        res = exerciseDAO.list_exercises_by_user(2, date_str=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print(res)


    def test_re(self):
        content = """肠粉:约50千卡
                    鸭蛋：约60千卡
                    总热量：约110千卡"""
        match = re.search(r'总热量：?约?(\d+(\.\d+)?)千卡', content)
        if match:
            print(float(match.group(1)))
            print(match.group(0))

        food_items = []
        food_pattern = r'([^：:\n]+)[：:](?:约)?(\d+(\.\d+)?)千卡'
        matches = re.finditer(food_pattern, content)
        for match in matches:
            food_name = match.group(1).strip()
            calories = float(match.group(2))
            if food_name == "总热量":
                continue
            food_items.append({'food_name': food_name, 'calories': calories})
        print(food_items)


    def test_HealthService(self):
        health_service = HealthService()
        # health_service.save_user_info(wx_id="000", nickname="Horse", content="设置个人信息 身高：170cm，体重：77kg，性别：男，年龄：21岁，活动水平：轻度活动")  # 测试保存用户信息 content="设置个人信息 身高：170cm，体重：77kg，性别：男，年龄：21岁，活动水平：轻度活动"
        # userDAO = UserDAO()
        # print(health_service._calculate_bmr(userDAO.get_user_by_wx_id(wx_id="222")))  # 测试计算bmr
        # health_service.save_exercise_record("999", "Adele", "记录运动 游泳 消耗150千卡")  # 记录运动 游泳 消耗150千卡

        content = """玉米：约90千卡
                    鸡蛋：约155千卡
                    紫薯：约86千卡
                    白粥：约46千卡
                    包子：约250千卡（取中间值）
                    馒头：约221千卡
                    花卷：约311千卡
                    火腿肠：约312千卡
                    总热量：约1557千卡
                    
                    饮食建议：
                    1. **均衡饮食**：确保每日摄入足够的蛋白质、碳水化合物、脂肪以及维生素和矿物质。
                    2. **控制分量**：虽然您的BMI在正常范围内，但保持适当的食量有助于维持健康体重。
                    3. **增加蔬菜摄入**：可以考虑在早餐中加入一些蔬菜，如凉拌黄瓜或西红柿，以增加纤维和营养素的摄入。
                    4. **选择健康烹饪方式**：尽量采用蒸、煮、炖等低油低盐的烹饪方法，减少油脂和钠的摄入。
                    5. **适量运动**：保持每周至少150分钟的中等强度有氧运动，有助于提高心肺功能和整体健康水平。
                    
                    请注意，这些建议是基于一般性指导原则，具体饮食计划应根据个人健康状况和营养需求进行调整。如有需要，建议咨询专业营养师或医生的意见。"""
        # content = "肠粉:约50千卡                    鸭蛋：约60千卡                    总热量：约110千卡"
        # health_service.save_food_record("888", "Amy", content)
        # res = health_service.get_user_today_food_report("222", "222")
        # print(res)
        res = health_service.get_exercise_info(exercise_id=1)
        print(res)

    def testTime(self):
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

if __name__ == '__main__':
    unittest.main()
