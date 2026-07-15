import os
import json
import os
import sys
import uuid
import shutil
import asyncio
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI, UploadFile, File, Form, HTTPException,
    BackgroundTasks, Depends, Request, Response
)
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import aiofiles

# 配置日志输出到 stdout（Docker 日志捕获）
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger("subtitle-burner")

BASE_DIR = Path("/data")
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/media"))

# GPU 编码器检测
import subprocess as _sp

def _detect_encoders():
    """检测可用的硬件编码器"""
    encoders = {"h264_nvenc": False, "hevc_nvenc": False, "av1_nvenc": False, "h264_qsv": False, "hevc_qsv": False}
    try:
        result = _sp.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, timeout=10)
        output = result.stdout.decode("utf-8", errors="ignore")
        for enc in encoders:
            if enc in output:
                encoders[enc] = True
        logger.info(f"FFmpeg 编码器检测结果: {encoders}")
    except Exception as e:
        logger.error(f"FFmpeg 编码器检测失败: {e}")
    return encoders

GPU_ENCODERS = _detect_encoders()
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
DB_DIR = BASE_DIR / "db"
DB_PATH = DB_DIR / "subtitle_burner.db"

INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "2048")) * 1024 * 1024
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_TASKS", "2"))

ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin123")
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-please-32-chars-min!!")
SESSION_COOKIE = "sb_session"
SESSION_MAX_AGE = 7 * 24 * 3600

serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="subtitle-burner-auth")

