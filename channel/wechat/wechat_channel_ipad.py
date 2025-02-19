# encoding:utf-8

"""
wechat channel
"""

import io

import time

import requests

from bridge.context import *
from bridge.reply import *
from channel.chat_channel import ChatChannel
from channel.wechat.wechat_message import *
from common.expired_dict import ExpiredDict
from common.log import logger
from common.singleton import singleton
from common.time_check import time_checker
from config import conf, get_appdata_dir

from channel.wechat.iPadWx_Beta import iPadWx
import time
from typing import Dict


def _check(func):
    def wrapper(self, cmsg: ChatMessage):
        msgId = cmsg.msg_id
        current_time = int(time.time())  # 获取当前时间戳

        # 清除超过5分钟的旧消息ID
        # 保证self.receivedMsgs只包含5分钟内的消息ID
        self.receivedMsgs = {msg_id: timestamp for msg_id, timestamp in self.receivedMsgs.items()
                             if current_time - timestamp <= 300}  # 300秒 = 5分钟

        # 如果该消息已经接收过，则跳过处理
        if msgId in self.receivedMsgs:
            logger.info("Wechat message {} already received, ignore".format(msgId))
            return

        # 保存当前消息ID和时间戳
        self.receivedMsgs[msgId] = current_time

        create_time = int(cmsg.create_time)  # 消息的创建时间戳
        # 如果消息是5分钟前的历史消息（跳过），也忽略
        if current_time - create_time > 300:  # 300秒 = 5分钟
            logger.debug("[WX]history message {} skipped".format(msgId))
            return

        # 跳过自己的消息，但不跳过群消息
        # if cmsg.my_msg and not cmsg.is_group:
        #     logger.debug("[WX]my message {} skipped".format(msgId))
        #     return

        # 如果通过了以上所有检查，则执行目标函数
        return func(self, cmsg)

    return wrapper
