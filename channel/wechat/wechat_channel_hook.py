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
from channel.wechat.wechat_message_hook import *
from common.expired_dict import ExpiredDict
from common.log import logger
from common.singleton import singleton
from common.time_check import time_checker
from config import conf, get_appdata_dir

from channel.wechat.Wx_Zhang import Wx_Zhang

@singleton
class WechatChannel(ChatChannel):
    NOT_SUPPORT_REPLYTYPE = []

    def __init__(self):
        super().__init__()
        self.receivedMsgs = ExpiredDict(60 * 60)
        self.auto_login_times = 0
        self.bot=Wx_Zhang()

    def init_load(self):
        '''
        初始化加载
        '''

        self.name = self.bot.bot_info['nickName']
        self.user_id = self.bot.bot_info['wxid']
        logger.info("Wechat login success, user_id: {}, nickname: {},到期时间{}".format(self.user_id, self.name,
                                                                                        "2029年"))

    def startup(self):


        port = conf().get("wechatipad_port", 5711)
        self.init_load()

    def handle_group(self, cmsg: ChatMessage):
        #if cmsg.is_at and self.user_id in cmsg.at_list:
        if cmsg.ctype == ContextType.VOICE:
            if conf().get("group_speech_recognition") != True:
                return
            logger.debug("[WX]receive voice for group msg: {}".format(cmsg.content))
        elif cmsg.ctype == ContextType.IMAGE:
            logger.debug("[WX]receive image for group msg: {}".format(cmsg.content))
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
                            logger.info("[WX] sendMsg={}, receiver={}".format(current_message, receiver))
                            current_message = segment
                else:
                    current_message = content
                if current_message:
                    bot.send_message(receiver, current_message)
                    logger.info("[WX] sendMsg={}, receiver={}".format(current_message, receiver))
                    time.sleep(2.0)
        receiver = context["receiver"]
        if reply.type == ReplyType.TEXT:
            send_long_text(self.bot,receiver,reply)
            #self.bot.send_message(receiver,reply.content)
            #logger.info("[WX] sendMsg={}, receiver={}".format(reply, receiver))
        elif reply.type == ReplyType.ERROR or reply.type == ReplyType.INFO:
            self.bot.send_txt(receiver,reply.content)
            logger.info("[WX] sendMsg={}, receiver={}".format(reply, receiver))
        elif reply.type == ReplyType.VOICE:
            self.bot.send_voice(receiver,reply.content,reply.ext)
            logger.info("[WX] sendFile={}, receiver={}".format(reply.content, receiver))
        elif reply.type == ReplyType.IMAGE_URL:  # 从网络下载图片
            #todo 这个地方，先发一段文字，然后再发图片
            img_url = reply.content
            if reply.ext: #如果有ext 说明有文字要发送，一次发完，这个地方已经完成了ext信息的包装

                self.bot.send_txt(receiver,reply.ext["prompt"])
                #time.sleep(1.5)


            self.bot.send_image_url(receiver,reply.content)
            logger.info("[WX] sendImage url={}, receiver={}".format(img_url, receiver))
            #time.sleep(2)
            if reply.ext:
                for url in reply.ext["urls"]:
                    #time.sleep(2)
                    self.bot.send_image_url(receiver, url)
                    logger.info("[WX] sendImage url={}, receiver={}".format(url, receiver))

        elif reply.type == ReplyType.IMAGE:  # 从文件读取图片
            image_storage = reply.content
            #image_storage.seek(0)
            #itchat.send_image(image_storage, toUserName=receiver)
            logger.info("[WX] sendImage, receiver={}".format(receiver))
            # done 上传文件
            image_url = self.bot.upload_pic(image_storage, "")['url']
            self.bot.send_image_url(receiver, image_url)
            #self.bot.send_image_url(receiver, url=reply.content)
        elif reply.type == ReplyType.FILE:  # 新增文件回复类型
            #todo
            file_storage = reply.content
            #itchat.send_file(file_storage, toUserName=receiver)
            logger.info("[WX] sendFile, receiver={}".format(receiver))
        elif reply.type == ReplyType.VIDEO:  # 新增视频回复类型
            #todo
            video_storage = reply.content
            #itchat.send_video(video_storage, toUserName=receiver)
            logger.info("[WX] sendFile, receiver={}".format(receiver))
        elif reply.type == ReplyType.VIDEO_URL:  # 新增视频URL回复类型
            # todo
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
            #itchat.send_video(video_storage, toUserName=receiver)
            logger.info("[WX] sendVideo url={}, receiver={}".format(video_url, receiver))
        elif reply.type == ReplyType.LINK:
            self.bot.forward_video(receiver, reply.content)
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


async def message_handler(recv, channel):
    channel.handle_group(recv)
