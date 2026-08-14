package com.renshengchongkai.app;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.animation.ObjectAnimator;
import android.animation.ValueAnimator;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.KeyEvent;
import android.view.View;
import android.view.animation.AccelerateDecelerateInterpolator;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.net.InetSocketAddress;
import java.net.Socket;

/**
 * AI 人生重开手帐 — Android 套壳入口。
 *
 * 启动流程：
 *  1. 解压 assets/python（templates/static）→ filesDir/app_assets
 *  2. 创建数据目录 filesDir/data（config.json / .sessions / records / generated）
 *  3. 后台线程启动 Python：Flask 监听 127.0.0.1:3000
 *  4. 轮询端口就绪后，WebView 加载 http://127.0.0.1:3000
 *
 * WebView 支持：
 *  - JS + DOM Storage（游戏本地存档 localStorage 依赖）
 *  - 文件选择（导入存档 <input type=file>）
 *  - AndroidBridge：导出 txt/json/html/png 保存到系统下载目录
 */
public class MainActivity extends Activity {

    private static final String TAG = "LifeGame";
    static final int PORT = 3000;
    private static final String HOME_URL = "http://127.0.0.1:" + PORT + "/";
    private static final int SERVER_WAIT_TIMEOUT_MS = 60_000;

    private static final int REQ_FILE_CHOOSER = 0x1001;
    private static final int REQ_WRITE_STORAGE = 0x1002;