@singleton
class WechatChannel(ChatChannel):
    NOT_SUPPORT_REPLYTYPE = []

    def __init__(self):
        super().__init__()
        self.receivedMsgs = ExpiredDict(60 * 60)
        self.auto_login_times = 0
        self.bots: Dict[str, iPadWx] = {}  # Type hint for the bots dictionary
        
    def init_bot(self, app_id: str) -> iPadWx:
        """Initialize and return a bot instance for the given app_id.
        
        Args:
            app_id (str): The application ID for the bot
            
        Returns:
            iPadWx: The initialized bot instance
        """
        if app_id not in self.bots:
            bot = iPadWx()
            bot.app_id = app_id
            bot.initialize()
            self.bots[app_id] = bot
            logger.info(f"初始化机器人 {app_id} 成功")
        return self.bots[app_id]
        
    def init_load(self):
        '''初始化加载'''
        # 从配置中获取所有机器人的app_id
        bots_config = conf().get('bots', [])
        for bot_conf in bots_config:
            app_id = bot_conf.get('app_id')
            if app_id:
                bot = self.init_bot(app_id)
                if bot.initialize():
                    logger.info(f"Wechat login success, user_id: {bot.bot_wxid}, nickname: {bot.name}, app_id: {app_id}")
                    
                    # 更新群信息
                    update_group = False
                    if update_group:
                        groups = bot.get_contact_list()
                        need_save = False
                        if groups:
                            for room_id in groups['data']:
                                if room_id not in bot.shared_wx_contact_list:
                                    logger.info(f"群还未查询过{room_id}")
                                    room_info = bot.get_room_info(room_id)
                                    iPadWx.shared_wx_contact_list[room_id] = room_info['data']
                                    members = bot.get_chatroom_memberlist(room_id)
                                    iPadWx.shared_wx_contact_list[room_id]['chatRoomMembers'] = members['data']
                                    logger.info(f"群还未查询过{room_id},名称{room_info['data']['nickName']}")
                                    need_save = True

                            if need_save:
                                bot.save_contact()

                            # 获取需要监控的群列表
                            group_need_monitors = []
                            for group_need_monitor in conf().get("group_name_white_list", []):
                                for key, item in iPadWx.shared_wx_contact_list.items():
                                    if item['nickName'].lower() == group_need_monitor.lower():
                                        group_need_monitors.append(key)
                                        break

                            # 显示未监控的群
                            not_monitor = set(groups['data']) - set(group_need_monitors)
                            for room_id in list(not_monitor):
                                logger.info(f"还未监控的群{room_id},群名{iPadWx.shared_wx_contact_list[room_id]['nickName']}")

                            # 设置群监听
                            payload = {"group": group_need_monitors}
                            bot.group_listen(payload=payload)

    def startup(self):


        port = conf().get("wechatipad_port", 5711)
        self.init_load()

        #quart_app.run("0.0.0.0", port, use_reloader=False)


        # urls = (
        #     '/chat', 'channel.wechat.wechat_channel.WechatPadChannel'
        # )
        # app = web.application(urls, globals(), autoreload=False)
        # web.httpserver.runsimple(app.wsgifunc(), ("0.0.0.0", port))

        # try:
        #     itchat.instance.receivingRetryCount = 600  # 修改断线超时时间
        #     # login by scan QRCode
        #     hotReload = conf().get("hot_reload", False)
        #     status_path = os.path.join(get_appdata_dir(), "itchat.pkl")
        #     itchat.auto_login(
        #         enableCmdQR=2,
        #         hotReload=hotReload,
        #         statusStorageDir=status_path,
        #         qrCallback=qrCallback,
        #         exitCallback=self.exitCallback,
        #         loginCallback=self.loginCallback
        #     )
        #     self.user_id = itchat.instance.storageClass.userName
        #     self.name = itchat.instance.storageClass.nickName
        #     logger.info("Wechat login success, user_id: {}, nickname: {}".format(self.user_id, self.name))
        #     # start message listener
        #     itchat.run()
        # except Exception as e:
        #     logger.exception(e)


    # handle_* 系列函数处理收到的消息后构造Context，然后传入produce函数中处理Context和发送回复
    # Context包含了消息的所有信息，包括以下属性
    #   type 消息类型, 包括TEXT、VOICE、IMAGE_CREATE
    #   content 消息内容，如果是TEXT类型，content就是文本内容，如果是VOICE类型，content就是语音文件名，如果是IMAGE_CREATE类型，content就是图片生成命令
    #   kwargs 附加参数字典，包含以下的key：
    #        session_id: 会话id
    #        isgroup: 是否是群聊
    #        receiver: 需要回复的对象
    #        msg: ChatMessage消息对象
    #        origin_ctype: 原始消息类型，语音转文字后，私聊时如果匹配前缀失败，会根据初始消息是否是语音来放宽触发规则
    #        desire_rtype: 希望回复类型，默认是文本回复，设置为ReplyType.VOICE是语音回复
    # def handle_single(self, cmsg: ChatMessage):
    #     # filter system message
    #     if cmsg.other_user_id in ["weixin"]:
    #         return
    #     if cmsg.ctype == ContextType.VOICE:
    #         if conf().get("speech_recognition") != True:
    #             return
    #         logger.debug("[WX]receive voice msg: {}".format(cmsg.content))
    #     elif cmsg.ctype == ContextType.IMAGE:
    #         logger.debug("[WX]receive image msg: {}".format(cmsg.content))
    #     elif cmsg.ctype == ContextType.PATPAT:
    #         logger.debug("[WX]receive patpat msg: {}".format(cmsg.content))
    #     elif cmsg.ctype == ContextType.TEXT:
    #         logger.debug("[WX]receive text msg: {}, cmsg={}".format(json.dumps(cmsg._rawmsg, ensure_ascii=False), cmsg))
    #     else:
    #         logger.debug("[WX]receive msg: {}, cmsg={}".format(cmsg.content, cmsg))
    #     context = self._compose_context(cmsg.ctype, cmsg.content, isgroup=False, msg=cmsg)
    #     if context:
    #         self.produce(context)
    @_check
    def handle_group(self, cmsg: ChatMessage):
        # 根据消息中的app_id获取对应的机器人
        app_id = cmsg._rawmsg.get("Appid")
        if not app_id:
            logger.warn("消息中没有app_id")
            return
            
        # 获取或初始化对应的机器人
        self.bot = self.init_bot(app_id)
        
        #if cmsg.is_at and self.user_id in cmsg.at_list:
        if cmsg.ctype == ContextType.VOICE:
            if cmsg.is_group:
                if conf().get("group_speech_recognition") != True:
                    return
            else:
                if conf().get("speech_recognition") != True:
                    return
            logger.debug("[WX]receive voice for group msg: {}".format(cmsg.content))
        elif cmsg.ctype == ContextType.IMAGE:
            logger.debug("[WX]receive image for group msg: ")
        elif cmsg.ctype in [ContextType.JOIN_GROUP, ContextType.PATPAT, ContextType.ACCEPT_FRIEND, ContextType.EXIT_GROUP]:
            logger.debug("[WX]receive note msg: {}".format(cmsg.content))
        elif cmsg.ctype == ContextType.TEXT:
            logger.debug("[WX]receive msg: {}, cmsg={}".format(json.dumps(cmsg._rawmsg, ensure_ascii=False), cmsg))
            pass
        elif cmsg.ctype == ContextType.FILE:
            logger.debug(f"[WX]receive attachment msg, file_name={cmsg.content}")
        elif cmsg.ctype == ContextType.XML:
            logger.debug(f"[WX]receive XML msg")
        else:
            logger.debug("[WX]receive msg: {}".format(cmsg.content))
        context = self._compose_context(cmsg.ctype, cmsg.content, isgroup=cmsg.is_group, msg=cmsg,no_need_at=True)
        if context:
            self.produce(context)
        else:
            logger.debug("本次context返回为空，不放入队列")
    def upload_pic(self,local_file,upload_url):
        '''
        '{"url":"https://openai-75050.gzc.vod.tencent-cloud.com/openaiassets_14eb211d797ccdf33edc19839a7bcbcc_2579861717036942746.jpg","filekey":"openaiassets_14eb211d797ccdf33edc19839a7bcbcc_2579861717036942746.jpg"}'
        :param local_file:
        :param upload_url:
        :return:
        '''
        if os.path.exists(local_file):
            upload_url = "https://openai.weixin.qq.com/weixinh5/webapp/h774yvzC2xlB4bIgGfX2stc4kvC85J/cos/upload"
            payload = {}
            files = [
                    ('media', (
                    '0bbe70c70de11d13ffb2c.jpg', open(local_file, 'rb'),
                    'image/jpeg'))
                    ]
            headers={
            'Cookie':'oin:sess=eyJ1aWQiOiJmT1FMdFd1bUc0UyIsInNpZ25ldGltZSI6MTcxNjk2NjAwNTUxMCwiX2V4cGlyZSI6MTcxNzA1MjQwNjI4NiwiX21heEFnZSI6ODY0MDAwMDB9;oin:sess.sig=rHMmxTzNuo3bYpAwWzSoMA3S4DQ;wxuin=16966005491375;wxuin.sig=DMJDEtL7jcUjxUMAcDjetb9HBrA'
            }

            response=requests.post(upload_url,headers = headers,data = payload,files = files)

            print(response.text)
            return response.json()
        else:
            logger.info(f"本地文件不存在")
            return ""


    # 统一的发送函数，每个Channel自行实现，根据reply的type字段发送不同类型的消息
    def send(self, reply: Reply, context: Context):
        def send_long_text(bot, receiver, reply):
            max_length = 1000
            if reply.type == ReplyType.TEXT:
                content = reply.content
                if len(content)>max_length:
                    segments = content.split('\n')
                    current_message = ""
                    for segment in segments:
                        total_length = len(current_message) + len(segment) + 1
                        if total_length <= max_length:  # +1 for the newline character
                            if current_message:
                                current_message += '\n' + segment
                            else:
                                current_message = segment
                        else:
                            bot.send_message(receiver, current_message)
                            time.sleep(2.0)
                            logger.info("[WX] sendMsg={}, receiver={}".format(current_message, receiver))
                            current_message = segment
                else:
                    current_message = content
                if current_message:
                    bot.send_message(receiver, current_message)
                    logger.info("[WX] sendMsg={}, receiver={}".format(current_message, receiver))
                    time.sleep(2.0)

        receiver = context["receiver"]
        # 获取消息中的app_id
        #app_id = context["msg"].app_id
        app_id = context["msg"]._rawmsg.get("Appid")
        if not app_id:
            logger.warn("消息中没有app_id")
            return
        
        # 获取对应的机器人实例
        bot = self.init_bot(app_id)
        
        if reply.type == ReplyType.TEXT:
            send_long_text(bot, receiver, reply)
        elif reply.type == ReplyType.ERROR or reply.type == ReplyType.INFO:
            bot.send_message(receiver, reply.content)
            logger.info("[WX] sendMsg={}, receiver={}".format(reply, receiver))
        elif reply.type == ReplyType.VOICE:
            bot.send_voice(receiver, reply.content, 4)
            logger.info("[WX] sendFile={}, receiver={}".format(reply.content, receiver))
        elif reply.type == ReplyType.IMAGE_URL:
            img_url = reply.content
            if reply.ext:
                bot.send_message(receiver, reply.ext["prompt"])
            bot.send_image_url(receiver, reply.content)
            logger.info("[WX] sendImage url={}, receiver={}".format(img_url, receiver))
            if reply.ext:
                for url in reply.ext["urls"]:
                    bot.send_image_url(receiver, url)
                    logger.info("[WX] sendImage url={}, receiver={}".format(url, receiver))
        elif reply.type == ReplyType.IMAGE:
            image_storage = reply.content
            image_url = bot.upload_pic(image_storage, "")['url']
            bot.send_image_url(receiver, image_url)
        elif reply.type == ReplyType.IMAGE_XML:
            bot.forward_image(receiver, reply.content)
        elif reply.type == ReplyType.FILE_XML:
            bot.forward_file(receiver, reply.content)
        elif reply.type == ReplyType.FILE:
            file_storage = reply.content
            file_name = os.path.basename(file_storage)
            bot.send_file(receiver, file_storage, file_name=file_name)
            logger.info("[WX] sendFile, receiver={}".format(receiver))
        elif reply.type == ReplyType.VIDEO:
            video_storage = reply.content
            logger.info("[WX] sendFile, receiver={}".format(receiver))
        elif reply.type == ReplyType.VIDEO_URL:
            video_url = reply.content
            logger.debug(f"[WX] start download video, video_url={video_url}")
            video_res = requests.get(video_url, stream=True)
            video_storage = io.BytesIO()
            size = 0
            for block in video_res.iter_content(1024):
                size += len(block)
                video_storage.write(block)
            logger.info(f"[WX] download video success, size={size}, video_url={video_url}")
            video_storage.seek(0)
            logger.info("[WX] sendVideo url={}, receiver={}".format(video_url, receiver))
        elif reply.type == ReplyType.LINK:
            bot.forward_video(receiver, reply.content)
            logger.info("[WX] sendCARD={}, receiver={}".format(reply.content, receiver))

        # 统一的发送函数，每个Channel自行实现，根据reply的type字段发送不同类型的消息

