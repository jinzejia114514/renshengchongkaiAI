package com.renshengchongkai.app;

import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.util.Base64;
import android.util.Log;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/**
 * 注入 WebView 的 JS 桥（window.AndroidBridge）。
 *
 * 前端 Blob + <a download> 的下载方式在 WebView 中不可靠，
 * 因此 WebView 环境下前端把文件内容 base64 后交给本桥保存到系统下载目录：
 *   - API 29+：MediaStore.Downloads（无需权限）
 *   - API 26-28：公共下载目录 + WRITE_EXTERNAL_STORAGE（Manifest 已声明，
 *     MainActivity 启动时申请运行时权限）
 */
public class AndroidBridge {

    private static final String TAG = "AndroidBridge";

    private final Context context;
    private final WebView webView;

    public AndroidBridge(Context context, WebView webView) {
        this.context = context.getApplicationContext();
        this.webView = webView;
    }

    @JavascriptInterface
    public void saveBase64File(String filename, String mimeType, String base64Data) {
        Log.i(TAG, "saveBase64File: " + filename + " (" + mimeType + ", " +
                (base64Data == null ? 0 : base64Data.length()) + " chars)");
        try {
            if (base64Data == null || base64Data.isEmpty()) {
                showToast("保存失败：文件内容为空");
                return;
            }
            // 兼容 "data:..." 前缀
            String b64 = base64Data;
            int comma = b64.indexOf(',');
            if (comma >= 0) {
                b64 = b64.substring(comma + 1);
            }
            byte[] bytes = Base64.decode(b64, Base64.DEFAULT);

            boolean saved = (Build.VERSION.SDK_INT >= 29)
                    ? saveViaMediaStore(filename, mimeType, bytes)
                    : saveLegacy(filename, bytes);
            showToast(saved ? "已保存到下载目录：" + filename : "保存失败，请查看日志");
        } catch (Exception e) {
            Log.e(TAG, "save failed", e);
            showToast("保存失败：" + e.getMessage());
        }
    }

    @JavascriptInterface
    public void toast(String message) {
        showToast(message);
    }

    /**
     * 通用 HTTP 代理（异步版）：把 JS 的 fetch 转发到本机 Flask 服务。
     * <p>
     * 必须异步：JavascriptInterface 的同步方法运行在 WebView 的 JS 执行线程上，
     * 阻塞式 HTTP（LLM 请求可达数十秒）会冻结整个页面（表现为卡顿后全部响应
     * 突然弹出）。因此这里在后台线程执行请求，完成后通过主线程
     * evaluateJavascript 回调 JS 侧注册的 Promise。
     * <p>
     * 回调：window.__fetchBridgeCallback(callbackId, resultJson)
     * resultJson = {"status": int, "contentType": "...", "body": "...", "base64": "..."}
     * 出错时 status 为 0 并带 "error" 字段。
     */
    @JavascriptInterface
    public void httpRequestAsync(String method, String path, String body, String callbackId) {
        final String m = method == null ? "GET" : method;
        final String p = path == null ? "/" : path;
        final String b = body;
        final String cid = callbackId == null ? "" : callbackId;
        new Thread(() -> {
            final String result = httpRequestSync(m, p, b);
            if (webView == null) {
                return;
            }
            webView.post(() -> {
                try {
                    String cbIdJs = JSONObject.quote(cid);
                    webView.evaluateJavascript(
                            "window.__fetchBridgeCallback(" + cbIdJs + ", " + result + ");", null);
                } catch (Exception e) {
                    Log.e(TAG, "callback failed", e);
                }
            });
        }, "fetch-bridge").start();
    }

