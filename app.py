# encoding:utf-8
import os.path
import signal
import sys
from channel import channel_factory
from common import const
from plugins import *
import threading
from quart import jsonify, render_template, send_file, Quart, request, Response, redirect, session, url_for
import concurrent.futures
import asyncio
import traceback
from werkzeug.security import generate_password_hash
import aiohttp
import json
import uuid
import time
from datetime import datetime
from models import Session_sql
from models import AutoReply,ScheduledTasks,MediaMessage,WeChatAccount
from sqlalchemy.exc import PendingRollbackError#
#from flask_sqlalchemy import SQLAlchemy
from pymysql.err import OperationalError
from blueprints import user_bp,group_bp,plugins_bp
from config import load_config
from functools import wraps
from blueprints.decorators import login_required

hashed_password = generate_password_hash('123456789', method='pbkdf2:sha256', salt_length=8)
quart_app = Quart(__name__)
quart_app.register_blueprint(user_bp)  # 不带 url_prefix
quart_app.register_blueprint(group_bp)  # 不带 url_prefix
quart_app.register_blueprint(plugins_bp)  # 不带 url_prefix
max_worker = 5
ch = None
wxbot = None
quart_app.secret_key = 'secret_123'  # 替换为您的秘密密钥
URL = 'mysql+pymysql://root:adminadmin_asdf@www.hdgame.top:3316/wechat_bot?connect_timeout=60'
quart_app.config['SQLALCHEMY_DATABASE_URI'] = URL
quart_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
quart_app.config['SQLALCHEMY_POOL_RECYCLE'] = 30
quart_app.config['SQLALCHEMY_POOL_SIZE'] = 500
quart_app.config['SQLALCHEMY_POOL_TIMEOUT'] = 10
quart_app.config['SQLALCHEMY_MAX_OVERFLOW'] = 50
load_config()

channel_name = conf().get("channel_type", "wx")
if channel_name == "wx":
    from channel.wechat.wechat_channel import WechatChannel
    from channel.wechat.wechat_message import WechatMessage
    from channel.wechat.wechat_channel import message_handler
    from channel.wechat.iPadWx import iPadWx

    ch = WechatChannel()
    wxbot = iPadWx()
elif channel_name == "wx-beta":
    from channel.wechat.wechat_channel_ipad import WechatChannel
    from channel.wechat.wechat_message_ipad import WechatMessage
    from channel.wechat.wechat_channel_ipad import message_handler
    from channel.wechat.iPadWx_Beta import iPadWx

    wxbot = iPadWx()
    ch = WechatChannel()
elif channel_name == "wx-hook":
    from channel.wechat.wechat_channel_hook import WechatChannel
    from channel.wechat.wechat_channel_hook import message_handler
    from channel.wechat.wechat_message_hook import WechatMessage

    ch = WechatChannel()
    from channel.wechat.Wx_Zhang import Wx_Zhang

    wxbot = Wx_Zhang()


# Number of max retries
MAX_RETRIES = 3
SLEEP_TIME_SEC = 1  # Time to wait before retrying
def retry_on_operational_error(func):
    def wrapper(*args, **kwargs):
        retries = MAX_RETRIES
        while retries > 0:
            try:
                return func(*args, **kwargs)
            except OperationalError as e:
                retries -= 1
                if retries == 0:
                    raise  # Re-raise the exception if all retries failed
                print(f"Lost connection. Retrying in {SLEEP_TIME_SEC} seconds... ({retries} attempts left)")
                time.sleep(SLEEP_TIME_SEC)
                # Optionally, you can check and create a new session here if it's disconnected

    return wrapper
def sigterm_handler_wrap(_signo):
    old_handler = signal.getsignal(_signo)

    def func(_signo, _stack_frame):
        print("Signal {} received, exiting...".format(_signo))
        conf().save_user_datas()
        if callable(old_handler):
            return old_handler(_signo, _stack_frame)
        sys.exit(0)

    signal.signal(_signo, func)


