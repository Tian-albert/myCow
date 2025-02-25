import json
import os
from bot.session_manager import Session
from common.log import logger


class ZhipuAISession(Session):
    def __init__(self, session_id, system_prompt=None, model="glm-4"):
        super().__init__(session_id, system_prompt)
        self.model = model
        self.conversation_id = None
        self.user_id = None
        self.reset()
        
        # 添加系统提示
        if system_prompt:
            self.messages.append({
                "role": "system",
                "content": system_prompt
            })
        else:
            logger.warn("[ZHIPUAI] system_prompt is empty")

    def reset(self):
        """重置会话"""
        super().reset()
        # 不重置 conversation_id，保持会话连续性

    def set_user_id(self, user_id: str):
        """设置用户ID"""
        self.user_id = user_id
        # 尝试加载已存在的会话ID
        self.load_conversation()

    def delete_conversation(self):
        """删除文件中的会话id"""
        if not self.user_id or not self.conversation_id:
            return

        try:
            # 确保目录存在
            os.makedirs('sessions', exist_ok=True)

            # 加载现有数据
            data = {}
            if os.path.exists('sessions/zhipuai_sessions.json'):
                with open('sessions/zhipuai_sessions.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)

            # 更新数据
            data[self.user_id] = {
                'conversation_id': "",
                'model': self.model,
                'session_id': self.session_id
            }

            # 保存数据
            with open('sessions/zhipuai_sessions.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            logger.debug(f"[ZHIPUAI] Saved conversation_id for user {self.user_id}")
        except Exception as e:
            logger.error(f"[ZHIPUAI] Failed to save conversation: {e}")

    def save_conversation(self):
        """保存会话ID到文件"""
        if not self.user_id or not self.conversation_id:
            return
            
        try:
            # 确保目录存在
            os.makedirs('sessions', exist_ok=True)
            
            # 加载现有数据
            data = {}
            if os.path.exists('sessions/zhipuai_sessions.json'):
                with open('sessions/zhipuai_sessions.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            # 更新数据
            data[self.user_id] = {
                'conversation_id': self.conversation_id,
                'model': self.model,
                'session_id': self.session_id
            }
            
            # 保存数据
            with open('sessions/zhipuai_sessions.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                
            logger.debug(f"[ZHIPUAI] Saved conversation_id for user {self.user_id}")
        except Exception as e:
            logger.error(f"[ZHIPUAI] Failed to save conversation: {e}")

    def load_conversation(self):
        """从文件加载会话ID"""
        if not self.user_id:
            return
            
        try:
            if os.path.exists('sessions/zhipuai_sessions.json'):
                with open('sessions/zhipuai_sessions.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if self.user_id in data:
                        self.conversation_id = data[self.user_id]['conversation_id']
                        logger.debug(f"[ZHIPUAI] Loaded conversation_id for user {self.user_id}")
        except Exception as e:
            logger.error(f"[ZHIPUAI] Failed to load conversation: {e}")

    def set_conversation_id(self, conversation_id: str):
        """设置会话ID并保存"""
        self.conversation_id = conversation_id
        self.save_conversation()

    def calc_tokens(self):
        """计算token数量"""
        return num_tokens_from_messages(self.messages, self.model)

    def discard_exceeding(self, max_tokens, cur_tokens=None):
        """处理超出token限制的情况"""
        if cur_tokens is None:
            cur_tokens = self.calc_tokens()
            
        while cur_tokens > max_tokens and len(self.messages) > 1:
            # 保留system消息，移除最早的对话
            if self.messages[1]["role"] != "system":
                self.messages.pop(1)
            cur_tokens = self.calc_tokens()
            
        return cur_tokens

    def add_query(self, query):
        """添加用户查询"""
        self.messages.append({
            "role": "user",
            "content": query
        })

    def add_reply(self, reply):
        """添加助手回复"""
        self.messages.append({
            "role": "assistant",
            "content": reply
        })


def num_tokens_from_messages(messages, model):
    tokens = 0
    for msg in messages:
        tokens += len(msg["content"])
    return tokens
