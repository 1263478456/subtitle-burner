# 贡献指南 / Contributing Guide

## 开发流程

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/1263478456/subtitle-burner.git
cd subtitle-burner

# 安装依赖
pip install -r app/requirements.txt

# 运行开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 代码检查（必须）

**提交前必须运行架构检查脚本：**

```bash
python scripts/check_architecture.py
```

检查项包括：
- 前端硬编码配置检测
- 资源清理对称性检查
- Dockerfile 依赖验证
- 文件类型覆盖检查
- 状态一致性检查

### 3. 提交规范

```
feat: 新功能
fix: 修复 bug
refactor: 重构代码
docs: 文档更新
chore: 构建/工具变更
```

## 架构原则

### 单一数据源

任何配置数据只能有一处定义，其他地方动态获取。

```
❌ 前端硬编码字体列表 + 后端硬编码映射
✅ 后端 API 动态返回 → 前端动态加载
```

### 创建/删除对称

任何资源的创建和删除必须是对称的。

```python
# 创建任务时
tasks[task_id] = {...}        # 写内存
db_execute("INSERT ...")      # 写数据库
await queue.put(task_id)      # 加入队列

# 删除任务时（必须清理所有）
if task_id in running_processes:
    running_processes[task_id].terminate()
    running_processes.pop(task_id)
if task_id in tasks:
    del tasks[task_id]
db_execute("DELETE ...")
for f in INPUT_DIR.glob(f"{task_id}_*"):
    f.unlink()
```

### 文件类型扩展

新增支持的文件格式时，必须检查以下位置：

1. `_build_ffmpeg_cmd()` — FFmpeg 命令构建
2. `run_burn_task()` — 任务执行
3. `/api/media/burn` — 媒体库烧录接口
4. 前端文件选择器 — accept 属性
5. 前端文件类型判断 — 扩展名匹配

### 状态管理

任务状态流转：`created → queued → processing → completed/failed`

每个状态变更必须同时更新：
1. 内存字典 (`tasks[task_id]`)
2. 数据库 (`UPDATE tasks SET status=...`)
3. 相关资源 (队列/进程/文件)

## 测试

### 运行架构检查

```bash
python scripts/check_architecture.py
```

### 手动测试清单

- [ ] 上传视频 + 字幕，执行压制
- [ ] 选择不同字体、样式，验证输出
- [ ] 测试 ASS/SSA/SRT/VTT 格式字幕
- [ ] 测试批量任务（多任务并行）
- [ ] 测试删除任务（验证进程被终止）
- [ ] 测试重启容器（验证 stuck 任务恢复）
- [ ] 测试历史记录筛选（按状态过滤）

## Docker 构建

```bash
# CPU 版本
docker compose build --profile default

# GPU 版本
docker compose build --profile gpu
```

## 问题反馈

提交 Issue 时请包含：
- 问题描述
- 复现步骤
- 期望行为
- 实际行为
- 环境信息（OS、Docker 版本、GPU 型号）
