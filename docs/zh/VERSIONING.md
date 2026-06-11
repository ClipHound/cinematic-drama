# 版本管理说明

本项目使用 Git 管理版本。根目录作为 monorepo，包含前端、离线内容理解系统、Django 后端和设计文档。

## 分支建议

- `main`：稳定基线，只放已确认可回退的版本。
- `feature/<name>`：新功能开发，例如 `feature/django-ingest`。
- `fix/<name>`：缺陷修复，例如 `fix/home-autoplay`。
- `audit/<name>`：审计或文档整理。

## 常用命令

```powershell
git status
git switch -c feature/django-backend
git add .
git commit -m "Implement Django catalog models"
git switch main
git merge feature/django-backend
```

## 回退方式

查看历史：

```powershell
git log --oneline --decorate --graph --all
```

临时回到某个版本查看：

```powershell
git switch --detach <commit>
```

撤销某次提交并保留历史：

```powershell
git revert <commit>
```

仅恢复某个文件：

```powershell
git restore --source <commit> -- path/to/file
```

## 不纳入版本库的内容

以下内容默认不提交：

- `.env` 和任何密钥文件
- `node_modules/`、`dist/`
- Django 本地数据库和上传媒体
- 运行日志、临时文件
- 离线 Pipeline 生成物
- 正片视频等大媒体文件

如果后续确实需要管理大视频或模型产物，应单独引入 Git LFS 或对象存储，不要直接提交到普通 Git 历史。
