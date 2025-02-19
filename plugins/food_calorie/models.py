from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserInfo(Base):
    """用户信息表"""
    __tablename__ = 'user_info'
    
    id = Column(Integer, primary_key=True)
    nickname = Column(String(100))  # 用户昵称
    user_id = Column(String(100))   # 微信user_id
    height = Column(Float)          # 身高(cm)
    weight = Column(Float)          # 体重(kg) 
    gender = Column(String(10), default='male')  # 性别
    created_at = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<UserInfo(nickname='{self.nickname}', height={self.height}, weight={self.weight})>"

class FoodRecord(Base):
    """食物记录表"""
    __tablename__ = 'food_records'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100))      # 关联用户ID
    food_name = Column(String(100))    # 食物名称
    weight = Column(Float)             # 食物重量(g)
    calories = Column(Float)           # 每100g卡路里
    total_calories = Column(Float)     # 总卡路里
    is_confirmed = Column(Integer, default=0)  # 是否经过用户确认
    confirmed_calories = Column(Float)  # 用户确认的卡路里
    record_time = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<FoodRecord(food_name='{self.food_name}', calories={self.calories}, total_calories={self.total_calories})>" 