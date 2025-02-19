# encoding:utf-8
import json
from quart import Blueprint
from quart import request, jsonify, render_template
import os
from collections import OrderedDict

from common.log import logger
from .decorators import login_required
import requests
import threading
import time
from plugins import *

from plugins.event import Event, EventContext
from wechatpy.enterprise import parse_message, WeChatCrypto
from wechatpy.enterprise.exceptions import InvalidCorpIdException
from wechatpy.exceptions import InvalidSignatureException
from config import conf

# 创建蓝图对象
plugins_bp = Blueprint('plugins', __name__)

# 事件机制，用于等待和通知
result_event = threading.Event()
result_data = None  # 用于存储回调结果


class VoiceResultManager:
    def __init__(self):
        self._result = None
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._has_new_result = False
        self._waiting_for_result = False

    def start_waiting(self):
        """开始等待结果"""
        with self._lock:
            self._waiting_for_result = True
            self._event.clear()
            self._result = None
            self._has_new_result = False

    def stop_waiting(self):
        """停止等待结果"""
        with self._lock:
            self._waiting_for_result = False
            self._event.set()

    def set_result(self, result):
        with self._lock:
            if self._waiting_for_result:  # 只有在等待结果时才接受
                self._result = result
                self._has_new_result = True
                self._event.set()
                logger.info(f"结果已设置: {result}")
            else:
                logger.debug("当前没有在等待结果，忽略接收到的消息")

    def get_result(self, timeout=None):
        """获取结果，带超时机制"""
        start_time = time.time()
        while timeout is None or time.time() - start_time < timeout:
            with self._lock:
                if self._has_new_result:
                    result = self._result
                    self._result = None
                    self._has_new_result = False
                    self._event.clear()
                    logger.info(f"获取到结果: {result}")
                    return result

            # 等待较短的时间后重试
            if not self._event.wait(1.0):  # 每秒检查一次
                continue

        logger.info("等待结果超时")
        return None


voice_manager = VoiceResultManager()


@plugins_bp.route('/settings', methods=['GET', 'POST'])
@login_required
async def settings():
    if request.method == 'POST':
        data = await request.json
        plugin_name = data.get('plugin_name')
        config_data = data.get('config')
        save_config(plugin_name, config_data)
        return jsonify({'status': 'success'})

    # Load plugins list and render the template
    plugins = load_plugins_list()
    return await render_template('settings.html', plugins=plugins)


@plugins_bp.route('/get_plugin_config/<plugin_name>', methods=['GET'])
@login_required
async def get_plugin_config(plugin_name):
    config = load_pconfig(plugin_name)
    return jsonify(config)


def load_plugins_list():
    plugins_file = os.path.join(os.getcwd(), 'plugins', 'plugins.json')
    with open(plugins_file, 'r', encoding='utf-8') as file:
        plugins_data = json.load(file)

    enabled_plugins = {}
    for plugin_name, plugin_info in plugins_data.get('plugins', {}).items():
        if plugin_name.lower() in ["admin", "godcmd", "finish"]:
            continue
        if plugin_info.get('enabled', False):
            enabled_plugins[plugin_name] = plugin_info

    return enabled_plugins


def load_pconfig(plugin_name):
    """加载插件配置，支持三种格式"""
    config_file = os.path.join(os.getcwd(), 'plugins', plugin_name, 'config.json')
    logger.info(f'Loading config file: {config_file}')
    if not os.path.exists(config_file):
        logger.warning(f'Config file not found: {config_file}')
        return {}
        
    with open(config_file, 'r', encoding='utf-8') as file:
        config = json.load(file, object_pairs_hook=OrderedDict)
        logger.debug(f'Loaded raw config: {config}')
        
    # 检查是否是复杂的嵌套 JSON 结构
    is_complex = any(isinstance(v, dict) and not ('value' in v and len(v) <= 2) for v in config.values())
    logger.debug(f'Is complex JSON: {is_complex}')

    if is_complex:
        # 复杂 JSON 结构，包装成特殊格式返回
        result = {
            "config_type": "json",
            "value": json.dumps(config, indent=2, ensure_ascii=False),
            "description": "Complex JSON Configuration"
        }
        logger.debug(f'Returning complex JSON config: {result}')
        return result
    
    # 检查是否是带描述的复杂格式
    first_value = next(iter(config.values())) if config else None
    logger.debug(f'First value in config: {first_value}')

    if isinstance(first_value, dict) and 'value' in first_value:
        logger.debug('Returning config with descriptions')
        return config
    else:
        # 简单格式，转换为前端期望的格式
        converted_config = {}
        for key, value in config.items():
            converted_config[key] = {
                "value": value,
                "description": key
            }
        logger.debug(f'Returning converted simple config: {converted_config}')
        return converted_config


