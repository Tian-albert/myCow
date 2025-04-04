# encoding:utf-8
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Text,VARCHAR, JSON, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from sqlalchemy.exc import PendingRollbackError#
import json
from sqlalchemy import update
from common.log import logger
import logging

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(VARCHAR(30), unique=True, nullable=False)
    password = Column(VARCHAR(200), nullable=False)
    owner_wxid = Column(VARCHAR(150),  unique=True, nullable=False)
    wechat_account = relationship("WeChatAccount", back_populates="user")

class WeChatAccount(Base):
    __tablename__ = 'wechat_accounts'
    id = Column(Integer, primary_key=True)
    account_id = Column(VARCHAR(30), unique=True, nullable=False)
    is_online = Column(Boolean, default=False)
    wx_id = Column(VARCHAR(30))
    end_time = Column(DateTime)
    nickname = Column(VARCHAR(50))
    province = Column(VARCHAR(45))
    city = Column(VARCHAR(45))
    token = Column(VARCHAR(300))
    auth = Column(VARCHAR(300))
    account_type = Column(Integer,default=1)
    auth_account=Column(VARCHAR(300))
    auth_password = Column(VARCHAR(300))
    callback_url = Column(VARCHAR(150))
    owner_wxid = Column(VARCHAR(150), ForeignKey('users.owner_wxid'))
    # 新增字段
    whitelisted_group_ids = Column(JSON)  # 使用JSON类型存储列表
    max_group = Column(Integer)
    push_needed = Column(Boolean, default=True)
    
    groups = relationship("WeChatGroup", back_populates="account")
    user = relationship("User", back_populates="wechat_account")

    @classmethod
    def update_end_time_sql(cls, session, account_id, new_end_time):
        """使用 SQL 语句更新 end_time 字段"""
        stmt = update(cls).where(cls.id == account_id).values(end_time=new_end_time)
        session.execute(stmt)
        session.commit()  # 提交更改
    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'is_online': self.is_online,
            'wx_id': self.wx_id,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'nickname': self.nickname,
            'province': self.province,
            'city': self.city,
            'token': self.token,
            'auth': self.auth,
            'auth_account': self.auth_account,
            'auth_password': self.auth_password,
            'callback_url': self.callback_url,
            'owner_wxid': self.owner_wxid,
            'whitelisted_group_ids': self.whitelisted_group_ids,
            'max_group': self.max_group,
            'push_needed': self.push_needed
        }

class WeChatGroup(Base):
    __tablename__ = 'wechat_groups'
    id = Column(Integer, primary_key=True)
    chatRoomId = Column(VARCHAR(150), unique=True, nullable=False)
    name = Column(VARCHAR(150), nullable=False)
    members_count = Column(Integer, default=0)
    bigHeadImgUrl = Column(VARCHAR(300))  # 群组图标链接
    account_id = Column(Integer, ForeignKey('wechat_accounts.id'))
    account = relationship("WeChatAccount", back_populates="groups")
    chatRoomOwner = Column(VARCHAR(150))
    update_time= Column(DateTime,default=datetime.now())

    # 定义与 WeChatGroupMember 的一对多关系
    '''
    relationship 的基本概念
    relationship 是一种在两个数据库表之间建立连接的方式，用于映射一对一、一对多或多对多的关系。
    它可以使我们通过ORM方式轻松地访问相关联的记录，而不必手动编写复杂的SQL查询。
    back_populates：
    用于双向关系定义，指明另一个模型中对应关系的属性名。
    例如，在 WeChatGroup 和 WeChatGroupMember 之间，可以这样使用：在 WeChatGroup 中定义 
    members = relationship("WeChatGroupMember", back_populates="group")，
    同时在 WeChatGroupMember 中定义 group = relationship("WeChatGroup", back_populates="members")。
    解释
    在 WeChatGroup 类中，members 是一个关系属性，表示一个 WeChatGroup 可以有多个 WeChatGroupMember。
    back_populates 用于在 WeChatGroupMember 中定义反向引用，这样你可以通过 group 属性轻松访问 WeChatGroup。
    cascade="all, delete-orphan" 确保当删除一个 WeChatGroup 时，其所有关联的 WeChatGroupMember 实例也会被删除。
    在 WeChatGroupMember 中，group 是一个关系属性，表示一个 WeChatGroupMember 只属于一个 WeChatGroup。
    '''
    members = relationship("WeChatGroupMember", back_populates="group", cascade="all, delete-orphan")

class WeChatGroupMember(Base):
    __tablename__ = 'wechat_group_members'
    id = Column(Integer, primary_key=True)
    chatRoomId = Column(VARCHAR(150), ForeignKey('wechat_groups.chatRoomId'))
    userName = Column(VARCHAR(150), nullable=False)
    nickName = Column(VARCHAR(150))
    displayName = Column(VARCHAR(150))
    inviterUserName = Column(VARCHAR(150))
    isAdmin = Column(Boolean, default=False)
    sex = Column(VARCHAR(10))  # '0': 未知, '1': 男, '2': 女
    bigHeadImgUrl = Column(VARCHAR(300))  # 头像链接

    # 定义与 WeChatGroup 的多对一关系
    group = relationship("WeChatGroup", back_populates="members")

