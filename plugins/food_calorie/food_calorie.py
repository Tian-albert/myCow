# encoding:utf-8

import plugins
from bridge.context import ContextType
from plugins import *
from common.log import logger

from common import memory
import xml.etree.ElementTree as ET

from bridge.reply import Reply, ReplyType
import json
from blueprints.plugins import voice_manager
import os
import requests
from datetime import datetime
from models import db_session, ImageMessage
import hashlib
from .HealthService import HealthService

config = conf()
channel_name = conf().get("channel_type", "wx")
if channel_name == "wx":
    from channel.wechat.iPadWx import iPadWx
elif channel_name == 'wx-beta':
    from channel.wechat.iPadWx_Beta import iPadWx


@plugins.register(
    name="food_calorie",
    desire_priority=900,
    desc="图片食物识别，记录卡路里",
    version="0.1",
    author="",
)
class food_calorie(Plugin):
    def __init__(self):
        super().__init__()
        try:
            # 初始化HealthService
            self.health_service = HealthService()

            # 加载配置
            cur_dir = os.path.dirname(__file__)
            config_path = os.path.join(cur_dir, "config.json")
            if not os.path.exists(config_path):
                logger.debug(f"[food_calorie]不存在配置文件{config_path}")
                conf = {
                    "corp_id": {"value": ""},
                    "secret": {"value": ""},
                    "forward_gh": {"value": ""}  # 企业微信公众号ID
                }
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(conf, f, indent=4)
            else:
                with open(config_path, "r", encoding="utf-8") as f:
                    conf = json.load(f)

            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            self.handlers[Event.ON_DECORATE_REPLY] = self.on_decorate_reply
            self.corp_id = conf.get("wechatcom_corp_id", {}).get("value", "")
            self.secret = conf.get("wechatcomapp_secret", {}).get("value", "")
            self.forward_gh = conf.get("要转发的人", {}).get("value", "")
            self.bot = iPadWx()
            logger.info("[food_calorie] inited.")

            # 创建保存目录
            self.emoji_dir = os.path.join("pic", "emoji")
            self.image_dir = os.path.join("pic", "picture")
            os.makedirs(self.emoji_dir, exist_ok=True)
            os.makedirs(self.image_dir, exist_ok=True)

            # 添加消息类型常量
            self.MSG_TYPE_IMAGE = "image"
            self.MSG_TYPE_EMOJI = "emoji"
        except Exception as e:
            logger.warn("[food_calorie] init failed.")
            raise e

    def save_image(self, image_data, chat_id, uploader_nickname, img_url=None):
        """保存图片到本地并更新数据库"""
        try:
            # 生成文件名
            file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{hashlib.md5(image_data).hexdigest()[:8]}.jpg"
            file_path = os.path.join(self.image_dir, file_name)

            # 保存文件
            with open(file_path, 'wb') as f:
                f.write(image_data)
            logger.info(f"[food_calorie] Saved image to {file_path}")

            # 保存到数据库
            image = ImageMessage(
                file_name=file_name,
                file_path=img_url,
                uploader_nickname=uploader_nickname,
                chat_id=chat_id
            )
            db_session.add(image)
            db_session.commit()
            logger.info(f"[food_calorie] Added image to database: {file_name}")
            return file_path

        except Exception as e:
            logger.error(f"[food_calorie] Error saving image: {e}")
            db_session.rollback()
            return None

    def update_food_record(self, reply_content, context, is_emoji=False):
        """更新食物记录"""
        if '无法直接' in reply_content or '没有实际' in reply_content:
            logger.warning(f"[food_calorie] 无法识别: {reply_content}")
            return
        try:
            if is_emoji:
                return  # 跳过表情处理

            # 保存到数据库
            msg = context["msg"]
            user_id = msg.from_user_id
            nickname = msg.from_user_nickname
            self.health_service.save_food_record(wx_id=user_id, content=reply_content, nickname=nickname)
            logger.info(f"[food_calorie] 所有食物记录保存完成")
        except Exception as e:
            logger.error(f"[food_calorie] 更新食物记录时发生错误: {e}")

    def handle_user_info(self, e_context: EventContext):
        """处理命令：保存用户信息"""
        context = e_context["context"]
        msg = context["msg"]
        content = context.content.strip()

        # 解析命令
        if content.startswith("设置个人信息"):
            try:
                # 格式: 设置个人信息 身高：170cm，体重：77kg，性别：男，年龄：21岁，活动水平：轻度活动
                user_id = msg.from_user_id
                nickname = msg.from_user_nickname

                res = self.health_service.save_user_info(wx_id=user_id, nickname=nickname, content=content)
                if res:
                    user = self.health_service.get_user_info(wx_id=user_id)
                    gender = "男" if user.gender == 1 else "女"
                    reply = Reply(ReplyType.TEXT,
                                  f"已更新您的个人信息：\n"
                                  f"身高：{user.height}cm\n"
                                  f"体重：{user.weight}kg\n"
                                  f"年龄：{user.age}岁\n"
                                  f"性别：{gender}\n"
                                  f"活动水平：{user.activity_level}\n"
                                  )
                    e_context["reply"] = reply
                else:
                    reply = Reply(ReplyType.TEXT,
                                  "设置失败，请使用正确的格式！\n"
                                  "例如：设置个人信息 身高：170cm，体重：77kg，性别：男，年龄：21岁，活动水平：轻度活动")
                    e_context["reply"] = reply

            except ValueError as e:
                reply = Reply(ReplyType.TEXT,
                              "设置失败，请使用正确的格式：\n"
                              "例如：设置个人信息 身高：170cm，体重：77kg，性别：男，年龄：21岁，活动水平：轻度活动")
                e_context["reply"] = reply

            e_context.action = EventAction.BREAK_PASS
            return

    def process_history_message(self, svrid):
        """
        处理历史消息
        Args:
            svrid: 消息ID
        Returns:
            tuple: (content, msg_type, error_msg)
            content: 消息内容
            msg_type: 消息类型 (image/emoji)
            error_msg: 错误信息，如果有的话
        """
        if not svrid:
            return None, None, None  # 改为返回 None，允许继续处理引用消息

        history_msg = memory.get_msg_from_cache(svrid)
        if not history_msg:
            return None, None, None  # 改为返回 None，允许继续处理引用消息

        content = history_msg.get("content")
        if not content:
            return None, None, None  # 改为返回 None，允许继续处理引用消息

        return content, history_msg.get("type"), None

    def process_reference_message(self, reference):
        """
        处理引用消息
        Args:
            reference: 引用消息数据
        Returns:
            tuple: (content, msg_type, error_msg)
        """
        ref_content = reference.get('content', '')
        if ref_content is None:
            ref_content = ""
        ref_content = ref_content.strip()
        refer_type = int(reference.get('type', 0))

        if not ref_content:
            return None, None, "引用内容为空"

        # 处理表情消息
        if refer_type == 47 and (ref_content.endswith('::0') or ref_content.startswith('<msg><emoji')):
            return ref_content, self.MSG_TYPE_EMOJI, None

        # 处理图片消息
        return ref_content, self.MSG_TYPE_IMAGE, None

    def process_image_content(self, content):
        """
        处理图片内容，验证必要属性
        Args:
            content: 图片XML内容
        Returns:
            tuple: (processed_content, error_msg)
        """
        try:
            root = ET.fromstring(content)
            img_element = root.find('.//img')
            if img_element is None:
                return None, "消息不是图片格式"

            # 验证必要属性
            required_attrs = ['cdnmidimgurl', 'aeskey']
            if not all(attr in img_element.attrib for attr in required_attrs):
                return None, "图片缺少必要属性"

            return content, None

        except ET.ParseError as e:
            logger.error(f"[food_calorie] Failed to parse image XML: {e}")
            return None, "图片解析失败"

    def handle_exercise_info(self, e_context: EventContext):
        """处理命令：设置运动信息"""
        context = e_context["context"]
        msg = context["msg"]
        content = context.content.strip()

        try:
            # 格式: 记录热量 数字
            if content.startswith("记录运动"):

                user_id = msg.from_user_id
                nickname = msg.from_user_nickname
                reply_text = ""

                exercise_id = self.health_service.save_exercise_record(wx_id=user_id, nickname=nickname,
                                                                       content=content)
                if exercise_id:
                    exercise = self.health_service.get_exercise_info(exercise_id=exercise_id)
                    reply_text = f"已记录运动：\n" \
                                 f"运动名称：{exercise.exercise_name}\n" \
                                 f"消耗热量：{exercise.burned_calories}千卡\n" \
                                 f"记录时间：{exercise.exercise_time}"""
                else:
                    reply_text = "记录失败，请使用正确的格式：\n" \
                                 "记录运动 运动名称 消耗多少千卡\n" \
                                 "例如：记录运动 跑步 消耗150千卡"

                reply = Reply(ReplyType.TEXT, reply_text)
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS

        except Exception as e:
            logger.error(f"[food_calorie] 记录运动数据失败: {e}")
            reply = Reply(ReplyType.TEXT,
                          "记录失败，请使用正确的格式：\n"
                          "记录运动 运动名称 消耗多少千卡\n"
                          "例如：记录运动 跑步 消耗150千卡")
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS

    def handle_calorie_query(self, e_context: EventContext):
        """处理命令：查询今日卡路里/今日热量"""
        context = e_context["context"]
        msg = context["msg"]
        content = context.content.strip()

        try:
            user_id = msg.from_user_id
            nickname = msg.from_user_nickname

            if content == "今日卡路里" or content == "今日热量":
                # 查询今日摄入的所有食物和总卡路里
                reply_text = self.health_service.get_user_today_food_report(wx_id=user_id, nickname=nickname)

                reply = Reply(ReplyType.TEXT, reply_text)
                e_context["reply"] = reply

            e_context.action = EventAction.BREAK_PASS

        except Exception as e:
            logger.error(f"[food_calorie] Error querying calories: {e}")
            reply = Reply(ReplyType.TEXT, "查询失败，请稍后重试")
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS

    def on_handle_context(self, e_context: EventContext):
        context = e_context["context"]

        if context.type == ContextType.TEXT:
            content = context.content.strip()
            if content.startswith("设置个人信息"):
                return self.handle_user_info(e_context)
            elif content == "今日卡路里" or content == "今日热量":
                return self.handle_calorie_query(e_context)
            elif content.startswith("记录运动"):
                return self.handle_exercise_info(e_context)
            elif content in ["帮助", "HELP", "help", "指南", "使用说明"]:
                return self._handle_help_command(e_context)

        # 处理识别热量命令——识别历史消息中最近的一张图片
        if context.type == ContextType.TEXT and context.content.strip() == "识别热量":
            return self._handle_recognition_command_history(e_context)

        # 处理识别热量命令——识别引用信息中的图片
        if context.type == ContextType.XML:
            return self._handle_recognition_command_reference(e_context)

        return

    def _handle_recognition_command_history(self, e_context: EventContext):
        """
        处理识别命令
        处理流程：
        1. 获取用户信息
        2. 从缓存获取最近消息
        3. 处理媒体内容
        4. 获取图片链接
        5. 保存文件
        """
        context = e_context["context"]
        msg = context["msg"]

        # 获取用户信息
        chat_id = msg.other_user_id if msg.is_group else msg.from_user_id
        uploader_nickname = msg.actual_user_nickname if msg.is_group else msg.from_user_nickname

        # 获取最近消息
        latest_msg = memory.get_recent_msg_from_cache(chat_id)
        if not latest_msg:
            reply = Reply(ReplyType.TEXT, "记忆中不存在最近的图片或表情")
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
            return

        # 处理媒体内容
        content = latest_msg.get("content")
        msg_type = latest_msg.get("type")

        if msg_type not in [self.MSG_TYPE_IMAGE, self.MSG_TYPE_EMOJI]:
            reply = Reply(ReplyType.TEXT, "最近的消息不是图片或表情")
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
            return

        try:
            # 处理不同类型的媒体
            if msg_type == self.MSG_TYPE_IMAGE:
                processed_content, error_msg = self.process_image_content(content)
                if error_msg:
                    raise Exception(error_msg)

                # 转发图片获取URL
                voice_manager.start_waiting()
                ret = self.bot.forward_img(self.forward_gh, processed_content)
                if not ret:
                    raise Exception("转发图片失败")

            # 等待获取图片链接
            result = voice_manager.get_result(timeout=15)
            if not result or not result.image:
                raise Exception("获取图片链接超时")

            # 保存文件
            file_path = None
            if msg_type == self.MSG_TYPE_EMOJI:
                pass
            else:
                response = requests.get(result.image)
                if response.status_code == 200:
                    file_path = self.save_image(response.content, chat_id, uploader_nickname, result.image)

            if not file_path:
                raise Exception("保存文件失败")

            # 获取用户信息
            user_id = msg.from_user_id
            prompt = self.user_info_prompt(user_id)

            image_url_local = get_image_url(file_path)
            image_url_local = image_url_local.replace("\\", "/")
            logger.info(f"要发送的图片 {image_url_local}")
            # 设置context用于识别
            e_context["context"].type = ContextType.TEXT
            e_context["context"].content = prompt
            if not hasattr(e_context["context"], "kwargs"):
                e_context["context"].kwargs = {}
            e_context["context"].kwargs.update({
                "image_url": image_url_local,  #result.image,
                "image_recognition": True,
                "file_path": file_path,
                "msg_type": msg_type
            })
            e_context.action = EventAction.BREAK

        except Exception as e:
            logger.error(f"[food_calorie] Save command failed: {e}")
            reply = Reply(ReplyType.TEXT, f"处理失败: {str(e)}")
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS

    def _handle_recognition_command_reference(self, e_context: EventContext):
        """
        处理识别命令
        处理流程：
        1. 解析引用消息
        2. 获取历史消息或处理引用内容
        3. 处理媒体内容
        4. 获取图片链接
        5. 保存文件
        """
        context = e_context["context"]
        msg = context["msg"]

        try:
            # 解析引用消息
            result = msg.parse_wechat_message(msg.content)
            if not (result.get('message_type') == 'appmsg' and result.get('subtype') == 'reference'):
                return

            # 检查命令
            title = result.get('title', '').strip()
            if not title.startswith("记录") and not title.startswith("热量") and not title.startswith("识别热量"):
                return

            # 获取引用信息
            reference = result.get('reference', {})
            svrid = reference.get('svrid')

            # 先尝试获取历史消息
            content = None
            msg_type = None
            error_msg = None

            if svrid:
                content, msg_type, error_msg = self.process_history_message(svrid)

            # 如果历史消息不存在或没有内容，尝试处理引用内容
            # content=None
            if not content:  # 修改这里的判断条件，只要没有content就尝试处理引用内容

                content, msg_type, error_msg = self.process_reference_message(reference)

            if not content:  # 如果两种方式都无法获取内容，才报错
                reply = Reply(ReplyType.TEXT, error_msg or "无法获取消息内容")
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return

            # 处理媒体内容
            chat_id = msg.other_user_id if msg.is_group else msg.from_user_id
            uploader_nickname = msg.actual_user_nickname if msg.is_group else msg.from_user_nickname

            if msg_type == self.MSG_TYPE_IMAGE:
                processed_content, error_msg = self.process_image_content(content)
                if error_msg:
                    raise Exception(error_msg)

                # 转发图片获取URL
                voice_manager.start_waiting()
                ret = self.bot.forward_img(self.forward_gh, processed_content)
                if not ret:
                    raise Exception("转发图片失败")

            # 等待获取图片链接
            result = voice_manager.get_result(timeout=15)
            if not result or not result.image:
                raise Exception("获取图片链接超时")

            # 保存文件
            file_path = None
            if msg_type == self.MSG_TYPE_EMOJI:
                pass
            else:
                response = requests.get(result.image)
                if response.status_code == 200:
                    file_path = self.save_image(response.content, chat_id, uploader_nickname, result.image)

            if not file_path:
                raise Exception("保存文件失败")

            # 获取用户信息
            user_id = msg.from_user_id
            prompt = self.user_info_prompt(user_id)

            image_url_local = get_image_url(file_path)
            image_url_local = image_url_local.replace("\\", "/")
            logger.info(f"要发送的图片 {image_url_local}")
            # 设置context用于识别
            logger.info(f"Prompt: {prompt}")
            e_context["context"].type = ContextType.TEXT
            e_context["context"].content = prompt
            image_url = result.image
            if image_url:
                if image_url.endswith("\\") or image_url.endswith("/"):
                    image_url = image_url[:-1]
            if not hasattr(e_context["context"], "kwargs"):
                e_context["context"].kwargs = {}
            e_context["context"].kwargs.update({
                "image_url": image_url_local,  #image_url,
                "image_recognition": True,
                "file_path": file_path,
                "msg_type": msg_type
            })
            e_context.action = EventAction.BREAK
        except Exception as e:
            logger.error(f"[food_calorie] Recognition command failed: {e}")
            reply = Reply(ReplyType.TEXT, f"图像识别处理失败: {str(e)}")
            e_context["reply"] = reply

            e_context.action = EventAction.BREAK_PASS

    def on_decorate_reply(self, e_context: EventContext):
        """处理回复装饰"""
        context = e_context["context"]
        reply = e_context["reply"]

        # 检查是否是图片识别请求的回复
        if context.get("image_recognition"):
            file_path = context.kwargs.get("file_path")
            msg_type = context.kwargs.get("msg_type")
            if file_path and reply and (reply.type == ReplyType.TEXT or reply.type == ReplyType.ERROR):
                self.update_food_record(reply.content, context, is_emoji=(msg_type == "emoji"))

    def get_help_text(self, **kwargs):  # 此命令不仅在内部调用，还接受外部调用
        help_text = (
            "1. 发送\"识别热量\"并引用一张图片即可识别图片中食物的热量\n"
            "2. 发送\"识别热量\"可以识别最近的一张图片中食物的热量（必须是最近的消息且消息是图片）\n"
            "3. 发送\"设置个人信息 身高：170cm，体重：77kg，性别：男，年龄：21岁，活动水平：轻度活动\"记录个人信息\n"
            "4. 发送\"记录运动 跑步 消耗150千卡\"可以记录运动信息\n"
            "5. 发送\"今日卡路里\\今日热量\"查看今日饮食记录、运动记录和热量统计"
        )
        return help_text

    def _handle_help_command(self, e_context: EventContext):
        """处理帮助命令"""
        help_text = self.get_help_text()
        reply = Reply(ReplyType.TEXT, help_text)
        e_context["reply"] = reply
        e_context.action = EventAction.BREAK_PASS

    def user_info_prompt(self, wx_id):  # 根据用户的个人信息构建提示词
        prompt = ""
        user_info = self.health_service.get_user_info(wx_id=wx_id)
        # 构建提示词
        base_prompt = "图片中是我当前的饮食，识别这张图片中的食物，列出每种食物的卡路里含量，并计算总热量。\n"
        if user_info.height and user_info.weight and user_info.gender and user_info.activity_level and user_info.gender != 0 and user_info.age:
            height = user_info.height
            weight = user_info.weight
            gender = "男" if user_info.gender == 1 else "女"
            activity_level = user_info.activity_level
            age = user_info.age
            bmi = weight / ((height / 100) ** 2)

            prompt = (
                f"{base_prompt}\n"
                f"请注意：我的身高{height}cm，体重{weight}kg，BMI为{bmi:.1f}，性别是{gender}，年龄为：{age}，活动水平是{activity_level}"
                f"请根据我的身体状况给出个性化的饮食建议。"
            )
        else:
            prompt = base_prompt + "\n请给出健康饮食建议。"
        return prompt


def get_image_url(image_name):
    if channel_name == "wx":
        http_addr = conf().get("http_hook")
    elif channel_name == 'wx-beta':
        http_addr = conf().get("http_hook_ipad")
    else:
        http_addr = conf().get("http_hook")
    parts = http_addr.split("/")
    result = "/".join(parts[:-1])

    result = f"{result}/{image_name}"
    logger.info(f"要发送的图片 {result}")
    return result