tasks = {}
queue = asyncio.Queue()
running_processes = {}  # task_id -> subprocess process

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY, user TEXT, video_name TEXT, subtitle_name TEXT,
        video_size INTEGER, output_size INTEGER, output_file TEXT,
        status TEXT, progress INTEGER DEFAULT 0, params TEXT, error TEXT,
        created_at TEXT, completed_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT, created_at TEXT
    )""")
    import hashlib
    pwd_hash = hashlib.sha256(ADMIN_PASS.encode()).hexdigest()
    conn.execute("INSERT OR IGNORE INTO users (username, password, created_at) VALUES (?, ?, ?)",
                 (ADMIN_USER, pwd_hash, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def db_query(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows

def db_execute(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(sql, params)
    conn.commit()
    conn.close()

def create_session_token(username):
    return serializer.dumps({"user": username})

def verify_session_token(token):
    try:
        data = serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data.get("user")
    except (BadSignature, SignatureExpired):
        return None

def get_current_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        return None
    return verify_session_token(token)

def require_auth(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "请先登录")
    return user

async def run_burn_task(task_id):
    task = tasks.get(task_id)
    if not task:
        return
    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 0
        tasks[task_id]["started_at"] = datetime.now().isoformat()
        db_execute("UPDATE tasks SET status=?, progress=? WHERE task_id=?",
                   ("processing", 0, task_id))

        video_files = list(INPUT_DIR.glob(f"{task_id}_video.*"))
        sub_files = list(INPUT_DIR.glob(f"{task_id}_subtitle.*"))
        if not video_files or not sub_files:
            raise Exception("找不到输入文件")

        video_path = video_files[0]
        sub_path = sub_files[0]
        video_name = task["video_name"]
        # 输出文件命名：原视频名(压制完成).mp4
        stem = Path(video_name).stem
        output_filename = f"{stem}(压制完成).mp4"
        output_path = OUTPUT_DIR / f"{task_id}_{output_filename}"

        sub_path_escaped = str(sub_path).replace(":", r"\:").replace("'", r"\'")
        vf_filters = [f"subtitles='{sub_path_escaped}'"]
        params = task["params"]

        if sub_path.suffix.lower() in ['.srt', '.vtt']:
            style = params.get('style') or 'FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1'
            vf_filters[0] += f":force_style='{style}'"

        crf = params.get('crf', 18)
        preset = params.get('preset', 'medium')
        codec = params.get('codec', 'libx264')

        cmd = _build_ffmpeg_cmd(video_path, sub_path, output_path, params)
        logger.info(f"[任务 {task_id}] 编码器: {codec}, FFmpeg 命令: {' '.join(cmd)}")

        # 获取视频总时长用于进度计算
        total_duration = 0
        try:
            probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)]
            probe_result = await asyncio.create_subprocess_exec(*probe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await probe_result.wait()
            if probe_result.returncode == 0:
                dur_str = (await probe_result.stdout.read()).decode().strip()
                total_duration = float(dur_str) if dur_str else 0
        except Exception:
            total_duration = 0

        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        running_processes[task_id] = process

        # 实时解析 stderr 更新进度
        async def read_stderr():
            nonlocal process
            current_time = 0.0
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="ignore").strip()
                # 解析 time= 字段
                if "time=" in line_str and total_duration > 0:
                    try:
                        time_part = line_str.split("time=")[1].split(" ")[0].strip()
                        # 格式: HH:MM:SS.ms 或 HH:MM:SS
                        parts = time_part.split(":")
                        if len(parts) == 3:
                            h, m, s = parts
                            s = float(s)
                            current_time = float(h) * 3600 + float(m) * 60 + s
                            progress = min(round((current_time / total_duration) * 100, 2), 99.99)
                            tasks[task_id]["progress"] = progress
                            db_execute("UPDATE tasks SET progress=? WHERE task_id=?", (progress, task_id))
                    except (ValueError, IndexError):
                        pass

        stderr_task = asyncio.create_task(read_stderr())
        await process.wait()
        stderr_task.cancel()
        running_processes.pop(task_id, None)

        if process.returncode != 0 or not output_path.exists():
            # 收集 FFmpeg 错误信息
            stderr_output = ""
            try:
                # 尝试读取剩余的 stderr
                remaining = await process.stderr.read()
                stderr_output = remaining.decode("utf-8", errors="ignore")[-500:]
            except:
                pass
            logger.error(f"[任务 {task_id}] FFmpeg 失败 (returncode={process.returncode}): {stderr_output}")
            raise Exception(f"FFmpeg 执行失败 (code={process.returncode}): {stderr_output[:200]}")

        out_size = output_path.stat().st_size
        tasks[task_id].update({"status": "completed", "progress": 100,
                               "output_file": output_filename, "output_path": str(output_path),
                               "output_size": out_size, "completed_at": datetime.now().isoformat()})
        db_execute("UPDATE tasks SET status=?, progress=?, output_file=?, output_size=?, completed_at=? WHERE task_id=?",
                   ("completed", 100, output_filename, out_size, datetime.now().isoformat(), task_id))
    except Exception as e:
        tasks[task_id].update({"status": "failed", "error": str(e), "completed_at": datetime.now().isoformat()})
        db_execute("UPDATE tasks SET status=?, error=?, completed_at=? WHERE task_id=?",
                   ("failed", str(e), datetime.now().isoformat(), task_id))

async def queue_worker():
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    async def process_one(task_id):
        async with semaphore:
            await run_burn_task(task_id)
    while True:
        try:
            task_id = await queue.get()
            asyncio.create_task(process_one(task_id))
        except Exception:
            pass

@asynccontextmanager
async def lifespan(app):
    init_db()
    worker = asyncio.create_task(queue_worker())
    yield
    worker.cancel()

app = FastAPI(title="字幕烧录工具", version="2.1", lifespan=lifespan, docs_url="/docs", redoc_url="/redoc")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# 自定义静态文件类：禁用缓存，确保前端代码更新立即生效
from starlette.responses import Response as StarletteResponse

class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if isinstance(response, StarletteResponse):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.mount("/static", NoCacheStaticFiles(directory="app/static"), name="static")

# 主页也禁用缓存
from starlette.responses import FileResponse as _FR

class NoCacheFileResponse(_FR):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        self.headers["Pragma"] = "no-cache"
        self.headers["Expires"] = "0"

# 健康检查（容器探针）
@app.get("/health", include_in_schema=False)
async def container_health():
    return {"status": "ok", "version": "2.1"}

@app.get("/")
async def index(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=302)
    return FileResponse("app/static/index.html")

@app.get("/login")
async def login_page():
    return FileResponse("app/static/login.html")

@app.get("/history")
async def history_page(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=302)
    return FileResponse("app/static/history.html")

@app.post("/api/login")
async def login(response: Response, username: str = Form(...), password: str = Form(...)):
    import hashlib
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    rows = db_query("SELECT username FROM users WHERE username=? AND password=?", (username, pwd_hash))
    if not rows:
        raise HTTPException(401, "用户名或密码错误")
    token = create_session_token(username)
    response.set_cookie(key=SESSION_COOKIE, value=token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax")
    return {"message": "登录成功", "user": username}

@app.post("/api/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"message": "已退出登录"}

@app.get("/api/me")
async def me(user: str = Depends(require_auth)):
    return {"user": user}

@app.get("/api/health")
async def health():
    return {"status": "ok", "ffmpeg": shutil.which("ffmpeg") is not None, "queue_size": queue.qsize()}

@app.post("/api/upload")
async def upload_files(user: str = Depends(require_auth),
                      video: UploadFile = File(...),
                      subtitle: UploadFile = File(...)):
    video_content = await video.read()
    subtitle_content = await subtitle.read()
    if len(video_content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"视频超过限制")
    task_id = uuid.uuid4().hex[:12]
    video_ext = Path(video.filename).suffix.lower() or ".mp4"
    sub_ext = Path(subtitle.filename).suffix.lower() or ".ass"
    video_path = INPUT_DIR / f"{task_id}_video{video_ext}"
    sub_path = INPUT_DIR / f"{task_id}_subtitle{sub_ext}"
    async with aiofiles.open(video_path, 'wb') as f:
        await f.write(video_content)
    async with aiofiles.open(sub_path, 'wb') as f:
        await f.write(subtitle_content)
    return {"task_id": task_id, "video_name": video.filename, "subtitle_name": subtitle.filename,
            "video_size": len(video_content), "subtitle_size": len(subtitle_content)}

@app.post("/api/burn")
async def burn_subtitle(user: str = Depends(require_auth),
                       task_id: str = Form(...),
                       video_name: str = Form(...),
                       subtitle_name: str = Form(""),
                       duration: float = Form(0),
                       crf: int = Form(18),
                       preset: str = Form("medium"),
                       codec: str = Form("libx264"),
                       style: str = Form(""),
                       sub_mode: str = Form("burn"),
                       keep_original_sub: bool = Form(False)):
    video_files = list(INPUT_DIR.glob(f"{task_id}_video.*"))
    if not video_files:
        raise HTTPException(404, "文件不存在")
    if task_id in tasks and tasks[task_id].get("status") in ("queued", "processing"):
        raise HTTPException(400, "任务已在队列中")
    params = {"video_name": video_name, "duration": duration, "crf": crf, "preset": preset, "codec": codec, "style": style, "sub_mode": sub_mode, "keep_original_sub": keep_original_sub}
    now = datetime.now().isoformat()
    tasks[task_id] = {"task_id": task_id, "user": user, "video_name": video_name, "status": "queued", "progress": 0, "params": params, "created_at": now}
    db_execute("""INSERT OR REPLACE INTO tasks (task_id, user, video_name, subtitle_name, status, progress, params, created_at)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
               (task_id, user, video_name, subtitle_name, "queued", 0, json.dumps(params), now))
    await queue.put(task_id)
    return {"task_id": task_id, "status": "queued", "queue_size": queue.qsize()}

