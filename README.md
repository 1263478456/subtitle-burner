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
- ⏹ 任务停止功能，支持排队中和处理中的任务
- 🎬 两种字幕模式：压制字幕（硬字幕）/ 添加字幕轨道（软字幕）
- 📁 媒体库浏览，智能配对视频和字幕文件
- 📥 输出文件命名：`源视频名(压制完成).mp4`
- 🎨 **字幕预览功能**：实时预览字幕效果，调整位置/样式/同步偏移

---

## ⚙️ 环境变量 / Environment

| 变量 | 说明 | 默认值 |
|---|---|---|
| `ADMIN_USERNAME` | 管理员账号 | `admin` |
| `ADMIN_PASSWORD` | 管理员密码 | `changeme` |
| `SESSION_SECRET` | Session 加密密钥（≥32 字节） | - |
| `BIND_HOST` | 绑定地址，IPv6 写 `[::]` | `0.0.0.0` |
| `BIND_PORT` | 主机端口 | `8000` |
| `MAX_CONCURRENT_TASKS` | 队列并行数 | `2` |
| `MAX_FILE_SIZE_MB` | 单文件上传上限 | `2048` |
| `MEDIA_ROOT` | 媒体库根目录（容器内路径） | `/media` |
| `NVIDIA_VISIBLE_DEVICES` | GPU profile 使用哪几张卡 | `all` |

> ⚠️ **安全提示**：生产环境务必修改 `ADMIN_PASSWORD` 与 `SESSION_SECRET`。可用 `openssl rand -hex 32` 生成密钥。

---

## 🎬 字幕处理模式

### 模式选择

| 模式 | 说明 | 适用场景 |
|---|---|---|
| **压制字幕（硬字幕）** | 字幕烧录到视频画面中，无法关闭 | 需要永久显示字幕，兼容所有播放器 |
| **添加字幕轨道（软字幕）** | 字幕作为独立轨道，可在播放器中开关 | 需要灵活控制字幕显示，保留原视频质量 |

### 原字幕轨道处理

- **删除原字幕**：移除视频中原有的字幕轨道（默认）
- **保留原字幕**：保留视频中原有的字幕轨道，新字幕作为额外轨道添加

> 💡 **软字幕模式**不需要重新编码视频，速度极快，但需要播放器支持字幕轨道切换。

---

## ⏹ 任务控制

- **停止任务**：排队中和处理中的任务都可以点击"停止"按钮终止
- **重试任务**：失败的任务可以点击"重试"按钮重新排队
- **批量操作**：支持批量烧录，显示总进度条

---

## 🎮 GPU 编码

### 支持的编码器

| 编码器 | 说明 |
|---|---|
| `h264_nvenc` | NVIDIA H.264 硬件编码 |
| `hevc_nvenc` | NVIDIA H.265/HEVC 硬件编码 |
| `h264_qsv` | Intel Quick Sync H.264 编码 |

### GPU 使用注意事项

1. **需要 NVIDIA Container Toolkit**：确保主机已安装 `nvidia-docker2`
2. **驱动版本要求**：主机 NVIDIA 驱动 ≥ 535（对应 CUDA 12.4）
3. **编码器检测**：启动时会自动检测可用的硬件编码器，日志中会显示检测结果
4. **字幕滤镜兼容**：使用 `subtitles` 滤镜时，视频解码在 CPU 进行，只有编码阶段使用 GPU

### 验证 GPU 是否可用

```bash
# 检查容器内 ffmpeg 是否支持 NVENC
docker exec subtitle-burner ffmpeg -hide_banner -encoders 2>/dev/null | grep nvenc

# 检查 NVIDIA 驱动
docker exec subtitle-burner nvidia-smi

# 查看启动日志中的编码器检测结果
docker logs subtitle-burner 2>&1 | grep "编码器检测"
```

### 常见问题

**Q: 选择 GPU 编码器但实际使用了 CPU？**
A: 检查容器日志中的编码器检测结果。如果显示 `h264_nvenc: False`，说明容器内 ffmpeg 不支持 NVENC。确保使用 `latest-gpu` 镜像。