class AutoReply(Base):
    __tablename__ = 'auto_replies'
    id = Column(Integer, primary_key=True)
    keyword = Column(VARCHAR(150), nullable=False)
    reply_type = Column(VARCHAR(10), nullable=False)  # 'text' or 'image'
    content = Column(Text, nullable=False)


class MediaMessage(Base):
    __tablename__ = 'media_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    msg_type = Column(VARCHAR(20), nullable=False)
    xml_content = Column(Text, nullable=False)
    md5 = Column(VARCHAR(32), nullable=True)
    file_name = Column(VARCHAR(100), nullable=True)
    uploader_nickname = Column(VARCHAR(100), nullable=False)
    received_date = Column(DateTime, default=datetime.utcnow)

    # Convert the object to a dictionary
    def to_dict(self):
        return {
            'id': self.id,
            'msg_type': self.msg_type,
            'xml_content': self.xml_content,
            'md5': self.md5,
            'file_name': self.file_name,
            'uploader_nickname': self.uploader_nickname,
            'received_date': self.received_date
        }


'''
CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                task_description TEXT NOT NULL,
                schedule_type TEXT NOT NULL,
                hour INTEGER,
                minute INTEGER,
                weekday INTEGER,
                interval_value INTEGER,
                interval_unit TEXT
                '''
class ScheduledTasks(Base):
    __tablename__ = 'scheduled_tasks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(VARCHAR(50), nullable=False)
    task_description = Column(VARCHAR(100), nullable=False)
    schedule_type = Column(VARCHAR(50), nullable=True)
    hour = Column(Integer, nullable=True)
    minute = Column(Integer, nullable=True)
    weekday = Column(Integer, nullable=True)
    interval_value = Column(Integer, nullable=True)
    interval_unit = Column(VARCHAR(50), nullable=True)
    status= Column(Integer, nullable=True)
    account_id = Column(Integer, ForeignKey('wechat_accounts.id'))

    # Convert the object to a dictionary
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'task_description': self.task_description,
            'schedule_type': self.schedule_type,
            'hour': self.hour,
            'minute': self.minute,
            'weekday': self.weekday,
            'interval_value': self.interval_value,
            'interval_unit': self.interval_unit,
            'status': self.status,
        }