@app.post("/api/retry/{task_id}")
async def retry_task(task_id: str, user: str = Depends(require_auth)):
    if task_id not in tasks:
        raise HTTPException(404, "任务不存在")
    task = tasks[task_id]
    if task.get("user") != user:
        raise HTTPException(403, "无权访问")
    if task.get("status") in ("queued", "processing"):
        raise HTTPException(400, "任务已在队列中")
    now = datetime.now().isoformat()
    tasks[task_id].update({
        "status": "queued",
        "progress": 0,
        "error": None,
        "completed_at": None,
        "created_at": now,
    })
    db_execute("UPDATE tasks SET status=?, progress=?, error=?, completed_at=?, created_at=? WHERE task_id=?",
               ("queued", 0, None, None, now, task_id))
    await queue.put(task_id)
    return {"task_id": task_id, "status": "queued", "queue_size": queue.qsize()}

@app.post("/api/stop/{task_id}")
async def stop_task(task_id: str, user: str = Depends(require_auth)):
    """停止正在执行的任务"""
    if task_id not in tasks:
        raise HTTPException(404, "任务不存在")
    task = tasks[task_id]
    if task.get("user") != user:
        raise HTTPException(403, "无权访问")
    
    # 如果任务正在执行中，终止 FFmpeg 进程
    process = running_processes.get(task_id)
    if process:
        try:
            process.terminate()
            await asyncio.sleep(0.5)
            if process.returncode is None:
                process.kill()
        except Exception:
            pass
        running_processes.pop(task_id, None)
    
    # 清理输出文件
    output_files = list(OUTPUT_DIR.glob(f"{task_id}_*"))
    for f in output_files:
        try:
            f.unlink()
        except Exception:
            pass
    
    now = datetime.now().isoformat()
    tasks[task_id].update({
        "status": "failed",
        "error": "用户手动停止",
        "completed_at": now,
    })
    db_execute("UPDATE tasks SET status=?, error=?, completed_at=? WHERE task_id=?",
               ("failed", "用户手动停止", now, task_id))
    
    return {"task_id": task_id, "status": "stopped"}

