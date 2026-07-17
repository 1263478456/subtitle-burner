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

## 📋 完整配置示例 / Complete Examples

### CPU 模式 (docker-compose.yml)

```yaml
services:
  subtitle-burner:
    image: 1263478456/subtitle-burner:latest
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
    image: 1263478456/subtitle-burner:latest-gpu
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
    image: 1263478456/subtitle-burner:latest
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
    image: 1263478456/subtitle-burner:latest-gpu
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
# TrueNAS Scale 应用配置
services:
  subtitle-burner:
    image: 1263478456/subtitle-burner:latest-gpu
    container_name: subtitle-burner
    restart: unless-stopped
    network_mode: bridge
    ports:
      - "8000:8000"
    environment:
      - TZ=Asia/Shanghai
      - ADMIN_USERNAME=admin
      - ADMIN_PASSWORD=your_secure_password_here
      - SESSION_SECRET=your_random_secret_at_least_32_chars
      - MEDIA_ROOT=/media
    volumes:
      - /mnt/pool/apps/subtitle-burner/data:/data
      - /mnt/pool/media:/media  # 你的媒体库路径
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
- 📥 输出文件命名：`源视频名(压制完成).mp4`
- 🎨 **字幕预览功能**：实时预览字幕效果，调整位置/样式/同步偏移
- 🔊 **音频自动转码**：预览时自动将 EAC3/DTS/TrueHD 等编码转为 AAC，确保浏览器兼容
- ⚡ **智能片段转码**：渐进式加载，视频秒开，音频异步转码，MediaSource API 无缝播放
- 🔥 **预览压制选项**：预览页面直接设置硬/软字幕、编码器、CRF 等压制参数
- 💾 **字幕预设系统**：保存/加载/管理字幕样式预设，支持默认预设
- 📋 **待压制队列**：预览页面可将多个任务添加到队列，主页批量开始压制
- ⏱️ **精确剩余时间**：进度条旁显示预计剩余时间，精确到秒
- 📝 **内嵌字幕选择**：自动检测视频内嵌字幕，支持加载指定轨道
- 🗑️ **延迟删除内嵌字幕**：标记删除，压制时才生效，不修改原始文件
- 🎬 **按语言匹配字幕**：按语言代码（chi/eng/jpn 等）匹配字幕轨道，跨视频通用
- 📐 **视频安全区参考线**：显示视频实际显示区域和标题安全区，辅助字幕定位
- 📏 **字幕缩放预览**：字幕大小/位置按视频原始分辨率缩放，预览与导出一致
- ✏️ **自定义字幕名称**：软字幕模式可自定义字幕轨道名称
- ℹ️ **关于页面**：首页显示版本号、运行状态、GitHub/DockerHub 链接

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
| 🔊 音频自动转码 | EAC3/DTS/TrueHD/FLAC 等格式自动转为 AAC，确保浏览器播放 |
| ⚡ 智能片段转码 | 只转码当前播放位置附近内容，提前 10秒预加载，播放连续不中断 |
| 🔥 压制选项 | 预览页面直接设置硬/软字幕、原字幕保留、编码器(CPU/GPU)、CRF、编码预设 |
| 💾 字幕预设 | 保存/加载/管理字幕样式预设，支持设为默认预设 |
| 📋 待压制队列 | 预览页面可将多个任务添加到队列，主页批量开始压制 |
| 📝 内嵌字幕选择 | 自动检测视频内嵌字幕，支持加载指定轨道 |
| 🗑️ 删除内嵌字幕 | 标记删除，压制时生效，不修改原始文件 |
| 🎬 按语言匹配字幕 | 按语言代码匹配（chi/eng/jpn 等），跨视频通用 |
| 📐 视频安全区参考线 | 显示视频实际显示区域和标题安全区，辅助字幕定位 |
| 📏 字幕缩放预览 | 字幕大小/位置按视频原始分辨率缩放，预览与导出一致 |
| ✏️ 自定义字幕名称 | 软字幕模式可自定义字幕轨道名称 |

### 音频格式兼容性

预览功能会自动检测视频的音频编码，不兼容的格式将实时转码：

| 音频编码 | 处理方式 |
|----------|----------|
| AAC / MP3 / Opus / Vorbis | 直接播放（支持随机跳转） |
| **EAC3 (Dolby Digital Plus)** | 智能片段转码 |
| **AC3 (Dolby Digital)** | 智能片段转码 |
| **DTS** | 智能片段转码 |
| **TrueHD** | 智能片段转码 |
| **FLAC** | 智能片段转码 |

### 智能片段转码

对于需要转码的视频（如 EAC3 音频），采用 MediaSource API 实现无缝播放：

| 操作 | 行为 |
|------|------|
| 首次加载 | 只转码前 20秒，约 1-3秒完成 |
| 播放到第 15秒 | 自动预加载下一个 20秒片段（提前 5秒缓冲） |
| 拖动到任意位置 | 自动加载对应位置片段 |
| 同一位置重复访问 | 使用 5分钟缓存，瞬间加载 |

**技术方案**：
- ✅ 使用 MediaSource Extensions (MSE) API 实现无缝音频拼接
- ✅ 无需等待完整视频转码（50分钟视频只需 1-3秒）
- ✅ 拖动到任意位置快速预览
- ✅ 适合快速对齐字幕和视频

> 💡 如果视频音频格式兼容（AAC/MP3 等），则直接播放原文件，支持随机跳转，无需转码。

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

## 🎬 内嵌字幕管理

### 延迟删除

点击「🗑️ 删除内嵌字幕」不会立即修改文件，而是标记删除，在压制时才从输出文件中移除。

### 两种删除模式

| 模式 | 说明 |
|------|------|
| **删除所有字幕** | 压制时移除所有内嵌字幕轨道 |
| **按语言选择保留** | 只保留指定语言的字幕，删除其他 |

### 语言代码参考

| 语言 | 代码 |
|------|------|
| 中文 | `chi` / `zho` / `chs` / `cht` |
| 英文 | `eng` |
| 日文 | `jpn` |
| 韩文 | `kor` |
| 法文 | `fre` |
| 德文 | `ger` |
| 西班牙文 | `spa` |

### 跨视频匹配

预设中保存的语言代码可跨视频通用：

```
预设: 保留 chi,eng