def start_channel(channel_name: str):
    logger.info("加载插件2")
    channel = channel_factory.create_channel(channel_name)
    if channel_name in ["wx", "wx-beta", "wx-hook", "wxy", "terminal", "wechatmp", "wechatmp_service", "wechatcom_app",
                        "wework", const.FEISHU, const.DINGTALK]:
        PluginManager().load_plugins()

    if conf().get("use_linkai"):
        try:
            from common import linkai_client
            threading.Thread(target=linkai_client.start, args=(channel,)).start()
        except Exception as e:
            pass
    channel.startup()


async def listen_ws(ws, session):
    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            try:
                print("Received message:", msg.data)

                # 解析原始消息
                original_message = json.loads(msg.data)

                data = json.loads(original_message['data'])
                if data.get("type") == -1:
                    continue

                # cmsg = WechatMessage(json.loads(msg.data), True)
                # await message_handler_with_debug(cmsg, ch)
                if original_message.get("code") == 200:
                    data = json.loads(original_message["data"])

                    # 转换消息格式
                    transformed_message = transform_message(data)

                    # 发送到指定HTTP接口
                    await send_to_http(transformed_message, session)
            except Exception as e:
                print(f"Error in message processing: {e}")
                traceback.print_exc()
        elif msg.type == aiohttp.WSMsgType.ERROR:
            print(f"WebSocket error: {ws.exception()}")


def transform_message(data):
    # 生成唯一ID
    unique_id = str(uuid.uuid4().int)[:19]
    timestamp = int(time.time())
    formatted_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 转换为目标格式
    transformed = {
        "msg": data.get("content"),
        "group": data.get("wxid").endswith("@chatroom"),
        "self": False,  # 假设默认不是自己发送的消息
        "from_id": data.get("sender"),
        "to_id": "wxid_6q3ar4xb7m1922",  # 假设这个是固定的 bot ID
        "uuid": unique_id,
        "msg_id": str(timestamp),
        "arr_at": formatted_time,
        "type": "9001",  # 假设这个是固定的消息类型
        "bot_id": "wxid_6q3ar4xb7m1922",  # 假设这个是固定的 bot ID
        "room_id": data.get("wxid"),
        "at_ids": []  # 假设这个是固定的 at_ids
    }

    return transformed


async def send_to_http(transformed_message, session):
    port = conf().get("wechatipad_port", 5711)
    url = "http://127.0.0.1:{0}/chat".format(port)
    try:
        async with session.post(url, json=transformed_message) as response:
            if response.status == 200:
                print("Message successfully sent to HTTP endpoint.")
            else:
                print(f"Failed to send message, HTTP status: {response.status}")
    except Exception as e:
        print(f"Error sending message to HTTP: {e}")
        traceback.print_exc()


