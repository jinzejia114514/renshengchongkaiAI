# -*- coding: utf-8 -*-
"""
路由蓝图注册
"""

from .pages import pages_bp
from .api import api_bp


def register_blueprints(app):
    """将所有蓝图注册到 Flask app"""
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)
