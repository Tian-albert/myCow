import json
import os
import re
import unittest
import uuid
from datetime import datetime


# from dao import *
# from .HealthService import HealthService
from qcloud_cos import CosConfig, CosS3Client


class MyTestCase(unittest.TestCase):
    # def test_UserDAO(self):
    #     userDAO = UserDAO()
    #     # res = userDAO.create_user("333", "Jack", 2, 180, 60, 21, "轻度活动")
    #     user = userDAO.get_user_by_wx_id("333")
    #     print(user)
    #     self.assertEqual(not user, False, "结果应该是 False")  # add assertion here
    #
    # def test_ExerciseDAO(self):
    #     exerciseDAO = ExerciseDAO()
    #     # exerciseDAO.insert_exercise("羽毛球", 2, 650)
    #     res = exerciseDAO.list_exercises_by_user(2, date_str=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    #     print(res)
    #
    #
    # def test_re(self):
    #     content = """肠粉:约50千卡
    #                 鸭蛋：约60千卡
    #                 总热量：约110千卡"""
    #     match = re.search(r'总热量：?约?(\d+(\.\d+)?)千卡', content)
    #     if match:
    #         print(float(match.group(1)))
    #         print(match.group(0))
    #
    #     food_items = []
    #     food_pattern = r'([^：:\n]+)[：:](?:约)?(\d+(\.\d+)?)千卡'
    #     matches = re.finditer(food_pattern, content)
    #     for match in matches:
    #         food_name = match.group(1).strip()
    #         calories = float(match.group(2))
    #         if food_name == "总热量":
    #             continue
    #         food_items.append({'food_name': food_name, 'calories': calories})
    #     print(food_items)
    #
    #
    # def test_HealthService(self):
    #     health_service = HealthService()
    #     # health_service.save_user_info(wx_id="000", nickname="Horse", content="设置个人信息 身高：170cm，体重：77kg，性别：男，年龄：21岁，活动水平：轻度活动")  # 测试保存用户信息 content="设置个人信息 身高：170cm，体重：77kg，性别：男，年龄：21岁，活动水平：轻度活动"
    #     # userDAO = UserDAO()
    #     # print(health_service._calculate_bmr(userDAO.get_user_by_wx_id(wx_id="222")))  # 测试计算bmr
    #     # health_service.save_exercise_record("999", "Adele", "记录运动 游泳 消耗150千卡")  # 记录运动 游泳 消耗150千卡
    #
    #     content = """玉米：约90千卡
    #                 鸡蛋：约155千卡
    #                 紫薯：约86千卡
    #                 白粥：约46千卡
    #                 包子：约250千卡（取中间值）
    #                 馒头：约221千卡
    #                 花卷：约311千卡
    #                 火腿肠：约312千卡
    #                 总热量：约1557千卡
    #
    #                 饮食建议：
    #                 1. **均衡饮食**：确保每日摄入足够的蛋白质、碳水化合物、脂肪以及维生素和矿物质。
    #                 2. **控制分量**：虽然您的BMI在正常范围内，但保持适当的食量有助于维持健康体重。
    #                 3. **增加蔬菜摄入**：可以考虑在早餐中加入一些蔬菜，如凉拌黄瓜或西红柿，以增加纤维和营养素的摄入。
    #                 4. **选择健康烹饪方式**：尽量采用蒸、煮、炖等低油低盐的烹饪方法，减少油脂和钠的摄入。
    #                 5. **适量运动**：保持每周至少150分钟的中等强度有氧运动，有助于提高心肺功能和整体健康水平。
    #
    #                 请注意，这些建议是基于一般性指导原则，具体饮食计划应根据个人健康状况和营养需求进行调整。如有需要，建议咨询专业营养师或医生的意见。"""
    #     # content = "肠粉:约50千卡                    鸭蛋：约60千卡                    总热量：约110千卡"
    #     # health_service.save_food_record("888", "Amy", content)
    #     # res = health_service.get_user_today_food_report("222", "222")
    #     # print(res)
    #     res = health_service.get_exercise_info(exercise_id=1)
    #     print(res)

    def test_Time(self):
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    #
    def test_Cos(self):
        curdir = os.path.dirname(__file__)
        config_path = os.path.join(curdir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)


        # 初始化COS配置
        self.cos_config = self.config.get("cos", {})

        """初始化腾讯云 COS 客户端"""

        config = CosConfig(
            Region=self.cos_config.get("region"),
            SecretId=self.cos_config.get("secret_id"),
            SecretKey=self.cos_config.get("secret_key")
        )
        self.cos_client = CosS3Client(config)

        if not self.cos_client:

            return None

        file_path = r"E:\wangyuan\毕业设计\cow\pic\picture\untitled-1.bash"
        # 生成唯一的文件名
        file_ext = os.path.splitext(file_path)[1]
        key = f"picture/{str(uuid.uuid4())}{file_ext}"

        # 上传文件
        self.cos_client.upload_file(
            Bucket=self.cos_config.get("bucket"),
            LocalFilePath=file_path,
            Key=key
        )

        # 生成预签名URL
        url = self.cos_client.get_presigned_url(
            Method='GET',
            Bucket=self.cos_config.get("bucket"),
            Key=key,
            Expired=self.cos_config.get("url_expire", 3600)
        )

        print(url)


    def test_Path(self):
        # print(os.path.dirname(__file__))
        # print(os.path.join(os.path.dirname(__file__), "pic"))

        directory = "pic/picture/untitled-1.bash"  # 目录名称（可以是相对路径）
        absolute_path = os.path.abspath(directory)

        print(f"'{directory}' 的绝对路径是: {absolute_path}")


if __name__ == '__main__':
    unittest.main()