async def handle_ws_messages():
    ws_url = conf().get("ws_url", 'ws://127.0.0.1:5555/websocket')

    headers = {
        "we-token": conf().get('token'),
        "we-auth": conf().get('auth')
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.ws_connect(ws_url) as ws:
            print("WebSocket connection opened")
            await listen_ws(ws, session)


async def message_handler_with_debug(msg, channel):
    print("Handling message:", msg)
    await message_handler(msg, channel)


async def run_servers():
    wss_server = False
    http_server = True
    logger.info("启动服务")
    start_database_task = False
    if start_database_task:
        from apscheduler.schedulers.background import BackgroundScheduler
        logger.info("启动数据库服务")
        scheduler = BackgroundScheduler()
        scheduler.add_job(keep_connection_alive, 'interval', minutes=1)
        scheduler.start()

    if wss_server and not http_server:

        ws_task = asyncio.create_task(handle_ws_messages())
        await asyncio.gather(ws_task, )
    elif http_server and not wss_server:
        channel_name = conf().get("channel_type", "wx")
        if channel_name == "wx":
            port = conf().get("wechatipad_port", 5711)
        else:
            port = conf().get("wechatipadbeta_port", 5711)
        http_task = asyncio.create_task(quart_app.run_task("0.0.0.0", port=port, debug=True))
        await asyncio.gather(http_task)
    elif wss_server and http_server:
        port = conf().get("wechatipad_port", 5711)
        ws_task = asyncio.create_task(handle_ws_messages())
        http_task = asyncio.create_task(quart_app.run_task("0.0.0.0", port=port, debug=True))
        await asyncio.gather(ws_task, http_task)


# @quart_app.before_serving
def run():
    try:
        logger.info("加载配置")
        load_config()
        sigterm_handler_wrap(signal.SIGINT)
        sigterm_handler_wrap(signal.SIGTERM)
        logger.info("加载插件1")
        channel_name = conf().get("channel_type", "wx")
        start_channel(channel_name)

        # asyncio.run(run_servers())
    except Exception as e:
        print("App startup failed!")
        traceback.print_exc()


run()




@quart_app.route("/chat", methods=["POST", 'GET'])
async def chat():
    # 类常量
    global ch
    global cmsg
    FAILED_MSG = '{"success": false}'
    SUCCESS_MSG = '{"success": true}'
    MESSAGE_RECEIVE_TYPE = "8001"
    if request.method == "POST":
        try:
            msg = await request.get_json()
            if msg:
                #logger.info(msg)
                if "成功" in msg.get("testMsg", ""):
                    logger.info(msg)
                    return jsonify({
                        "ret": 200,
                        "message": "Message received"
                    })
            else:
                return Response("Message failed", mimetype='text/plain')
        except Exception as e:
            logger.error(e)
            logger.error(msg)
    ch = WechatChannel()
    try:
        try:
            msg = await request.get_json()
            # 确保将所有二进制字段解码为UTF-8
            # for key, value in msg.items():
            #     if isinstance(value, dict):
            #         for sub_key, sub_value in value.items():
            #             if isinstance(sub_value, dict) and 'string' in sub_value:
            #                 # 解码UTF-8字符串
            #                 value[sub_key] = sub_value['string'].encode('latin1').decode('utf-8')
            logger.info(f"[Wechat] receive request: {msg}")
            # logger.debug(f"[Wechat] receive request: {msg}")
            if msg:
                if msg.get("testMsg", "") == "验证回调地址是否可用":
                    return Response("Message received", mimetype='text/plain')
            else:
                return Response("Message failed", mimetype='text/plain')
        except Exception as e:
            logger.error(e)
            return FAILED_MSG
        # if "TypeName" in msg:
        #     if msg["TypeName"] != "AddMsg" or msg["Data"]["MsgType"] != 1:
        #         logger.debug("[WX]skip message {}".format(msg))
        #         return Response("Message skiped", mimetype='text/plain')
        #     elif msg["Data"]["FromUserName"]["string"]!= "53166313936@chatroom":
        #         pass
        #         logger.debug("[WX]skip message {}".format(msg))
        #         return Response("Message skip2", mimetype='text/plain')


        try:
            cmsg = WechatMessage(msg, True)
        except NotImplementedError as e:
            logger.debug("[WX]group message {} skipped: {}".format(msg, e))
            return jsonify({
                "ret": 200,
                "message": "Message received"
            })
        # if cmsg.is_group and cmsg.other_user_nickname in ['测试群'] and cmsg.ctype ==1:
        #    return Response("Message received", mimetype='text/plain')
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_worker):
            asyncio.create_task(
                # .handle_group(cmsg)
                message_handler(cmsg, ch)
            ).add_done_callback(callback)

        # return a response
        return jsonify({
            "ret": 200,
            "message": "Message received"
        })

    except Exception as error:
        logger.error("".join(traceback.format_exc()))
        traceback.print_exc()
        logger.error(f"An error occurred: {error}")

        return Response(str(error), mimetype='text/plain')


@quart_app.route('/pic/<path:filename>')
async def serve_pic(filename):
    # 构造文件在服务器上的完整路径
    file_path = os.path.join('pic', filename)

    # 确保文件存在于所提供的路径
    if os.path.isfile(file_path):
        return await send_file(file_path)
    else:
        # 文件不存在，返回404错误
        return await send_file('404.html'), 404


@quart_app.route('/plugins/food_calorie/pic/<path:filename>')
async def serve_food_calorie_pic(filename):
    file_path = os.path.join('plugins', 'food_calorie', 'pic', filename)

    if os.path.isfile(file_path):
        return await send_file(file_path)
    else:
        return await send_file('404.html'), 404


def callback(worker):
    worker_exception = worker.exception()
    if worker_exception:
        logger.error(worker_exception)


