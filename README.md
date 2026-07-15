## ⚠️ 免责声明 / Disclaimer

> **本代码由 AI 生成，谨慎使用。**
> 本项目部分或全部代码由人工智能辅助生成，未经过大规模生产环境验证。
> 使用前请自行评估安全性、稳定性与合规性，作者不对直接使用造成的任何损失负责。
> 建议在测试环境充分验证后再部署到生产环境。

---

# 🎬 字幕烧录工具 · Subtitle Burner

> 基于 FFmpeg + libass 的自托管字幕烧录 Web 服务，支持 ASS / SRT / VTT / SSA / Sub 全格式。
> Self-hosted subtitle burn-in Web service based on FFmpeg + libass.

[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-1263478456%2Fsubtitle--burner-blue?logo=docker)](https://hub.docker.com/r/1263478456/subtitle-burner)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![TrueNAS](https://img.shields.io/badge/Tested%20on-TrueNAS%20Scale-blueviolet)](https://www.truenas.com/)

---

## 🚀 快速开始 / Quick Start

```bash
# 1. 创建目录并进入
mkdir subtitle-burner && cd subtitle-burner

# 2. 下载编排文件
curl -O https://raw.githubusercontent.com/1263478456/subtitle-burner/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/1263478456/subtitle-burner/main/.env.example

# 3. 配置环境变量
cp .env.example .env
nano .env   # 修改 ADMIN_PASSWORD / SECRET_KEY

# 4. 启动服务
docker compose up -d

# 浏览器访问 http://<host-ip>:8000
```

**GPU 模式**（NVIDIA NVENC）：
```bash
docker compose --profile gpu up -d
# 访问端口 8001
```

---

## ✨ 特性 / Features

- 🎯 多格式支持：ASS / SSA / SRT / VTT / Sub
- 🌐 中文 Web UI，原生 HTML/JS，无框架依赖
- 🔐 登录鉴权 + Session
- 📦 批量队列，并行压制
- 📋 历史记录 + SQLite 持久化
- 🐳 CPU / GPU 双镜像 + Compose 一键启动
- 📡 `/health` 健康探针 + OpenAPI 自动文档
- ⚡ FFmpeg 实时进度解析，精确到秒
- 🔄 失败任务自动重试，批量总进度条

---

## ⚙️ 环境变量 / Environment

| 变量 | 说明 | 默认值 |
|---|---|---|
| `ADMIN_USERNAME` | 管理员账号 | `admin` |
| `ADMIN_PASSWORD` | 管理员密码 | `changeme` |
| `SECRET_KEY` | Session 加密密钥（≥32 字节） | - |
| `BIND_HOST` | 绑定地址，IPv6 写 `[::]` | `0.0.0.0` |
| `BIND_PORT` | 主机端口 | `8000` |
| `MAX_CONCURRENT_TASKS` | 队列并行数 | `2` |
| `MAX_FILE_SIZE_MB` | 单文件上传上限 | `2048` |
| `NVIDIA_VISIBLE_DEVICES` | GPU profile 使用哪几张卡 | `all` |

> ⚠️ **安全提示**：生产环境务必修改 `ADMIN_PASSWORD` 与 `SECRET_KEY`。可用 `openssl rand -hex 32` 生成密钥。

---

## 🛠️ 技术栈 / Tech Stack

- **后端**：Python 3.11 + FastAPI
- **前端**：原生 HTML/CSS/JS，模块化拆分
- **数据库**：SQLite
- **核心**：FFmpeg + libass
- **容器**：Docker + Docker Compose
- **CI/CD**：GitHub Actions → Docker Hub / GHCR

---

## 🏗️ TrueNAS Scale 部署

```bash
# 1. SSH 登录 TrueNAS
ssh root@truenas.local

# 2. 创建数据集目录
mkdir -p /mnt/pool/apps/subtitle-burner/data/{uploads,outputs,fonts,db}
cd /mnt/pool/apps/subtitle-burner

# 3. 写入 docker-compose.yml 与 .env
# 4. 启动
docker compose up -d
```

**IPv6-only 环境**：把 `BIND_HOST=[::]` 即可在公网双栈访问。

---

## 🤖 CI/CD 与版本发布

- 推送 `v*.*.*` tag → 自动构建并发布 release 镜像
- 合入 `main` 分支 → 自动构建 `dev` 镜像
- 多架构支持：`linux/amd64` + `linux/arm64`

镜像标签：
- `1263478456/subtitle-burner:latest` — 最新 release
- `1263478456/subtitle-burner:v3.0.8` — 语义化版本
- `ghcr.io/1263478456/subtitle-burner:v3.0.8` — GHCR 同步

---

## 📖 完整文档 / Full Documentation

详见 [GitHub README](https://github.com/1263478456/subtitle-burner#readme)。