**Q: GPU 编码失败？**
A: 可能原因：
- NVIDIA 驱动版本过低
- 容器没有正确挂载 GPU 设备
- 视频文件路径包含特殊字符

---

## 📁 媒体库模式

支持直接浏览服务器上的媒体文件，无需上传：

1. 点击"📁 从媒体库选择"切换到媒体库模式
2. 浏览目录，选择视频和字幕文件
3. 支持手动配对或"智能匹配"（按文件名自动配对）
4. 支持批量配对和批量烧录

**智能匹配规则**：
- 视频和字幕文件名（去掉扩展名）相同则自动配对
- 支持语言后缀匹配（如 `video.zh.srt` 匹配 `video.mp4`）

---

## 🎨 字幕预览功能

访问 `/preview` 页面，可在压制前实时预览和调整字幕效果。

### 功能特性

| 功能 | 说明 |
|------|------|
| 🎬 视频预览 | 支持本地上传或从媒体库加载视频 |
| 💬 字幕加载 | 支持 SRT / ASS / VTT 格式，自动解析显示 |
| ⏱️ 时间同步 | 字幕时间偏移（±秒），修正音画不同步 |
| 📍 位置调整 | 底部 / 顶部 / 居中 + 边距微调（0-200px） |
| 🔤 字体样式 | 大小（12-72px）、颜色、粗细、字体族（微软雅黑/苹方/黑体等） |
| ✨ 描边阴影 | 描边宽度/颜色、阴影偏移、背景透明度 |
| 📁 媒体库集成 | 直接从媒体库选择视频和字幕文件 |

### 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| `Space` | 播放 / 暂停 |
| `←` `→` | 快退 / 快进 5 秒 |
| `↑` `↓` | 字幕偏移 ±0.5 秒 |
| `[` `]` | 字号 ±2px |

### 使用流程

1. 点击导航栏「字幕预览」进入预览页面
2. 加载视频文件（本地上传或从媒体库选择）
3. 加载字幕文件，自动解析显示
4. 拖动滑块实时调整字幕位置、样式、时间偏移
5. 满意后点击「🔥 应用到压制」保存参数
6. 返回主页压制任务，预览参数自动应用

> 💡 **提示**：预览参数会保存在浏览器 localStorage 中，压制时自动读取。如需重置，清除浏览器缓存即可。

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
mkdir -p /mnt/pool/apps/subtitle-burner/data/{input,output,fonts,db}
mkdir -p /mnt/pool/apps/subtitle-burner/media
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
- `1263478456/subtitle-burner:latest` — 最新 CPU 版本
- `1263478456/subtitle-burner:latest-gpu` — 最新 GPU 版本
- `1263478456/subtitle-burner:v3.x.x` — 语义化版本
- `ghcr.io/1263478456/subtitle-burner:v3.x.x` — GHCR 同步

---

## 📖 API 文档

启动后访问 `/docs` 查看 Swagger UI 自动文档。

主要 API 端点：
- `POST /api/upload` — 上传视频和字幕
- `POST /api/burn` — 提交烧录任务
- `POST /api/media/burn` — 从媒体库提交任务
- `POST /api/stop/{task_id}` — 停止任务
- `POST /api/retry/{task_id}` — 重试任务
- `GET /api/queue` — 查看任务队列
- `GET /api/download/{task_id}` — 下载输出文件
- `GET /api/gpu/status` — 查询 GPU 状态

---

## 📝 更新日志

### v3.0.24+
- ✅ 修复下载功能（支持服务重启后下载历史任务）
- ✅ 修复历史记录页面按钮样式
- ✅ 新增任务停止功能（排队中/处理中均可停止）
- ✅ 新增字幕处理模式选择（压制字幕 / 添加字幕轨道）
- ✅ 新增原字幕轨道保留选项
- ✅ 输出文件命名改为 `源视频名(压制完成).mp4`
- ✅ 修复 GPU 编码参数（移除无效的 `-hwaccel cuda`，修复 NVENC 预设映射）
- ✅ 修复 uvicorn 多 worker 导致的内存不共享问题

---

## 📄 License

MIT License