    /** 同步执行 HTTP（在后台线程中调用），返回 JSON 结果字符串 */
    private String httpRequestSync(String method, String path, String body) {
        // 关键：与 WebView 共享 cookie。
        // 页面导航（WebView 网络栈）与 fetch 桥（HttpURLConnection）是两个独立的
        // cookie 存储，Flask session 依赖 cookie——不同步会导致会话断裂
        // （如"请从首页开始游戏"拦截、游戏状态丢失）。
        // 因此请求前把 WebView cookie jar 的 cookie 带上，响应后把 Set-Cookie 写回。
        CookieManager webCookies = null;
        try {
            webCookies = CookieManager.getInstance();
        } catch (Exception ignore) {
            // WebView 未初始化时不可用，跳过 cookie 同步
        }
        HttpURLConnection conn = null;
        try {
            String url = "http://127.0.0.1:" + MainActivity.PORT + path;
            conn = (HttpURLConnection) new URL(url).openConnection();
            conn.setRequestMethod(method == null ? "GET" : method);
            // LLM 请求可能耗时较长，读超时放宽
            conn.setConnectTimeout(15_000);
            conn.setReadTimeout(180_000);
            conn.setInstanceFollowRedirects(true);
            // 带上 WebView 侧的 cookie（含 Flask session）
            if (webCookies != null) {
                String cookieHeader = webCookies.getCookie(url);
                if (cookieHeader != null && !cookieHeader.isEmpty()) {
                    conn.setRequestProperty("Cookie", cookieHeader);
                }
            }
            if (body != null && !body.isEmpty()) {
                conn.setDoOutput(true);
                conn.setRequestProperty("Content-Type", "application/json");
                try (OutputStream out = conn.getOutputStream()) {
                    out.write(body.getBytes(StandardCharsets.UTF_8));
                }
            }
            int status = conn.getResponseCode();
            // 响应 Set-Cookie 写回 WebView cookie jar，保证会话在导航与桥之间一致
            if (webCookies != null) {
                java.util.List<String> setCookies = conn.getHeaderFields().get("Set-Cookie");
                if (setCookies != null) {
                    for (String sc : setCookies) {
                        try {
                            webCookies.setCookie(url, sc);
                        } catch (Exception ignore) {
                        }
                    }
                }
            }
            InputStream in = (status >= 400) ? conn.getErrorStream() : conn.getInputStream();
            String respBody = in == null ? "" : readAll(in);
            String contentType = conn.getContentType();

            JSONObject result = new JSONObject();
            result.put("status", status);
            result.put("contentType", contentType == null ? "" : contentType);
            result.put("body", respBody);
            result.put("base64", android.util.Base64.encodeToString(
                    respBody.getBytes(StandardCharsets.UTF_8), android.util.Base64.NO_WRAP));
            return result.toString();
        } catch (Exception e) {
            Log.e(TAG, "httpRequest failed: " + method + " " + path, e);
            JSONObject result = new JSONObject();
            try {
                result.put("status", 0);
                result.put("error", e.toString());
            } catch (Exception ignore) {
            }
            return result.toString();
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    private static String readAll(InputStream in) throws IOException {
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        byte[] buf = new byte[64 * 1024];
        int n;
        while ((n = in.read(buf)) > 0) {
            out.write(buf, 0, n);
        }
        return out.toString("UTF-8");
    }

    /**
     * 读取 config.json 原始内容（JSON 字符串）。
     * WebView 的 fetch 在某些环境下不可靠，设置面板优先走此桥直接读文件。
     */
    @JavascriptInterface
    public String readConfigFile() {
        try {
            File f = new File(DataDirs.getDataDir(context), "config.json");
            if (!f.exists()) {
                return null;
            }
            return new String(Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8);
        } catch (Exception e) {
            Log.e(TAG, "readConfigFile failed", e);
            return null;
        }
    }

    /**
     * 写入 config.json（合并 llm / image_gen 段，保留 app 段不变）。
     * 写入后 Flask 的热重载会检测到 mtime 变化自动生效。
     * 返回 "ok" 或 "error: 详情"。
     */
    @JavascriptInterface
    public String saveConfigFile(String jsonContent) {
        try {
            File dir = DataDirs.getDataDir(context);
            if (!dir.exists() && !dir.mkdirs()) {
                return "error: 无法创建数据目录";
            }
            File f = new File(dir, "config.json");
            JSONObject merged;
            if (f.exists()) {
                merged = new JSONObject(
                        new String(Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8));
            } else {
                merged = new JSONObject();
            }
            JSONObject incoming = new JSONObject(jsonContent);
            if (incoming.has("llm")) {
                merged.put("llm", incoming.getJSONObject("llm"));
            }
            if (incoming.has("image_gen")) {
                merged.put("image_gen", incoming.getJSONObject("image_gen"));
            }
            // app 段（secret_key 等）保持不变，防止 session 失效
            Files.write(f.toPath(), merged.toString(2).getBytes(StandardCharsets.UTF_8));
            return "ok";
        } catch (Exception e) {
            Log.e(TAG, "saveConfigFile failed", e);
            return "error: " + e.getMessage();
        }
    }

    private boolean saveViaMediaStore(String filename, String mimeType, byte[] bytes) {
        ContentValues values = new ContentValues();
        values.put(MediaStore.MediaColumns.DISPLAY_NAME, filename);
        values.put(MediaStore.MediaColumns.MIME_TYPE, mimeType == null || mimeType.isEmpty()
                ? "application/octet-stream" : mimeType);
        values.put(MediaStore.MediaColumns.RELATIVE_PATH,
                Environment.DIRECTORY_DOWNLOADS);
        Uri uri = context.getContentResolver()
                .insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
        if (uri == null) {
            Log.e(TAG, "MediaStore insert returned null");
            return false;
        }
        try (OutputStream out = context.getContentResolver().openOutputStream(uri)) {
            if (out == null) {
                return false;
            }
            out.write(bytes);
            return true;
        } catch (IOException e) {
            Log.e(TAG, "MediaStore write failed", e);
            return false;
        }
    }

    private boolean saveLegacy(String filename, byte[] bytes) {
        File downloads = Environment.getExternalStoragePublicDirectory(
                Environment.DIRECTORY_DOWNLOADS);
        if (!downloads.exists() && !downloads.mkdirs()) {
            Log.e(TAG, "cannot create downloads dir: " + downloads);
            return false;
        }
        File target = new File(downloads, sanitize(filename));
        try (FileOutputStream out = new FileOutputStream(target)) {
            out.write(bytes);
            return true;
        } catch (IOException e) {
            Log.e(TAG, "legacy save failed", e);
            return false;
        }
    }

    private static String sanitize(String name) {
        String cleaned = name == null ? "download" : name;
        cleaned = cleaned.replaceAll("[/\\\\:*?\"<>|]", "_");
        return cleaned.isEmpty() ? "download" : cleaned;
    }

    private void showToast(final String message) {
        new Handler(Looper.getMainLooper()).post(() ->
                Toast.makeText(context, message, Toast.LENGTH_LONG).show());
    }
}
