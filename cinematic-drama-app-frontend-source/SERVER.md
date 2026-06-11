# Cinematic Drama 后端说明

## 启动

打开两个终端。

后端：

```powershell
cd C:\Users\Lenovo\demo\cinematic-drama-app
npm run server
```

前端：

```powershell
cd C:\Users\Lenovo\demo\cinematic-drama-app
npm run dev
```

前端地址：`http://127.0.0.1:5174/home`  
后端健康检查：`http://127.0.0.1:8787/api/health`

## 数据位置

- 剧目和选集：`server/data/catalog.json`
- 视频：`server/storage/videos/{dramaId}/`
- 互动清单：`server/storage/interactions/{dramaId}/`

前端工程的 `public` 和构建后的 `dist` 不保存正片视频。视频通过后端 `/api/videos/:dramaId/:episodeNumber` 接口传输。

## 已提供接口

| 方法 | 地址 | 作用 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/dramas` | 获取全部剧目 |
| GET | `/api/dramas/:id` | 获取作品介绍和选集 |
| GET | `/api/dramas/:id/episodes` | 获取选集 |
| GET | `/api/dramas/:id/episodes/:number` | 获取单集信息 |
| GET | `/api/dramas/:id/episodes/:number/interactions` | 获取互动清单 |
| GET/HEAD | `/api/videos/:id/:number` | 视频流，支持 Range 分段请求 |
| POST | `/api/ai/search` | AI 搜索预留接口，当前返回 501 |

## Android 和线上部署

Web 本地开发使用 Vite 代理，不需要设置 API 地址。

Android 真机和线上前端必须设置可访问的后端地址：

```powershell
$env:VITE_API_BASE_URL="https://你的后端域名"
npm run build
npx cap sync android
```

真机不能使用电脑的 `127.0.0.1`。正式环境建议使用 HTTPS，并把视频文件替换为对象存储或 CDN 地址。

## 添加新剧

1. 在 `server/data/catalog.json` 增加剧目信息。
2. 将视频放入 `server/storage/videos/{dramaId}/`。
3. 将互动清单放入 `server/storage/interactions/{dramaId}/`。
4. 在剧目的 `episodes` 中填写 `videoFile` 和 `interactionFile`。

