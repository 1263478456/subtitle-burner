# 🎬 字幕烧录工具 · Subtitle Burner

> 基于 FFmpeg + libass 的自托管字幕烧录 Web 服务，支持 ASS / SRT / VTT / SSA / Sub 全格式。
> Self-hosted subtitle burn-in Web service based on FFmpeg + libass.

[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-1263478456%2Fsubtitle--burner-blue?logo=docker)](https://hub.docker.com/r/1263478456/subtitle-burner)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![TrueNAS](https://img.shields.io/badge/Tested%20on-TrueNAS%20Scale-blueviolet)](https://www.truenas.com/)

---

## ✨ 特性 / Features

| | 中文 | English |
|---|---|---|
| 🎯 | 多格式支持：ASS / SSA / SRT / VTT / Sub | Multi-format: ASS/SSA/SRT/VTT/Sub |
| 🌐 | 中文 Web UI，原生 HTML/JS | Native HTML/JS web UI |
| 🔐 | 登录鉴权 + Session | Login auth + Session |
| 📦 | 批量队列，并行压制 | Batch queue with parallel encoding |
| 📋 | 历史记录 + SQLite 持久化 | History with SQLite persistence |
| 🐳 | CPU / GPU 双镜像 + Compose 一键启动 | CPU/GPU dual images + Compose |
| 📡 | `/health` 健康探针 + OpenAPI 自动文档 | `/health` probe + OpenAPI docs |

## 🚀 快速开始 / Quick Start

### 方式一：Docker Compose（推荐）

```bash
# 1. 创建并进入项目目录 / create project dir
mkdir subtitle-burner && cd subtitle-burner

# 2. 下载编排文件 / fetch compose
curl -O https://raw.githubusercontent.com/1263478456/subtitle-burner/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/1263478456/subtitle-burner/main/.env.example

# 3. 复制并修改环境变量 / configure env
cp .env.example .env
nano .env   # 修改 AUTH_USER / AUTH_PASS / SECRET_KEY

# 4. 拉取并启动 / pull & up
docker compose pull   # 拉取已发布镜像（跳过本地构建）
docker compose up -d  # 后台启动

# 浏览器访问 / visit: http://<host-ip>:8000
```

### 方式二：从源码本地构建

```bash
git clone https://github.com/1263478456/subtitle-burner.git
cd subtitle-burner
cp .env.example .env
docker compose up -d --build   # 走 app/Dockerfile.cpu
```

### 方式三：GPU 模式（需要 NVIDIA Container Toolkit）

```bash
# 主机先装 nvidia-container-toolkit：https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
docker compose --profile gpu up -d
# 访问端口 8001（与 CPU 实例错开）
```

## 📖 使用说明 / Usage

### 1. 烧录字幕 / Burn subtitles

1. 点击"选择视频文件"和"选择字幕文件"（支持多选）
2. 调整全局压制参数（编码器、质量、速度）
3. 点击"加入烧录队列"
4. 在队列页查看实时进度
5. 完成后点击"下载"获取成品

### 2. 智能匹配 / Auto-matching

- 视频和字幕同名（如 `movie.mp4` + `movie.ass`）会自动配对
- 不同名时按选择顺序配对

### 3. 自定义字体 / Custom fonts

将 `.ttf` / `.otf` 字体文件放入 `data/fonts/` 目录，重启容器即可生效：

```bash
cp SourceHanSansCN-Regular.otf data/fonts/
docker compose restart
```

### 4. 自定义 SRT/VTT 样式 / Custom style

在"全局压制参数"中填写 `force_style`：

```
FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1
```

颜色格式：`&H00FFFFFF` = 白色（**BBGGRR** 顺序，A=透明度）

## ⚙️ 配置说明 / Configuration

编辑 `.env`：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `ADMIN_USERNAME` | 管理员账号 | `admin` |
| `ADMIN_PASSWORD` | 管理员密码 | `changeme` |
| `SECRET_KEY` | Session 加密密钥（≥32 字节） | - |
| `BIND_HOST` | 绑定地址，IPv6 写 `[::]` | `0.0.0.0` |
| `BIND_PORT` | 主机端口 | `8000` |
| `LOG_LEVEL` | DEBUG / INFO / WARNING / ERROR | `INFO` |
| `MAX_CONCURRENT_TASKS` | 队列并行数 | `2` |
| `MAX_FILE_SIZE_MB` | 单文件上传上限 | `2048` |
| `NVIDIA_VISIBLE_DEVICES` | GPU profile 使用几张卡 | `all` |
| `NVIDIA_VISIBLE_DEVICES` | GPU profile 使用哪几张卡 | `1` |

> ⚠️ **安全提示 / Security**：
> 生产环境务必修改 `AUTH_PASS` 与 `SECRET_KEY`。
> 可用 `openssl rand -hex 32` 生成密钥。

## 🔌 API 文档 / API Reference

启动后访问：

- Swagger UI：<http://localhost:8000/docs>
- ReDoc：<http://localhost:8000/redoc>
- OpenAPI JSON：<http://localhost:8000/openapi.json>

主要端点 / Main endpoints：

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET`  | `/` | Web UI（登录页） |
| `GET`  | `/static/{file}` | 静态资源 |
| `GET`  | `/health` | 健康探针（返回 `{"status":"ok"}`） |
| `POST` | `/login` | 登录 |
| `POST` | `/api/encode` | 提交烧录任务（multipart/form-data） |
| `GET`  | `/api/tasks` | 查询队列状态 |
| `GET`  | `/api/history` | 历史记录 |
| `GET`  | `/download/{file}` | 下载烧录产物 |

> 鉴权基于 Session Cookie；API 调用需先 `POST /login` 拿到 `session` Cookie。

## 🛠️ 技术栈 / Tech Stack

- **后端 Backend**：Python 3.11 + FastAPI
- **前端 Frontend**：原生 HTML/CSS/JS（无框架依赖 / no framework）
- **数据库 Database**：SQLite
- **核心 Core**：FFmpeg + libass
- **容器 Container**：Docker + Docker Compose
- **CI/CD**：GitHub Actions → Docker Hub / GHCR

## 🏗️ TrueNAS Scale 部署 / TrueNAS Deployment

```bash
# 1. SSH 登录 TrueNAS
ssh root@truenas.local

# 2. 创建数据集（推荐）
#    Storage → Pools → 选池 → Create Dataset:
#      name = subtitle-burner
#      share type = Apps（如果用 Apps 部署）
#    或手动建目录：
mkdir -p /mnt/pool/apps/subtitle-burner/data/{uploads,outputs,fonts,db}
cd /mnt/pool/apps/subtitle-burner

# 3. 写入 docker-compose.yml 与 .env（参考上面的快速开始）
# 4. 启动
docker compose up -d
```

**IPv6-only 环境**：把 `BIND_HOST=[::]` 即可在公网双栈访问；如需 Cloudflare 反代，开启 `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` 即可。

## 🤖 CI/CD 与版本发布 / CI/CD & Release

### 触发条件 / Triggers

- 推送 `v*.*.*` tag → 自动构建并发布 release 镜像
- 合入 `main` 分支 → 自动构建 `dev` 镜像
- Pull Request → 仅构建验证，不推送
- 手动触发（`workflow_dispatch`）→ 可选输入版本号

### 镜像标签策略 / Image Tagging

每次 push tag `v1.2.3` 会同时推送：

| Tag | 说明 |
|---|---|
| `1263478456/subtitle-burner:1.2.3` | 语义化版本（推荐生产使用） |
| `1263478456/subtitle-burner:1.2` | 次版本号（滚动更新） |
| `1263478456/subtitle-burner:1` | 主版本号 |
| `1263478456/subtitle-burner:latest` | 始终指向最新 release |
| `1263478456/subtitle-burner:1.2.3-20260714` | 版本 + 构建日期 |
| `ghcr.io/1263478456/subtitle-burner:1.2.3` | GitHub Container Registry 同步镜像 |

### 多架构支持 / Multi-arch

构建目标：`linux/amd64` + `linux/arm64`

```bash
# 本地验证多架构构建
docker buildx build --platform linux/amd64,linux/arm64 \
  -f app/Dockerfile.cpu -t subtitle-burner:dev --load .
```

### 手动发布流程 / Manual Release

```bash
# 在本地
git tag v1.2.3
git push origin v1.2.3
# GitHub Actions 会自动构建并发布，5-10 分钟后即可：
docker pull 1263478456/subtitle-burner:1.2.3
```

### 所需 Secrets / Required Secrets

在 GitHub 仓库 **Settings → Secrets and variables → Actions** 中添加：

| Secret | 用途 | 获取方式 |
|---|---|---|
| `DOCKERHUB_USERNAME` | Docker Hub 账号 | https://hub.docker.com/ |
| `DOCKERHUB_TOKEN`    | Docker Hub Access Token | Docker Hub → Account Settings → Security → New Access Token |

> Token 比密码更安全、且可独立吊销。

### Conventional Commits / 提交规范

本项目使用 Conventional Commits 规范，配合 `git-cliff` 自动生成 CHANGELOG：

```bash
feat: 新增 GPU NVENC 编码支持
fix: 修复大文件上传超时
docs: 更新 API 文档
refactor: 重构队列调度
chore: 升级依赖版本
perf: 优化 ffmpeg 启动延迟
```

## 🧪 故障排查 / Troubleshooting

<details>
<summary><b>Q: 容器启动后立即退出？</b></summary>

```bash
docker compose logs app
# 常见原因：端口被占用 → 修改 .env 中 BIND_PORT
#           磁盘满   → docker system prune -a
```
</details>

<details>
<summary><b>Q: 中文/方块字体显示？</b></summary>

需要把字体文件挂载进容器：
```bash
mkdir -p data/fonts
cp /path/to/SourceHanSansCN-Regular.otf data/fonts/
docker compose restart
```
</details>

<details>
<summary><b>Q: GPU 模式启动失败？</b></summary>

```bash
# 1. 检查 NVIDIA 驱动
nvidia-smi
# 2. 检查 Container Toolkit
docker run --rm --runtime=nvidia --gpus all nvidia/cuda:12.0-base nvidia-smi
# 3. 若 docker-compose 报 "unknown runtime nvidia"
#    安装：https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
```
</details>

<details>
<summary><b>Q: IPv6-only 环境如何从外网访问？</b></summary>

`BIND_HOST=[::]` 已默认监听双栈；如需 HTTPS，用 Caddy / Nginx 反代：
```nginx
server {
  listen [::]:443 ssl http2;
  server_name lobe.1129.ltd;
  client_max_body_size 0;
  location / {
    proxy_pass http://[::1]:8000;
  }
}
```
</details>

<details>
<summary><b>Q: 升级后数据库报错？</b></summary>

```bash
# 保留 data/db/ 目录即可；如需迁移请看 docs/MIGRATION.md
docker compose down
docker compose pull
docker compose up -d
```
</details>

## 🛠️ 本地开发 / Local Development

```bash
# 克隆
git clone https://github.com/1263478456/subtitle-burner.git
cd subtitle-burner

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate # Linux/macOS

# 安装依赖
pip install -r app/requirements.txt

# 安装 ffmpeg（项目自带 Docker 镜像，开发机自行安装）
# macOS:   brew install ffmpeg
# Ubuntu:  sudo apt install ffmpeg libass-dev
# Windows: https://www.gyan.dev/ffmpeg/builds/

# 启动
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 🤝 贡献 / Contributing

欢迎 PR / Issue！

1. Fork 仓库
2. 创建分支：`git checkout -b feature/AmazingFeature`
3. 提交改动：`git commit -m 'feat: add AmazingFeature'`
4. 推送分支：`git push origin feature/AmazingFeature`
5. 提交 Pull Request

## 📄 许可证 / License

[MIT](LICENSE)

## 🙏 致谢 / Acknowledgments

- [FFmpeg](https://ffmpeg.org/) - 强大的多媒体处理工具
- [libass](https://github.com/libass/libass) - ASS/SSA 字幕渲染库
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化 Python Web 框架
- [git-cliff](https://git-cliff.org/) - 自动生成 CHANGELOG

---

⭐ 如果这个项目对你有帮助，欢迎点个 Star！
If this project helps you, please give it a Star!