# 免费 HTTPS 部署与 Android 切换

正式环境推荐使用 HTTPS。最稳定的免费方案是准备一个域名或免费 DNS 子域名，将 A 记录指向你的服务器 IP：

```text
<YOUR_SERVER_IP>
```

以下示例假设 API 域名为 `api.example.com`、Django 监听 `127.0.0.1:8787`，服务器系统为 Ubuntu/Debian。

## 1. 配置 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name api.example.com;

    client_max_body_size 500m;

    location / {
        proxy_pass http://127.0.0.1:8787;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_buffering off;
    }
}
```

确认以下地址先能通过 HTTP 返回 Django JSON，而不是 `502`：

```text
http://api.example.com/api/dramas
```

## 2. 申请 Let’s Encrypt 免费证书

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d api.example.com
sudo certbot renew --dry-run
```

服务器防火墙和云安全组需要开放 TCP `80`、`443`。证书自动续期由 Certbot 定时任务负责。

Let’s Encrypt 也支持公网 IP 证书，但这类证书有效期很短、续期要求更高。除非已经有成熟的自动续期方案，否则优先使用域名证书。

## 3. 配置 Django

在 `django-backend/.env` 中至少配置：

```text
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=请替换为足够长的随机值
DJANGO_ALLOWED_HOSTS=api.example.com,<YOUR_SERVER_IP>
DJANGO_CORS_ALLOWED_ORIGINS=https://localhost
```

不要把真实密钥提交到 Git 或源码 ZIP。

## 4. 将 Android 切换到 HTTPS

修改 `cinematic-drama-app-frontend-source/.env.production`：

```text
VITE_API_BASE_URL=https://api.example.com
```

修改 `capacitor.config.ts`：

```ts
server: {
  androidScheme: 'https',
},
```

HTTPS 正常后，删除 `AndroidManifest.xml` 中的：

```xml
android:networkSecurityConfig="@xml/network_security_config"
```

并删除：

```text
android/app/src/main/res/xml/network_security_config.xml
```

最后重新同步和构建：

```powershell
npm ci
npm run android:sync
npm run android:apk
```

## 5. 上线检查

- `https://api.example.com/api/dramas` 返回 `200` 和 JSON。
- 响应包含 `Access-Control-Allow-Origin: https://localhost`。
- HTTPS 证书链在 Android 浏览器中无警告。
- 视频接口支持 Range 请求和 `206 Partial Content`。
- 真机关闭 Wi-Fi、使用移动网络时仍能加载剧目和播放视频。