@app.get("/api/status/{task_id}")
async def get_task_status(task_id: str, user: str = Depends(require_auth)):
    if task_id not in tasks:
        raise HTTPException(404, "任务不存在")
    return tasks[task_id]

@app.get("/api/queue")
async def get_queue(user: str = Depends(require_auth)):
    items = [t for t in tasks.values() if t.get("user") == user]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"tasks": items, "queue_size": queue.qsize()}

@app.get("/api/download/{task_id}")
async def download_result(task_id: str, user: str = Depends(require_auth)):
    # 先查内存，再查数据库
    task = tasks.get(task_id)
    if not task:
        rows = db_query("SELECT * FROM tasks WHERE task_id=? AND user=?", (task_id, user))
        if not rows:
            raise HTTPException(404, "任务不存在")
        task = dict(rows[0])
        if task.get('params'):
            try: task['params'] = json.loads(task['params'])
            except: pass
    else:
        if task.get("user") != user:
            raise HTTPException(403, "无权访问")
    if task["status"] != "completed":
        raise HTTPException(400, "任务未完成")
    # 查找输出文件：先查内存中的路径，再 glob 搜索
    file_path = None
    if task.get("output_path") and Path(task["output_path"]).exists():
        file_path = Path(task["output_path"])
    else:
        # 从 OUTPUT_DIR 搜索
        candidates = list(OUTPUT_DIR.glob(f"{task_id}_*"))
        if candidates:
            file_path = candidates[0]
    if not file_path or not file_path.exists():
        raise HTTPException(404, "输出文件不存在")
    return FileResponse(file_path, media_type="video/mp4", filename=task.get("output_file", file_path.name))