def save_config(plugin_name, new_config):
    """保存插件配置，处理三种格式"""
    config_file = os.path.join(os.getcwd(), 'plugins', plugin_name, 'config.json')
    
    # 检查是否是复杂 JSON 配置
    if isinstance(new_config, dict) and "config_type" in new_config and new_config["config_type"] == "json":
        try:
            # 解析并格式化 JSON 字符串
            updated_config = json.loads(new_config["value"])
            logger.debug(f"Saving complex JSON config: {updated_config}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            return
    else:
        # 读取原有配置以确定格式
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as file:
                current_config = json.load(file)
                
            # 检查是否是简单格式
            first_value = next(iter(current_config.values())) if current_config else None
            is_simple_format = not (isinstance(first_value, dict) and 'value' in first_value)
            
            if is_simple_format:
                # 简单格式，只保存值
                updated_config = {}
                for key, value in new_config.items():
                    if isinstance(value, dict) and "value" in value:
                        if isinstance(value["value"], str) and value["value"].lower() in ['true', 'false']:
                            updated_config[key] = value["value"].lower() == 'true'
                        else:
                            updated_config[key] = value["value"]
                    else:
                        updated_config[key] = value
            else:
                # 复杂格式，保持原有结构
                updated_config = current_config
                for key, value in new_config.items():
                    if key in updated_config:
                        if isinstance(value, dict) and "value" in value:
                            if isinstance(value["value"], str) and value["value"].lower() in ['true', 'false']:
                                value["value"] = value["value"].lower() == 'true'
                            updated_config[key]['value'] = value["value"]
                        else:
                            updated_config[key] = value
        else:
            # 新文件，使用简单格式
            updated_config = {}
            for k, v in new_config.items():
                if isinstance(v, dict) and "value" in v:
                    updated_config[k] = v["value"]
                else:
                    updated_config[k] = v

    logger.debug(f"Final config to save: {updated_config}")
    # 保存配置
    with open(config_file, 'w', encoding='utf-8') as file:
        json.dump(updated_config, file, indent=4, ensure_ascii=False)

    # 触发配置更新事件
    e_context = EventContext(Event.ON_CONFIG_CHANGED)
    e_context["plugin_name"] = plugin_name
    e_context["config"] = new_config
    PluginManager().emit_event(e_context)


@plugins_bp.route('/voice_callback', methods=['POST'])
async def voice_callback():
    """接收程序 B 的回调通知"""
    data = await request.json
    task_id = data['task_id']
    result = data['result']
    logger.info(f"收到回调结果: task_id={task_id}, result={result}")
    voice_manager.set_result(result)
    logger.info("已设置结果并通知等待线程")
    return jsonify({'status': 'received'}), 200


@plugins_bp.route('/voice_upload', methods=['POST'])
async def voice_upload():
    """接收语音数据并开始处理"""
    data = await request.json
    task_id = data['task_id']
    audio_data = data['audio_data']
    callback_url = data['callback_url']

    # 异步处理任务
    # threading.Thread(target=process_audio, args=(task_id, audio_data, callback_url)).start()
    return jsonify({'status': 'processing', 'task_id': task_id}), 202

def decode_wechatcom_msg(request, data):
    """独立的解码函数，不依赖于 WechatComAppChannel"""
    try:
        # 从配置中获取必要的参数
        corp_id = conf().get("wechatcom_corp_id")
        token = conf().get("wechatcomapp_token")
        aes_key = conf().get("wechatcomapp_aes_key")
        
        # 创建一个临时的 crypto 对象，而不是整个 channel
        crypto = WeChatCrypto(token, aes_key, corp_id)
        
        # 获取请求参数
        params = request.args
        signature = params.get("msg_signature")
        timestamp = params.get("timestamp")
        nonce = params.get("nonce")
        
        # 解密消息
        message = crypto.decrypt_message(data, signature, timestamp, nonce)
        msg = parse_message(message)
        
        # 只返回语音和图片消息
        if msg.type in ["voice", "image","video","file"]:
            return msg
        return None
        
    except (InvalidSignatureException, InvalidCorpIdException) as e:
        logger.error(f"Invalid signature or corp id: {e}")
        return None
    except Exception as e:
        logger.error(f"Error decoding message: {e}")
        return None

@plugins_bp.route("/wxcomapp", methods=["GET", "POST"])
async def wxcomapp_post():
    if request.method == "GET":
        params = request.args
        logger.info("[wechatcom] receive params: {}".format(params))
        try:
            signature = params.get("msg_signature")
            timestamp = params.get("timestamp")
            nonce = params.get("nonce")
            echostr = params.get("echostr")
            corp_id = conf().get("wechatcom_corp_id")
            token = conf().get("wechatcomapp_token")
            aes_key = conf().get("wechatcomapp_aes_key")
            # 创建一个临时的 crypto 对象，而不是整个 channel
            crypto = WeChatCrypto(token, aes_key, corp_id)

            echostr = crypto.check_signature(signature, timestamp, nonce, echostr)
        except InvalidSignatureException:
            logger.info("error")
            raise Exception
        return echostr
    else:
        data = await request.data
        ret = decode_wechatcom_msg(request, data)
        if ret and ret.type in ["voice", "image","video","file"]:
            logger.info(f"收到{ret.type}消息")
            voice_manager.set_result(ret)
            logger.info("已设置结果并通知等待线程")
        else:
            logger.info(f"收到消息,无法处理")
            voice_manager.set_result(ret)
            logger.info(ret)
        return jsonify({"code": 0, "message": "Message processed."})

