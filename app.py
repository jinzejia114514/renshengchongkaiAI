#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 人生重开手帐 - Flask 应用主入口

支持 OpenAI 格式的 LLM 接口
完整游戏流程：身份设定 → 天赋抽取 → 属性分配 → 开始人生
"""

import os
import secrets
import time
from datetime import timedelta

from flask import Flask, request, send_from_directory
from flask_session import Session

from game_data import get_trait_icon, get_trait_desc
from llm_client import load_config, merge_config, LLMClient
from game_utils import cleanup_old_sessions
from paths import BASE_DIR, CONFIG_PATH, SESSIONS_DIR, GENERATED_DIR
from routes import register_blueprints

# ============ 初始化 ============

SESSION_DIR = SESSIONS_DIR
SESSION_DIR.mkdir(parents=True, exist_ok=True)

# 全量配置（config.json 原文）用于 app 级参数（secret_key / port / debug）
RAW_CONFIG = load_config()
# LLM 专用配置（合并环境变量）
LLM_CONFIG = merge_config()

# 模板与静态资源目录显式指定：桌面端默认项目根目录，Android 上由 APP_BASE_DIR
# 指向解压后的 assets 目录（Chaquopy 打包的模块 __file__ 不在此处）
app = Flask(__name__,
            template_folder=str(BASE_DIR / 'templates'),
            static_folder=str(BASE_DIR / 'static'))
# 优先环境变量，其次配置文件；都不配时生成随机密钥，避免硬编码默认值
app.secret_key = os.environ.get('SECRET_KEY') or RAW_CONFIG.get('app', {}).get('secret_key')
if not app.secret_key:
    app.secret_key = secrets.token_hex(32)
    print("[Security] 未配置 SECRET_KEY，已生成随机密钥（重启后 session 将失效）")
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


# ============ 配置热重载（基于文件 mtime，避免每次请求都读写磁盘）============

# 配置路径来自 paths.py（数据目录优先 APP_DATA_DIR，桌面端为项目根目录）
_config_mtime = CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else 0
_reload_interval = 5  # 最短检查间隔（秒）

def reload_config_if_changed():
    """仅在 config.json 修改时间变化时重新加载，避免每次请求都读写磁盘"""
    global _config_mtime
    now = time.time()
    if now - _reload_interval < getattr(reload_config_if_changed, '_last_check', 0):
        return
    reload_config_if_changed._last_check = now
    try:
        current_mtime = CONFIG_PATH.stat().st_mtime
    except OSError:
        return
    if current_mtime <= _config_mtime:
        return
    _config_mtime = current_mtime
    try:
        raw = load_config()
        merged = merge_config()
        app.llm_client = LLMClient(merged)
        app.LLM_CONFIG = merged
        app.secret_key = os.environ.get('SECRET_KEY', raw.get('app', {}).get('secret_key', app.secret_key))
        print("[Config Reload] config.json 已重载")
    except Exception as e:
        print(f"[Config Reload] 重载失败: {e}")


@app.before_request
def _before_request():
    """每次请求前检查 config.json 是否变化（跳过静态文件）"""
    if request.path.startswith('/static/'):
        return
    reload_config_if_changed()


@app.after_request
def _no_cache(response):
    """禁用响应缓存：APK 覆盖安装后 WebView 的 HTTP 缓存会残留旧页面，
    加 no-store 保证每次都能拿到最新模板与静态资源。"""
    response.headers['Cache-Control'] = 'no-store'
    return response


# ============ 运行时生成图片的静态服务 ============

# 四格漫画保存在数据目录（桌面端项目内 / Android filesDir/data），
# 与只读 static 资源分离，保证应用升级时不会清空已生成的图片。
# 此路由比 Flask 默认的 /static/<path> 更具体（静态段更多），匹配优先。
@app.route('/static/generated/<path:filename>')
def serve_generated(filename):
    return send_from_directory(GENERATED_DIR, filename)


# ============ 注册路由蓝图 ============

register_blueprints(app)


# ============ 启动 ============

if __name__ == '__main__':
    app_cfg = RAW_CONFIG.get('app', {})
    host = app_cfg.get('host', '0.0.0.0')
    port = app_cfg.get('port', 3000)
    # 默认关闭 debug：Werkzeug 调试器允许在浏览器中执行任意 Python，
    # 一旦和公网绑定同时开启就等于远程代码执行。
    debug = app_cfg.get('debug', False)

    cleanup_old_sessions(SESSION_DIR)

    print("=" * 50)
    print("AI 人生重开手帐")
    print("=" * 50)
    if debug and host not in ('127.0.0.1', 'localhost'):
        print(f"[Security] 警告：debug=True 且绑定 {host}，Werkzeug 调试器将暴露在网络上，")
        print("           可被用于执行任意代码。生产环境请把 config.json 的 app.debug 设为 false。")
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

    app.run(debug=debug, host=host, port=port)
