# encoding:utf-8
import os
import time
import requests
import json
import webbrowser
import configparser
import hashlib
import random
from config import conf,load_config,save_config
from pydub import AudioSegment
from common.log import logger
#import azure.cognitiveservices.speech as speechsdk
import os
#import av
#import pilk
import subprocess
from common.singleton import singleton

class iPadWx:
    """
    登录模块
    """

    shared_wx_contact_list = {}
    function_called = False
    def __init__(self):
        config = conf()

        self.base_url = config.get('base_url_ipad')
        self.base_url_ipad_download = config.get('base_url_ipad_download')

        self.app_id = config.get('app_id')

        self.status = config.get('status')
        self.subscription_key= config.get('subscription_key')
        self.service_region = config.get('service_region')
        self.token = config.get('token_ipad')
        self.headers = {
            "X-GEWE-TOKEN": self.token,
            "Content-Type": "application/json"
        }
        self.bot_wxid=None
        self.uuid = None  # 添加uuid属性
        self.is_initialized = False  # 添加初始化标志
        self.name=None
        self.is_login = False

    def initialize(self):
        """延迟初始化方法，只在需要时调用"""
        if self.is_initialized:
            return True
            
        if not iPadWx.function_called and self.app_id and self.token:
            self.load_contact()

        if self.app_id and self.token:
            if self.bot_wxid is None:
                ret = self.get_profile()
                if ret:
                    if ret.get("ret",0)==404:
                        logger.info(ret)
                        self.is_login = False
                        return False
                    elif ret.get("ret",0)== 200 or ret.get("code",0)== 0:
                        self.bot_wxid = ret['data']['wxid']
                        self.name = ret['data']['nickName']
                        self.is_login = True

                    else:
                        self.bot_wxid = None
                        self.name = None
                        self.is_login = False
                        logger.info(f"获取机器人信息失败:{ret}")
                        return False

            iPadWx.function_called = True
        
        self.is_initialized = True
        return True

    def init_load(self):
        pass

    def get_contact_file(self):
        """获取联系人文件路径"""
        if self.app_id:
            return f"contact_beta_{self.app_id}.json"
        return "contact_beta.json"

    def load_contact(self):
        """加载联系人信息"""
        contact_file = self.get_contact_file()
        if os.path.exists(contact_file):
            try:
                with open(contact_file, 'r', encoding='utf-8') as f:
                    iPadWx.shared_wx_contact_list = json.load(f)
                logger.info(f"读取联系人成功: {contact_file}")
                iPadWx.function_called = True
                return True
            except Exception as e:
                logger.error(f"读取联系人文件失败: {e}")
                return False
        else:
            logger.info(f"联系人文件不存在: {contact_file}")
            iPadWx.shared_wx_contact_list = {}
            return False

    def save_contact(self):
        """保存联系人信息"""
        contact_file = self.get_contact_file()
        try:
            with open(contact_file, 'w', encoding='utf-8') as f:
                json.dump(iPadWx.shared_wx_contact_list, f, ensure_ascii=False, indent=4)
            logger.info(f"保存联系人成功: {contact_file}")
            return True
        except Exception as e:
            logger.error(f"保存联系人文件失败: {e}")
            return False
    ##登录模块
    def call_api(self, method, endpoint, data=None):
        url = f"{self.base_url}/{endpoint}"
        self.headers = {
            "X-GEWE-TOKEN": self.token,
            "Content-Type": "application/json"
        }
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=data)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            else:
                return None
            if response.status_code == 200:
                #logger.debug(response.json())
                return response.json()
            else:
                logger.error(f"API请求失败，状态码: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"API请求失败: {e}")
            return None
    def call_api_download(self, method, endpoint, data=None):
        url = f"{self.base_url}/{endpoint}"


        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=data)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            else:
                return None
            if response.status_code == 200:
                logger.debug(response.json())
                return response.json()
            else:
                logger.error(f"API请求失败，状态码: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"API请求失败: {e}")
            return None
    def get_token(self):
        """
        获取tokenId 将tokenId 配置到 类中的token 属性
        """
        response = self.call_api("POST", "tools/getTokenId")
        if response:
            self.token = response.get("data")
            self.headers["X-GEWE-TOKEN"] = self.token
            conf().__setitem__("token_ipad",self.token)
            #self.save_config()
        return response

    def set_callback_url(self, callback_url):
        """
        设置微信消息的回调地址
        """
        param = {
            "token": self.token,
            "callbackUrl": callback_url
        }
        response = self.call_api("POST", "tools/setCallback", data=param)
        return response

    def get_qrcode(self):
        """
        获取登录二维码
        """
        if 'gewe' in self.base_url:
            param = {
                "appId": self.app_id,
                "regionId":"510000",
                "proxyIp":None
            }
        else:
            param = {
                "appId": self.app_id,
            }
        response = self.call_api("POST", "login/getLoginQrCode", data=param)
        if response and response.get("data"):
            self.app_id = response["data"].get("appId")
            self.uuid = response["data"].get("uuid")
            #self.save_config()
        return response

    def check_qr(self, captch_code=None):
        """检查二维码状态"""
        if not self.uuid:
            return {"status": -1, "message": "UUID not found"}

        param = {
            "appId": self.app_id,
            "uuid": self.uuid,
            "captchCode": captch_code
        }
        response = self.call_api("POST", "login/checkLogin", data=param)
        if response and response.get("data"):
            if response['data']['status'] == 2:
                self.status = 2
                self.bot_info = response["data"].get("loginInfo")
                # self.save_config()

        return response


    def start_listen(self):
        return {"ret": 200}
    def stop_listen(self):
        return {"ret":200}
    def group_listen(self,payload):
        return {"ret":200}
    def filter_msg(self):
        return {"ret": 200}
    def log_reconnection(self):
        """
        退出微信
        """
        param = {
            "appId": self.app_id
        }
        response = self.call_api("POST", "login/reconnection", data=param)
        return response
    def log_out(self):
        """
        退出微信
        """
        param = {
            "appId": self.app_id
        }
        response = self.call_api("POST", "login/logout", data=param)
        return response

    def dialog_login(self):
        """
        弹框登录
        """
        param = {
            "appId": self.app_id
        }
        response = self.call_api("POST", "login/dialogLogin", data=param)
        return response

    def check_online(self):
        """检查在线状态前确保已初始化"""
        if not self.is_initialized:
            self.initialize()
        """
        检查是否在线,如果data为空，则是离线
        """
        param = {
            "appId": self.app_id
        }
        response = self.call_api("POST", "login/checkOnline", data=param)
        return response

    def generate_qr_code_html(self, qr_code_base64, output_file):
        # 从 base64 数据中提取图片数据
        image_data = qr_code_base64

        # 创建 HTML 页面
        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>QR Code Login</title>
        </head>
        <body>
            <h1>请使用微信扫描下方二维码确认登录</h1>
            <img src="{image_data}" alt="QR Code Image">
        </body>
        </html>
        '''

        # 将 HTML 内容保存到指定文件中
        with open(output_file, 'w') as file:
            file.write(html_content)

        logger.info(f"HTML 文件已生成，请查看 {output_file} 文件来展示二维码图片。")
        webbrowser.open(output_file)

    def save_config(self):
        """
        保存配置信息到文件
        """
        config =conf()
        with open("config-ipad.json", "w") as file:
            json.dump(config, file, indent=4)
        logger.info("配置信息已保存到 config.json 文件")

    def load_config(self):
        """
        从文件加载配置信息
        """
        if os.path.exists("config.json"):
            with open("config.json", "r") as file:
                config = json.load(file)
                self.token = config.get("token")
                self.app_id = config.get("app_id")
                self.uuid = config.get("uuid")
                self.headers["X-GEWE-TOKEN"] = self.token
                self.status = config.get("status")
                self.bot_info = config.get("loginInfo")
                if self.bot_info:
                    self.bot_wxid = self.bot_info.get("wxid")
                    logger.info(self.bot_info)
            logger.info("配置信息已从 config.json 文件加载")
        '''
     * 消息模块
     '''
    def send_txt_msg(self, to_wxid, content, ats=None):
        """发送消息前确保已初始化"""
        if not self.is_initialized:
            self.initialize()
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "content": content,
            "ats": ats
        }
        return self.call_api("POST", "message/postText", data=param)
    def send_message(self, to_wxid, content, ats=None):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "content": content,
            "ats": ats
        }
        return self.call_api("POST", "message/postText", data=param)
    def send_at_msg(self, to_wxid, content, ats):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "content": content,
            "ats": ats
        }
        return self.call_api("POST", "message/postText", data=param)
    def send_file(self, to_wxid, file_url, file_name):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "fileUrl": file_url,
            "fileName": file_name
        }
        ret = self.call_api("POST", "message/postImage", data=param)
        logger.info(ret)
        return ret
        #return self.call_api("POST", "message/postFile", data=param)

    def send_image_url(self, to_wxid, img_url):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "imgUrl": img_url
        }
        ret = self.call_api("POST", "message/postImage", data=param)
        logger.info(ret)
        return ret
    # def text_to_mp3(self,text,output):
    #
    #     # This example requires environment variables named "SPEECH_KEY" and "SPEECH_REGION"
    #     speech_config = speechsdk.SpeechConfig(subscription=self.subscription_key, region=self.service_region)
    #
    #     # The language of the voice that speaks.
    #     speech_config.speech_synthesis_voice_name = 'zh-CN-XiaoxiaoNeural'  # 这个男声 有 磁性
    #     #text = "讲一个笑话：和朋友去饭店吃饭，要了一盘红烧肉，结果发现怎么咬都咬不动，我顿时就火了，把服务员叫过来喊道：你们这肉怎么咬都咬不动，把你们经理叫来。服务员说：叫我们经理干啥啊，你都咬不动，他能咬得动啊！"
    #     speech_config.set_speech_synthesis_output_format(
    #         speechsdk.SpeechSynthesisOutputFormat.Audio24Khz160KBitRateMonoMp3)  # 这里配置文件为mp3格式，要保存其它文件格式，修改这里参数
    #     speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
    #
    #     result = speech_synthesizer.speak_text_async(text).get()
    #     stream = speechsdk.AudioDataStream(result)
    #     stream.save_to_wav_file(output)  # mp3文件保存路径
    #
    #     if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    #         print("Speech synthesized Completed,  for text [{}]".format(text))
    #         audio=AudioSegment.from_file(output,format="mp3")
    #         duration= len(audio)
    #         return True,duration
    #     elif result.reason == speechsdk.ResultReason.Canceled:
    #         cancellation_details = result.cancellation_details
    #         print("Speech synthesis canceled: {}".format(cancellation_details.reason))
    #         if cancellation_details.reason == speechsdk.CancellationReason.Error:
    #             if cancellation_details.error_details:
    #                 print("Error details: {}".format(cancellation_details.error_details))
    #                 print("Did you set the speech resource key and region values?")
    #                 return False,0
    #     return False,0
    #
    #
    # def text_to_mp32(self,text, output, voice_name='zh-CN-XiaoxiaoNeural', style='chat-casual', rate='+10%', volume='+0%'):
    #     # This example requires environment variables named "SPEECH_KEY" and "SPEECH_REGION"
    #     speech_config = speechsdk.SpeechConfig(subscription=self.subscription_key, region=self.service_region)
    #
    #     # 设置声音的类型
    #     speech_config.speech_synthesis_voice_name = voice_name
    #
    #     # 使用 SSML 设置声音的样式、语速和音量
    #     ssml_text=f"""
    #     <speak xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xmlns:emo="http://www.w3.org/2009/10/emotionml" version="1.0" xml:lang="zh-CN">
    #     <voice name='{voice_name}'>
    #     <mstts:express-as style='{style}'>
    #     <prosody rate='{rate}' volume='{volume}' pitch="+5.00%">
    #     {text}
    #     </prosody></mstts:express-as></voice></speak>
    #     """
    #     ssml_text2 = f"""
    #     <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='zh-CN'>
    #         <voice name='{voice_name}'>
    #             <mstts:express-as style='{style}'>
    #                 <prosody rate='{rate}' volume='{volume}'>
    #                     {text}
    #                 </prosody>
    #             </mstts:express-as>
    #         </voice>
    #     </speak>
    #     """
    #     logger.debug(ssml_text)
    #
    #     speech_config.set_speech_synthesis_output_format(
    #         speechsdk.SpeechSynthesisOutputFormat.Audio24Khz160KBitRateMonoMp3)  # 配置文件为mp3格式
    #     speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
    #
    #     result = speech_synthesizer.speak_ssml_async(ssml_text).get()
    #     stream = speechsdk.AudioDataStream(result)
    #     stream.save_to_wav_file(output)  # 保存mp3文件
    #
    #     if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    #         print("Speech synthesized Completed, for text [{}]".format(text))
    #
    #         # 获取声音文件的长度
    #         audio = AudioSegment.from_file(output, format="mp3")
    #         duration_in_seconds = len(audio)   # 转换为秒
    #         print(f"Audio length: {duration_in_seconds} seconds")
    #
    #         return True,duration_in_seconds
    #     elif result.reason == speechsdk.ResultReason.Canceled:
    #         cancellation_details = result.cancellation_details
    #         print("Speech synthesis canceled: {}".format(cancellation_details.reason))
    #         if cancellation_details.reason == speechsdk.CancellationReason.Error:
    #             if cancellation_details.error_details:
    #                 print("Error details: {}".format(cancellation_details.error_details))
    #                 print("Did you set the speech resource key and region values?")
    #                 return False,0
    #     return False,0
    #
    #
    # def convert_to_silk(media_path: str) -> str:
    #     """任意媒体文件转 silk, 返回silk路径"""
    #     pcm_path, sample_rate = to_pcm(media_path)
    #     silk_path = os.path.splitext(pcm_path)[0] + '.silk'
    #     pilk.encode(pcm_path, silk_path, pcm_rate=sample_rate, tencent=True)
    #     os.remove(pcm_path)
    #     return silk_path
    # def text_to_silk(self,text):
    #     output_file = "pic/output.mp3"
    #     ret, duration = self.text_to_mp32(text,output_file)
    #     if ret:
    #
    #         silk_path = convert_to_silk(output_file)
    #         return silk_path,duration

    def send_voice(self, to_wxid, voice_url, voice_duration):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "voiceUrl": voice_url,
            "voiceDuration": voice_duration
        }
        return self.call_api("POST", "message/postVoice", data=param)

    def send_video(self, to_wxid, video_url, thumb_url, video_duration):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "videoUrl": video_url,
            "thumbUrl": thumb_url,
            "videoDuration": video_duration
        }
        return self.call_api("POST", "message/postVideo", data=param)

    def send_link(self, to_wxid, title, desc, link_url, thumb_url):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "title": title,
            "desc": desc,
            "linkUrl": link_url,
            "thumbUrl": thumb_url
        }
        return self.call_api("POST", "message/postLink", data=param)

    def send_name_card(self, to_wxid, nick_name, name_card_wxid):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "nickName": nick_name,
            "nameCardWxid": name_card_wxid
        }
        return self.call_api("POST", "message/postNameCard", data=param)

    def send_emoji(self, to_wxid, emoji_md5, emoji_size):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "emojiMd5": emoji_md5,
            "emojiSize": emoji_size
        }
        return self.call_api("POST", "message/postEmoji", data=param)

    def send_app_msg(self, to_wxid, appmsg):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "appmsg": appmsg
        }
        return self.call_api("POST", "message/postAppMsg", data=param)

    def send_mini_app(self, to_wxid, mini_app_id, display_name, page_path, cover_img_url, title, user_name):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "miniAppId": mini_app_id,
            "displayName": display_name,
            "pagePath": page_path,
            "coverImgUrl": cover_img_url,
            "title": title,
            "userName": user_name
        }
        return self.call_api("POST", "message/postMiniApp", data=param)

    def forward_file(self, to_wxid, xml):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "xml": xml
        }
        return self.call_api("POST", "message/forwardFile", data=param)

    def forward_image(self, to_wxid, xml):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "xml": xml
        }
        return self.call_api("POST", "message/forwardImage", data=param)

    def forward_video(self, to_wxid, xml):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "xml": xml
        }
        return self.call_api("POST", "message/forwardVideo", data=param)

    def forward_url(self, to_wxid, xml):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "xml": xml
        }
        return self.call_api("POST", "message/forwardUrl", data=param)

    def forward_mini_app(self, to_wxid, xml, cover_img_url):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "xml": xml,
            "coverImgUrl": cover_img_url
        }
        return self.call_api("POST", "message/forwardMiniApp", data=param)

    def revoke_msg(self, to_wxid, msg_id, new_msg_id, create_time):
        param = {
            "appId": self.app_id,
            "toWxid": to_wxid,
            "msgId": msg_id,
            "newMsgId": new_msg_id,
            "createTime": create_time
        }
        return self.call_api("POST", "message/revokeMsg", data=param)


    #############联系人模块


    def get_contact_list(self):
        param = {"appId": self.app_id}
        return self.call_api("POST", "contacts/fetchContactsList", data=param)

    def get_brief_info(self, wxids):
        param = {
            "appId": self.app_id,
            "wxids": wxids
        }
        return self.call_api("POST", "contacts/getBriefInfo", data=param)

    def get_detail_info(self, wxids):
        param = {
            "appId": self.app_id,
            "wxids": wxids
        }
        return self.call_api("POST", "contacts/getDetailInfo", data=param)

    def search_contacts(self, contacts_info):
        param = {
            "appId": self.app_id,
            "contactsInfo": contacts_info
        }
        return self.call_api("POST", "contacts/search", data=param)

    def agree_friend(self, scene, option, v3, v4, content):
        param = {
            "appId": self.app_id,
            "scene": scene,
            "option": option,
            "v3": v3,
            "v4": v4,
            "content": content
        }
        return self.call_api("POST", "contacts/addContacts", data=param)

    def delete_friend(self, wxid):
        param = {
            "appId": self.app_id,
            "wxid": wxid
        }
        return self.call_api("POST", "contacts/deleteFriend", data=param)

    def set_friend_permissions(self, wxid, only_chat):
        param = {
            "appId": self.app_id,
            "wxid": wxid,
            "onlyChat": only_chat
        }
        return self.call_api("POST", "contacts/setFriendPermissions", data=param)

    def set_friend_remark(self, wxid, remark):
        param = {
            "appId": self.app_id,
            "wxid": wxid,
            "remark": remark
        }
        return self.call_api("POST", "contacts/setFriendRemark", data=param)

    def get_phone_address_list(self, phones):
        param = {
            "appId": self.app_id,
            "phones": phones
        }
        return self.call_api("POST", "contacts/getPhoneAddressList", data=param)

    def upload_phone_address_list(self, phones, op_type):
        param = {
            "appId": self.app_id,
            "phones": phones,
            "opType": op_type
        }
        return self.call_api("POST", "contacts/uploadPhoneAddressList", data=param)

    ##群模块
    def create_chatroom(self, wxids):
        param = {
            "appId": self.app_id,
            "wxid": wxids
        }
        return self.call_api("POST", "group/createChatroom", data=param)

    def modify_chatroom_name(self, chatroom_name, chatroom_id):
        param = {
            "appId": self.app_id,
            "chatroomName": chatroom_name,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/modifyChatroomName", data=param)

    def modify_chatroom_remark(self, chatroom_remark, chatroom_id):
        param = {
            "appId": self.app_id,
            "chatroomRemark": chatroom_remark,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/modifyChatroomRemark", data=param)

    def modify_chatroom_nick_name_for_self(self, nick_name, chatroom_id):
        param = {
            "appId": self.app_id,
            "nickName": nick_name,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/modifyChatroomNickNameForSelf", data=param)

    def invite_member(self, wxids, chatroom_id, reason):
        param = {
            "appId": self.app_id,
            "wxids": wxids,
            "reason": reason,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/inviteMember", data=param)

    def remove_member(self, wxids, chatroom_id):
        param = {
            "appId": self.app_id,
            "wxids": wxids,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/removeMember", data=param)

    def quit_chatroom(self, chatroom_id):
        param = {
            "appId": self.app_id,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/quitChatroom", data=param)

    def disband_chatroom(self, chatroom_id):
        param = {
            "appId": self.app_id,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/disbandChatroom", data=param)

    def get_chatroom_info(self, chatroom_id):
        param = {
            "appId": self.app_id,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/getChatroomInfo", data=param)

    def get_chatroom_member_list(self, chatroom_id):
        param = {
            "appId": self.app_id,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/getChatroomMemberList", data=param)

    def get_chatroom_member_detail(self, chatroom_id, member_wxids):
        param = {
            "appId": self.app_id,
            "memberWxids": member_wxids,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/getChatroomMemberDetail", data=param)
    def get_chatroom_nickname(self, room_id: str = 'null', wxid: str = 'ROOT'):
        '''
        获取群聊中用户昵称 Get chatroom's user's nickname
        群成员如果变了，没有获取到，则重新获取
        :param room_id: 群号(以@chatroom结尾) groupchatid(end with@chatroom)
        :param wxid: wxid(新用户的wxid以wxid_开头 老用户他们可能修改过 现在改不了) wechatid(start with wxid_)
        :return: Dictionary
        '''
        if room_id.endswith("@chatroom") and not wxid.endswith("@chatroom"):
            if room_id in iPadWx.shared_wx_contact_list:
                logger.debug("无需网络获取，本地读取")
                # logger.info(iPadWx.shared_wx_contact_list[room_id])
                member = iPadWx.shared_wx_contact_list[room_id]['memberList']
                # logger.info(member)
                member_info = self.get_user(member, wxid)
                return member_info['displayName'], member_info['nickName']
        return None, None
    def get_user(self,users, username):
        # 使用 filter 函数通过给定的 userName 来找寻符合条件的元素
        res = list(filter(lambda user: user['wxid'] == username, users))

        return res[0] if res else None  # 如果找到了就返回找到的元素（因为 filter 返回的是列表，所以我们取第一个元素），否则返回 None

    def get_chatroom_announcement(self, chatroom_id):
        param = {
            "appId": self.app_id,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/getChatroomAnnouncement", data=param)

    def set_chatroom_announcement(self, chatroom_id, content):
        param = {
            "appId": self.app_id,
            "chatroomId": chatroom_id,
            "content": content
        }
        return self.call_api("POST", "group/setChatroomAnnouncement", data=param)

    def agree_join_room(self, url):
        param = {
            "appId": self.app_id,
            "chatroomName": url
        }
        return self.call_api("POST", "group/agreeJoinRoom", data=param)

    def add_group_member_as_friend(self, member_wxid, chatroom_id, content):
        param = {
            "appId": self.app_id,
            "memberWxid": member_wxid,
            "chatroomId": chatroom_id,
            "content": content
        }
        return self.call_api("POST", "group/addGroupMemberAsFriend", data=param)

    def get_chatroom_qr_code(self, chatroom_id):
        param = {
            "appId": self.app_id,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/getChatroomQrCode", data=param)

    def save_contract_list(self, oper_type, chatroom_id):
        param = {
            "appId": self.app_id,
            "chatroomName": oper_type,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/saveContractList", data=param)

    def admin_operate(self, chatroom_id, wxids, oper_type):
        param = {
            "appId": self.app_id,
            "wxids": wxids,
            "operType": oper_type,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/adminOperate", data=param)

    def pin_chat(self, top, chatroom_id):
        param = {
            "appId": self.app_id,
            "top": top,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/pinChat", data=param)

    def set_msg_silence(self, silence, chatroom_id):
        param = {
            "appId": self.app_id,
            "silence": silence,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/setMsgSilence", data=param)

    def join_room_using_qr_code(self, qr_url):
        param = {
            "appId": self.app_id,
            "qrUrl": qr_url
        }
        return self.call_api("POST", "group/joinRoomUsingQRCode", data=param)

    def room_access_apply_check_approve(self, new_msg_id, chatroom_id, msg_content):
        param = {
            "appId": self.app_id,
            "newMsgId": new_msg_id,
            "msgContent": msg_content,
            "chatroomId": chatroom_id
        }
        return self.call_api("POST", "group/roomAccessApplyCheckApprove", data=param)
    ####下载模块


    def download_image(self, xml, type):
        param = {
            "appId": self.app_id,
            "type": type,
            "xml": xml
        }
        return self.call_api_download("POST", "message/downloadImage", data=param)

    def download_voice(self, xml, msg_id):
        param = {
            "appId": self.app_id,
            "xml": xml,
            "msgId": msg_id
        }
        return self.call_api("POST", "message/downloadVoice", data=param)

    def download_video(self, xml):
        param = {
            "appId": self.app_id,
            "xml": xml
        }
        return self.call_api_download("POST", "message/downloadVideo", data=param)

    def download_emoji_md5(self, emoji_md5):
        param = {
            "appId": self.app_id,
            "emojiMd5": emoji_md5
        }
        return self.call_api("POST", "message/downloadEmojiMd5", data=param)

    def download_cdn_image(self, aes_key, file_id, file_type, total_size, suffix):
        param = {
            "appId": self.app_id,
            "aesKey": aes_key,
            "fileId": file_id,
            "totalSize": total_size,
            "type": file_type,
            "suffix": suffix
        }
        return self.call_api_download("POST", "message/downloadCdn", data=param)
    ###同步收藏夹

    """
    收藏夹模块
    """

    def sync(self, app_id, sync_key):
        """
        同步收藏夹
        """
        data = {
            "appId": app_id,
            "syncKey": sync_key
        }
        return self.call_api("POST", "favor/sync", data)

    def get_content(self, app_id, fav_id):
        """
        获取收藏夹内容
        """
        data = {
            "appId": app_id,
            "favId": fav_id
        }
        return self.call_api("POST", "favor/getContent", data)

    def delete_fav(self, app_id, fav_id):
        """
        删除收藏夹
        """
        data = {
            "appId": app_id,
            "favId": fav_id
        }
        return self.call_api("POST", "favor/delete", data)
    def add_label(self, app_id, label_name):
        """
        添加标签
        """
        data = {
            "appId": app_id,
            "labelName": label_name
        }
        return self.call_api("POST", "label/add", data)

    def delete_label(self, app_id, label_ids):
        """
        删除标签
        """
        data = {
            "appId": app_id,
            "labelIds": label_ids
        }
        return self.call_api("POST", "label/delete", data)

    def list_label(self, app_id):
        """
        获取标签列表
        """
        data = {
            "appId": app_id
        }
        return self.call_api("POST", "label/list", data)

    def modify_member_list(self, app_id, label_ids, wx_ids):
        """
        修改标签成员列表
        """
        data = {
            "appId": app_id,
            "labelIds": label_ids,
            "wxIds": wx_ids
        }
        return self.call_api("POST", "label/modifyMemberList", data)

    ###个人模块
    def get_profile(self):
        """
        获取个人资料
        """
        data = {
            "appId": self.app_id
        }
        return self.call_api("POST", "personal/getProfile", data)

    def get_qr_code(self):
        """
        获取自己的二维码
        """
        data = {
            "appId": ""
        }
        return self.call_api("POST", "personal/getQrCode", data)

    def get_safety_info(self, app_id):
        """
        获取设备记录
        """
        data = {
            "appId": app_id
        }
        return self.call_api("POST", "personal/getSafetyInfo", data)

    def privacy_settings(self, app_id, option, open):
        """
        隐私设置
        """
        data = {
            "appId": app_id,
            "option": option,
            "open": open
        }
        return self.call_api("POST", "personal/privacySettings", data)

    def update_profile(self, app_id, city, country, nick_name, province, sex, signature):
        """
        修改个人信息
        """
        data = {
            "appId": app_id,
            "city": city,
            "country": country,
            "nickName": nick_name,
            "province": province,
            "sex": sex,
            "signature": signature
        }
        return self.call_api("POST", "personal/updateProfile", data)

    def update_head_img(self, app_id, head_img_url):
        """
        修改头像
        """
        data = {
            "appId": app_id,
            "headImgUrl": head_img_url
        }
        return self.call_api("POST", "personal/updateHeadImg", data)
def check_status(wxbot):


    # 获取token
    if not wxbot.token: #首次授权
        ret = wxbot.get_token()
        print(ret)


    if wxbot.bot_wxid:
        ret = wxbot.check_online()
        if ret.get("ret",0)==200 or ret.get("code",-1)==0: #离线了，需要扫码，并且带app_id
            if  ret['data']==False:
                login_status = login_proc(wxbot)
            else:
                login_status=True
            if login_status:
                conf().__setitem__("app_id",wxbot.app_id)
                save_config()

        else: #首次登录
            # 获取登录二维码
            login_status = login_proc(wxbot)

        return login_status
    else:
        wxbot.log_out()
        login_status = login_proc(wxbot)
        return login_status

def login_proc(wxbot):
    # 获取登录二维码
    qr = wxbot.get_qrcode()
    if qr and qr.get("data"):
        if qr['data'].get("qrImgBase64"):
            wxbot.generate_qr_code_html(qr['data']['qrImgBase64'], "qrkh.html")
            # 循环检测扫码状态
            while True:
                response = wxbot.check_qr()
                if response and response.get("data"):
                    status = response["data"].get("status")
                    if status == 1:
                        logger.info("二维码已被扫码")
                    elif status == 2:
                        logger.info("登录已确认")
                        logininfo = response['data']['loginInfo']
                        wxbot.name = logininfo['nickName']
                        wxbot.bot_wxid= logininfo['wxid']


                        return True

                    elif status == 0:
                        logger.info("等待扫码...")
                time.sleep(5)  # 每5秒检测一次
        else:
            logger.info(qr.get("data"))
            return False
    return False

def convert_mp3_to_amr(mp3_file, amr_file):
    # Call ffmpeg to convert MP3 to AMR
    command = [
        'ffmpeg',
        '-i', mp3_file,              # Input file
        '-ac', '1',                  # Set audio channels to 1 (mono)
        '-ar', '8000',               # Set audio sample rate to 8000 Hz (common for AMR)
        '-ab', '12k',                # Set audio bitrate to 12 kbps (common for AMR)
        '-c:a', 'libopencore_amrnb', # Use AMR-NB codec
        amr_file                     # Output file
    ]
    subprocess.run(command, check=True)
#
# def to_pcm(in_path: str) -> tuple[str, int]:
#     """任意媒体文件转 pcm"""
#     out_path = os.path.splitext(in_path)[0] + '.pcm'
#     with av.open(in_path) as in_container:
#         in_stream = in_container.streams.audio[0]
#         sample_rate = in_stream.codec_context.sample_rate
#         with av.open(out_path, 'w', 's16le') as out_container:
#             out_stream = out_container.add_stream(
#                 'pcm_s16le',
#                 rate=sample_rate,
#                 layout='mono'
#             )
#             try:
#                for frame in in_container.decode(in_stream):
#                   frame.pts = None
#                   for packet in out_stream.encode(frame):
#                      out_container.mux(packet)
#             except:
#                pass
#     return out_path, sample_rate
#
#
# def convert_to_silk(media_path: str) -> str:
#     """任意媒体文件转 silk, 返回silk路径"""
#     pcm_path, sample_rate = to_pcm(media_path)
#     silk_path = os.path.splitext(pcm_path)[0] + '.silk'
#     pilk.encode(pcm_path, silk_path, pcm_rate=sample_rate, tencent=True)
#     os.remove(pcm_path)
#     return silk_path
if __name__ == "__main__":
    # Example usage
    #mp3_file = r"D:\BaiduNetdiskDownload\honeybee2024\DEW2-2024暑假复习\wonders mp3\unit 2\A Prairie Guard Dog.mp3"

    #convert_to_silk(mp3_file)
    #exit(0)
    wxbot = iPadWx()
    #wxbot.log_out()
    ret= check_status(wxbot)
    if ret:
        wxbot.init_load()
        #wxbot.send_text("zhaokaihui123","this is a test",ats=None)
        #wxbot.send_image("zhaokaihui123",img_url="http://www.hdgame.top:5712/pic/test.jpg")
        #wxbot.fetch_contacts_list()
        wxbot.send_at_msg("49839968445@chatroom","@大辉辉 测试",ats="zhaokaihui123")
        #wxbot.send_voice("49670972421@chatroom","http://www.hdgame.top:5712/pic/test.silk",8000)

