#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 人生重开手帐 - Flask 应用主入口

支持 OpenAI 格式的 LLM 接口
完整游戏流程：身份设定 → 天赋抽取 → 属性分配 → 开始人生
"""

import os
from datetime import timedelta
from pathlib import Path

from flask import Flask, request
from flask_session import Session

from game_data import get_trait_icon, get_trait_desc
from llm_client import load_config, merge_config, LLMClient
from game_utils import cleanup_old_sessions
from routes import register_blueprints

# ============ 初始化 ============

SESSION_DIR = Path(__file__).parent / '.sessions'
SESSION_DIR.mkdir(exist_ok=True)

# 全量配置（config.json 原文）用于 app 级参数（secret_key / port / debug）
RAW_CONFIG = load_config()
# LLM 专用配置（合并环境变量）
LLM_CONFIG = merge_config()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', RAW_CONFIG.get('app', {}).get('secret_key', 'ai_life_restart_secret_key_2024'))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = str(SESSION_DIR)
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=3)
Session(app)

# ============ Jinja 全局函数 ============

app.jinja_env.globals.update(get_trait_icon=get_trait_icon)
app.jinja_env.globals.update(get_trait_desc=get_trait_desc)
app.jinja_env.globals.update(url_for_static=lambda filename: f'/static/{filename}')


@app.context_processor
def inject_globals():
    llm_model = app.LLM_CONFIG.get("model", "未配置")
    return dict(request=request, llm_model=llm_model)


# ============ LLM 客户端（全局实例）============

llm_client = LLMClient(LLM_CONFIG)

# 存储到 app 上，供蓝图通过 current_app 获取（避免循环导入）
app.llm_client = llm_client
app.LLM_CONFIG = LLM_CONFIG


# ============ 配置热重载 ============

def reload_config():
    """从磁盘重新加载 config.json，更新 app 上的 llm_client 和 LLM_CONFIG"""
    try:
        raw = load_config()
        merged = merge_config()
        new_client = LLMClient(merged)
        app.llm_client = new_client
        app.LLM_CONFIG = merged
        app.secret_key = os.environ.get('SECRET_KEY', raw.get('app', {}).get('secret_key', app.secret_key))
    except Exception as e:
        print(f"[Config Reload] 重载失败: {e}")


@app.before_request
def _before_request():
    """每次请求前热重载 config.json"""
    reload_config()


# ============ 注册路由蓝图 ============

register_blueprints(app)


# ============ 启动 ============

if __name__ == '__main__':
    port = RAW_CONFIG.get('app', {}).get('port', 5000)
    debug = RAW_CONFIG.get('app', {}).get('debug', True)

    cleanup_old_sessions(SESSION_DIR)

    print("=" * 50)
    print("AI 人生重开手帐")
    print("=" * 50)
    print(f"LLM 状态: {'已启用' if llm_client.enabled else '未启用'}")
    if llm_client.enabled:
        print(f"API 地址: {LLM_CONFIG['api_base']}")
        print(f"模型: {LLM_CONFIG['model']}")
    print()
    print("\n配置文件: config.json（支持热重载，修改后立即生效）")
    print("可直接修改 config.json 来配置 LLM 参数:")
    print("  llm.enabled: true")
    print("  llm.api_base: https://api.openai.com/v1")
    print("  llm.api_key: sk-xxx")
    print("  llm.model: gpt-4o")
    print("  llm.custom_request_body: { \"thinking\": true }")
    print("=" * 50)
    print()

    app.run(debug=debug, host='0.0.0.0', port=port)
