# encoding:utf-8

import re
import time
from bridge.context import ContextType
from channel.chat_message import ChatMessage
from common.log import logger
from common.tmp_dir import TmpDir
import json
import os
import xml.etree.ElementTree as ET
from config import conf
import requests
from channel.wechat.iPadWx_Beta import iPadWx
import uuid,base64

class WechatMessage(ChatMessage):
    '''

    '''

    def __init__(self, itchat_msg, is_group=False):
        super().__init__(itchat_msg)
        msg_type = None
        self.is_group = False
        self.msg_id = ""
        self.create_time = ""
        
        # 获取app_id
        self.app_id = itchat_msg.get("Appid")
        
        # 从WechatChannel获取bot实例
        from channel.wechat.wechat_channel_ipad import WechatChannel
        if self.app_id:
            self.bot = WechatChannel().init_bot(self.app_id)
        else:
            self.bot = None
            logger.warn("消息中没有app_id，无法初始化bot")

        if 'testMsg' in itchat_msg:
            if itchat_msg["testMsg"] == '回调地址链接成功！':
                return

        if itchat_msg.get("TypeName","") == "Offline" or itchat_msg.get("type_name","") == "Offline":
            logger.info("设备已离线")
            return
        if itchat_msg.get("TypeName","") == "Long_Serve_START_Connect":
            logger.info("心跳包")
            return
        if "Data" in itchat_msg and isinstance(itchat_msg["Data"], dict):
            self.msg_id = itchat_msg['Data'].get("MsgId","001")

        if itchat_msg.get('TypeName',"")=="AddMsg" or itchat_msg.get('type_name',"")=="AddMsg":
            self.msg_id = itchat_msg["Data"]["MsgId"]
            self.create_time = itchat_msg["Data"]['CreateTime']
            if isinstance(itchat_msg["Data"]['FromUserName'],dict):

                self.is_group = itchat_msg["Data"]['FromUserName']['string'].endswith("@chatroom")
            else:
                self.is_group = itchat_msg["Data"]['FromUserName'].endswith("@chatroom")
            if isinstance( itchat_msg["Data"]['FromUserName'],dict):
                self.room_id = itchat_msg["Data"]['FromUserName']['string'] if self.is_group else None
            else:
                self.room_id = itchat_msg["Data"]['FromUserName']if self.is_group else None
            msg_type = itchat_msg["Data"]['MsgType']


        if itchat_msg.get('TypeName',"")=="ModContacts" or itchat_msg.get('type_name',"")=="ModContacts":
            msg_type = 9001 #系统联系人修改消息



        if msg_type == 1:
            self.ctype = ContextType.TEXT
            if self.is_group:
                if isinstance(itchat_msg["Data"]['Content'], dict):
                    content = itchat_msg["Data"]['Content']['string']
                else:
                    content = itchat_msg["Data"]['Content']
                pos =  content.find("\n")
                self.content = content[pos+1:]
                self.from_user_id = content[:pos-1]
                self.to_user_id = itchat_msg["Data"]['ToUserName']['string']

            else:
                if isinstance(itchat_msg["Data"]['Content'], dict):
                    self.content = itchat_msg["Data"]['Content']['string']
                else:
                    self.content = itchat_msg["Data"]['Content']
        elif msg_type==3:#群聊图片
            self.ctype = ContextType.IMAGE
            #self.content = TmpDir().path() + itchat_msg.get("FileName")  # content直接存临时目录路径
            #self._prepare_fn = lambda: itchat_msg.download(self.content)
            pos = itchat_msg["Data"]['Content']['string'].find("\n")
            self.content= itchat_msg["Data"]['Content']['string'][pos+1:]
            xml_data = self.content
            download_image =True
            if download_image:
                time.sleep(2)
                ret = self.bot.download_image(self.content,2)
                if ret:
                    logger.info(ret)
                    if 'data' in ret:
                        fileurl = ret['data']['fileUrl']
                        app_public_end = fileurl.find('/app/public/download') + len('/app/public/download/')
                        fileurl =fileurl[app_public_end:]
                        #http://127.0.0.1:8073/v2/api/download?file=20250210/wx_eSaL7YuRnC3CTCgm1_qGb/cul1fg9euu2odr5gmueg.png
                        download_url = f"{conf().get('base_url_ipad_download')}?file={fileurl}"

                        #self.content = download_image_file(download_url, TmpDir().path())

                        self.content = download_url
                        logger.info(self.content)
                    else:
                        logger.info(ret)
                        self.content = ret['Data']['fileUrl']
                        download_url = f"{conf().get('base_url_ipad_download') }/{ret['Data']['fileUrl']}"
                        #self.content = download_image_file(download_url, TmpDir().path())
                        logger.info(self.content)
                        self.content = download_url
                # self.bot.forward_img("gh_c95e05e75405", self.content)
                #self.content = TmpDir().path() + itchat_msg.get("FileName")  # content直接存临时目录路径
                    self._prepare_fn = lambda: download_image_file(download_url, TmpDir().path())
                    #download_image_file(download_url, TmpDir().path())
                #
            # root = ET.fromstring(xml_data)
            #
            # # Find the <img> tag
            # img_tag = root.find('img')
            #
            # # Extract the necessary attributes
            # aes_key = img_tag.get('aeskey')
            # file_id = img_tag.get('cdnmidimgurl')  # Assuming cdnmidimgurl is the file ID
            # file_type = 2 # Assuming the file type is 'image'
            # total_size = img_tag.get('length')
            # suffix = 'jpg'  # Assuming the suffix is 'jpg' based on common image file extensions
            #
            #
            # #ret = self.bot.download_cdn_image(aes_key, file_id, file_type, total_size, suffix)
            # #if ret['ret']==200:
            # #    logger.debug(ret['Data']['fileUrl'])


        elif msg_type ==43 :
            self.ctype = ContextType.VIDEO
            pos = itchat_msg["Data"]['Content']['string'].find("\n")
            self.content= itchat_msg["Data"]['Content']['string'][pos+1:]
            # ret = self.bot.download_video(self.content)
            # if ret:
            #     logger.info(ret)
            #     self.content = ret['Data']['fileUrl']
            #     download_url = f"{conf().get('base_url_ipad_download')}/{ret['Data']['fileUrl']}"
            #     self.content = download_image_file(download_url, TmpDir().path())
            #     logger.info(self.content)

        elif msg_type ==34 :#群聊语音消息
            self.ctype = ContextType.VOICE
            self.content = itchat_msg["Data"]['Content']['string']
            msg = itchat_msg
            logger.info(msg)

            if 'ImgBuf' in msg['Data'] and 'buffer' in msg['Data']['ImgBuf'] and msg['Data']['ImgBuf']['buffer']:
                silk_data = base64.b64decode(msg['Data']['ImgBuf']['buffer'])
                silk_file_name = f"voice_{str(uuid.uuid4())}.silk"
                logger.info(f"voice file {silk_file_name}")
                silk_file_path = TmpDir().path() + silk_file_name
                logger.info(f"voice file {silk_file_path}")
                with open(silk_file_path, "wb") as f:
                    f.write(silk_data)
                # TODO: silk2mp3

                self.content = silk_file_path
                self._prepare_fn = lambda: download_voice(silk_file_path, TmpDir().path())
                logger.info(f"语音准备消息下载成功")
            # result = self.bot.download_voice(self.content,msg_id=self.msg_id)
            # if result and result.get("ret",500) == 200:
            #     voice_url = result.get("Data",{}).get("fileUrl")
            #     file_name = voice_url.split("/")[-1].split("?")[0]
            #     self.content =  TmpDir().path()+file_name  # content直接存临时目录路径
            #     #self._prepare_fn = lambda: itchat_msg.download(self.content)
            #     #download_image_file(voice_url, TmpDir().path())
            #     self._prepare_fn = lambda: download_image_file(voice_url, TmpDir().path())
            # else:
            #     logger.info(f"语音消息下载失败")
            #     self.content=None
            #     self._prepare_fn=None
        elif msg_type in ['8006', '9006']:  # 群聊地图位置消息
            self.ctype = ContextType.MAP
        elif msg_type in ['8007', '9007']:#群聊表情包
            self.ctype = ContextType.EMOJI
            self.content = itchat_msg["Data"]['Content']['string']
        elif msg_type in ['8008', '9008']:#群聊名片
            self.ctype = ContextType.CARD
            self.content = itchat_msg["Data"]['Content']['string']
        elif msg_type in ['7005','9005',10002,49]: #xml格式的 10002 进群,电话
            pos = itchat_msg["Data"]['Content']['string'].find("\n")
            self.content = itchat_msg["Data"]['Content']['string'][pos + 1:]
            result = self.parse_wechat_message( self.content)
            if result['message_type'] =='sysmsgtemplate' and  result['subtype'] =='invite' :
                # 这里只能得到nickname， actual_user_id还是机器人的id
                self.ctype = ContextType.JOIN_GROUP
                if result.get("joiners_usernames",[]):
                    self.actual_user_nickname = result['joiners_usernames'][0]['nickname']
                    #self.actual_user_nickname = result['joiners_usernames'][0]['nickname']
                #self.content= f"{result['inviter_username']['nickname']} 邀请 {self.actual_user_nickname } 加入了群聊!"
            elif result['message_type'] =='pat':
                self.ctype = ContextType.PATPAT
                if is_group:
                    self.from_user_id = result['from_user_id']
                    self.actual_user_id = result['from_user_id']
                    self.to_user_id = itchat_msg["Data"]['ToUserName']['string']
                    displayName, nickname = self.get_chatroom_nickname(self.room_id, self.actual_user_id)
                    self.actual_user_nickname = displayName or nickname
                    self.content = result['action']
            elif result['message_type'] =='appmsg' and  result['subtype'] =='reference' :
                # 这里只能得到nickname， actual_user_id还是机器人的id
                '''
                {
                'subtype': 'reference',
                'title': title,
                'reference': {
                    'type': refer_type,
                    'svrid': svrid,
                    'fromusr': fromusr,
                    'chatusr': chatusr,
                    'displayname': displayname,
                    'content': content.strip()
                    }
                }
                '''
                if result["reference"]["url"] and result["reference"]["url"] !="N/A":
                    self.ctype = ContextType.TEXT
                    #self.content = result["title"] #引用说的话
                    self.content = f'{result["title"]} {result["reference"]["url"]}'
                else:
                    self.ctype = ContextType.XML

            elif result['message_type'] ==19 and 'title' in  result  and  result['title'] =='群聊的聊天记录':

                # 这里只能得到nickname， actual_user_id还是机器人的id
                self.ctype = ContextType.LINK
                self.content = json.dumps(result["image_infos"]) # 内容 list
            elif result['message_type'] == 'ilinkvoip':
                self.ctype = ContextType.VOICE_CALL
                self.content =  itchat_msg["Data"]['Content']['string']

            elif "你已添加了" in self.content:  #通过好友请求
                self.ctype = ContextType.ACCEPT_FRIEND

            elif is_group and ("移出了群聊" in self.content):
                self.ctype = ContextType.EXIT_GROUP
                self.content = self.content
                self.actual_user_nickname = re.findall(r"\"(.*?)\"",self.content)

            elif "你已添加了" in self.content:  #通过好友请求
                self.ctype = ContextType.ACCEPT_FRIEND


            else:
                self.ctype = ContextType.XML
                pass
                #raise NotImplementedError("Unsupported note message: " + itchat_msg["msg"])
        elif msg_type in ['8005','9005']:
            self.ctype = ContextType.FILE
            #self.content = TmpDir().path() + itchat_msg.get("FileName")  # content直接存临时目录路径
            if self.content:
                pass
                #self._prepare_fn = lambda: itchat_msg.download(self.content)
        elif msg_type == '9006':
            self.ctype = ContextType.XML
            self.content = itchat_msg.get("msg")

        elif  msg_type ==9001: #群成员变化会出现这个消息
            self.is_group = False
            self.room_id = itchat_msg["Data"]['UserName']['string']
            self.from_user_nickname = self.room_id = itchat_msg["Data"]['NickName']['string']
            self.from_user_id = itchat_msg["Data"]['UserName']['string']
            self.content = itchat_msg['Data']
            self.ctype = ContextType.EXIT_GROUP
            #self.
            pass
        elif msg_type==50:
            self.ctype = ContextType.VOICE_CALL
            self.content = itchat_msg["Data"]['Content']['string']

        elif msg_type==51:
            self.ctype = ContextType.TEXT
            self.content = itchat_msg["Data"]['Content']['string']

        elif msg_type ==37: #添加好友消息
            # 解析 XML
            xml_data = itchat_msg["Data"]['Content']['string']
            root = ET.fromstring(xml_data)

            # 获取 scene 和 ticket
            scene = root.get('scene')
            ticket = root.get('ticket')
            self.ctype = ContextType.ADD_FRIEND
            logger.info(f"scene: {scene}, ticket: {ticket}")
            self.content = xml_data
        else:
            pass
            raise NotImplementedError("Unsupported message type: Type:{} MsgType:{}".format(msg_type,
                                                                                            msg_type))
        if not self.from_user_id:
            if 'FromUserName' in itchat_msg["Data"]:
                self.from_user_id = itchat_msg["Data"]['FromUserName']['string']
                self.to_user_id = itchat_msg["Data"]['ToUserName']['string']
            else:
                self.from_user_id=""
                self.to_user_id=""



        # 虽然from_user_id和to_user_id用的少，但是为了保持一致性，还是要填充一下
        # 以下很繁琐，一句话总结：能填的都填了。
        #other_user_id: 对方的id，如果你是发送者，那这个就是接收者id，如果你是接收者，那这个就是发送者id，如果是群消息，那这一直是群id(必填)

        try:  # 陌生人时候, User字段可能不存在
            # my_msg 为True是表示是自己发送的消息
            self.my_msg = self.from_user_id== self.bot.bot_wxid
            if self.is_group:
                self.other_user_id = self.room_id
                displayName,nickname = self.get_chatroom_nickname(self.room_id, self.from_user_id)

                self.from_user_nickname = nickname
                self.self_display_name =  displayName or nickname
                _,self.to_user_nickname  = self.get_chatroom_nickname(self.room_id, self.to_user_id)

                #self.to_user_nickname = self.get_chatroom_nickname(self.room_id, self.to_user_id)
                self.other_user_nickname = iPadWx.shared_wx_contact_list.get(self.room_id,{}).get('nickName',"")

            else:
                if self.my_msg:#机器人发送
                    self.other_user_id = itchat_msg["Data"]['FromUserName']['string']
                    self.other_user_nickname = self.to_user_nickname
                else:
                    self.from_user_id = itchat_msg["Data"]['FromUserName']['string']
                    self.to_user_id = itchat_msg["Data"]['ToUserName']['string']

                    if self.from_user_id not in iPadWx.shared_wx_contact_list:
                        self.save_single_contact(self.from_user_id)
                    if self.from_user_id in iPadWx.shared_wx_contact_list:
                        self.from_user_nickname = iPadWx.shared_wx_contact_list[self.from_user_id]['nickName']
                    if self.to_user_id not in iPadWx.shared_wx_contact_list:
                        self.save_single_contact(self.to_user_id)
                    if self.to_user_id  in iPadWx.shared_wx_contact_list:
                        self.to_user_nickname = iPadWx.shared_wx_contact_list[self.to_user_id]['nickName']
                    self.other_user_id = self.from_user_id
                    self.other_user_nickname = self.from_user_nickname
            if itchat_msg["Data"]['FromUserName']['string']:
                pass
                # 自身的展示名，当设置了群昵称时，该字段表示群昵称
                #self.self_display_name = self.from_user_nickname
        except KeyError as e:  # 处理偶尔没有对方信息的情况
            logger.warn("[WX]get other_user_id failed: " + str(e))

        if self.is_group:
            msg_source = itchat_msg["Data"]["MsgSource"]
            at_list_match = re.findall(r"<atuserlist><!\[CDATA\[(.*?)\]\]></atuserlist>", msg_source)
            self.at_list = at_list_match[0].split(',') if at_list_match else []
            self.is_at = True if self.at_list else False

            #content = itchat_msg["Data"]["Content"]['string']
            #self.content = re.sub(r"@\S+\u2005", "", content).strip()

            subtract_res = self.content
            for at_id in self.at_list:
                at_info = self.get_user(iPadWx.shared_wx_contact_list.get(self.room_id,{}).get("memberList",""), at_id)
                if at_info:
                    nickname = at_info['nickName']
                    if nickname:
                        pattern = f"@{re.escape(nickname)}(\u2005|\u0020)"
                        subtract_res = re.sub(pattern, r"", subtract_res)
                displayName = at_info['displayName'] if at_info['displayName'] else ""
                if displayName:
                    pattern = f"@{re.escape(at_info['displayName'])}(\u2005|\u0020)"
                    subtract_res = re.sub(pattern, r"", subtract_res)
                # 如果昵称没去掉，则用替换的方法
                if subtract_res == self.content:
                    # 前缀移除后没有变化，使用群昵称再次移除
                    # pattern = f"@{re.escape(context['msg'].self_display_name)}(\u2005|\u0020)"
                    subtract_res = self.content.replace("@" + nickname, "").replace(
                        "@" + displayName, "")
            self.content = subtract_res

            #self.at_list_member = self.bot.shared_wx_contact_list[self.room_id]['chatRoomMembers']
            if not self.actual_user_id:
                self.actual_user_id = itchat_msg["Data"]["FromUserName"]['string']
            if self.ctype not in [ContextType.JOIN_GROUP, ContextType.PATPAT, ContextType.EXIT_GROUP]:
                pass
                self.actual_user_nickname = self.self_display_name #发送者的群昵称 还是本身的昵称

        # 添加app_id属性
        self.app_id = itchat_msg.get("AppId")  # 从消息中获取AppId

    def get_user(self,users, username):
        # 使用 filter 函数通过给定的 userName 来找寻符合条件的元素
        if not isinstance(users,list):
            return None
        res = list(filter(lambda user: user['wxid'] == username, users))

        return res[0] if res else None  # 如果找到了就返回找到的元素（因为 filter 返回的是列表，所以我们取第一个元素），否则返回 None
    def get_chatroom_nickname(self, room_id: str = 'null', wxid: str = 'ROOT'):
        '''
        获取群聊中用户昵称 Get chatroom's user's nickname
        群成员如果变了，没有获取到，则重新获取
        :param room_id: 群号(以@chatroom结尾) groupchatid(end with@chatroom)
        :param wxid: wxid(新用户的wxid以wxid_开头 老用户他们可能修改过 现在改不了) wechatid(start with wxid_)
        :return: Dictionary
        '''
        if room_id is None or wxid is None:
            return None,None
        if room_id.endswith("@chatroom") and not wxid.endswith("@chatroom"):
            if room_id in iPadWx.shared_wx_contact_list :
                logger.debug("无需网络获取，本地读取")
                #logger.info(iPadWx.shared_wx_contact_list[room_id])
                member = iPadWx.shared_wx_contact_list[room_id]['memberList']
                #logger.info(member)
                member_info = self.get_user(member, wxid)

            else:
                #本地不存在群信息，网络获取

                members = self.bot.get_chatroom_info(room_id)
                if members and members.get("code",1) == 0:
                    member_info = self.get_user(members['Data']['memberList'], wxid)
                    iPadWx.shared_wx_contact_list[room_id]=members['Data']
                    self.bot.save_contact()
                else:
                    member_info = None

            #本地群存在，但是成员没找到，需要网络获取
            if not member_info:
                members = self.bot.get_chatroom_info(room_id)
                if members and members.get("code",1)==0:
                    member_info = self.get_user(members['Data'], wxid)
                    iPadWx.shared_wx_contact_list[room_id] = members['Data']
                    self.bot.save_contact()


            if member_info:
                return  member_info['displayName'] , member_info['nickName']
        return None,None

    def parse_wechat_message(self,xml_data):
        def get_member_info(member_element):
            if member_element is not None:
                username = member_element.findtext('.//username').strip()
                nickname = member_element.findtext('.//nickname').strip()
                return {
                    'username': username,
                    'nickname': nickname
                }
            else:
                return None
        try:
            # 解析XML
            root = ET.fromstring(xml_data)
        except Exception as e:
            logger.error(f"解析XML失败: {e}")
            return {'message_type': -1, 'info': '未知消息类型'}

        # 获取消息类型
        message_type = root.get('type')
        refermsg = root.find('.//refermsg')
        # 根据消息类型提取信息
        if message_type == 'pat':
            # 拍一拍消息
            from_username = root.find('.//fromusername').text if root.find('.//fromusername') is not None else None
            template_content = root.find('.//template').text if root.find('.//template') is not None else None
            return {
                'message_type': message_type,
                'from_user_id': from_username,
                'action': template_content
            }
        elif message_type == 'sysmsgtemplate':
            # 系统消息，可能是邀请或撤回
            sub_type = root.find('./subtype').text if root.find('./subtype') is not None else None
            sub_type = root.find('.//sysmsgtemplate/content_template[@type="tmpl_type_profile"]')
            if sub_type:

                # 获取邀请者信息
                inviter_link = root.find('.//link_list/link[@name="username"]')
                inviter = get_member_info(inviter_link.find('.//member') if inviter_link is not None else None)

                # 获取加入群聊的成员信息
                names_link = root.find('.//link_list/link[@name="names"]')
                members = names_link.findall('.//memberlist/member') if names_link is not None else []
                joiners = [get_member_info(member) for member in members if get_member_info(member)]

                return {
                    'message_type': message_type,
                    'subtype': "invite",
                    'inviter_username': inviter,
                    'joiners_usernames': joiners
                }
            else:
                return {'message_type': message_type, 'subtype': sub_type, 'info': '未知系统消息类型'}
        elif message_type == 'revokemsg':
            # 消息撤回
            session = root.find('./session').text if root.find('./session') is not None else None
            msgid = root.find('./revokemsg/msgid').text if root.find('./revokemsg/msgid') is not None else None
            newmsgid = root.find('./revokemsg/newmsgid').text if root.find('./revokemsg/newmsgid') is not None else None
            replacemsg = root.find('./revokemsg/replacemsg').text if root.find(
                './revokemsg/replacemsg') is not None else None

            # 返回撤回消息的字典
            return {
                'message_type': 'revokemsg',
                'session': session,
                'original_message_id': msgid,
                'new_message_id': newmsgid,
                'replace_message': replacemsg
            }
        elif message_type == 'NewXmlChatRoomAccessVerifyApplication':
            # 提取关键信息
            # 提取邀请人用户名
            inviter_username = root.find('.//inviterusername').text if root.find(
                './/inviterusername') is not None else "N/A"

            # 从 <text> 标签中提取邀请人的昵称
            text_content = root.find('.//text').text if root.find('.//text') is not None else ""
            start_index = text_content.find('"') + 1
            end_index = text_content.find('"', start_index + 1)
            inviter_nickname = text_content[start_index:end_index] if start_index < end_index else "N/A"

            room_name = root.find('.//RoomName').text if root.find('.//RoomName') is not None else "N/A"
            invitation_reason = root.find('.//invitationreason').text if root.find(
                './/invitationreason') is not None else "N/A"

            joiners = []
            memberlist = root.find('.//memberlist')
            if memberlist is not None:
                for member in memberlist.findall('member'):
                    username = member.find('username').text if member.find('username') is not None else "N/A"
                    nickname = member.find('nickname').text if member.find('nickname') is not None else "N/A"
                    headimgurl = member.find('headimgurl').text if member.find('headimgurl') is not None else "N/A"
                    joiners.append({
                        'username': username,
                        'nickname': nickname,
                        'headimgurl': headimgurl
                    })

                # 构建JSON结构
            message_info = {
                'message_type': 'NewXmlChatRoomAccessVerifyApplication',
                'subtype': 'invite',
                'inviter_username': inviter_username,
                'inviter_nickname': inviter_nickname,
                'room_name': room_name,
                'invitation_reason': invitation_reason,
                'joiners': joiners
            }

            return message_info
        elif message_type == 'ilinkvoip':
            return {'message_type': message_type, 'info': '语音电话'}
        elif refermsg is not None:
            # 这是一个引用消息
            logger.info("引用消息存在，提取关键信息：")

            appmsg = root.find('appmsg')
            title = appmsg.find('title').text if appmsg.find('title') is not None else "N/A"


            svrid = refermsg.find('svrid').text if refermsg.find('svrid') is not None else "N/A"
            fromusr = refermsg.find('fromusr').text if refermsg.find('fromusr') is not None else "N/A"
            chatusr = refermsg.find('chatusr').text if refermsg.find('chatusr') is not None else "N/A"
            displayname = refermsg.find('displayname').text if refermsg.find('displayname') is not None else "N/A"
            content = refermsg.find('content').text if refermsg.find('content') is not None else "N/A"
            refer_type = refermsg.find('type').text if refermsg.find('type') is not None else "N/A"
            try:
                root2 = ET.fromstring(content)
                url = root2.find('.//url').text if root2.find('.//url') is not None else "N/A"
                #refer_type = refermsg.find('type').text if refermsg.find('type') is not None else "N/A"
            except:
                url = ""
                #refer_type=None
            message_info = {
                'message_type': 'appmsg',
                'title': title,
                'content': content
            }
            # 添加引用消息的信息
            message_info.update({
                'subtype': 'reference',
                'title': title,
                'reference': {
                    'type': refer_type,
                    'svrid': svrid,
                    'fromusr': fromusr,
                    'chatusr': chatusr,
                    'displayname': displayname,
                    'content': content,
                    'url': url,
                }
            })
            # 输出提取的信息
            logger.info(f"消息内容: {title}")
            logger.info(f"引用消息类型: {refer_type}")
            logger.info(f"消息ID: {svrid}")
            logger.info(f"发送人: {fromusr}")
            logger.info(f"聊天群: {chatusr}")
            logger.info(f"显示名: {displayname}")
            logger.info(f"引用消息: {content}")
            logger.info(f"文章URl: {url}")
            return message_info
        else:
            # 提取关键信息
            title = root.find('.//title').text if root.find('.//title') is not None else ''
            message_type = root.find('.//type').text if root.find('.//type') is not None else ''
            if message_type.isdigit():
                message_type = int(message_type)
            if title =='群聊的聊天记录' and message_type ==19:
                from_username = root.find('.//fromusername').text if root.find('.//fromusername') is not None else ''
                # 提取图片信息
                images_info = []
                recorditem = root.findall(".//recorditem")
                # 遍历datalist中的所有dataitem元素
                root2 = ET.fromstring(recorditem[0].text)
                for dataitem in root2.findall('.//datalist/dataitem'):
                    # 提取dataitem中的信息
                    image_info = {
                        # 'htmlid': dataitem.get('htmlid'),
                        'datatype': dataitem.get('datatype'),
                        # 'dataid': dataitem.get('dataid'),
                        # 'messageuuid': dataitem.find('.//messageuuid').text if dataitem.find('.//messageuuid') is not None else '',
                        # 'cdnthumburl': dataitem.find('.//cdnthumburl').text if dataitem.find('.//cdnthumburl') is not None else '',
                        'sourcetime': dataitem.find('.//sourcetime').text if dataitem.find(
                            './/sourcetime') is not None else '',
                        # 'fromnewmsgid': dataitem.find('.//fromnewmsgid').text if dataitem.find('.//fromnewmsgid') is not None else '',
                        # 'datasize': dataitem.find('.//datasize').text if dataitem.find('.//datasize') is not None else '',
                        # 'thumbfullmd5': dataitem.find('.//thumbfullmd5').text if dataitem.find('.//thumbfullmd5') is not None else '',
                        'filetype': dataitem.find('.//filetype').text if dataitem.find(
                            './/filetype') is not None else '',
                        # 'cdnthumbkey': dataitem.find('.//cdnthumbkey').text if dataitem.find('.//cdnthumbkey') is not None else '',
                        'sourcename': dataitem.find('.//sourcename').text if dataitem.find(
                            './/sourcename') is not None else '',
                        'datadesc': dataitem.find('.//datadesc').text if dataitem.find(
                            './/datadesc') is not None else '',
                        # 'cdndataurl': dataitem.find('.//cdndataurl').text if dataitem.find('.//cdndataurl') is not None else '',
                        # 'sourceheadurl': dataitem.find('.//sourceheadurl').text if dataitem.find('.//sourceheadurl') is not None else '',
                        # 'fullmd5': dataitem.find('.//fullmd5').text if dataitem.find('.//fullmd5') is not None else ''
                    }
                    # 将提取的信息添加到images_info列表中
                    images_info.append(image_info)

                # 构建JSON结构
                message_info = {
                    'title': title,
                    'message_type': message_type,
                    'from_username': from_username,
                    'image_infos': images_info
                }

                # 将结果转换为JSON字符串
                json_result = json.dumps(message_info, ensure_ascii=False, indent=2)

                return  message_info
            return {'message_type': message_type, 'info': '未知消息类型'}

    # def load_contact(self):
    #     if not self.bot:
    #         logger.warn("bot未初始化，无法加载联系人")
    #         return
    #
    #     if os.path.exists(f"contact_beta_{self.app_id}.json"):
    #         iPadWx.shared_wx_contact_list = json.load(open(f"contact_beta_{self.app_id}.json", 'r', encoding='utf-8'))
    #         logger.info(f"读取联系人!")
    #     else:
    #         iPadWx.shared_wx_contact_list = {}

    def save_single_contact(self, user_id):
        if not self.bot:
            logger.warn("bot未初始化，无法保存联系人")
            return

        result = self.bot.get_brief_info([user_id,])
        # 将好友保存到联系人中
        if result.get('ret') == 200 and result.get('Data')[0]:
            logger.info(f"用户昵称不存在,重新获取用户信息")
            info = result.get('Data', {})[0]

            if user_id not in iPadWx.shared_wx_contact_list:
                iPadWx.shared_wx_contact_list[user_id] = info
                self.bot.save_contact()

def download_voice(voice_url, temp_dir):
    http_addr = conf().get("http_hook_ipad")

    parts = http_addr.split("/")
    result = "/".join(parts[:-1])

    result = f"{result}//{voice_url}"
    logger.info(f"语音地址 {result}")
    return result

def download_image_file(image_url, temp_dir):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
    }
    # 设置代理
    # self.proxies
    # , proxies=self.proxies
    response = requests.get(image_url, headers=headers, stream=True, timeout=60 * 5)
    if response.status_code == 200:

        # 生成文件名
        file_name = image_url.split("/")[-1].split("?")[0]

        # 检查临时目录是否存在，如果不存在则创建
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        # 将文件保存到临时目录
        file_path = os.path.join(temp_dir, file_name)
        with open(file_path, 'wb') as file:
            file.write(response.content)
        return file_path
    else:
        logger.info(f"[Dingtalk] Failed to download image file, {response.content}")
        return None
