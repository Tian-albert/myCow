from common.expired_dict import ExpiredDict
import time
import logging

# 用于dify_bot的图片上传功能，使用session_id作为key
USER_IMAGE_CACHE = ExpiredDict(expires_in_seconds=60*60*8)  # 8小时过期

# 用于图片识别功能，使用uuid作为key
RECOGNITION_CACHE = ExpiredDict(expires_in_seconds=60*60*8)  # 8小时过期

logger = logging.getLogger(__name__)

def save_msg_to_cache(msg_id, content, msg_type, chat_id, session_id=None, msg=None):
    """
    保存消息到缓存
    msg_id: 消息ID (uuid)
    content: 消息内容
    msg_type: 消息类型 (image/emoji/file/video)
    chat_id: 聊天ID
    session_id: 会话ID (可选)
    msg: 原始消息对象 (可选，向后兼容)
    """
    if msg_type == "video":
        logger.info(f"[Memory] Saving video message: id={msg_id}, chat_id={chat_id}")
        
    # 保存到基于uuid的缓存中
    RECOGNITION_CACHE[msg_id] = {
        "content": content,
        "type": msg_type,
        "chat_id": chat_id,
        "msg": msg,
        "timestamp": time.time()
    }
    
    # 如果提供了session_id，同时保存到基于session的缓存中
    if session_id:
        USER_IMAGE_CACHE[session_id] = {
            "content": content,
            "msg": msg,
            "path": None,  # 保持与原有结构兼容
            "type": msg_type,
            "chat_id": chat_id,
            "timestamp": time.time()
        }
    
    # 更新最近消息缓存（也使用RECOGNITION_CACHE）
    RECOGNITION_CACHE[f"recent_{chat_id}"] = {
        "content": content,
        "type": msg_type,
        "chat_id": chat_id,
        "msg": msg,
        "timestamp": time.time()
    }
    
    logger.debug(f"[Memory] Message saved to cache: type={msg_type}, id={msg_id}")

def get_msg_from_cache(msg_id):
    """获取指定uuid的消息"""
    return RECOGNITION_CACHE.get(msg_id)

def get_recent_msg_from_cache(chat_id):
    """获取指定chat_id最近的一条消息"""
    latest_msg = None
    latest_time = 0
    
    # 先检查是否有专门保存的最近消息
    recent_key = f"recent_{chat_id}"
    if recent_key in RECOGNITION_CACHE:
        return RECOGNITION_CACHE[recent_key]
    
    # 如果没有，则遍历所有消息找最新的
    for msg_id, msg_data in RECOGNITION_CACHE.items():
        if isinstance(msg_data, dict) and msg_data.get("chat_id") == chat_id:
            msg_timestamp = msg_data.get("timestamp", 0)
            if msg_timestamp > latest_time:
                latest_msg = msg_data
                latest_time = msg_timestamp
    
    return latest_msg
    return latest_msg