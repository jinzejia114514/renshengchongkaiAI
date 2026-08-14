package com.renshengchongkai.app;

import android.content.Context;
import android.content.res.AssetManager;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

/**
 * 把 assets/python 下的静态资源（templates/ static/）解压到
 * filesDir/app_assets，供 Flask 的 template_folder / static_folder 使用。
 *
 * 解压结果带版本标记（.version = assets 内容指纹）：
 * 每次启动计算当前 APK assets 的指纹，与已解压的比对——
 * 不同（APK 更新了模板/静态资源）则整体删除重解压；
 * 相同则跳过，避免每次启动都写盘。
 *
 * 注意：指纹基于「文件路径+大小」而非内容哈希，足够检测资源更新；
 * Python 模块本身由 Chaquopy 打包，不在此处解压。
 */
public final class AssetExtractor {

    private static final String TAG = "AssetExtractor";
    private static final String ASSET_PREFIX = "python";

    private AssetExtractor() {
    }

    public static void extract(Context context) {
        File destDir = new File(context.getFilesDir(), "app_assets");
        File versionFile = new File(destDir, ".version");

        try {
            String fingerprint = computeFingerprint(context.getAssets());
            if (destDir.exists() && versionFile.exists()) {
                String existing = readString(versionFile);
                if (existing != null && existing.equals(fingerprint)) {
                    return; // 指纹一致，直接复用
                }
            }
            deleteRecursive(destDir);
            if (!copyAssetDir(context.getAssets(), ASSET_PREFIX, destDir)) {
                throw new IOException("asset copy incomplete");
            }
            writeString(versionFile, fingerprint);
            Log.i(TAG, "assets extracted to " + destDir + " (fingerprint " +
                    fingerprint.length() + " bytes)");
        } catch (Exception e) {
            Log.e(TAG, "extract failed", e);
        }
    }

    /** 遍历 assets/python 下所有文件，拼接路径与大小作为指纹 */
    private static String computeFingerprint(AssetManager am) throws IOException {
        StringBuilder sb = new StringBuilder();
        collectFingerprint(am, ASSET_PREFIX, sb);
        return sb.toString();
    }

    private static void collectFingerprint(AssetManager am, String path, StringBuilder sb)
            throws IOException {
        String[] children = am.list(path);
        if (children == null || children.length == 0) {
            try (InputStream in = am.open(path)) {
                sb.append(path).append(':').append(in.available()).append(';');
            }
        } else {
            for (String child : children) {
                collectFingerprint(am, path + "/" + child, sb);
            }
        }
    }

    private static boolean copyAssetDir(AssetManager am, String path, File dest) {
        try {
            String[] children = am.list(path);
            if (children == null || children.length == 0) {
                // 文件
                return copyAssetFile(am, path, dest);
            }
            if (!dest.exists() && !dest.mkdirs()) {
                Log.e(TAG, "mkdir failed: " + dest);
                return false;
            }
            for (String child : children) {
                if (!copyAssetDir(am, path + "/" + child, new File(dest, child))) {
                    return false;
                }
            }
            return true;
        } catch (IOException e) {
            Log.e(TAG, "list failed: " + path, e);
            return false;
        }
    }

    private static boolean copyAssetFile(AssetManager am, String path, File dest) throws IOException {
        try (InputStream in = am.open(path)) {
            if (dest.getParentFile() != null && !dest.getParentFile().exists()) {
                //noinspection ResultOfMethodCallIgnored
                dest.getParentFile().mkdirs();
            }
            try (OutputStream out = new FileOutputStream(dest)) {
                byte[] buf = new byte[64 * 1024];
                int n;
                while ((n = in.read(buf)) > 0) {
                    out.write(buf, 0, n);
                }
            }
            return true;
        }
    }

    private static void deleteRecursive(File f) {
        if (f == null || !f.exists()) {
            return;
        }
        if (f.isDirectory()) {
            File[] children = f.listFiles();
            if (children != null) {
                for (File child : children) {
                    deleteRecursive(child);
                }
            }
        }
        //noinspection ResultOfMethodCallIgnored
        f.delete();
    }

    private static String readString(File f) {
        try {
            byte[] buf = new byte[(int) f.length()];
            try (java.io.FileInputStream in = new java.io.FileInputStream(f)) {
                int off = 0, n;
                while (off < buf.length && (n = in.read(buf, off, buf.length - off)) > 0) {
                    off += n;
                }
            }
            return new String(buf, "UTF-8");
        } catch (Exception e) {
            return null;
        }
    }

    private static void writeString(File f, String s) throws IOException {
        try (FileOutputStream out = new FileOutputStream(f)) {
            out.write(s.getBytes("UTF-8"));
        }
    }
}