@quart_app.route("/send_msg", methods=["GET","POST"])
async def send_msg():
    global wxbot
    if request.method == 'POST':
        data = await request.get_json()
        to_id = data.get('to_id',"")
        text = data.get('text',"")
        content = data.get('content',"")
        title = data.get('title',"")
        at_id = data.get('at_id',"")
        from_wxid = data.get('from_wxid', "")  # Sender's wxid
        if to_id=="":
            to_id ="rongrong3938"
        text = text or content or title
    else:
        to_id = request.args.get('to_id')
        text = request.args.get('text')
        at_id = request.args.get('at_id')
        from_wxid = request.args.get('from_wxid')

    if not to_id or not text:
        return jsonify({"code": -1, "message": "Both 'to_id' and 'text' parameters are required."}), 400

    try:
        current_wxbot = None
        
        # 如果指定了from_wxid且与当前机器人不同
        if from_wxid and from_wxid != wxbot.wx_id:
            # 查询数据库获取token和auth
            db_session = Session_sql()
            wechat_account = db_session.query(WeChatAccount).filter_by(wx_id=from_wxid).first()
            db_session.close()

            if wechat_account and wechat_account.token and wechat_account.auth:
                # 创建新的iPadWx实例
                current_wxbot = iPadWx()
                current_wxbot.token = wechat_account.token
                current_wxbot.auth = wechat_account.auth
                current_wxbot.wx_id = from_wxid
                
                # 尝试加载联系人文件
                contact_file = f"contact_ipad_{from_wxid}.json"
                if os.path.exists(contact_file):
                    try:
                        with open(contact_file, 'r', encoding='utf-8') as f:
                            contact_data = json.load(f)
                            if contact_data:
                                current_wxbot.shared_wx_contact_list = contact_data
                                logger.info(f"成功加载机器人{from_wxid}的联系人数据")
                    except Exception as e:
                        logger.warning(f"加载机器人{from_wxid}的联系人数据失败: {e}")
            else:
                return jsonify({"code": -1, "message": f"No valid configuration found for wxid: {from_wxid}"}), 404
        else:
            current_wxbot = wxbot

        # 发送消息
        try:
            if at_id:
                # 如果有联系人数据，获取昵称；否则跳过
                if current_wxbot.shared_wx_contact_list:
                    displayName, nickname = current_wxbot.get_chatroom_nickname(to_id, at_id)
                    name = displayName or nickname
                    if name:
                        content = "@" + name + " " + text
                        result = current_wxbot.send_at_msg(to_id=to_id, at_ids=at_id, nickname=name, content=content)
                    else:
                        # 如果找不到昵称，直接发送消息
                        result = current_wxbot.send_txt_msg(to_id=to_id, text=text)
                else:
                    # 没有联系人数据，直接发送普通消息
                    result = current_wxbot.send_txt_msg(to_id=to_id, text=text)
            else:
                result = current_wxbot.send_txt_msg(to_id=to_id, text=text)

            if result:
                logger.info(f"消息发送完成: {to_id},内容: {text}")
                return jsonify({"code": 0, "message": "Message sent successfully."})
            else:
                logger.info(f"消息发送失败 {to_id},内容 {text}，结果: {result}")
                return jsonify({"code": -1, "message": "Failed to send message."}), 500

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return jsonify({"code": -1, "message": f"Error sending message: {str(e)}"}), 500

    except Exception as e:
        logger.error(f"Error getting bot configuration: {e}")
        return jsonify({"code": -1, "message": "Failed to get bot configuration"}), 500


