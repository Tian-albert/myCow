# encoding:utf-8

import time
import json
import requests
from bot.bot import Bot
from bot.zhipuai.zhipu_ai_session import ZhipuAISession
from bot.zhipuai.zhipu_ai_image import ZhipuAIImage
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf

class ZHIPUAIBot(Bot, ZhipuAIImage):
    def __init__(self):
        super().__init__()
        self.sessions = SessionManager(ZhipuAISession, model=conf().get("model") or "ZHIPU_AI")
        
        # 获取配置
        self.api_key = conf().get("zhipu_ai_api_key")
        self.app_id = conf().get("zhipu_ai_app_id")
        
        if not self.api_key:
            raise Exception("[ZHIPUAI] api_key not configured")
        if not self.app_id:
            raise Exception("[ZHIPUAI] app_id not configured")
            
        # API基础URL
        self.base_url = "https://open.bigmodel.cn/api/llm-application/open"

    def _http_request(self, method, endpoint, **kwargs):
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        if kwargs.get("headers"):
            headers.update(kwargs.pop("headers"))
        
        response = requests.request(method, url, headers=headers, **kwargs)
        if not response.ok:
            raise Exception(f"Request failed: {response.text}")
        return response

    def _upload_file(self, file_path, upload_unit_id):
        """上传文件到智谱AI"""
        try:
            with open(file_path, 'rb') as f:
                files = {'files': f}
                data = {
                    'app_id': self.app_id,
                    'upload_unit_id': upload_unit_id
                }
                response = self._http_request(
                    'POST',
                    '/v2/application/file_upload',
                    data=data,
                    files=files
                )
                result = response.json()
                if result.get('code') == 200 and result['data']['success_info']:
                    return result['data']['success_info'][0]['file_id']
                else:
                    raise Exception(f"File upload failed: {result}")
        except Exception as e:
            logger.error(f"[ZHIPUAI] File upload error: {e}")
            raise

    def _check_file_status(self, file_ids):
        """检查文件解析状态"""
        try:
            response = self._http_request(
                'POST',
                '/v2/application/file_stat',
                json={
                    'app_id': self.app_id,
                    'file_ids': file_ids
                }
            )
            result = response.json()
            if result.get('code') == 200:
                return all(item['code'] == 0 for item in result['data'])
            return False
        except Exception as e:
            logger.error(f"[ZHIPUAI] Check file status error: {e}")
            return False

    def reply_text(self, session: ZhipuAISession, context=None, retry_count=0) -> dict:
        """使用智谱AI智能体API发送请求"""
        try:
            # 设置用户ID
            if context and context.get("msg"):
                user_id = context["msg"].from_user_id
                session.set_user_id(user_id)

            # 如果没有会话ID，创建新会话
            if not session.conversation_id:
                response = self._http_request(
                    "POST",
                    f"/v2/application/{self.app_id}/conversation"
                )
                conversation_id = response.json()["data"]["conversation_id"]
                session.set_conversation_id(conversation_id)

            # 准备对话请求参数
            request_params = {
                "app_id": self.app_id,
                "conversation_id": session.conversation_id,
                "key_value_pairs": [{
                    "id": "user",
                    "type": "input",
                    "name": "用户",
                    "value": session.messages[-1]["content"]
                }]
            }

            # 处理图片识别请求
            if context and context.kwargs:
                # 处理图片URL
                if context.kwargs.get("image_recognition"):
                    image_url = context.kwargs.get("image_url")
                    if image_url:
                        request_params["key_value_pairs"][0]["ivfiles"] = [{
                            "type": 1,  # 1表示图片
                            "url": image_url
                        }]
                
                # 处理文件上传
                if context.kwargs.get("file_path") and context.kwargs.get("upload_unit_id"):
                    file_id = self._upload_file(
                        context.kwargs["file_path"],
                        context.kwargs["upload_unit_id"]
                    )
                    # 等待文件解析完成
                    while not self._check_file_status([file_id]):
                        time.sleep(1)
                    request_params["key_value_pairs"][0]["files"] = [file_id]

            # 创建对话请求
            logger.info(f"[ZHIPUAI] Request Params: {request_params}")
            response = self._http_request(
                "POST",
                "/v2/application/generate_request_id",
                json=request_params
            )
            request_id = response.json()["data"]["id"]
            logger.info(f"[ZHIPUAI] Request ID: {request_id}")

            # 获取对话结果
            response = self._http_request(
                "POST",
                f"/v2/model-api/{request_id}/sse-invoke",
                headers={"Accept": "text/event-stream"},
                stream=True
            )

            # 处理SSE响应
            content = ""
            completion_tokens = 0
            total_tokens = 0

            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data:'):
                        try:
                            data = json.loads(line[5:])
                            if 'msg' in data:
                                content += data['msg']
                            elif 'usage' in data:
                                completion_tokens = data['usage'].get('completion_tokens', 0)
                                total_tokens = data['usage'].get('total_tokens', 0)
                        except json.JSONDecodeError:
                            continue

            return {
                "total_tokens": total_tokens,
                "completion_tokens": completion_tokens,
                "content": content
            }

        except Exception as e:
            logger.error(f"[ZHIPUAI] Error: {e}")
            if retry_count < 2:
                time.sleep(5)
                return self.reply_text(session, context, retry_count + 1)
            return {
                "completion_tokens": 0,
                "content": f"发生错误: {str(e)}"
            }

    def reply(self, query, context=None):
        """处理回复"""
        if context.type == ContextType.TEXT:
            logger.info("[ZHIPUAI] query={}".format(query))
            if not query:
                reply = Reply(ReplyType.TEXT, "您好，请问有什么能帮到您？")
                return reply
            
            session_id = context["session_id"]
            reply = None
            
            # 处理特殊命令
            clear_memory_commands = conf().get("clear_memory_commands", ["#清除记忆", "开启新会话"])

            if query in clear_memory_commands:
                # 获取会话
                session = self.sessions.session_query(query, session_id)
                user_id = context["msg"].from_user_id
                session.set_user_id(user_id)
                if session:
                    # 删除conversation_id
                    logger.info(f"[ZHIPUAI] session={session}")
                    session.delete_conversation()
                self.sessions.clear_session(session_id)
                reply = Reply(ReplyType.TEXT, "已开启新会话！")
                logger.info("[ZHIPUAI] 已开启新会话")
                return reply
            
            # 获取会话
            session = self.sessions.session_query(query, session_id)
            
            # 获取回复
            reply_content = self.reply_text(session, context)
            
            # 处理响应
            if reply_content["completion_tokens"] == 0 and len(reply_content["content"]) > 0:
                reply = Reply(ReplyType.TEXT, reply_content["content"])
            elif reply_content["completion_tokens"] > 0:
                self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
                reply = Reply(ReplyType.TEXT, reply_content["content"])
            else:
                reply = Reply(ReplyType.TEXT, reply_content["content"])
            
            return reply
            
        elif context.type == ContextType.IMAGE_CREATE:
            ok, retstring = self.create_img(query, 0)
            reply = None
            if ok:
                reply = Reply(ReplyType.IMAGE_URL, retstring)
            else:
                reply = Reply(ReplyType.ERROR, retstring)
            return reply

        else:
            reply = Reply(ReplyType.ERROR, f"Bot不支持处理{context.type}类型的消息")
            return reply
