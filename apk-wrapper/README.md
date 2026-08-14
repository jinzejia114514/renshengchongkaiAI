# apk-wrapper — Android 套壳工程

把 Flask 应用（AI 人生重开手帐）打包成 Android APK 的 Gradle 工程。

## 技术方案

| 层 | 技术 |
|---|---|
| Python 运行时 | [Chaquopy](https://chaquo.com/chaquopy/) 16.0.0，Python 3.11 |
| Web 框架 | Flask 3.0.3 + flask-session **0.6.0**（0.7+/0.8 依赖 msgspec C 扩展，Chaquopy 无 android wheel）+ cachelib 0.14.0 + requests + pillow 11.0.0 |
| UI | 原生 WebView 加载 `http://127.0.0.1:3000` |
| 构建 | AGP 8.2.2 / Gradle 8.5 / compileSdk 34 / minSdk 26 / **仅 arm64-v8a**（v2.0 起，APK ~27MB） |
| 版本 | 当前 v2.0（versionCode 2） |

## 运行时目录（Android）

| 路径 | 内容 |
|---|---|
| `filesDir/app_assets/` | 从 assets 解压的 templates/static 只读资源（APK 版本升级时自动重解压） |
| `filesDir/data/config.json` | LLM 配置（Python 首启自动补全生成，支持热重载） |
| `filesDir/data/.sessions/` | Flask-Session 会话文件 |
| `filesDir/data/records/` | 游戏记录（不审核直接保存） |
| `filesDir/data/static/generated/` | 生成的四格漫画图片 |

config.json、记录、图片全部位于应用私有数据目录，与代码分离；
升级 APK 不会清空用户数据。

## 源码同步

`app/build.gradle` 的两个 Gradle 任务负责把**项目根目录**（Flask 源码唯一来源）
同步进构建：

- `syncPythonSrc` → `build/python-src/`：`*.py` + `routes/`，由 Chaquopy 编译成 pyc 打包
- `syncPythonAssets` → `build/python-assets/python/`：`templates/` + `static/`，
  打包进 APK assets，Java 首启解压

所以修改 Flask 代码后**无需手工复制**，直接重新构建即可。

## 构建

**一键构建**：双击 `build_apk.bat`（设置环境变量 → 构建 → APK 复制到桌面）。

或手动：
```bat
set ANDROID_HOME=D:\Android
cd apk-wrapper
D:\Android\gradle\latest\bin\gradle.bat assembleDebug --no-daemon
```

产物：`app/build/outputs/apk/debug/app-debug.apk`（构建脚本自动复制到桌面）

## 安装到设备

```bat
D:\Android\platform-tools\adb.exe install -r app-debug.apk
```

## WebView 能力适配

- **全局 fetch 原生桥**：WebView 的 fetch 不可靠（全部请求静默失败），
  `base.html` 在 Android 环境把 `window.fetch` 包装为
  `AndroidBridge.httpRequest()`（HttpURLConnection + CookieManager 维持 Flask
  session）——游戏核心 API、设置、公告、导出全部自动生效，浏览器环境不变
- **配置直写文件**：设置面板与数据管理页在 Android 走
  `AndroidBridge.readConfigFile()/saveConfigFile()` 直读直写 config.json
  （保留 app 段），浏览器走 `/api/config`
- **导入存档**（`<input type=file>`）：`MainActivity` 实现 `onShowFileChooser`
- **导出 txt/json/html/png**：前端统一 `downloadBlob()`——WebView 走
  `AndroidBridge.saveBase64File()` 保存到系统下载目录
  （API 29+ MediaStore，无需权限；API 26-28 公共下载目录 + 运行时权限）
- **html2canvas**：已本地化到 `static/vendor/html2canvas.min.js`（原 CDN 在无网时不可用）
- **localStorage 存档**：WebView 开启 DOM Storage
- **载入界面**：星空主题 splash 覆盖 Python 启动到首页渲染完成，`onPageFinished` 淡出
- **assets 指纹**：`AssetExtractor` 用内容指纹（非 versionCode）判断是否重解压，
  APK 更新模板/静态资源后自动生效

## 调试

- WebView 开启远程调试：Chrome 打开 `chrome://inspect`，设备连 USB
- Python 日志输出到 logcat，标签为 `python` / `LifeGame` / `AndroidBridge`
- 后端异常可在游戏内 LLM 设置面板或 logcat 查看