@quart_app.route("/send_msg_wx", methods=["GET", "POST"])
async def send_msg_wx():
    global wxbot
    if request.method == 'POST':
        data = await request.get_json()
        to_id = data.get('to_id', "")
        text = data.get('text', "")
        content = data.get('content', "")
        title = data.get('title', "")
        at_id = data.get('at_id', "")
        from_wxid = data.get('from_wxid', "")  # Sender's wxid
        if to_id == "":
            to_id = "rongrong3938"
        text = text or content or title
    else:
        to_id = request.args.get('to_id')
        text = request.args.get('text')
        at_id = request.args.get('at_id')
        from_wxid = request.args.get('from_wxid')

    if not to_id or not text:
        return jsonify({"code": -1, "message": "Both 'to_id' and 'text' parameters are required."}), 400

    try:
        current_wxbot = None
        # 查询数据库获取token和auth
        db_session = Session_sql()
        wechat_account = db_session.query(WeChatAccount).filter_by(account_id=from_wxid).first()
        wx_id = wechat_account.wx_id
        db_session.close()
        # 如果指定了from_wxid且与当前机器人不同

        if wechat_account and wechat_account.token and wechat_account.auth:
            # 创建新的iPadWx实例
            current_wxbot = iPadWx()
            current_wxbot.token = wechat_account.token
            current_wxbot.auth = wechat_account.auth
            current_wxbot.wx_id = wx_id

            # 尝试加载联系人文件
            contact_file = f"contact_ipad_{wx_id}.json"
            wx_contact_list={}
            if os.path.exists(contact_file):
                try:
                    with open(contact_file, 'r', encoding='utf-8') as f:
                        contact_data = json.load(f)
                        if contact_data:
                            wx_contact_list = contact_data
                            logger.info(f"成功加载机器人{wx_id}的联系人数据")
                except Exception as e:
                    logger.warning(f"加载机器人{wx_id}的联系人数据失败: {e}")
            else:# 如果加载失败，需要获取联系人列表
                wx_contact_list = current_wxbot.get_contact_all(wx_id)
                contact_file = f"contact_ipad_{wx_id}.json"
                json.dump(wx_contact_list, open(contact_file, 'w', encoding='utf-8'), ensure_ascii=False,
                          indent=4)
                logger.info(f"保存联系人到{contact_file}!")
        else:
            return jsonify({"code": -1, "message": f"No valid configuration found for wxid: {from_wxid}"}), 404


        # 发送消息
        try:
            to_wxid= ""
            name=""
            for id, contact in wx_contact_list.items():
                if not id.endswith("@chatroom") and contact['weixin'] == to_id:
                    to_wxid =  contact['userName']
                    displayName =  contact['nickName']
                    nickname=  contact['nickName']
                    name = displayName or nickname
                    break

            if at_id:
                # 如果有联系人数据，获取昵称；否则跳过
                if current_wxbot.shared_wx_contact_list:
                    if name:
                        content = "@" + name + " " + text
                        result = current_wxbot.send_at_msg(to_id=to_wxid, at_ids=at_id, nickname=name, content=content)
                    else:
                        # 如果找不到昵称，直接发送消息
                        result = current_wxbot.send_txt_msg(to_id=to_wxid, text=text)
                else:
                    # 没有联系人数据，直接发送普通消息
                    result = current_wxbot.send_txt_msg(to_id=to_wxid, text=text)
            else:
                if to_wxid!="":
                    if text =="[小红花]":
                        logger.info(f"[自动回复] [{wx_id}] 收到表情消息，不处理")
                        md5 = "1c97bb5e04310cf4d80ec961a5aa8308"
                        length = "151661"
                        #bot = self._get_bot_instance(wx_id)
                        result =current_wxbot.send_emoji(to_wxid, md5, length)
                    else:
                        result = current_wxbot.send_txt_msg(to_id=to_wxid, text=text)
                    if result:
                        logger.info(f"消息发送完成: {to_id},内容: {text}")
                        return jsonify({"code": 0, "message": "Message sent successfully."})
                    else:
                        logger.info(f"消息发送失败 {to_id},内容 {text}，结果: {result}")
                        return jsonify({"code": -1, "message": "Failed to send message."}), 500
                else:
                    logger.info(f"消息发送失败 未找到联系人：{to_id}")
                    return jsonify({"code": -1, "message": f"消息发送失败 未找到联系人：{to_id}"}), 500
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return jsonify({"code": -1, "message": f"Error sending message: {str(e)}"}), 500

    except Exception as e:
        logger.error(f"Error getting bot configuration: {e}")
        return jsonify({"code": -1, "message": "Failed to get bot configuration"}), 500