class EmojiMessage(Base):
    __tablename__ = 'emoji_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    md5 = Column(VARCHAR(32), nullable=False)
    len = Column(VARCHAR(10))
    file_path = Column(VARCHAR(255), nullable=False)
    meaning = Column(Text)
    uploader_nickname = Column(VARCHAR(100))
    chat_id = Column(VARCHAR(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'md5': self.md5,
            'len': self.len,
            'file_path': self.file_path,
            'reply_content': self.meaning,
            'uploader_nickname': self.uploader_nickname,
            'chat_id': self.chat_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class ImageMessage(Base):
    __tablename__ = 'image_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(VARCHAR(255), nullable=False)
    file_path = Column(VARCHAR(255), nullable=False)
    meaning = Column(Text)
    uploader_nickname = Column(VARCHAR(100))
    chat_id = Column(VARCHAR(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'file_name': self.file_name,
            'file_path': self.file_path,
            'reply_content': self.meaning,
            'uploader_nickname': self.uploader_nickname,
            'chat_id': self.chat_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class VideoMessage(Base):
    __tablename__ = 'video_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(VARCHAR(255), nullable=False)
    file_path = Column(VARCHAR(255), nullable=False)
    meaning = Column(Text)
    uploader_nickname = Column(VARCHAR(100))
    chat_id = Column(VARCHAR(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'file_name': self.file_name,
            'file_path': self.file_path,
            'reply_content': self.meaning,
            'uploader_nickname': self.uploader_nickname,
            'chat_id': self.chat_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

engine = create_engine('sqlite:///app.db')
Base.metadata.create_all(engine)

Session_sql = sessionmaker(bind=engine)
db_session = Session_sql()


def create_tables():
    """创建所有表"""
    try:
        inspector = inspect(engine)
        
        # 创建表情消息表
        if 'emoji_messages' not in inspector.get_table_names():
            EmojiMessage.__table__.create(engine)
            logger.info("Created table: emoji_messages")

        # 创建图片消息表
        if 'image_messages' not in inspector.get_table_names():
            ImageMessage.__table__.create(engine)
            logger.info("Created table: image_messages")

    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        raise e

# 在数据库连接初始化时创建表
create_tables()

Session_sql = sessionmaker(bind=engine)
db_session = Session_sql()
def insert_wechat_data(json_data, account_id):
    group_data_list = []
    member_data_list = []

    for group_data in json_data.values():
        # 检查是否包含有效的群组ID
        if "chatRoomId" not in group_data:
            continue

        # 尝试查询是否已存在群组信息
        group = db_session.query(WeChatGroup).filter_by(chatRoomId=group_data['chatRoomId']).first()
        if group:
            # 更新群组信息
            group.name = group_data['nickName']
            group.members_count = int(group_data['memberCount'])
            group.bigHeadImgUrl = group_data['bigHeadImgUrl']
            group.chatRoomOwner = group_data['chatRoomOwner']
            group.account_id = account_id

            # 删除旧的群成员
            db_session.query(WeChatGroupMember).filter_by(chatRoomId=group.chatRoomId).delete()
        else:
            # 如果群组不存在，创建新的群组对象并添加到会话中
            group = WeChatGroup(
                chatRoomId=group_data['chatRoomId'],
                name=group_data['nickName'],
                members_count=int(group_data['memberCount']),
                bigHeadImgUrl=group_data['bigHeadImgUrl'],
                chatRoomOwner=group_data['chatRoomOwner'],
                account_id=account_id
            )
            db_session.add(group)
            db_session.flush()  # 确保 group.chatRoomId 可用于成员记录

        # 准备成员数据
        for member_data in group_data['chatRoomMembers']:
            member_data_list.append({
                'chatRoomId': group.chatRoomId,
                'userName': member_data['userName'],
                'nickName': member_data['nickName'],
                'displayName': member_data.get('displayName', ''),
                'inviterUserName': member_data.get('inviterUserName', ''),
                'isAdmin': member_data['isAdmin'],
                'sex': member_data['sex'],
                'bigHeadImgUrl': member_data['bigHeadImgUrl']
            })

    # 使用 bulk_insert_mappings 批量插入成员数据
    if member_data_list:
        db_session.bulk_insert_mappings(WeChatGroupMember, member_data_list)

    # 提交事务并关闭会话
    try:
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        if isinstance(e, PendingRollbackError):
            print("检测到PendingRollbackError，事务已回滚。请检查并处理导致事务失败的原因。")
        else:
            raise
    finally:
        db_session.close()


def insert_wechat_data11(json_data, id):

    for group_data in json_data.values():
        # Create or update the WeChat group
        if "chatRoomId" not in group_data:
            continue
        group = db_session.query(WeChatGroup).filter_by(chatRoomId=group_data['chatRoomId']).first()
        if not group:
            group = WeChatGroup(chatRoomId=group_data['chatRoomId'])
            db_session.add(group)

        # Update group information
        group.name = group_data['nickName']
        group.members_count = int(group_data['memberCount'])
        group.bigHeadImgUrl = group_data['bigHeadImgUrl']  # 群组图标链接
        group.chatRoomOwner = group_data['chatRoomOwner']  # 群主
        group.chatRoomOwner = group_data['chatRoomOwner']  # 群主
        # Delete existing members if group is updated
        if group.id:
            db_session.query(WeChatGroupMember).filter_by(chatRoomId=group.chatRoomId).delete()

        #Add group members
        for member_data in group_data['chatRoomMembers']:
            member = WeChatGroupMember(
                chatRoomId=group.chatRoomId,
                userName=member_data['userName'],
                nickName=member_data['nickName'],
                displayName=member_data.get('displayName', ''),
                inviterUserName=member_data.get('inviterUserName', ''),
                isAdmin=member_data['isAdmin'],
                sex=member_data['sex'],
                bigHeadImgUrl=member_data['bigHeadImgUrl']
            )
            db_session.add(member)

        group.account_id = id# Assuming user has one account for simplicity

    # Commit changes and close the db_session
    try:
        # 尝试执行数据库操作
        db_session.commit()  # 提交事务
    except Exception as e:
        db_session.rollback()  # 如果发生异常，回滚事务
        if isinstance(e, PendingRollbackError):
            print("检测到PendingRollbackError，事务已回滚。请检查并处理导致事务失败的原因。")
        else:
            raise  # 如果不是PendingRollbackError，再次抛出异常以便上层处理
    db_session.close()


# # Drop all tables and recreate them
# Base.metadata.drop_all(engine)
# Base.metadata.create_all(engine)
# Call the function with the path to your JSON file



 #示例用法
def update_account_end_time_sql(account_id, new_end_time):
    session = Session_sql()  # 创建数据库会话
    try:
        WeChatAccount.update_end_time_sql(session, account_id, new_end_time)
        print(f"Updated end_time for account ID {account_id} to {new_end_time}")
    except Exception as e:
        session.rollback()  # 回滚事务
        print(f"Error updating end_time: {e}")
    finally:
        session.close()  # 关闭会话

now =   datetime.today()
update_account_end_time_sql(1, now)

def init_db():
    """
    初始化数据库，创建所有表
    """
    try:
        # 创建所有定义的表
        Base.metadata.create_all(engine)
        logging.info("Database tables created successfully")
    except Exception as e:
        logging.error(f"Error creating database tables: {str(e)}")
        raise

# 在模块导入时自动创建表
try:
    init_db()
except Exception as e:
    logging.error(f"Failed to initialize database: {str(e)}")