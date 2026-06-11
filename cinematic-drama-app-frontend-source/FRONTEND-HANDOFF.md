# Cinematic Drama App 前端源码交接

## 技术栈

- React 19
- Vite 8
- TypeScript
- Tailwind CSS 4
- React Router
- Capacitor

## 本地运行

```powershell
npm install
npm run dev
```

默认地址：`http://127.0.0.1:5174/home`

本地开发时，Vite 会把 `/api` 请求代理到：

```text
http://127.0.0.1:8787
```

## 配置后端地址

复制 `.env.example` 为 `.env`，填写：

```text
VITE_API_BASE_URL=https://你的后端域名
```

正式 Android App 必须使用手机可访问的 HTTPS 后端地址，不能使用 `127.0.0.1`。

## 前端依赖的 API

| 方法 | 地址 | 用途 |
|---|---|---|
| GET | `/api/dramas` | 剧目列表 |
| GET | `/api/dramas/:id` | 作品介绍和选集 |
| GET | `/api/dramas/:id/episodes` | 选集列表 |
| GET | `/api/dramas/:id/episodes/:number` | 单集信息 |
| GET | `/api/dramas/:id/episodes/:number/interactions` | 单集互动清单 |
| GET/HEAD | `/api/videos/:id/:number` | 视频流，必须支持 Range |
| POST | `/api/ai/search` | AI 搜索预留接口 |

## 视频接口要求

- 支持 `Range: bytes=start-end`。
- 分段响应状态码为 `206 Partial Content`。
- 返回 `Accept-Ranges`、`Content-Range`、`Content-Length`。
- MP4 返回 `Content-Type: video/mp4`。
- 允许前端拖动进度和跳转播放位置。

## 主要目录

```text
src/pages/                 页面
src/components/            公共组件
src/data/catalog.ts        后端 API 数据层
src/interaction/           动画注册表与播放时间轴
public/assets/             动画所需资源
public/vendor/             Lottie 运行库
```

## 源码包说明

此交接包不包含：

- `node_modules`
- `dist`
- Android 生成工程
- 后端视频文件
- 编译产物

安装依赖后即可运行和继续开发。