# Update route decorators to require login
@quart_app.route("/auto_reply", methods=['GET', 'POST'])
@login_required
async def manage_auto_reply():
    if request.method == 'POST':
        data = await request.form
        keyword = data.get('keyword')
        reply_type = data.get('reply_type')
        content = data.get('content')
        # Add new auto-reply to the database
        db_session = Session_sql()
        new_auto_reply = AutoReply(keyword=keyword, reply_type=reply_type, content=content)
        db_session.add(new_auto_reply)  # Continue adding the new auto-reply to the database
        try:
            # 尝试执行数据库操作
            db_session.commit()  # 提交事务
        except Exception as e:
            db_session.rollback()  # 如果发生异常，回滚事务
            if isinstance(e, PendingRollbackError):
                print("检测到PendingRollbackError，事务已回滚。请检查并处理导致事务失败的原因。")
            else:
                raise  # 如果不是PendingRollbackError，再次抛出异常以便上层处理
    db_session = Session_sql()
    auto_replies = db_session.query(AutoReply).all()
    return await render_template('auto_reply.html', title='Auto Reply Management', active='auto_reply',
                                 auto_replies=auto_replies)


@quart_app.route('/auto_reply/edit/<int:auto_reply_id>', methods=['POST'])
@login_required
async def edit_auto_reply(auto_reply_id):
    data = await request.form
    keyword = data.get('keyword')
    reply_type = data.get('reply_type')
    content = data.get('content')
    db_session = Session_sql()
    auto_reply = db_session.query(AutoReply).get(auto_reply_id)
    if auto_reply:
        auto_reply.keyword = keyword
        auto_reply.reply_type = reply_type
        auto_reply.content = content
        try:
            # 尝试执行数据库操作
            db_session.commit()  # 提交事务
        except Exception as e:
            db_session.rollback()  # 如果发生异常，回滚事务
            if isinstance(e, PendingRollbackError):
                print("检测到PendingRollbackError，事务已回滚。请检查并处理导致事务失败的原因。")
            else:
                raise  # 如果不是PendingRollbackError，再次抛出异常以便上层处理

    return redirect('/auto_reply')

# 获取所有 Media Messages
@quart_app.route('/media_messages', methods=['GET'])
@login_required
async def get_media_messages():
    db_session = Session_sql()
    messages = db_session.query(MediaMessage).all()
    result = [message.to_dict() for message in messages]
    db_session.close()
    #return jsonify({'status': 'success', 'data': result})


    return await render_template('media_messages.html', title='素材', active='media_messages', media_messages=result)


# 根据ID获取特定消息
@quart_app.route('/media_messages/<int:message_id>', methods=['GET'])
@login_required
async def get_media_message(message_id):
    db_session = Session_sql()
    message = db_session.query(MediaMessage).filter_by(id=message_id).first()
    if message:
        result = message.to_dict()
        db_session.close()
        return jsonify({'status': 'success', 'data': result})
    db_session.close()
    return jsonify({'status': 'error', 'message': '消息不存在'})


# 新增消息
@quart_app.route('/media_messages', methods=['POST'])
@login_required
async def add_media_message():
    try:
        data = await request.get_json()
        db_session = Session_sql()
        new_message = MediaMessage(
            msg_type=data['msg_type'],
            md5=data['md5'],
            file_name=data['file_name'],
            uploader_nickname=data['uploader_nickname'],
            received_date=data['received_date']
        )
        db_session.add(new_message)
        db_session.commit()
        db_session.close()
        return jsonify({'status': 'success', 'message': '消息添加成功'})
    except Exception as e:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': str(e)})


# 修改消息
@quart_app.route('/media_messages/<int:message_id>', methods=['PUT'])
@login_required
async def update_media_message(message_id):
    try:
        data = await request.get_json()
        db_session = Session_sql()
        message = db_session.query(MediaMessage).filter_by(id=message_id).first()
        if message:
            message.msg_type = data['msg_type']
            message.md5 = data['md5']
            message.file_name = data['file_name']
            message.uploader_nickname = data['uploader_nickname']
            message.received_date = data['received_date']
            db_session.commit()
            db_session.close()
            return jsonify({'status': 'success', 'message': '消息更新成功'})
        db_session.close()
        return jsonify({'status': 'error', 'message': '消息不存在'})
    except Exception as e:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': str(e)})


# 删除消息
@quart_app.route('/media_messages/<int:message_id>', methods=['DELETE'])
@login_required
async def delete_media_message(message_id):
    try:
        db_session = Session_sql()
        message = db_session.query(MediaMessage).filter_by(id=message_id).first()
        if message:
            db_session.delete(message)
            db_session.commit()
            db_session.close()
            return jsonify({'status': 'success', 'message': '消息删除成功'})
        db_session.close()
        return jsonify({'status': 'error', 'message': '消息不存在'})
    except Exception as e:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': str(e)})

