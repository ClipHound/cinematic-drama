# Android App 源码交付包

## 包含内容

- `cinematic-drama-app-frontend-source/`：React 前端、Capacitor 配置和完整 Android 原生工程。
- `django-backend/`：Android App 依赖的 Django API 服务源码。
- `HTTPS-DEPLOYMENT.md`：免费 HTTPS 证书、反向代理和 App 切换说明。

Android 合作者请先阅读：

```text
cinematic-drama-app-frontend-source/FRONTEND-HANDOFF.md
```

## 网络配置

- 生产环境需要部署 Django 后端到一台有公网 IP 或域名的服务器。
- Android App 的网络例外配置在 `capacitor.config.ts` 和 `AndroidManifest.xml` 中，详见 `FRONTEND-HANDOFF.md`。
- 部署指南请参考 `HTTPS-DEPLOYMENT.md`。

## 安全说明

归档不包含 `.env`、密钥、数据库、上传文件、`node_modules`、`dist`、Gradle 构建产物、日志或 Python 缓存。合作者需要按文档安装依赖。

APK/AAB 只包含 Android 容器和前端资源，不包含 Django、数据库或视频服务。
