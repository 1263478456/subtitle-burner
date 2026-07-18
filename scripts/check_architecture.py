#!/usr/bin/env python3
"""
Subtitle Burner 架构检查脚本 v2
自动检测常见架构问题，防止类似 bug 再次出现

用法：
    python scripts/check_architecture.py

退出码：
    0 = 全部通过
    1 = 有警告
    2 = 有错误
"""
import re
import sys
import io
from pathlib import Path

# 设置 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 项目根目录
ROOT = Path(__file__).parent.parent
ERRORS = []
WARNINGS = []


def error(msg):
    ERRORS.append(f"ERROR: {msg}")
    print(f"ERROR: {msg}")


def warn(msg):
    WARNINGS.append(f"WARN: {msg}")
    print(f"WARN: {msg}")


def ok(msg):
    print(f"OK: {msg}")


def read_file(path):
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


# ============================================================
# 检查 1：前端硬编码配置检测
# ============================================================
def check_frontend_hardcoded_lists():
    """检测前端 JS/HTML 中是否有硬编码的配置列表"""
    print("\n--- 检查 1：前端硬编码配置 ---")

    frontend_files = list(ROOT.glob("app/static/**/*.html")) + list(ROOT.glob("app/static/**/*.js"))

    hardcoded_patterns = [
        (r"<option value=\"[^\"]+\">[^<]+</option>", "HTML 下拉选项"),
        (r"const\s+\w+\s*=\s*\[[^\]]*\]", "JS 数组常量"),
    ]

    for f in frontend_files:
        content = read_file(f)
        for pattern, desc in hardcoded_patterns:
            matches = re.findall(pattern, content)
            config_matches = [m for m in matches if any(
                kw in m.lower() for kw in ["font", "codec", "preset", "encoder", "nvenc", "qsv"]
            )]
            if config_matches:
                rel = f.relative_to(ROOT)
                warn(f"{rel} 中发现 {desc}（可能需要从 API 动态获取）")

    ok("前端配置检查完成")


# ============================================================
# 检查 2：资源清理对称性检查
# ============================================================
def check_resource_cleanup():
    """检测删除操作是否清理了所有关联资源"""
    print("\n--- 检查 2：资源清理对称性 ---")

    main_py = ROOT / "app" / "main.py"
    if not main_py.exists():
        warn("main.py 不存在，跳过")
        return

    content = read_file(main_py)

    # 不涉及进程的函数
    skip_funcs = {"delete_preset", "delete_presets", "clear_presets"}
    delete_funcs = re.findall(r"def\s+(delete_\w+|clear_\w+)", content)
    for func in delete_funcs:
        if func in skip_funcs:
            continue
        pattern = rf"def\s+{func}\(.*?\n(.*?)(?=\ndef|\nclass|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            body = match.group(1)
            if "running_processes" in body:
                ok(f"{func}() 正确清理了 running_processes")
            else:
                error(f"{func}() 没有清理 running_processes，可能导致进程泄漏")

    ok("资源清理检查完成")


# ============================================================
# 检查 3：Dockerfile 字体包验证
# ============================================================
def check_dockerfile_fonts():
    """验证 Dockerfile 中的字体包名称"""
    print("\n--- 检查 3：Dockerfile 依赖 ---")

    dockerfiles = list(ROOT.glob("app/Dockerfile.*"))
    known_invalid = [
        "fonts-noto-serif-cjk",
        "fonts-noto-serif-cjk-extra",
    ]

    for df in dockerfiles:
        content = read_file(df)
        for invalid_pkg in known_invalid:
            if invalid_pkg in content:
                error(f"{df.name} 中包含不存在的包: {invalid_pkg}")

    ok("Dockerfile 依赖检查完成")


# ============================================================
# 检查 4：文件类型覆盖检查
# ============================================================
def check_file_type_coverage():
    """验证新增文件格式是否在所有处理分支中覆盖"""
    print("\n--- 检查 4：文件类型覆盖 ---")

    main_py = ROOT / "app" / "main.py"
    if not main_py.exists():
        warn("main.py 不存在，跳过")
        return

    content = read_file(main_py)

    # 查找所有字幕格式判断
    suffix_checks = re.findall(r"\.suffix\.lower\(\)\s+in\s+\[([^\]]+)\]", content)
    all_extensions = set()
    for check in suffix_checks:
        exts = re.findall(r"'(\.\w+)'", check)
        all_extensions.update(exts)

    # 检查 ASS/SSA 是否在所有分支中处理
    subtitle_exts = {".srt", ".vtt", ".ass", ".ssa"}
    for branch_name in ["_build_ffmpeg_cmd", "run_burn_task", "_build_media_burn_cmd"]:
        pattern = rf"def\s+{branch_name}"
        match = re.search(pattern, content)
        if match:
            start = match.end()
            next_func = re.search(r"\ndef\s+", content[start:])
            end = start + next_func.start() if next_func else len(content)
            body = content[start:end]

            found_exts = set()
            for ext_match in re.findall(r"'\.(\w+)'", body):
                found_exts.add(f".{ext_match}")

            missing = subtitle_exts - found_exts
            if missing:
                warn(f"{branch_name}() 缺少对 {missing} 格式的处理")

    ok("文件类型覆盖检查完成")