@app.get("/api/history")
async def list_history(user: str = Depends(require_auth), page: int = 1, page_size: int = 20):
    offset = (page - 1) * page_size
    total = db_query("SELECT COUNT(*) FROM tasks WHERE user=?", (user,))[0][0]
    rows = db_query("SELECT * FROM tasks WHERE user=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (user, page_size, offset))
    items = []
    for r in rows:
        item = dict(r)
        if item.get('params'):
            try: item['params'] = json.loads(item['params'])
            except: pass
        items.append(item)
    return {"total": total, "page": page, "page_size": page_size, "items": items}

@app.delete("/api/history/{task_id}")
async def delete_history(task_id: str, user: str = Depends(require_auth)):
    # 先校验归属（DB 行级 user 过滤）再删文件，避免越权清理他人文件
    owned = db_query("SELECT task_id FROM tasks WHERE task_id=? AND user=?", (task_id, user))
    if not owned:
        raise HTTPException(404, "任务不存在或无权访问")
    for f in INPUT_DIR.glob(f"{task_id}_*"):
        try: f.unlink()
        except: pass
    for f in OUTPUT_DIR.glob(f"{task_id}_*"):
        try: f.unlink()
        except: pass
    db_execute("DELETE FROM tasks WHERE task_id=? AND user=?", (task_id, user))
    if task_id in tasks and tasks[task_id].get("user") == user:
        del tasks[task_id]
    return {"message": "已删除"}

@app.post("/api/history/clear")
async def clear_history(user: str = Depends(require_auth)):
    rows = db_query("SELECT task_id FROM tasks WHERE user=?", (user,))
    for r in rows:
        tid = r["task_id"]
        for f in INPUT_DIR.glob(f"{tid}_*"):
            try: f.unlink()
            except: pass
        for f in OUTPUT_DIR.glob(f"{tid}_*"):
            try: f.unlink()
            except: pass
    db_execute("DELETE FROM tasks WHERE user=?", (user,))
    return {"message": "已清空"}

@app.get("/api/stats")
async def get_stats(user: str = Depends(require_auth)):
    rows = db_query("SELECT status, COUNT(*) as count FROM tasks WHERE user=? GROUP BY status", (user,))
    stats = {r["status"]: r["count"] for r in rows}
    return {"total": sum(stats.values()), "queued": stats.get("queued", 0),
            "processing": stats.get("processing", 0), "completed": stats.get("completed", 0),
            "failed": stats.get("failed", 0)}

VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.ts', '.m4v', '.mpg', '.mpeg'}
SUB_EXTS = {'.ass', '.ssa', '.srt', '.vtt', '.sub'}

@app.get("/api/media/list")
async def list_media(path: str = "", user: str = Depends(require_auth)):
    """浏览媒体库目录"""
    # 安全检查：防止路径遍历
    if path:
        target = (MEDIA_ROOT / path).resolve()
    else:
        target = MEDIA_ROOT.resolve()

    # 确保在 MEDIA_ROOT 内
    if not str(target).startswith(str(MEDIA_ROOT.resolve())):
        raise HTTPException(403, "禁止访问该路径")

    if not target.exists():
        raise HTTPException(404, "目录不存在")
    if not target.is_dir():
        raise HTTPException(400, "不是目录")

    items = []
    try:
        for entry in sorted(target.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            rel_path = entry.relative_to(MEDIA_ROOT)
            items.append({
                "name": entry.name,
                "path": str(rel_path),
                "is_dir": entry.is_dir(),
                "size": entry.stat().st_size if entry.is_file() else None,
                "ext": entry.suffix.lower() if entry.is_file() else None,
            })
    except PermissionError:
        raise HTTPException(403, "无权限访问")

    return {
        "current_path": str(target.relative_to(MEDIA_ROOT)) if target != MEDIA_ROOT else "",
        "media_root": str(MEDIA_ROOT),
        "items": items,
    }

@app.post("/api/media/burn")
async def burn_from_media(
    user: str = Depends(require_auth),
    video_path: str = Form(...),
    subtitle_path: str = Form(...),
    crf: int = Form(18),
    preset: str = Form("medium"),
    codec: str = Form("libx264"),
    style: str = Form(""),
    sub_mode: str = Form("burn"),
    keep_original_sub: bool = Form(False),
):
    """直接从媒体库添加烧录任务（不需要上传）"""
    logger.info(f"[媒体库烧录] 用户: {user}, codec: {codec}, crf: {crf}, preset: {preset}, sub_mode: {sub_mode}")
    # 安全检查
    video_full = (MEDIA_ROOT / video_path).resolve()
    sub_full = (MEDIA_ROOT / subtitle_path).resolve()

    if not str(video_full).startswith(str(MEDIA_ROOT.resolve())):
        raise HTTPException(403, "视频路径非法")
    if not str(sub_full).startswith(str(MEDIA_ROOT.resolve())):
        raise HTTPException(403, "字幕路径非法")
    if not video_full.is_file():
        raise HTTPException(404, "视频文件不存在")
    if not sub_full.is_file():
        raise HTTPException(404, "字幕文件不存在")

    # 创建软链接到 input 目录，复用现有烧录逻辑
    task_id = uuid.uuid4().hex[:12]
    video_ext = video_full.suffix.lower()
    sub_ext = sub_full.suffix.lower()
    link_video = INPUT_DIR / f"{task_id}_video{video_ext}"
    link_sub = INPUT_DIR / f"{task_id}_subtitle{sub_ext}"

    link_video.symlink_to(video_full)
    link_sub.symlink_to(sub_full)

    params = {
        "video_name": video_full.name,
        "duration": 0,
        "crf": crf,
        "preset": preset,
        "codec": codec,
        "style": style,
        "sub_mode": sub_mode,
        "keep_original_sub": keep_original_sub,
    }

    now = datetime.now().isoformat()
    tasks[task_id] = {
        "task_id": task_id,
        "user": user,
        "video_name": video_full.name,
        "status": "queued",
        "progress": 0,
        "params": params,
        "created_at": now,
        "from_media": True,
    }

    db_execute(
        """INSERT OR REPLACE INTO tasks (task_id, user, video_name, subtitle_name, status, progress, params, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (task_id, user, video_full.name, sub_full.name, "queued", 0,
         json.dumps(params), now)
    )

    await queue.put(task_id)

    return {
        "task_id": task_id,
        "status": "queued",
        "queue_size": queue.qsize(),
        "video_name": video_full.name,
    }

@app.get("/api/gpu/status")
async def gpu_status(user: str = Depends(require_auth)):
    """查询 GPU 和可用编码器"""
    available = [name for name, supported in GPU_ENCODERS.items() if supported]
    
    # 检测 NVIDIA 显卡
    gpu_info = None
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader"],
            capture_output=True, timeout=5
        )
        if result.returncode == 0:
            line = result.stdout.decode().strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",")]
            gpu_info = {
                "name": parts[0],
                "memory": parts[1] if len(parts) > 1 else "unknown",
                "driver": parts[2] if len(parts) > 2 else "unknown",
            }
    except Exception:
        pass
    
    return {
        "gpu_info": gpu_info,
        "available_encoders": available,
        "recommended_encoder": _pick_best_encoder("h264"),
    }

def _pick_best_encoder(codec="h264"):
    """根据可用硬件选择最佳编码器"""
    # 优先 NVIDIA
    if codec == "h264":
        if GPU_ENCODERS.get("h264_nvenc"):
            return "h264_nvenc"
        if GPU_ENCODERS.get("h264_qsv"):
            return "h264_qsv"
    elif codec == "hevc":
        if GPU_ENCODERS.get("hevc_nvenc"):
            return "hevc_nvenc"
        if GPU_ENCODERS.get("hevc_qsv"):
            return "hevc_qsv"
    return f"lib{codec}"

def _build_ffmpeg_cmd(video_path, sub_path, output_path, params):
    """根据参数智能构建 FFmpeg 命令"""
    codec = params.get("codec", "libx264")
    crf = params.get("crf", 18)
    preset = params.get("preset", "medium")
    style = params.get("style", "")
    sub_mode = params.get("sub_mode", "burn")  # burn=压制字幕, soft=添加字幕轨道
    keep_original_sub = params.get("keep_original_sub", False)  # 是否保留原字幕轨道
    
    # NVENC 预设映射
    nvenc_preset_map = {
        "ultrafast": "p1", "superfast": "p2", "veryfast": "p3",
        "faster": "p4", "fast": "p4", "medium": "p5",
        "slow": "p6", "veryslow": "p7"
    }
    nvenc_preset = nvenc_preset_map.get(preset, "p5")
    
    # 软字幕模式：添加字幕轨道（不重新编码视频）
    if sub_mode == "soft":
        cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(sub_path)]
        
        # 映射流
        cmd.extend(["-map", "0:v:0", "-map", "0:a?"])
        if keep_original_sub:
            cmd.extend(["-map", "0:s?"])  # 保留原字幕轨道
        cmd.extend(["-map", "1:0"])  # 添加新字幕轨道
        
        # 编码设置
        cmd.extend(["-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text"])
        cmd.append(str(output_path))
        return cmd
    
    # 硬字幕模式：压制字幕到画面
    sub_escaped = str(sub_path).replace(":", r"\:").replace("'", r"\'")
    vf_parts = [f"subtitles='{sub_escaped}'"]
    if sub_path.suffix.lower() in ['.srt', '.vtt']:
        s = style or 'FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1'
        vf_parts[0] += f":force_style='{s}'"
    vf = ",".join(vf_parts)
    
    # GPU 编码特殊处理
    # 注意：使用 subtitles 滤镜时不能用 -hwaccel cuda（会导致滤镜失败）
    # 必须让 FFmpeg 在 CPU 解码后应用字幕滤镜，再用 GPU 编码
    if codec == "h264_nvenc":
        return [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", vf, "-c:v", "h264_nvenc",
            "-preset", nvenc_preset,
            "-rc", "vbr", "-cq", str(crf),
            "-c:a", "copy",
            "-map", "0:v:0", "-map", "0:a?",
            str(output_path)
        ]
    elif codec == "hevc_nvenc":
        return [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", vf, "-c:v", "hevc_nvenc",
            "-preset", nvenc_preset,
            "-rc", "vbr", "-cq", str(crf),
            "-c:a", "copy",
            "-map", "0:v:0", "-map", "0:a?",
            str(output_path)
        ]
    elif codec == "h264_qsv":
        return [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", vf, "-c:v", "h264_qsv",
            "-preset", "medium", "-global_quality", str(crf),
            "-c:a", "copy",
            "-map", "0:v:0", "-map", "0:a?",
            str(output_path)
        ]
    else:
        # CPU 编码
        return [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", vf, "-c:v", codec,
            "-crf", str(crf), "-preset", preset,
            "-c:a", "copy",
            "-map", "0:v:0", "-map", "0:a?",
            str(output_path)
        ]

PREVIEW_DIR = OUTPUT_DIR / "previews"
PREVIEW_DIR.mkdir(exist_ok=True)

@app.post("/api/preview")
async def generate_preview(
    user: str = Depends(require_auth),
    task_id: str = Form(...),
    start: int = Form(0),
    duration: int = Form(10),
):
    """生成字幕预览片段（10 秒短视频）"""
    video_files = list(INPUT_DIR.glob(f"{task_id}_video.*"))
    sub_files = list(INPUT_DIR.glob(f"{task_id}_subtitle.*"))
    if not video_files or not sub_files:
        raise HTTPException(404, "任务文件不存在")
    
    video_path = video_files[0]
    sub_path = sub_files[0]
    
    preview_id = uuid.uuid4().hex[:12]
    output_path = PREVIEW_DIR / f"{preview_id}.mp4"
    
    # 获取视频实际时长
    probe = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await probe.communicate()
    try:
        total_duration = float(stdout.decode().strip())
    except Exception:
        total_duration = 0
    
    # 如果起始时间超出视频长度，从头开始
    if start >= total_duration > 0:
        start = 0
    
    sub_escaped = str(sub_path).replace(":", r"\:").replace("'", r"\'")
    
    # 使用 ultrafast 快速生成预览
    cmd = [
        "ffmpeg", "-y", "-ss", str(start), "-i", str(video_path),
        "-vf", f"subtitles='{sub_escaped}'",
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart",
        str(output_path)
    ]
    
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await process.communicate()
    
    if process.returncode != 0 or not output_path.exists():
        raise HTTPException(500, "预览生成失败")
    
    return {
        "preview_id": preview_id,
        "preview_url": f"/api/preview/{preview_id}",
        "duration": duration,
        "start": start,
    }

@app.get("/api/preview/{preview_id}")
async def get_preview(preview_id: str):
    """返回预览视频"""
    file_path = PREVIEW_DIR / f"{preview_id}.mp4"
    if not file_path.exists():
        raise HTTPException(404, "预览不存在或已过期")
    return FileResponse(file_path, media_type="video/mp4")

@app.get("/api/probe/{task_id}")
async def probe_video(task_id: str, user: str = Depends(require_auth)):
    """获取视频时长信息"""
    video_files = list(INPUT_DIR.glob(f"{task_id}_video.*"))
    if not video_files:
        raise HTTPException(404, "文件不存在")
    video_path = video_files[0]
    
    probe = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,codec_name",
        "-of", "json", str(video_path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await probe.communicate()
    
    try:
        import json as _json
        data = _json.loads(stdout.decode())
        fmt = data.get("format", {})
        streams = data.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        return {
            "duration": float(fmt.get("duration", 0)),
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "codec": video_stream.get("codec_name"),
        }
    except Exception:
        return {"duration": 0}

# 转码预设
TRANSCODE_PRESETS = {
    "compress_1080p": {"scale": "scale=-2:1080", "crf": 23, "preset": "medium", "codec": "libx264", "audio_bitrate": "128k"},
    "compress_720p": {"scale": "scale=-2:720", "crf": 25, "preset": "medium", "codec": "libx264", "audio_bitrate": "128k"},
    "compress_480p": {"scale": "scale=-2:480", "crf": 28, "preset": "medium", "codec": "libx264", "audio_bitrate": "96k"},
    "high_quality": {"scale": None, "crf": 18, "preset": "slow", "codec": "libx265", "audio_bitrate": "192k"},
    "fast_compress": {"scale": None, "crf": 28, "preset": "ultrafast", "codec": "libx264", "audio_bitrate": "128k"},
    "av1_small": {"scale": None, "crf": 30, "preset": "medium", "codec": "libsvtav1", "audio_bitrate": "128k"},
}

@app.post("/api/transcode")
async def transcode_video(
    user: str = Depends(require_auth),
    task_id: str = Form(...),
    video_name: str = Form(...),
    preset_name: str = Form("compress_1080p"),
):
    """转码视频（应用预设）"""
    video_files = list(INPUT_DIR.glob(f"{task_id}_video.*"))
    if not video_files:
        raise HTTPException(404, "文件不存在")
    
    if preset_name not in TRANSCODE_PRESETS:
        raise HTTPException(400, f"未知预设: {preset_name}")
    
    preset = TRANSCODE_PRESETS[preset_name]
    video_path = video_files[0]
    
    # 创建软链接（因为后面会通过 task_id 找文件）
    # 直接在 output 目录创建结果
    output_filename = f"{Path(video_name).stem}_{preset_name}.mp4"
    output_path = OUTPUT_DIR / f"{task_id}_{output_filename}"
    
    # 构建滤镜
    vf_parts = []
    if preset.get("scale"):
        vf_parts.append(preset["scale"])
    
    vf = ",".join(vf_parts) if vf_parts else None
    
    # 构建命令
    cmd = ["ffmpeg", "-y", "-i", str(video_path)]
    if vf:
        cmd.extend(["-vf", vf])
    cmd.extend([
        "-c:v", preset["codec"],
        "-crf", str(preset["crf"]),
        "-preset", preset["preset"],
        "-c:a", "aac",
        "-b:a", preset.get("audio_bitrate", "128k"),
        "-movflags", "+faststart",
        str(output_path)
    ])
    
    # 如果是 NVENC，使用 GPU 加速
    if preset["codec"] == "libx264" and GPU_ENCODERS.get("h264_nvenc"):
        # 用 NVENC 替代
        nv_idx = cmd.index("-c:v")
        cmd[nv_idx + 1] = "h264_nvenc"
        crf_idx = cmd.index("-crf")
        cmd[crf_idx:crf_idx + 2] = ["-cq", str(preset["crf"]), "-rc", "vbr", "-b:v", "0"]
        preset_idx = cmd.index("-preset")
        cmd[preset_idx + 1] = "p4"
    
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await process.communicate()
    
    if process.returncode != 0 or not output_path.exists():
        raise HTTPException(500, f"转码失败: {stderr.decode()[-300:]}")
    
    # 记录到数据库
    params = {"preset": preset_name, "codec": preset["codec"], "crf": preset["crf"]}
    now = datetime.now().isoformat()
    db_execute(
        """INSERT OR REPLACE INTO tasks (task_id, user, video_name, subtitle_name, status, progress, output_file, output_size, params, created_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (task_id, user, video_name, "(转码)", "completed", 100, output_filename,
         output_path.stat().st_size, json.dumps(params), now, now)
    )
    
    return {
        "task_id": task_id,
        "output_file": output_filename,
        "output_size": output_path.stat().st_size,
        "preset": preset_name,
        "codec_used": cmd[cmd.index("-c:v") + 1],
    }

@app.get("/api/transcode/presets")
async def list_presets():
    """列出可用的转码预设"""
    return {"presets": TRANSCODE_PRESETS}
async def validation_exception_handler(request, exc):
    """全局 422 处理：未登录时改返 401，已登录时返 422 + 详情"""
    auth = request.headers.get("Authorization", "") or request.cookies.get("sb_session", "")
    if not auth:
        return JSONResponse(status_code=401, content={"detail": "请先登录"})
    return JSONResponse(status_code=422, content={"detail": str(exc)})

# 注册到 app 上（用 add_exception_handler 比装饰器更稳）
from fastapi.exceptions import RequestValidationError
app.add_exception_handler(RequestValidationError, validation_exception_handler)
