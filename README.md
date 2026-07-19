# 🎬 字幕烧录工具 · Subtitle Burner

> 基于 FFmpeg + libass 的自托管字幕烧录 Web 服务，支持 ASS / SRT / VTT / SSA / Sub 全格式。
> Self-hosted subtitle burn-in Web service based on FFmpeg + libass.

[![GitHub Container Registry](https://img.shields.io/badge/GHCR-ghcr.io%2F1263478456%2Fsubtitle--burner-blue?logo=github)](https://github.com/1263478456/subtitle-burner/pkgs/container/subtitle-burner)
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

## 📋 完整配置示例 / Complete Examples

### CPU 模式 (docker-compose.yml)

```yaml
services:
  subtitle-burner:
    image: ghcr.io/1263478456/subtitle-burner:latest
    container_name: subtitle-burner
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - TZ=Asia/Shanghai
      - ADMIN_USERNAME=admin
      - ADMIN_PASSWORD=your_secure_password_here
      - SESSION_SECRET=your_random_secret_at_least_32_chars
      - MEDIA_ROOT=/media
    volumes:
      - ./data:/data
      - /path/to/your/videos:/media  # 修改为你的媒体目录
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
```

### GPU 模式 (docker-compose.yml)

```yaml
services:
  subtitle-burner-gpu:
    image: ghcr.io/1263478456/subtitle-burner:latest-gpu
    container_name: subtitle-burner-gpu
    restart: unless-stopped
    ports:
      - "8000:8000"  # 或使用 8001:8000 避免与其他服务冲突
    environment:
      - TZ=Asia/Shanghai
      - ADMIN_USERNAME=admin
      - ADMIN_PASSWORD=your_secure_password_here
      - SESSION_SECRET=your_random_secret_at_least_32_chars
      - MEDIA_ROOT=/media
    volumes:
      - ./data:/data
      - /path/to/your/videos:/media  # 修改为你的媒体目录
    runtime: nvidia
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1  # 使用 GPU数量，或 "all"
              capabilities: [gpu, video, compute, utility]
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s
```

### 同时运行 CPU + GPU

```yaml
services:
  # CPU 服务 - 端口 8000
  subtitle-burner:
    image: ghcr.io/1263478456/subtitle-burner:latest
    container_name: subtitle-burner
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - TZ=Asia/Shanghai
      - ADMIN_USERNAME=admin
      - ADMIN_PASSWORD=your_secure_password_here
      - SESSION_SECRET=your_random_secret_at_least_32_chars
    volumes:
      - ./data:/data
      - /path/to/your/videos:/media

  # GPU 服务 - 端口 8001
  subtitle-burner-gpu:
    image: ghcr.io/1263478456/subtitle-burner:latest-gpu
    container_name: subtitle-burner-gpu
    restart: unless-stopped
    ports:
      - "8001:8000"
    environment:
      - TZ=Asia/Shanghai
      - ADMIN_USERNAME=admin
      - ADMIN_PASSWORD=your_secure_password_here
      - SESSION_SECRET=your_random_secret_at_least_32_chars
    volumes:
      - ./data:/data
      - /path/to/your/videos:/media
    runtime: nvidia
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu, video, compute, utility]
```

### TrueNAS Scale 部署示例

```yaml
services:
  subtitle-burner:
    image: ghcr.io/1263478456/subtitle-burner:latest-gpu
    container_name: subtitle-burner
    restart: unless-stopped
    network_mode: bridge
    ports:
      - "3214:8000"
    environment:
      - TZ=Asia/Shanghai
      - ADMIN_USERNAME=${ADMIN_USERNAME}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
      - SESSION_SECRET=${SESSION_SECRET}
      - MAX_FILE_SIZE_MB=204800
      - MAX_CONCURRENT_TASKS=4
      - MEDIA_ROOT=/media
      - LOG_LEVEL=INFO
      - FFMPEG_TIMEOUT=7200
      - PROGRESS_STALL_TIMEOUT=600
    volumes:
      - /mnt/vol1/apps/subtitle-burner/data/input:/data/input
      - /mnt/vol1/apps/subtitle-burner/data/output:/data/output
      - /mnt/vol1/apps/subtitle-burner/data/fonts:/usr/share/fonts/custom:ro
      - /mnt/vol1/apps/subtitle-burner/data/db:/data/db
      - /mnt/vol1/media:/media:ro
    runtime: nvidia
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu, video, compute, utility]
```

> 💡 **提示**：
> - 修改 `your_secure_password_here` 为强密码
> - 修改 `your_random_secret_at_least_32_chars` 为随机字符串（可用 `openssl rand -hex 32` 生成）
> - 修改 `/path/to/your/videos` 为你的实际媒体目录
> - GPU模式需要主机已安装 [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

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
- ⏹ 任务停止功能，支持排队中和处理中的任务
- 🎬 两种字幕模式：压制字幕（硬字幕）/ 添加字幕轨道（软字幕）
- 📁 媒体库浏览，智能配对视频和字幕文件

---

## 🔧 环境变量 / Environment Variables

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ADMIN_USERNAME` | `admin` | 管理员用户名 |
| `ADMIN_PASSWORD` | - | 管理员密码（必填） |
| `SESSION_SECRET` | - | Session 加密密钥（必填，≥32字符） |
| `MEDIA_ROOT` | `/media` | 媒体库根目录 |
| `MAX_FILE_SIZE_MB` | `204800` | 最大上传文件大小（MB） |
| `MAX_CONCURRENT_TASKS` | `4` | 最大并发任务数 |
| `FFMPEG_TIMEOUT` | `7200` | FFmpeg 超时时间（秒） |
| `PROGRESS_STALL_TIMEOUT` | `600` | 进度卡住超时（秒） |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_ACCESS` | `false` | 是否记录访问日志 |

---

## 📦 镜像源 / Image Sources

| 源 | 地址 |
|----|------|
| GitHub Container Registry | `ghcr.io/1263478456/subtitle-burner:latest` |
| GitHub Container Registry (GPU) | `ghcr.io/1263478456/subtitle-burner:latest-gpu` |

---

## 🏗️ 本地构建 / Local Build

如果需要从源码构建：

```bash
# CPU 版本
docker build -f app/Dockerfile.cpu -t subtitle-burner:local ./app

# GPU 版本
docker build -f app/Dockerfile.gpu -t subtitle-burner:local-gpu ./app
```

然后在 `docker-compose.yml` 中使用本地镜像：

```yaml
image: subtitle-burner:local
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