# 获取所有 Scheduled Tasks
@quart_app.route('/scheduled_tasks', methods=['GET'])
@login_required
async def get_scheduled_tasks():
    db_session = Session_sql()
    tasks = db_session.query(ScheduledTasks).all()
    result = [task.to_dict() for task in tasks]
    db_session.close()
    #return jsonify({'status': 'success', 'data': result})

    return await render_template('scheduled_tasks.html', title='定时任务', active='scheduled_tasks', scheduled_tasks=result)



# 根据ID获取特定任务
@quart_app.route('/scheduled_tasks/<int:task_id>', methods=['GET'])
async def get_scheduled_task(task_id):
    db_session = Session_sql()
    task = db_session.query(ScheduledTasks).filter_by(id=task_id).first()
    if task:
        result = task.to_dict()
        db_session.close()
        return jsonify({'status': 'success', 'data': result})
    db_session.close()
    return jsonify({'status': 'error', 'message': '任务不存在'})


# 新增任务
@quart_app.route('/scheduled_tasks', methods=['POST'])
async def add_scheduled_task():
    try:
        data = await request.get_json()
        db_session = Session_sql()
        new_task = ScheduledTasks(
            user_id=data['user_id'],
            task_description=data['task_description'],
            schedule_type=data['schedule_type'],
            hour=data['hour'],
            minute=data['minute'],
            interval_value=data['interval_value']
        )
        db_session.add(new_task)
        db_session.commit()
        db_session.close()
        return jsonify({'status': 'success', 'message': '任务添加成功'})
    except Exception as e:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': str(e)})


# 修改任务
@quart_app.route('/scheduled_tasks/<int:task_id>', methods=['PUT'])
async def update_scheduled_task(task_id):
    try:
        data = await request.get_json()
        db_session = Session_sql()
        task = db_session.query(ScheduledTasks).filter_by(id=task_id).first()
        if task:
            task.user_id = data['user_id']
            task.task_description = data['task_description']
            task.schedule_type = data['schedule_type']
            task.hour = data['hour']
            task.minute = data['minute']
            task.interval_value = data['interval_value']
            db_session.commit()
            db_session.close()
            return jsonify({'status': 'success', 'message': '任务更新成功'})
        db_session.close()
        return jsonify({'status': 'error', 'message': '任务不存在'})
    except Exception as e:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': str(e)})


# 删除任务
@quart_app.route('/scheduled_tasks/<int:task_id>', methods=['DELETE'])
async def delete_scheduled_task(task_id):
    try:
        db_session = Session_sql()
        task = db_session.query(ScheduledTasks).filter_by(id=task_id).first()
        if task:
            db_session.delete(task)
            db_session.commit()
            db_session.close()
            return jsonify({'status': 'success', 'message': '任务删除成功'})
        db_session.close()
        return jsonify({'status': 'error', 'message': '任务不存在'})
    except Exception as e:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': str(e)})

@quart_app.route("/wxcomapp1", methods=["GET", "POST"])
async def wxcomapp_post1():
    from channel.wechatcom.wechatcomapp_channel import WechatComAppChannel
    from channel.wechatcom.wechatcomapp_channel import Query
    from wechatpy.exceptions import InvalidSignatureException

    if request.method == "GET":
        pass
        channel2 = WechatComAppChannel()
        params = request.args
        logger.info("[wechatcom] receive params: {}".format(params))
        try:
            signature = params.get("msg_signature")
            timestamp = params.get("timestamp")
            nonce = params.get("nonce")
            echostr = params.get("echostr")

            echostr = channel2.crypto.check_signature(signature, timestamp, nonce, echostr)
        except InvalidSignatureException:
            logger.info("error")
            raise Exception
        return echostr
    else:
        data = await request.data
        Query().handle_message(request, data)
        return jsonify({"code": 0, "message": "Message sent successfully."})

def keep_connection_alive():
    db_session = Session_sql()
    db_session.execute("SELECT 1")

if __name__ == "__main__":
    # run()
    asyncio.run(run_servers())
