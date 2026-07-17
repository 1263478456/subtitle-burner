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

def _build_ffmpeg_cmd(video_path, sub_path, output_path, params):
    """构建 FFmpeg 命令"""
    sub_mode = params.get('sub_mode', 'burn')
    keep_original_sub = params.get('keep_original_sub', False)
    sub_name = params.get('sub_name', '中文字幕')  # 字幕轨道名称
    crf = params.get('crf', 18)
    preset = params.get('preset', 'medium')
    codec = params.get('codec', 'libx264')
    
    # 预览参数（用于字幕样式调整）
    preview_params = {}
    if 'preview_params' in params:
        try:
            preview_params = json.loads(params['preview_params']) if isinstance(params['preview_params'], str) else params['preview_params']
        except:
            pass
    
    cmd = ["ffmpeg", "-y"]
    
    # 字幕路径转义
    sub_path_escaped = str(sub_path).replace(":", r"\:").replace("'", r"\'")
    sub_path_posix = str(sub_path).replace("\\", "/")
    
    # 时间偏移
    time_offset = preview_params.get('timeOffset', 0)
    if time_offset and time_offset != 0:
        # 使用 -itsoffset 参数实现时间偏移（不支持小数点格式的偏移）
        # 对于字幕，我们通过修改 subtitles 滤镜的 ts_offset 来实现
        logger.info(f"[FFmpeg] 时间偏移: {time_offset}s")
    
    if sub_mode == 'soft':
        # 软字幕模式：添加字幕轨道
        cmd.extend(["-i", str(video_path)])
        
        # 添加字幕文件作为输入
        cmd.extend(["-i", str(sub_path_posix)])
        
        # 映射流
        cmd.extend(["-map", "0:v", "-map", "0:a?"])
        cmd.extend(["-map", "1:0"])  # 添加字幕轨道
        
        # 视频编码
        if codec.startswith('h264_nvenc') or codec.startswith('hevc_nvenc'):
            cmd.extend(["-c:v", codec])
            cmd.extend(["-preset", "p5"])
            cmd.extend(["-rc", "vbr", "-cq", str(crf)])
        elif codec.startswith('h264_qsv') or codec.startswith('hevc_qsv'):
            cmd.extend(["-c:v", codec])
            cmd.extend(["-global_quality", str(crf)])
        else:
            cmd.extend(["-c:v", codec])
            cmd.extend(["-crf", str(crf)])
            cmd.extend(["-preset", preset])
        
        cmd.extend(["-c:a", "copy"])
        cmd.extend(["-c:s", "mov_text"])  # 字幕编码
        
        # 设置字幕轨道名称
        cmd.extend(["-metadata:s:s:0", f"title={sub_name}"])
        
        # 是否保留原字幕
        if not keep_original_sub:
            # 只保留新添加的字幕
            cmd.extend(["-map", "-0:s?"])
            cmd.extend(["-map", "1:0"])
        
    else:
        # 硬字幕模式：烧录字幕到视频
        
        # 添加时间偏移参数
        if time_offset and time_offset != 0:
            # 使用 -itsoffset 偏移字幕
            cmd.extend(["-itsoffset", str(time_offset)])
        
        cmd.extend(["-i", str(video_path)])
        
        # 构建字幕滤镜
        vf_filter = f"subtitles='{sub_path_escaped}'"
        
        # SRT/VTT 样式强制设置
        if sub_path.suffix.lower() in ['.srt', '.vtt']:
            # 构建样式字符串
            style_parts = []
            
            if preview_params.get('fontSize'):
                style_parts.append(f"FontSize={preview_params['fontSize']}")
            
            if preview_params.get('fontFamily'):
                font_map = {
                    'sans-serif': 'Arial',
                    'serif': 'Times New Roman',
                    'monospace': 'Courier New',
                    'Microsoft YaHei': 'Microsoft YaHei',
                    'PingFang SC': 'PingFang SC',
                    'SimHei': 'SimHei',
                    'SimSun': 'SimSun',
                    'KaiTi': 'KaiTi',
                }
                font_name = font_map.get(preview_params['fontFamily'], 'Arial')
                style_parts.append(f"FontName={font_name}")
            
            if preview_params.get('fontColor'):
                color = preview_params['fontColor']
                # 转换 #RRGGBB 为 ASS 颜色格式 &HBBGGRR&
                if color.startswith('#') and len(color) == 7:
                    r, g, b = color[1:3], color[3:5], color[5:7]
                    ass_color = f"&H00{b}{g}{r}&"
                    style_parts.append(f"PrimaryColour={ass_color}")
            
            if preview_params.get('outlineWidth'):
                style_parts.append(f"Outline={preview_params['outlineWidth']}")
            
            if preview_params.get('outlineColor'):
                color = preview_params['outlineColor']
                if color.startswith('#') and len(color) == 7:
                    r, g, b = color[1:3], color[3:5], color[5:7]
                    ass_color = f"&H00{b}{g}{r}&"
                    style_parts.append(f"OutlineColour={ass_color}")
            
            if preview_params.get('shadowOffset'):
                style_parts.append(f"Shadow={preview_params['shadowOffset']}")
            
            if preview_params.get('fontWeight') == 'bold':
                style_parts.append("Bold=1")
            elif preview_params.get('fontWeight') == 'lighter':
                style_parts.append("Bold=0")
            
            # 位置调整
            if preview_params.get('positionY'):
                alignment_map = {
                    'bottom': 2,  # 底部居中
                    'top': 8,     # 顶部居中
                    'center': 5,  # 居中
                }
                alignment = alignment_map.get(preview_params['positionY'], 2)
                style_parts.append(f"Alignment={alignment}")
            
            if preview_params.get('marginBottom') and preview_params.get('positionY', 'bottom') == 'bottom':
                style_parts.append(f"MarginV={preview_params['marginBottom']}")
            elif preview_params.get('marginTop') and preview_params.get('positionY') == 'top':
                style_parts.append(f"MarginV={preview_params['marginTop']}")
            
            if style_parts:
                style_str = ','.join(style_parts)
                vf_filter += f":force_style='{style_str}'"
        
        # ASS 字幕：如果有预览参数，可能需要覆盖样式
        elif sub_path.suffix.lower() in ['.ass', '.ssa'] and preview_params:
            # ASS 字幕已经有完整样式定义，但我们可以通过 ASS 滤镜的 force_style 覆盖部分
            style_parts = []
            
            if preview_params.get('fontSize'):
                style_parts.append(f"FontSize={preview_params['fontSize']}")
            
            if preview_params.get('fontFamily'):
                font_map = {
                    'sans-serif': 'Arial',
                    'serif': 'Times New Roman',
                    'monospace': 'Courier New',
                    'Microsoft YaHei': 'Microsoft YaHei',
                    'PingFang SC': 'PingFang SC',
                    'SimHei': 'SimHei',
                    'SimSun': 'SimSun',
                    'KaiTi': 'KaiTi',
                }
                font_name = font_map.get(preview_params['fontFamily'], 'Arial')
                style_parts.append(f"FontName={font_name}")
            
            if preview_params.get('fontColor'):
                color = preview_params['fontColor']
                if color.startswith('#') and len(color) == 7:
                    r, g, b = color[1:3], color[3:5], color[5:7]
                    ass_color = f"&H00{b}{g}{r}&"
                    style_parts.append(f"PrimaryColour={ass_color}")
            
            if style_parts:
                style_str = ','.join(style_parts)
                vf_filter += f":force_style='{style_str}'"
        
        cmd.extend(["-vf", vf_filter])
        
        # 视频编码
        if codec.startswith('h264_nvenc') or codec.startswith('hevc_nvenc'):
            cmd.extend(["-c:v", codec])
            cmd.extend(["-preset", "p5"])
            cmd.extend(["-rc", "vbr", "-cq", str(crf)])
            cmd.extend(["-pix_fmt", "yuv420p"])
        elif codec.startswith('h264_qsv') or codec.startswith('hevc_qsv'):
            cmd.extend(["-c:v", codec])
            cmd.extend(["-global_quality", str(crf)])
        else:
            cmd.extend(["-c:v", codec])
            cmd.extend(["-crf", str(crf)])
            cmd.extend(["-preset", preset])
        
        # 音频：直接复制
        cmd.extend(["-c:a", "copy"])
        
        # 映射流
        cmd.extend(["-map", "0:v:0", "-map", "0:a?"])
        
        # 是否保留原字幕
        if keep_original_sub:
            cmd.extend(["-map", "0:s?"])
    
    # 输出文件
    cmd.extend(["-movflags", "+faststart"])
    cmd.append(str(output_path))
    
    return cmd

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
    conn.execute("""CREATE TABLE IF NOT EXISTS presets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        params TEXT NOT NULL,
        is_default BOOLEAN DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(user, name)
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

        # 收集 stderr 输出用于错误诊断
        stderr_lines = []

        # 实时解析 stderr 更新进度
        async def read_stderr():
            nonlocal process
            current_time = 0.0
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="ignore").strip()
                stderr_lines.append(line_str)
                # 保留最后 50 行
                if len(stderr_lines) > 50:
                    stderr_lines.pop(0)
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
            # 使用收集的 stderr 输出
            stderr_output = "\n".join(stderr_lines[-30:])
            logger.error(f"[任务 {task_id}] FFmpeg 失败 (returncode={process.returncode}):\n{stderr_output}")
            raise Exception(f"FFmpeg 执行失败 (code={process.returncode}): {stderr_output[:300]}")

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
    return {"status": "ok", "version": "3.0.93"}

@app.get("/api/health")
async def api_health():
    """API 健康检查，返回详细信息"""
    return {
        "status": "ok",
        "version": "3.0.93",
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "queue_size": queue.qsize(),
        "gpu_encoders": [name for name, supported in GPU_ENCODERS.items() if supported]
    }

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

@app.get("/preview")
async def preview_page(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=302)
    return FileResponse("app/static/preview.html")

@app.get("/api/media/file")
async def get_media_file(path: str, request: Request):
    """获取媒体库中的文件内容（用于预览字幕）"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "请先登录")
    
    # 安全检查：防止路径遍历
    if ".." in path:
        raise HTTPException(400, "无效的路径")
    
    full_path = MEDIA_ROOT / path
    if not full_path.exists():
        raise HTTPException(404, "文件不存在")
    
    # 检查是否是字幕文件
    subtitle_exts = ['.srt', '.vtt', '.ass', '.ssa', '.sub']
    if full_path.suffix.lower() not in subtitle_exts:
        raise HTTPException(400, "不是字幕文件")
    
    # 读取文件内容（支持多种编码）
    try:
        # 先读取原始字节，检测编码
        raw_bytes = full_path.read_bytes()
        
        # 检测 BOM（字节顺序标记）
        if raw_bytes[:2] == b'\xff\xfe':
            # UTF-16 LE BOM
            content = raw_bytes.decode('utf-16-le')
            # 移除 BOM 字符
            if content and content[0] == '\ufeff':
                content = content[1:]
            logger.info(f"[字幕] 检测到 UTF-16 LE 编码: {full_path.name}")
        elif raw_bytes[:2] == b'\xfe\xff':
            # UTF-16 BE BOM
            content = raw_bytes.decode('utf-16-be')
            if content and content[0] == '\ufeff':
                content = content[1:]
            logger.info(f"[字幕] 检测到 UTF-16 BE 编码: {full_path.name}")
        elif raw_bytes[:3] == b'\xef\xbb\xbf':
            # UTF-8 BOM
            content = raw_bytes[3:].decode('utf-8')
            logger.info(f"[字幕] 检测到 UTF-8 BOM: {full_path.name}")
        else:
            # 没有 BOM，尝试多种编码
            for encoding in ['utf-8', 'gbk', 'gb2312', 'big5', 'latin-1']:
                try:
                    content = raw_bytes.decode(encoding)
                    logger.info(f"[字幕] 使用 {encoding} 编码: {full_path.name}")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                content = raw_bytes.decode('latin-1')
                logger.info(f"[字幕] 回退到 latin-1 编码: {full_path.name}")
    except Exception as e:
        logger.error(f"[字幕] 读取文件失败: {e}")
        raise HTTPException(500, f"读取文件失败: {str(e)}")
    
    return {"content": content, "filename": full_path.name, "type": full_path.suffix.lower()}

@app.get("/api/media/stream")
async def stream_media_file(path: str, request: Request):
    """流式传输媒体文件（用于视频预览，直接返回原文件）"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "请先登录")
    
    # 安全检查
    if ".." in path:
        raise HTTPException(400, "无效的路径")
    
    full_path = MEDIA_ROOT / path
    if not full_path.exists():
        raise HTTPException(404, "文件不存在")
    
    # 检查是否是视频文件
    video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts', '.m4v']
    if full_path.suffix.lower() not in video_exts:
        raise HTTPException(400, "不是视频文件")
    
    # 直接返回原文件，让浏览器尝试播放
    # 浏览器支持的格式会正常播放，不支持的可能只有画面没有声音
    return FileResponse(full_path, media_type="video/mp4")

@app.get("/api/media/audio-transcode")
async def audio_transcode_media(
    path: str, 
    request: Request,
    start: float = 0,
    duration: float = 20
):
    """单独转码音频为 AAC 格式（用于预览时补充声音）"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "请先登录")
    
    if ".." in path:
        raise HTTPException(400, "无效的路径")
    
    full_path = MEDIA_ROOT / path
    if not full_path.exists():
        raise HTTPException(404, "文件不存在")
    
    video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts', '.m4v']
    if full_path.suffix.lower() not in video_exts:
        raise HTTPException(400, "不是视频文件")
    
    # 探测音频编码
    BROWSER_AUDIO_CODECS = {'aac', 'mp3', 'opus', 'vorbis', 'wav', 'pcm_s16le'}
    try:
        probe_cmd = [
            "ffprobe", "-v", "quiet", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(full_path)
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        audio_codec = probe_result.stdout.strip().lower() if probe_result.returncode == 0 else "unknown"
    except Exception:
        audio_codec = "unknown"
    
    # 如果音频已经是浏览器支持的格式，返回空（不需要转码）
    if audio_codec in BROWSER_AUDIO_CODECS:
        return Response(status_code=204)  # No Content
    
    logger.info(f"[音频转码] 文件: {full_path.name}, 音频编码: {audio_codec}, start: {start}s, duration: {duration}s")
    
    # 生成临时文件
    import tempfile
    import hashlib
    import time as _time
    
    hash_name = hashlib.md5(f"{full_path}_audio_{start}_{duration}".encode()).hexdigest()[:16]
    temp_dir = Path("/tmp/preview_cache")
    temp_dir.mkdir(exist_ok=True)
    temp_file = temp_dir / f"{hash_name}.m4a"
    
    # 检查缓存
    if temp_file.exists():
        cache_age = _time.time() - temp_file.stat().st_mtime
        if cache_age < 300:
            logger.info(f"[音频转码] 使用缓存: {temp_file}")
            return FileResponse(temp_file, media_type="audio/mp4")
    
    # 构建 FFmpeg 命令 - 只转码音频
    cmd = ["ffmpeg", "-y", "-fflags", "+genpts"]
    
    if start > 0:
        cmd.extend(["-ss", str(start)])
    
    cmd.extend(["-i", str(full_path)])
    
    if duration > 0:
        cmd.extend(["-t", str(duration)])
    
    # 只提取和转码音频，不要视频
    cmd.extend([
        "-vn",                       # 不要视频流
        "-c:a", "aac",               # 音频转码为 AAC
        "-b:a", "128k",
        "-ac", "2",
        "-movflags", "+faststart",
        str(temp_file)
    ])
    
    logger.info(f"[音频转码] 开始: {full_path.name} [{start}s - {start + duration}s]")
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            logger.error(f"[音频转码] 失败: {result.stderr.decode()[-300:]}")
            return Response(status_code=500)
        logger.info(f"[音频转码] 完成: {temp_file}")
    except subprocess.TimeoutExpired:
        logger.error("[音频转码] 超时")
        return Response(status_code=500)
    except Exception as e:
        logger.error(f"[音频转码] 异常: {e}")
        return Response(status_code=500)
    
    return FileResponse(temp_file, media_type="audio/mp4")

@app.get("/api/media/probe")
async def probe_media_file(path: str, request: Request):
    """探测媒体文件的编码信息"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "请先登录")
    
    if ".." in path:
        raise HTTPException(400, "无效的路径")
    
    full_path = MEDIA_ROOT / path
    if not full_path.exists():
        raise HTTPException(404, "文件不存在")
    
    # 使用 ffprobe 获取媒体信息
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", str(full_path)
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            raise Exception("ffprobe 失败")
        
        import json as _json
        info = _json.loads(result.stdout)
        
        # 提取音频编码信息
        audio_codec = None
        audio_channels = None
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "audio":
                audio_codec = stream.get("codec_name")
                audio_channels = stream.get("channels")
                break
        
        # 提取字幕流信息
        subtitle_streams = []
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "subtitle":
                subtitle_streams.append({
                    "index": stream.get("index"),
                    "codec": stream.get("codec_name", "unknown"),
                    "title": stream.get("tags", {}).get("title") or stream.get("display_name") or f"字幕轨道 {stream.get('index')}",
                    "language": stream.get("tags", {}).get("language", "")
                })
        
        return {
            "audio_codec": audio_codec,
            "audio_channels": audio_channels,
            "format": info.get("format", {}),
            "streams": info.get("streams", []),
            "subtitle_streams": subtitle_streams,
            "duration": float(info.get("format", {}).get("duration", 0))
        }
    except Exception as e:
        logger.error(f"媒体探测失败: {e}")
        return {"audio_codec": "unknown", "audio_channels": 0, "error": str(e)}

@app.get("/api/media/extract-subtitle")
async def extract_embedded_subtitle(
    path: str,
    request: Request,
    subtitle_index: int = 0
):
    """从视频中提取内嵌字幕"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "请先登录")
    
    if ".." in path:
        raise HTTPException(400, "无效的路径")
    
    full_path = MEDIA_ROOT / path
    if not full_path.exists():
        raise HTTPException(404, "文件不存在")
    
    video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts', '.m4v']
    if full_path.suffix.lower() not in video_exts:
        raise HTTPException(400, "不是视频文件")
    
    try:
        # 先探测字幕流
        probe_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-select_streams", "s",
            str(full_path)
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        
        if probe_result.returncode != 0:
            raise Exception("ffprobe 失败")
        
        import json as _json
        info = _json.loads(probe_result.stdout)
        subtitle_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "subtitle"]
        
        if not subtitle_streams:
            raise HTTPException(404, "视频中没有内嵌字幕")
        
        if subtitle_index >= len(subtitle_streams):
            subtitle_index = 0
        
        # 提取字幕
        subtitle_stream = subtitle_streams[subtitle_index]
        stream_index = subtitle_stream.get("index", 0)
        codec_name = subtitle_stream.get("codec_name", "unknown")
        
        # 生成临时文件
        temp_dir = Path("/tmp/preview_cache")
        temp_dir.mkdir(exist_ok=True)
        
        # 根据编码选择输出格式
        if codec_name in ['ass', 'ssa']:
            output_ext = '.ass'
        else:
            output_ext = '.srt'
        
        temp_file = temp_dir / f"subtitle_{hashlib.md5(f'{path}_{subtitle_index}'.encode()).hexdigest()[:16]}{output_ext}"
        
        # 提取字幕
        extract_cmd = [
            "ffmpeg", "-y",
            "-i", str(full_path),
            "-map", f"0:{stream_index}",
            "-c:s", "copy" if output_ext == '.ass' else "srt",
            str(temp_file)
        ]
        
        extract_result = subprocess.run(extract_cmd, capture_output=True, timeout=30)
        
        if extract_result.returncode != 0:
            # 尝试转换为 SRT 格式
            extract_cmd = [
                "ffmpeg", "-y",
                "-i", str(full_path),
                "-map", f"0:{stream_index}",
                "-c:s", "srt",
                str(temp_file.with_suffix('.srt'))
            ]
            extract_result = subprocess.run(extract_cmd, capture_output=True, timeout=30)
            
            if extract_result.returncode != 0:
                raise Exception(f"字幕提取失败: {extract_result.stderr.decode()[-300:]}")
            
            temp_file = temp_file.with_suffix('.srt')
        
        # 读取字幕内容
        content = temp_file.read_text(encoding='utf-8', errors='ignore')
        
        # 获取字幕标题
        title = subtitle_stream.get("tags", {}).get("title") or f"字幕轨道 {stream_index}"
        language = subtitle_stream.get("tags", {}).get("language", "")
        
        return {
            "content": content,
            "filename": f"{Path(path).stem}_{title}{output_ext}",
            "type": output_ext,
            "title": title,
            "language": language,
            "codec": codec_name
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[字幕提取] 失败: {e}")
        raise HTTPException(500, f"字幕提取失败: {str(e)}")

@app.post("/api/media/remove-subtitles")
async def remove_subtitles(
    request: Request,
    video_path: str = Form(...),
    keep_subtitle_indices: str = Form("")
):
    """删除视频中的内嵌字幕，只保留指定的轨道
    
    Args:
        video_path: 视频文件路径
        keep_subtitle_indices: 要保留的字幕轨道索引，逗号分隔，为空则删除所有字幕
    """
    user = require_auth(request)
    
    if ".." in video_path:
        raise HTTPException(400, "无效的路径")
    
    full_path = MEDIA_ROOT / video_path
    if not full_path.exists():
        raise HTTPException(404, "文件不存在")
    
    video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts', '.m4v']
    if full_path.suffix.lower() not in video_exts:
        raise HTTPException(400, "不是视频文件")
    
    try:
        # 解析要保留的字幕索引
        keep_indices = set()
        if keep_subtitle_indices.strip():
            for idx in keep_subtitle_indices.split(','):
                idx = idx.strip()
                if idx.isdigit():
                    keep_indices.add(int(idx))
        
        # 探测视频流信息
        probe_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", str(full_path)
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        
        if probe_result.returncode != 0:
            raise Exception("ffprobe 失败")
        
        import json as _json
        info = _json.loads(probe_result.stdout)
        
        # 分析流信息
        streams = info.get("streams", [])
        video_streams = []
        audio_streams = []
        subtitle_streams = []
        
        for stream in streams:
            codec_type = stream.get("codec_type")
            index = stream.get("index")
            if codec_type == "video":
                video_streams.append(index)
            elif codec_type == "audio":
                audio_streams.append(index)
            elif codec_type == "subtitle":
                subtitle_streams.append({
                    "index": index,
                    "codec": stream.get("codec_name", "unknown"),
                    "title": stream.get("tags", {}).get("title", f"字幕轨道 {index}"),
                    "language": stream.get("tags", {}).get("language", "")
                })
        
        if not subtitle_streams:
            raise HTTPException(400, "视频中没有内嵌字幕")
        
        # 生成输出文件
        output_filename = f"{full_path.stem}_no_subs{full_path.suffix}"
        output_path = full_path.parent / output_filename
        
        # 构建 FFmpeg 命令
        cmd = ["ffmpeg", "-y", "-i", str(full_path)]
        
        # 映射视频和音频流
        for idx in video_streams:
            cmd.extend(["-map", f"0:{idx}"])
        for idx in audio_streams:
            cmd.extend(["-map", f"0:{idx}"])
        
        # 映射要保留的字幕流
        if keep_indices:
            for sub in subtitle_streams:
                if sub["index"] in keep_indices:
                    cmd.extend(["-map", f"0:{sub['index']}"])
        
        # 如果不保留任何字幕，添加 -sn 参数
        if not keep_indices:
            cmd.append("-sn")
        
        # 复制所有流（不重新编码）
        cmd.extend(["-c", "copy"])
        
        # 设置字幕轨道名称（如果保留了字幕）
        if keep_indices:
            sub_idx = 0
            for sub in subtitle_streams:
                if sub["index"] in keep_indices:
                    title = sub.get("title", f"字幕 {sub_idx}")
                    cmd.extend([f"-metadata:s:s:{sub_idx}", f"title={title}"])
                    sub_idx += 1
        
        cmd.append(str(output_path))
        
        logger.info(f"[删除字幕] 开始: {full_path.name}, 保留轨道: {keep_indices if keep_indices else '无'}")
        logger.info(f"[删除字幕] FFmpeg 命令: {' '.join(cmd)}")
        
        # 执行 FFmpeg
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        
        if result.returncode != 0:
            error_msg = result.stderr.decode()[-500:]
            logger.error(f"[删除字幕] 失败: {error_msg}")
            raise Exception(f"FFmpeg 执行失败: {error_msg}")
        
        logger.info(f"[删除字幕] 完成: {output_path}")
        
        return {
            "success": True,
            "output_path": str(output_path.relative_to(MEDIA_ROOT)),
            "output_filename": output_filename,
            "original_subtitle_count": len(subtitle_streams),
            "kept_subtitle_count": len(keep_indices),
            "removed_subtitle_count": len(subtitle_streams) - len(keep_indices)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[删除字幕] 失败: {e}")
        raise HTTPException(500, f"删除字幕失败: {str(e)}")

@app.get("/api/media/preview-stream")
async def preview_stream_media(
    path: str, 
    request: Request,
    start: float = 0,        # 起始时间（秒）
    duration: float = 20      # 转码时长（秒），默认 20秒（够判断字幕对齐）
):
    """为预览提供转码后的流媒体（确保浏览器兼容性）
    
    支持按需片段转码：
    - start: 从哪个时间点开始转码（秒）
    - duration: 转码多长时间（秒），默认 60秒
    
    这样可以快速预览视频的任意片段，不需要转码完整视频。
    """
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "请先登录")
    
    if ".." in path:
        raise HTTPException(400, "无效的路径")
    
    full_path = MEDIA_ROOT / path
    if not full_path.exists():
        raise HTTPException(404, "文件不存在")
    
    video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts', '.m4v']
    if full_path.suffix.lower() not in video_exts:
        raise HTTPException(400, "不是视频文件")
    
    # 浏览器支持的音频编码
    BROWSER_AUDIO_CODECS = {'aac', 'mp3', 'opus', 'vorbis', 'wav', 'pcm_s16le'}
    
    # 探测音频编码
    try:
        probe_cmd = [
            "ffprobe", "-v", "quiet", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(full_path)
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        audio_codec = probe_result.stdout.strip().lower() if probe_result.returncode == 0 else "unknown"
    except Exception:
        audio_codec = "unknown"
    
    logger.info(f"[预览流] 文件: {full_path.name}, 音频编码: {audio_codec}, start: {start}s, duration: {duration}s")
    
    # 如果音频已经是浏览器支持的格式，且不需要转码片段
    if audio_codec in BROWSER_AUDIO_CODECS and start == 0:
        logger.info(f"[预览流] 音频编码 {audio_codec} 已兼容，直接返回")
        return FileResponse(full_path, media_type="video/mp4")
    
    # 需要转码（音频不兼容或需要片段转码）
    import tempfile
    import hashlib
    import time as _time  # 导入 time 模块
    
    # 生成临时文件名（包含时间参数）
    hash_name = hashlib.md5(f"{full_path}_{start}_{duration}".encode()).hexdigest()[:16]
    temp_dir = Path("/tmp/preview_cache")
    temp_dir.mkdir(exist_ok=True)
    temp_file = temp_dir / f"{hash_name}.mp4"
    
    # 检查缓存是否存在（5分钟内的缓存有效）
    if temp_file.exists():
        cache_age = _time.time() - temp_file.stat().st_mtime
        if cache_age < 300:  # 5分钟缓存
            logger.info(f"[预览流] 使用缓存: {temp_file}")
            return FileResponse(
                temp_file, 
                media_type="video/mp4",
                headers={"Accept-Ranges": "bytes"}
            )
    
    # 构建 FFmpeg 命令
    # 混合策略：
    # - start=0：直接转码，不需要 seek
    # - start>0：使用 input seeking（-ss 在 -i 前面），速度快
    #   从 FFmpeg 2.1 开始，转码模式下的 input seeking 也是帧精确的
    cmd = ["ffmpeg", "-y", "-fflags", "+genpts"]  # 生成 PTS 保证精度
    
    # 对于 start>0，使用 input seeking（快速）
    if start > 0:
        cmd.extend(["-ss", str(start)])
    
    cmd.extend(["-i", str(full_path)])
    
    # 限制输出时长
    if duration > 0:
        cmd.extend(["-t", str(duration)])
    
    # 编码参数 - 降低质量换取速度
    cmd.extend([
        "-vf", "scale=640:-2",      # 降低到 640p 宽度（预览足够）
        "-c:v", "libx264",           # 使用 H.264 编码
        "-preset", "ultrafast",      # 最快的编码预设
        "-crf", "28",                # 较低的质量（预览不需要高质量）
        "-c:a", "aac",               # 音频转码为 AAC
        "-b:a", "96k",               # 较低的音频比特率
        "-ac", "2",                  # 立体声
        "-avoid_negative_ts", "make_zero",
        "-movflags", "+faststart",
        str(temp_file)
    ])
    
    logger.info(f"[预览流] 开始转码: {full_path.name} [{start}s - {start + duration}s]")
    
    # 执行转码（start=0 时需要更长时间处理 MKV 索引）
    timeout = 300 if start == 0 else 120  # start=0 时给 5分钟超时
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if result.returncode != 0:
            logger.error(f"[预览流] 转码失败: {result.stderr.decode()[-500:]}")
            # 如果片段转码失败，尝试返回原文件
            return FileResponse(full_path, media_type="video/mp4")
        logger.info(f"[预览流] 转码完成: {temp_file}")
    except subprocess.TimeoutExpired:
        logger.error(f"[预览流] 转码超时 ({timeout}秒)")
        # 超时时返回原文件（可能没声音但至少能看到画面）
        return FileResponse(full_path, media_type="video/mp4")
    except Exception as e:
        logger.error(f"[预览流] 转码异常: {e}")
        return FileResponse(full_path, media_type="video/mp4")
    
    return FileResponse(
        temp_file, 
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"}
    )

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
                       keep_original_sub: bool = Form(False),
                       preview_params: str = Form("")):
    video_files = list(INPUT_DIR.glob(f"{task_id}_video.*"))
    if not video_files:
        raise HTTPException(404, "文件不存在")
    if task_id in tasks and tasks[task_id].get("status") in ("queued", "processing"):
        raise HTTPException(400, "任务已在队列中")
    params = {"video_name": video_name, "duration": duration, "crf": crf, "preset": preset, "codec": codec, "style": style, "sub_mode": sub_mode, "keep_original_sub": keep_original_sub}
    
    # 解析预览参数
    if preview_params:
        try:
            params["preview_params"] = json.loads(preview_params)
            logger.info(f"[任务 {task_id}] 使用预览参数: {params['preview_params']}")
        except json.JSONDecodeError:
            logger.warning(f"[任务 {task_id}] 预览参数解析失败，使用默认样式")
    
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
    preview_params: str = Form(""),
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
    
    # 解析预览参数
    if preview_params:
        try:
            params["preview_params"] = json.loads(preview_params)
            logger.info(f"[任务 {task_id}] 使用预览参数: {params['preview_params']}")
        except json.JSONDecodeError:
            logger.warning(f"[任务 {task_id}] 预览参数解析失败，使用默认样式")

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
    
    # 预览参数
    preview_params = params.get("preview_params", {})
    time_offset = preview_params.get("timeOffset", 0)
    
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
        
        # 添加时间偏移
        if time_offset != 0:
            cmd.extend(["-itsoffset", str(time_offset)])
        
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
    
    # 构建 ASS 样式字符串
    if sub_path.suffix.lower() in ['.srt', '.vtt']:
        if style:
            # 用户自定义样式
            vf_parts[0] += f":force_style='{style}'"
        elif preview_params:
            # 使用预览参数生成样式
            ass_style = _preview_params_to_ass_style(preview_params)
            if ass_style:
                vf_parts[0] += f":force_style='{ass_style}'"
        else:
            # 默认样式
            default_style = 'FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1'
            vf_parts[0] += f":force_style='{default_style}'"
    
    vf = ",".join(vf_parts)
    
    # 添加时间偏移到输入
    input_args = ["-y"]
    if time_offset != 0:
        input_args.extend(["-itsoffset", str(time_offset)])
    input_args.extend(["-i", str(video_path)])
    
    # GPU 编码特殊处理
    # 注意：使用 subtitles 滤镜时不能用 -hwaccel cuda（会导致滤镜失败）
    # 必须让 FFmpeg 在 CPU 解码后应用字幕滤镜，再用 GPU 编码
    if codec == "h264_nvenc":
        return [
            "ffmpeg"] + input_args + [
            "-vf", vf, "-pix_fmt", "yuv420p",
            "-c:v", "h264_nvenc",
            "-preset", nvenc_preset,
            "-rc", "vbr", "-cq", str(crf),
            "-c:a", "copy",
            "-map", "0:v:0", "-map", "0:a?",
            str(output_path)
        ]
    elif codec == "hevc_nvenc":
        return [
            "ffmpeg"] + input_args + [
            "-vf", vf, "-pix_fmt", "yuv420p",
            "-c:v", "hevc_nvenc",
            "-preset", nvenc_preset,
            "-rc", "vbr", "-cq", str(crf),
            "-c:a", "copy",
            "-map", "0:v:0", "-map", "0:a?",
            str(output_path)
        ]
    elif codec == "h264_qsv":
        return [
            "ffmpeg"] + input_args + [
            "-vf", vf, "-pix_fmt", "yuv420p",
            "-c:v", "h264_qsv",
            "-preset", "medium", "-global_quality", str(crf),
            "-c:a", "copy",
            "-map", "0:v:0", "-map", "0:a?",
            str(output_path)
        ]
    else:
        # CPU 编码
        return [
            "ffmpeg"] + input_args + [
            "-vf", vf, "-c:v", codec,
            "-crf", str(crf), "-preset", preset,
            "-c:a", "copy",
            "-map", "0:v:0", "-map", "0:a?",
            str(output_path)
        ]

def _preview_params_to_ass_style(params):
    """将预览参数转换为 ASS 样式字符串"""
    styles = []
    
    # 字体大小
    font_size = params.get("fontSize", 24)
    styles.append(f"FontSize={font_size}")
    
    # 字体族
    font_family = params.get("fontFamily", "sans-serif")
    font_map = {
        "sans-serif": "Arial",
        "serif": "Times New Roman",
        "monospace": "Courier New",
        "Microsoft YaHei": "Microsoft YaHei",
        "PingFang SC": "PingFang SC",
        "SimHei": "SimHei",
        "SimSun": "SimSun",
        "KaiTi": "KaiTi"
    }
    ass_font = font_map.get(font_family, font_family)
    styles.append(f"Fontname={ass_font}")
    
    # 字体颜色 (RRGGBB -> &HBBGGRR)
    font_color = params.get("fontColor", "#ffffff")
    ass_color = hex_to_ass_color(font_color, "00")
    styles.append(f"PrimaryColour={ass_color}")
    
    # 字体粗细
    font_weight = params.get("fontWeight", "bold")
    if font_weight == "bold":
        styles.append("Bold=1")
    elif font_weight == "lighter":
        styles.append("Bold=0")
    
    # 描边
    outline_width = params.get("outlineWidth", 2)
    outline_color = params.get("outlineColor", "#000000")
    ass_outline_color = hex_to_ass_color(outline_color, "00")
    styles.append(f"Outline={outline_width}")
    styles.append(f"OutlineColour={ass_outline_color}")
    
    # 阴影
    shadow_offset = params.get("shadowOffset", 2)
    styles.append(f"Shadow={shadow_offset}")
    
    # 位置调整
    position_y = params.get("positionY", "bottom")
    margin_bottom = params.get("marginBottom", 30)
    margin_top = params.get("marginTop", 30)
    
    if position_y == "top":
        styles.append("Alignment=8")  # 顶部居中
        styles.append(f"MarginV={margin_top}")
    elif position_y == "center":
        styles.append("Alignment=5")  # 居中
    else:  # bottom
        styles.append("Alignment=2")  # 底部居中
        styles.append(f"MarginV={margin_bottom}")
    
    return ",".join(styles)

def hex_to_ass_color(hex_color, alpha="00"):
    """将十六进制颜色转换为 ASS 颜色格式 (&HAABBGGRR)"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r = hex_color[0:2]
        g = hex_color[2:4]
        b = hex_color[4:6]
        return f"&H{alpha}{b}{g}{r}"
    return "&H00FFFFFF"

PREVIEW_DIR = OUTPUT_DIR / "previews"
PREVIEW_DIR.mkdir(exist_ok=True)

# ============================================================
# 字幕预设 API / Subtitle Presets API
# ============================================================

@app.get("/api/presets")
async def list_presets(user: str = Depends(require_auth)):
    """获取当前用户的所有字幕预设"""
    rows = db_query(
        "SELECT * FROM presets WHERE user=? ORDER BY is_default DESC, updated_at DESC",
        (user,)
    )
    presets = []
    for r in rows:
        preset = dict(r)
        if preset.get('params'):
            try:
                preset['params'] = json.loads(preset['params'])
            except:
                pass
        presets.append(preset)
    return {"presets": presets, "total": len(presets)}

@app.get("/api/presets/{preset_id}")
async def get_preset(preset_id: int, user: str = Depends(require_auth)):
    """获取单个预设详情"""
    rows = db_query("SELECT * FROM presets WHERE id=? AND user=?", (preset_id, user))
    if not rows:
        raise HTTPException(404, "预设不存在")
    
    preset = dict(rows[0])
    if preset.get('params'):
        try:
            preset['params'] = json.loads(preset['params'])
        except:
            pass
    return preset

@app.post("/api/presets")
async def create_preset(
    user: str = Depends(require_auth),
    name: str = Form(...),
    description: str = Form(""),
    params: str = Form(...),
    is_default: bool = Form(False)
):
    """创建新的字幕预设"""
    # 检查名称是否已存在
    existing = db_query("SELECT id FROM presets WHERE user=? AND name=?", (user, name))
    if existing:
        raise HTTPException(400, "预设名称已存在")
    
    # 验证 params 是有效的 JSON
    try:
        json.loads(params)
    except json.JSONDecodeError:
        raise HTTPException(400, "参数格式无效")
    
    now = datetime.now().isoformat()
    
    # 如果设为默认，先取消其他默认
    if is_default:
        db_execute("UPDATE presets SET is_default=0 WHERE user=?", (user,))
    
    # 插入新预设
    db_execute(
        """INSERT INTO presets (user, name, description, params, is_default, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user, name, description, params, 1 if is_default else 0, now, now)
    )
    
    # 获取新创建的预设 ID
    new_preset = db_query("SELECT id FROM presets WHERE user=? AND name=?", (user, name))
    preset_id = new_preset[0]["id"] if new_preset else None
    
    logger.info(f"[预设] 用户 {user} 创建预设: {name} (ID: {preset_id})")
    return {"id": preset_id, "message": "预设创建成功"}

@app.put("/api/presets/{preset_id}")
async def update_preset(
    preset_id: int,
    user: str = Depends(require_auth),
    name: str = Form(None),
    description: str = Form(None),
    params: str = Form(None),
    is_default: bool = Form(None)
):
    """更新字幕预设"""
    # 检查预设是否存在
    existing = db_query("SELECT * FROM presets WHERE id=? AND user=?", (preset_id, user))
    if not existing:
        raise HTTPException(404, "预设不存在")
    
    current = dict(existing[0])
    now = datetime.now().isoformat()
    
    # 更新字段
    new_name = name if name is not None else current["name"]
    new_desc = description if description is not None else current.get("description", "")
    new_params = params if params is not None else current["params"]
    new_default = is_default if is_default is not None else bool(current["is_default"])
    
    # 检查名称冲突（如果修改了名称）
    if name and name != current["name"]:
        name_exists = db_query("SELECT id FROM presets WHERE user=? AND name=? AND id!=?", (user, name, preset_id))
        if name_exists:
            raise HTTPException(400, "预设名称已存在")
    
    # 验证 params
    if params:
        try:
            json.loads(params)
        except json.JSONDecodeError:
            raise HTTPException(400, "参数格式无效")
    
    # 如果设为默认，先取消其他默认
    if new_default and not current["is_default"]:
        db_execute("UPDATE presets SET is_default=0 WHERE user=?", (user,))
    
    # 更新预设
    db_execute(
        """UPDATE presets SET name=?, description=?, params=?, is_default=?, updated_at=?
           WHERE id=? AND user=?""",
        (new_name, new_desc, new_params, 1 if new_default else 0, now, preset_id, user)
    )
    
    logger.info(f"[预设] 用户 {user} 更新预设: {new_name} (ID: {preset_id})")
    return {"message": "预设更新成功", "updated_at": now}

@app.delete("/api/presets/{preset_id}")
async def delete_preset(preset_id: int, user: str = Depends(require_auth)):
    """删除字幕预设"""
    existing = db_query("SELECT name FROM presets WHERE id=? AND user=?", (preset_id, user))
    if not existing:
        raise HTTPException(404, "预设不存在")
    
    db_execute("DELETE FROM presets WHERE id=? AND user=?", (preset_id, user))
    
    logger.info(f"[预设] 用户 {user} 删除预设: {existing[0]['name']} (ID: {preset_id})")
    return {"message": "预设已删除"}

@app.post("/api/presets/{preset_id}/set-default")
async def set_default_preset(preset_id: int, user: str = Depends(require_auth)):
    """设置默认预设"""
    existing = db_query("SELECT name FROM presets WHERE id=? AND user=?", (preset_id, user))
    if not existing:
        raise HTTPException(404, "预设不存在")
    
    # 取消所有默认
    db_execute("UPDATE presets SET is_default=0 WHERE user=?", (user,))
    # 设置新的默认
    db_execute("UPDATE presets SET is_default=1 WHERE id=? AND user=?", (preset_id, user))
    
    logger.info(f"[预设] 用户 {user} 设置默认预设: {existing[0]['name']} (ID: {preset_id})")
    return {"message": "已设为默认预设"}

@app.get("/api/presets/default")
async def get_default_preset(user: str = Depends(require_auth)):
    """获取当前用户的默认预设"""
    rows = db_query("SELECT * FROM presets WHERE user=? AND is_default=1", (user,))
    if not rows:
        return {"preset": None}
    
    preset = dict(rows[0])
    if preset.get('params'):
        try:
            preset['params'] = json.loads(preset['params'])
        except:
            pass
    return {"preset": preset}

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