视频A (10个字幕轨): 0:chi 1:eng 2:jpn 3:kor ...
  → 保留 0,1 → 删除 2,3,...

视频B (8个字幕轨): 0:eng 1:chi 2:fre ...
  → 保留 0,1 → 删除 2,...
```

---

## 💾 字幕预设系统

### 保存范围

预设可保存以下参数组合（可自由勾选）：

| 参数类别 | 内容 |
|----------|------|
| 字幕样式 | 字体大小/颜色/粗细、描边、阴影、背景透明度 |
| 压制选项 | 编码器、CRF、编码预设、字幕模式、轨道名称 |
| 时间偏移 | 字幕同步偏移量 |
| 内嵌字幕保留 | 按语言匹配的字幕保留策略 |

### 使用流程

1. 在字幕预览页面调整好所有参数
2. 点击「💾 保存当前」打开保存弹窗
3. 选择保存范围（字幕样式/压制选项/时间偏移/内嵌字幕保留）
4. 输入预设名称，可选设为默认
5. 在主页烧录任务时可套用预设

---

## 📐 视频安全区参考线

点击视频控制栏的「📐 安全区」按钮，显示：

| 参考线 | 颜色 | 作用 |
|--------|------|------|
| 红色虚线外框 | 🔴 | 视频实际显示边界（object-fit: contain 后的真实区域） |
| 黄色虚线内框 | 🟡 | 标题安全区（视频区域的 80%），字幕放里面最安全 |
| 十字网格线 | ⬜ | 25% 分割线，辅助定位 |

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

> ⚠️ **声明**：本项目未经大范围生产环境测试，使用需谨慎。建议在测试环境充分验证后再部署到生产环境。