#ch = WechatChannel()
class WechatPadChannel:
    # 类常量
    FAILED_MSG = '{"success": false}'
    SUCCESS_MSG = '{"success": true}'
    MESSAGE_RECEIVE_TYPE = "8001"

    def GET(self):
        return "Wechat iPad service start success!"

    # def POST(self):
    #     '''
    #     todo 校验发过来的token和auth
    #     '''
    #     try:
    #         msg = json.loads(web.data().decode("utf-8"))
    #         logger.debug(f"[Wechat] receive request: {msg}")
    #     except Exception as e:
    #         logger.error(e)
    #         return self.FAILED_MSG
    #     try:
    #         cmsg = WechatMessage(msg, True)
    #     except NotImplementedError as e:
    #         logger.debug("[WX]group message {} skipped: {}".format(msg["msg_id"], e))
    #         return None
    #     if msg['group']:
    #         WechatChannel().handle_group(cmsg)
    #     else:
    #         WechatChannel().handle_single(cmsg)
    #     return None

async def message_handler(recv, channel):
    channel.handle_group(recv)
    #await asyncio.create_task(channel.handle_group(recv))


# def callback(worker):
#     worker_exception = worker.exception()
#     if worker_exception:
#         logger.error(worker_exception)

#
# wechat_pad_channel = WechatPadChannel()
# @app.route('/chat', methods=['GET', 'POST'])
# def chat():
#     return wechat_pad_channel.handle_request()