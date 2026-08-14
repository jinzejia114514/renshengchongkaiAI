# -*- coding: utf-8 -*-
"""
统一的可写路径解析。

所有需要写入磁盘的路径（config.json、.sessions、records、static/generated）
都从这里派生，避免在代码里硬编码相对路径：

- 桌面端：默认数据目录 = 项目根目录（保持原有行为不变）
- Android：启动脚本设置 APP_DATA_DIR 环境变量指向 <filesDir>/data，
  所有可写数据都落在应用私有数据目录内，符合 Android 存储规范；
  代码与静态资源则通过 APP_BASE_DIR 指向 <filesDir>/app_assets。

这两个环境变量只在 Android 端由 Java 启动层注入，桌面端无需配置。
"""

import os
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent


def get_data_dir() -> Path:
    """可写数据根目录。环境变量 APP_DATA_DIR 优先，否则用项目根目录。"""
    env = os.environ.get('APP_DATA_DIR')
    if env:
        return Path(env)
    return _PROJECT_DIR


def get_base_dir() -> Path:
    """代码/静态资源根目录（templates、static 只读资源所在处）。

    Android 上 Flask 模块来自 Chaquopy 打包的 pyc，__file__ 指向
    filesDir/chaquopy 下的解压目录，与 templates/static 不在同一处，
    因此由 APP_BASE_DIR 显式指定。桌面端默认项目根目录。
    """
    env = os.environ.get('APP_BASE_DIR')
    if env:
        return Path(env)
    return _PROJECT_DIR


DATA_DIR = get_data_dir()
BASE_DIR = get_base_dir()

# 配置文件（支持热重载）
CONFIG_PATH = DATA_DIR / 'config.json'

# Flask-Session 服务端会话文件
SESSIONS_DIR = DATA_DIR / '.sessions'

# 公开/隐藏游戏记录
RECORDS_DIR = DATA_DIR / 'records'

# 运行时生成的四格漫画（与只读 static 分离，保证升级 APK 不清空）
GENERATED_DIR = DATA_DIR / 'static' / 'generated'