# ============================================================
# 检查 5：任务状态一致性检查
# ============================================================
def check_task_state_consistency():
    """检查任务状态变更是否同时更新了内存和数据库"""
    print("\n--- 检查 5：任务状态一致性 ---")

    main_py = ROOT / "app" / "main.py"
    if not main_py.exists():
        warn("main.py 不存在，跳过")
        return

    content = read_file(main_py)

    db_updates = re.finditer(
        r"db_execute\(\"UPDATE tasks SET status=.*?\"\s*,\s*\(.*?\"(\w+)\".*?task_id",
        content
    )
    for match in db_updates:
        status = match.group(1)
        start = max(0, match.start() - 500)
        end = min(len(content), match.end() + 500)
        context = content[start:end]
        if f'tasks[task_id]' in context and f'"status"' in context:
            ok(f"状态 '{status}' 更新时同步了内存字典")
        elif f'tasks[' in context:
            ok(f"状态 '{status}' 更新时涉及内存字典")
        else:
            warn(f"状态 '{status}' 的数据库更新可能未同步到内存字典")

    ok("任务状态一致性检查完成")


# ============================================================
# 检查 6：API 鉴权检查
# ============================================================
def check_api_auth():
    """检查新增 API 是否有鉴权保护"""
    print("\n--- 检查 6：API 鉴权 ---")

    main_py = ROOT / "app" / "main.py"
    if not main_py.exists():
        warn("main.py 不存在，跳过")
        return

    content = read_file(main_py)

    # 找到所有 @app.get/post 装饰器
    api_defs = re.finditer(r'@app\.(get|post|put|delete)\("(/api/[^"]+)"', content)

    # 不需要鉴权的 API
    skip_apis = {"/api/login", "/api/health", "/health"}

    for match in api_defs:
        method = match.group(1)
        path = match.group(2)

        if path in skip_apis:
            continue

        # 找到函数定义
        start = match.end()
        next_decorator = re.search(r"@\w+\.", content[start:])
        end = start + next_decorator.start() if next_decorator else len(content)
        func_body = content[start:end]

        # 检查是否有鉴权
        has_auth = any([
            "require_auth" in func_body,
            "get_current_user" in func_body,
            "Depends(require_auth)" in func_body,
        ])

        if has_auth:
            ok(f"{method.upper()} {path} 有鉴权保护")
        else:
            warn(f"{method.upper()} {path} 没有鉴权保护（如果是公开 API 请忽略）")

    ok("API 鉴权检查完成")


# ============================================================
# 检查 7：子进程超时检查
# ============================================================
def check_subprocess_timeout():
    """检查子进程调用是否有超时保护"""
    print("\n--- 检查 7：子进程超时 ---")

    main_py = ROOT / "app" / "main.py"
    if not main_py.exists():
        warn("main.py 不存在，跳过")
        return

    content = read_file(main_py)

    # 找到所有 subprocess 调用
    subprocess_calls = re.finditer(
        r"subprocess\.(run|Popen|call)\((.*?)(?:\)|$)",
        content, re.DOTALL
    )

    for match in subprocess_calls:
        call_args = match.group(2)
        if "timeout" not in call_args:
            # 获取上下文
            start = max(0, match.start() - 100)
            context = content[start:match.start()].split("\n")[-1].strip()
            warn(f"subprocess 调用缺少 timeout 参数: {context[:60]}...")

    ok("子进程超时检查完成")


# ============================================================
# 检查 8：前端错误处理检查
# ============================================================
def check_frontend_error_handling():
    """检查前端 fetch 调用是否有错误处理"""
    print("\n--- 检查 8：前端错误处理 ---")

    frontend_files = list(ROOT.glob("app/static/**/*.html")) + list(ROOT.glob("app/static/**/*.js"))

    for f in frontend_files:
        content = read_file(f)
        if not content:
            continue

        # 找到所有 fetch 调用
        fetch_calls = re.finditer(r"fetch\(['\"]([^'\"]+)['\"]", content)
        for match in fetch_calls:
            url = match.group(1)
            # 检查是否有 try-catch
            start = max(0, match.start() - 200)
            end = min(len(content), match.end() + 500)
            context = content[start:end]

            if "try" in context and ("catch" in context or ".catch" in context):
                ok(f"fetch {url} 有错误处理")
            elif "await" in context:
                # async 函数中的 fetch 如果没有 try-catch，可能有问题
                rel = f.relative_to(ROOT)
                warn(f"{rel} 中 fetch {url} 缺少 try-catch 错误处理")

    ok("前端错误处理检查完成")


# ============================================================
# 主函数
# ============================================================
def main():
    print("=" * 60)
    print("Subtitle Burner 架构检查 v2")
    print("=" * 60)

    check_frontend_hardcoded_lists()
    check_resource_cleanup()
    check_dockerfile_fonts()
    check_file_type_coverage()
    check_task_state_consistency()
    check_api_auth()
    check_subprocess_timeout()
    check_frontend_error_handling()

    print("\n" + "=" * 60)
    print(f"检查完成: {len(ERRORS)} 个错误, {len(WARNINGS)} 个警告")
    print("=" * 60)

    if ERRORS:
        sys.exit(2)
    elif WARNINGS:
        sys.exit(1)
    else:
        print("全部通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
