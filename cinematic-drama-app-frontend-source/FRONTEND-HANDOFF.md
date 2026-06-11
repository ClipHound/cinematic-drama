# Android 源码构建说明

本目录是 React 19 + Vite 8 + Capacitor 8 工程，已经包含完整的 `android/` 原生项目。

## 环境要求

- Node.js 22 或更高版本
- Android Studio 2025.2.1 或兼容版本
- Android SDK Platform 36
- Android Studio 自带 JDK

## 当前 API 配置

`.env.production` 已配置：

```text
VITE_API_BASE_URL=http://116.204.134.65
```

Android 网络策略只允许该 IP 使用明文 HTTP。服务器地址改变时，需要同时修改：

```text
.env.production
android/app/src/main/res/xml/network_security_config.xml
```

服务器配置 HTTPS 后，请按上级目录的 `HTTPS-DEPLOYMENT.md` 切换配置。

## 首次构建

```powershell
npm ci
npm run android:sync
npm run android:open
```

在 Android Studio 中等待 Gradle Sync 完成，然后运行 `app`。

## 生成调试 APK

Windows：

```powershell
npm run android:apk
```

输出文件：

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

也可以在 Android Studio 中使用：

```text
Build > Build Bundle(s) / APK(s) > Build APK(s)
```

## 生成发布 AAB

```powershell
npm run android:aab
```

输出文件：

```text
android/app/build/outputs/bundle/release/app-release.aab
```

正式发布需要在 Android Studio 中配置自己的签名证书。不要把 `.jks`、`.keystore`、密码或 `keystore.properties` 放入源码包。

## 后端要求

- APK/AAB 不包含 Django 服务，后端必须单独部署。
- 手机中的 `127.0.0.1` 和 `localhost` 指向手机自身，不能作为远程 API 地址。
- 当前 Capacitor WebView 来源为 `http://localhost`。
- 当前 HTTP 模式下，Django CORS 必须允许 `http://localhost`。
- HTTPS 模式下，WebView 来源改为 `https://localhost`，Django CORS 也要同步修改。
- 视频接口必须支持 HTTP Range、`206 Partial Content`、`Accept-Ranges`、`Content-Range` 和 `Content-Length`。

## 日常开发流程

每次修改前端后执行：

```powershell
npm run android:sync
```

不要手工修改 `android/app/src/main/assets/public/`，同步时该目录会被 `dist/` 覆盖。

## Android 配置

- Application ID：`com.demo.cinematicdrama`
- App 名称：`Cinematic Drama`
- minSdk：24
- targetSdk：36
- compileSdk：36
- Web 构建目录：`dist`

正式上架前应确定最终 Application ID。一旦应用发布，不应再修改包名。

## 已知服务器状态

2026 年 6 月 11 日检查 `http://116.204.134.65/api/dramas` 时返回 `502 Bad Gateway`。这表示 Android 工程可以编译，但服务器反向代理尚未正确连接 Django；服务器修复前 App 无法加载在线数据。