    private WebView webView;
    private ValueCallback<Uri[]> filePathCallback;
    private volatile String pythonError;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.webview);

        // 1. 静态资源解压（版本一致时跳过）
        AssetExtractor.extract(this);
        // 2. 可写数据目录
        DataDirs.ensure(this);
        // 3. API 26-28 写公共下载目录需要运行时权限（29+ 走 MediaStore 无需权限）
        requestLegacyStoragePermissionIfNeeded();
        // 4. Python 运行时初始化必须在主线程（Chaquopy javaclass 桥依赖主线程注册，
        //    后台线程调用会导致 "No module named 'com'"）
        try {
            if (!Python.isStarted()) {
                Python.start(new AndroidPlatform(this));
            }
        } catch (Exception e) {
            java.io.StringWriter sw = new java.io.StringWriter();
            e.printStackTrace(new java.io.PrintWriter(sw));
            pythonError = sw.toString();
            Log.e(TAG, "python init failed: " + pythonError, e);
            showStartupError("Python 初始化失败：\n" + sw);
        }
        // 5. 后台启动 Flask 服务
        new Thread(this::startPythonServer, "python-server").start();
        // 6. WebView 配置
        setupWebView();
        // 7. 载入界面动画
        startSplashAnimation();
        // 8. 等待 Flask 端口就绪后加载首页
        waitForServerAndLoad();
    }

    // ============ 载入界面 ============

    private void startSplashAnimation() {
        // 三个星点依次呼吸（错开相位）
        final View[] dots = {
                findViewById(R.id.splash_dot1),
                findViewById(R.id.splash_dot2),
                findViewById(R.id.splash_dot3),
        };
        for (int i = 0; i < dots.length; i++) {
            final int idx = i;
            final float delay = idx * 260f;
            ObjectAnimator scaleX = ObjectAnimator.ofFloat(dots[i], "scaleX", 1f, 1.9f);
            scaleX.setDuration(900);
            scaleX.setStartDelay((long) delay);
            scaleX.setRepeatCount(ValueAnimator.INFINITE);
            scaleX.setRepeatMode(ValueAnimator.REVERSE);
            scaleX.setInterpolator(new AccelerateDecelerateInterpolator());
            scaleX.start();
            ObjectAnimator scaleY = ObjectAnimator.ofFloat(dots[i], "scaleY", 1f, 1.9f);
            scaleY.setDuration(900);
            scaleY.setStartDelay((long) delay);
            scaleY.setRepeatCount(ValueAnimator.INFINITE);
            scaleY.setRepeatMode(ValueAnimator.REVERSE);
            scaleY.setInterpolator(new AccelerateDecelerateInterpolator());
            scaleY.start();
            ObjectAnimator alpha = ObjectAnimator.ofFloat(dots[i], "alpha", 1f, 0.35f);
            alpha.setDuration(900);
            alpha.setStartDelay((long) delay);
            alpha.setRepeatCount(ValueAnimator.INFINITE);
            alpha.setRepeatMode(ValueAnimator.REVERSE);
            alpha.setInterpolator(new AccelerateDecelerateInterpolator());
            alpha.start();
        }
        // 图标呼吸微光
        ObjectAnimator iconGlow = ObjectAnimator.ofFloat(
                findViewById(R.id.splash_icon), "alpha", 0.72f, 1f);
        iconGlow.setDuration(1500);
        iconGlow.setRepeatCount(ValueAnimator.INFINITE);
        iconGlow.setRepeatMode(ValueAnimator.REVERSE);
        iconGlow.start();
    }

    private void hideSplash() {
        final View splash = findViewById(R.id.splash);
        if (splash == null || splash.getVisibility() != View.VISIBLE) {
            return;
        }
        splash.animate().alpha(0f).setDuration(500).withEndAction(() ->
                splash.setVisibility(View.GONE)).start();
    }

    // ============ Python 服务 ============

    private void startPythonServer() {
        try {
            PyObject module = Python.getInstance().getModule("startup");
            // filesDir 绝对路径直接传入，startup.py 无需依赖 javaclass 桥
            module.callAttr("main", getFilesDir().getAbsolutePath());
            Log.i(TAG, "python server thread exited");
        } catch (Exception e) {
            // 完整堆栈（含 Python traceback），弹窗显示方便直接定位
            java.io.StringWriter sw = new java.io.StringWriter();
            e.printStackTrace(new java.io.PrintWriter(sw));
            String msg = sw.toString();
            Log.e(TAG, "python server failed: " + msg, e);
            pythonError = msg;
            runOnUiThread(() -> showStartupError(msg));
        }
    }

    private void waitForServerAndLoad() {
        new Thread(() -> {
            long deadline = System.currentTimeMillis() + SERVER_WAIT_TIMEOUT_MS;
            boolean up = false;
            while (System.currentTimeMillis() < deadline) {
                if (pythonError != null) {
                    return; // 错误已由 startPythonServer 显示
                }
                if (isPortOpen()) {
                    up = true;
                    break;
                }
                try {
                    Thread.sleep(400);
                } catch (InterruptedException e) {
                    return;
                }
            }
            final boolean serverUp = up;
            runOnUiThread(() -> {
                if (serverUp) {
                    webView.loadUrl(HOME_URL);
                } else if (pythonError == null) {
                    showServerError();
                }
            });
        }, "server-wait").start();
    }

    private boolean isPortOpen() {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("127.0.0.1", PORT), 300);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private void showServerError() {
        showStartupError("Python 服务未能启动（60 秒内端口未就绪）");
    }

    private void showStartupError(String detail) {
        new AlertDialog.Builder(this)
                .setTitle("启动失败")
                .setMessage("Python 服务未能启动。\n\n错误信息：\n" + detail)
                .setPositiveButton("重试", (d, w) -> {
                    d.dismiss();
                    pythonError = null;
                    new Thread(this::startPythonServer, "python-server").start();
                    waitForServerAndLoad();
                })
                .setNegativeButton("退出", (d, w) -> finish())
                .setCancelable(false)
                .show();
    }

    // ============ WebView ============

    @SuppressWarnings("deprecation")
    private void setupWebView() {
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        s.setAllowFileAccess(false);
        // 仅本机 Flask 服务，允许远程调试（chrome://inspect 可查）
        WebView.setWebContentsDebuggingEnabled(true);

        // WebView cookie：Flask session 依赖；fetch 桥（AndroidBridge.httpRequest）
        // 也会读写这个 cookie jar，导航与 API 请求共享同一会话
        try {
            android.webkit.CookieManager cm = android.webkit.CookieManager.getInstance();
            cm.setAcceptCookie(true);
            cm.flush();
        } catch (Exception e) {
            Log.w(TAG, "cookie manager init failed", e);
        }

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                // 首页加载完成，淡出载入界面
                if (url.startsWith(HOME_URL)) {
                    hideSplash();
                }
            }

            @Override
            public void onReceivedError(WebView view, int errorCode,
                                        String description, String failingUrl) {
                super.onReceivedError(view, errorCode, description, failingUrl);
                // 首页加载失败：隐藏载入界面并提示，避免卡在 splash
                if (failingUrl != null && failingUrl.startsWith(HOME_URL)
                        && findViewById(R.id.splash).getVisibility() == View.VISIBLE) {
                    hideSplash();
                    new AlertDialog.Builder(MainActivity.this)
                            .setTitle("加载失败")
                            .setMessage("无法连接本地服务（" + errorCode + " " + description + "）\n"
                                    + "请点重试重新加载。")
                            .setPositiveButton("重试", (d, w) -> {
                                d.dismiss();
                                webView.loadUrl(HOME_URL);
                            })
                            .setNegativeButton("退出", (d, w) -> finish())
                            .setCancelable(false)
                            .show();
                }
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView webView,
                                             ValueCallback<Uri[]> filePathCallback,
                                             FileChooserParams fileChooserParams) {
                return MainActivity.this.onShowFileChooser(filePathCallback, fileChooserParams);
            }
        });
        webView.addJavascriptInterface(new AndroidBridge(this, webView), "AndroidBridge");
    }

    private boolean onShowFileChooser(ValueCallback<Uri[]> callback,
                                      WebChromeClient.FileChooserParams params) {
        if (filePathCallback != null) {
            filePathCallback.onReceiveValue(null);
        }
        filePathCallback = callback;
        try {
            startActivityForResult(params.createIntent(), REQ_FILE_CHOOSER);
            return true;
        } catch (ActivityNotFoundException e) {
            filePathCallback.onReceiveValue(null);
            filePathCallback = null;
            return false;
        }
    }

    @Override
    @SuppressWarnings("deprecation")
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == REQ_FILE_CHOOSER) {
            if (filePathCallback != null) {
                Uri[] results = null;
                if (resultCode == RESULT_OK && data != null) {
                    if (data.getClipData() != null) {
                        int count = data.getClipData().getItemCount();
                        results = new Uri[count];
                        for (int i = 0; i < count; i++) {
                            results[i] = data.getClipData().getItemAt(i).getUri();
                        }
                    } else if (data.getData() != null) {
                        results = new Uri[]{data.getData()};
                    }
                }
                filePathCallback.onReceiveValue(results);
                filePathCallback = null;
            }
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    private void requestLegacyStoragePermissionIfNeeded() {
        if (Build.VERSION.SDK_INT <= 28
                && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE},
                    REQ_WRITE_STORAGE);
        }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView.canGoBack()) {
            webView.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (webView != null) {
            webView.onPause();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) {
            webView.onResume();
        }
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
        }
        super.onDestroy();
    }
}
