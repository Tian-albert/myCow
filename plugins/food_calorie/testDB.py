from db_manager import DBManager
from dao import *
from datetime import datetime





DBManager = DBManager()


"""测试user_dao"""
userDAO = UserDAO(DBManager)
# userDAO.create_user(wx_id="222", age=21, nickname="222", gender=2, height=170, weight=66)  # 添加

user = userDAO.get_user_by_wx_id("222")  # 查询
print(user)

# userDAO.update_user_info("111", nickname="111", height=172, weight=60)  # 更新

# userDAO.delete_user_by_wx_id("111")  # 删除


"""测试food_record_dao"""
foodRecordDAO = FoodRecordDAO(DBManager)

# foodRecordDAO.insert_record(2, 1600)  # 添加记录

# current_date = datetime.now().date()  # 返回一个 date 对象（只包含年月日）
# print("当前日期为:", current_date)
record = foodRecordDAO.list_records_by_user(2, "2025-02-19")
print("饮食记录：", record)


"""测试food_dao"""
food_dao = FoodDAO(db_manager=DBManager)

# food_dao.insert_food("烤乳猪", 1500, 2)
# food = food_dao.get_food_by_id(4)
# print(food)
foods = food_dao.list_foods_by_record(1)
print(foods)
# food_dao.update_food_calories(4, 15)
# food_dao.delete_food(4)


"""测试exercise_dao"""
exercise_dao = ExerciseDAO(db_manager=DBManager)
# exercise_dao.insert_exercise("跑步", 2, 600)
# exercise = exercise_dao.get_exercise_by_id(2)
# print(exercise)
# exercise_dao.update_burned_calories(2, 800)
exercises = exercise_dao.list_exercises_by_user(2)
print(exercises)
# exercise_dao.delete_exercise(2)


# 2025/2/20 测试dao和model 结果正常 @Albert







