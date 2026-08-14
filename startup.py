# -*- coding: utf-8 -*-
"""
Android 启动入口（仅 Android 端由 Java 调用）。

职责：
1. 设置 APP_BASE_DIR / APP_DATA_DIR 环境变量，让 paths.py 解析到
   Android 应用私有目录（filesDir），而不是代码打包目录；
2. 启动 Flask 服务，固定监听 127.0.0.1:3000（忽略 config.json 的 app.host/port，
   保证只在本机回环地址可达）。
"""

import os
import sys
import traceback


def main(files_dir=None):
    """files_dir: Android filesDir 绝对路径（由 Java 侧传入）。

    不通过 com.chaquo.python.Android 取 Context（javaclass 桥在某些
    初始化时序下不可用），改为 Java 直接传参，更稳妥。
    """
    try:
        if not files_dir:
            from com.chaquo.python import Android
            files_dir = Android.getContext().getFilesDir().getAbsolutePath()

        base_dir = os.path.join(files_dir, 'app_assets')
        data_dir = os.path.join(files_dir, 'data')

        # 代码/静态资源（templates、static）与可写数据（config.json 等）分离
        os.environ['APP_BASE_DIR'] = base_dir
        os.environ['APP_DATA_DIR'] = data_dir

        import app as app_module
        from game_utils import cleanup_old_sessions
        from paths import SESSIONS_DIR

        # 清理 24 小时前的过期会话文件
        cleanup_old_sessions(SESSIONS_DIR)

        print(f'[Android] 静态资源目录: {base_dir}')
        print(f'[Android] 数据目录: {data_dir}')
        print('[Android] Flask 启动: http://127.0.0.1:3000')
        sys.stdout.flush()

        app_module.app.run(host='127.0.0.1', port=3000,
                           threaded=True, debug=False, use_reloader=False)
    except Exception:
        tb = traceback.format_exc()
        print(tb)
        sys.stdout.flush()
        # 把完整堆栈写入数据目录，便于文件管理器直接查看
        try:
            log_path = os.path.join(os.environ.get('APP_DATA_DIR', ''), 'startup_error.log')
            if log_path:
                with open(log_path, 'w', encoding='utf-8') as f:
                    f.write(tb)
                print(f'[Android] 错误已写入: {log_path}')
                sys.stdout.flush()
        except Exception:
            pass
        # 重新抛出，让 Java 层弹窗显示具体错误
        raise
