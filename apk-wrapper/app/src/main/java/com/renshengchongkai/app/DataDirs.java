package com.renshengchongkai.app;

import android.content.Context;
import android.util.Log;

import java.io.File;

/**
 * 应用可写数据目录：filesDir/data/
 *
 *   data/config.json           LLM 配置（Python 侧 ensure_config 自动补全生成）
 *   data/.sessions/            Flask-Session 会话文件
 *   data/records/              公开/隐藏游戏记录
 *   data/static/generated/     运行时生成的四格漫画
 *
 * 与只读的代码/静态资源（filesDir/app_assets）分离，APK 升级重解压
 * 静态资源时不会清空用户数据。
 */
public final class DataDirs {

    private static final String TAG = "DataDirs";

    private DataDirs() {
    }

    public static File getDataDir(Context context) {
        return new File(context.getFilesDir(), "data");
    }

    public static void ensure(Context context) {
        File dataDir = getDataDir(context);
        File[] subDirs = {
                new File(dataDir, ".sessions"),
                new File(dataDir, "records"),
                new File(dataDir, "static" + File.separator + "generated"),
        };
        for (File d : subDirs) {
            if (!d.exists() && !d.mkdirs()) {
                Log.e(TAG, "mkdir failed: " + d);
            }
        }
    }
}
