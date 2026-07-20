#!/usr/bin/env python3
"""
下载 JASSUB 库文件到本地 static/js/ 目录
从 npm registry 下载 tarball 并解压
"""
import urllib.request
import json
import os
import sys
from pathlib import Path
import ssl
import tarfile
import io
import subprocess
from datetime import datetime

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

JASSUB_VERSION = "2.0.15"

# 需要从 tarball 中提取的文件（tarball 内路径 -> 输出文件名）
FILE_MAP = {
    "package/dist/wasm/jassub-worker.js": "jassub-worker.js",
    "package/dist/wasm/jassub-worker.wasm": "jassub-worker.wasm",
    "package/dist/worker/worker.js": "_worker_src.js",
    "package/dist/worker/util.js": "_worker_util.js",
    "package/dist/worker/webgpu-renderer.js": "_worker_webgpu.js",
}

OUTPUT_DIR = Path(__file__).parent.parent / "app" / "static" / "js"


def get_latest_version() -> str:
    url = "https://registry.npmjs.org/jassub/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "subtitle-burner"})
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
            return json.loads(resp.read()).get("version", "")
    except Exception as e:
        print(f"获取最新版本失败: {e}")
        return ""


def list_tarball_files(version: str) -> list:
    """列出 tarball 中的所有文件"""
    url = f"https://registry.npmjs.org/jassub/-/jassub-{version}.tgz"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "subtitle-burner"})
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
            tarball_data = resp.read()
        with tarfile.open(fileobj=io.BytesIO(tarball_data), mode="r:gz") as tar:
            return [m.name for m in tar.getmembers() if m.isfile()]
    except Exception as e:
        print(f"列出文件失败: {e}")
        return []


def download_and_extract(version: str) -> dict:
    """下载 npm tarball 并解压指定文件"""
    url = f"https://registry.npmjs.org/jassub/{version}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "subtitle-burner"})
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
            pkg_info = json.loads(resp.read())
    except Exception as e:
        print(f"获取包信息失败: {e}")
        return {}
    
    tarball_url = pkg_info.get("dist", {}).get("tarball", "")
    if not tarball_url:
        print("未找到 tarball URL")
        return {}
    
    print(f"下载 tarball: {tarball_url}")
    
    try:
        req = urllib.request.Request(tarball_url, headers={"User-Agent": "subtitle-burner"})
        with urllib.request.urlopen(req, timeout=120, context=ssl_ctx) as resp:
            tarball_data = resp.read()
        print(f"  -> 下载完成 ({len(tarball_data):,} bytes)")
    except Exception as e:
        print(f"  -> 下载失败: {e}")
        return {}
    
    extracted = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(tarball_data), mode="r:gz") as tar:
            for member in tar.getmembers():
                for tar_path, output_name in FILE_MAP.items():
                    if member.name == tar_path and member.isfile():
                        f = tar.extractfile(member)
                        if f:
                            output_path = OUTPUT_DIR / output_name
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(output_path, "wb") as out:
                                out.write(f.read())
                            extracted[output_name] = output_path
                            print(f"  提取: {tar_path} -> {output_path} ({member.size:,} bytes)")
    except Exception as e:
        print(f"解压失败: {e}")
    
    return extracted


def build_bundle(version: str) -> bool:
    """用 esbuild 将 JASSUB 打包为浏览器可用的 ESM 格式（保留 import.meta.url）"""
    import tempfile, shutil as _shutil
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        (tmpdir / "package.json").write_text('{"name":"jassub-build","version":"1.0.0"}')
        
        print(f"  安装 jassub@{version} 依赖...")
        result = subprocess.run(
            ["npm", "install", f"jassub@{version}"],
            cwd=str(tmpdir), capture_output=True, timeout=60
        )
        if result.returncode != 0:
            print(f"  [ERROR] npm install 失败: {result.stderr.decode()[-200:]}")
            return False
        
        # 1. 打包主 JASSUB 类（ESM 格式，保留 import.meta.url）
        src_file = tmpdir / "node_modules" / "jassub" / "src" / "jassub.ts"
        entry_file = tmpdir / "entry.mjs"
        entry_file.write_text(
            'import JASSUB from "jassub"\n'
            'window.JASSUBClass = JASSUB\n'
            'export default JASSUB\n'
        )
        
        output_main = OUTPUT_DIR / "jassub.bundle.mjs"
        print(f"  esbuild 打包主类 (ESM)...")
        result = subprocess.run(
            ["npx", "esbuild", str(entry_file),
             "--bundle", "--format=esm",
             f"--outfile={output_main}", "--platform=browser",
             "--target=es2020", "--minify",
             "--loader:.wasm=empty", "--loader:.ts=ts"],
            cwd=str(tmpdir), capture_output=True, timeout=30
        )
        if result.returncode != 0:
            print(f"  [ERROR] 主类打包失败: {result.stderr.decode()[-200:]}")
            return False
        
        # 2. 打包 Worker 脚本（ESM 格式，bundle 所有依赖）
        worker_entry = tmpdir / "worker-entry.mjs"
        worker_entry.write_text(
            'export * from "jassub/dist/worker/worker.js"\n'
        )
        
        output_worker = OUTPUT_DIR / "jassub-worker-bundle.mjs"
        print(f"  esbuild 打包 Worker...")
        result = subprocess.run(
            ["npx", "esbuild", str(worker_entry),
             "--bundle", "--format=esm",
             f"--outfile={output_worker}", "--platform=browser",
             "--target=es2020", "--minify",
             "--loader:.wasm=empty", "--loader:.ts=ts"],
            cwd=str(tmpdir), capture_output=True, timeout=30
        )
        if result.returncode != 0:
            print(f"  [ERROR] Worker 打包失败: {result.stderr.decode()[-200:]}")
            return False
        
        ok = True
        if output_main.exists():
            print(f"  [OK] jassub.bundle.mjs ({output_main.stat().st_size:,} bytes)")
        else:
            print(f"  [ERROR] jassub.bundle.mjs 未生成"); ok = False
        
        if output_worker.exists():
            print(f"  [OK] jassub-worker-bundle.mjs ({output_worker.stat().st_size:,} bytes)")
        else:
            print(f"  [ERROR] jassub-worker-bundle.mjs 未生成"); ok = False
        
        return ok


def save_version_info(version: str, files: list):
    info = {
        "current_version": version,
        "files": files,
        "updated_at": datetime.now().isoformat(),
        "source": "npm registry",
        "package": "jassub",
    }
    version_file = OUTPUT_DIR / "jassub-version.json"
    with open(version_file, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)
    print(f"版本信息已保存: {version_file}")


def main():
    print(f"JASSUB 当前版本: {JASSUB_VERSION}")
    print(f"输出目录: {OUTPUT_DIR}")
    print()

    print("检查最新版本...")
    latest_version = get_latest_version()
    if latest_version:
        print(f"最新版本: {latest_version}")
        if latest_version != JASSUB_VERSION:
            print(f"发现新版本: {JASSUB_VERSION} -> {latest_version}")
    else:
        print(f"使用默认版本: {JASSUB_VERSION}")
    print()

    version_to_download = JASSUB_VERSION
    print(f"下载版本: {version_to_download}")
    extracted = download_and_extract(version_to_download)
    
    if extracted:
        save_version_info(version_to_download, list(extracted.keys()))
    
    print()
    success_count = len(extracted)
    total = len(FILE_MAP)
    if success_count == total:
        print(f"[OK] 全部 {success_count} 个文件下载成功")
    else:
        print(f"[WARN] 只有 {success_count}/{total} 个文件下载成功")
    
    # 打包为浏览器可用的 IIFE 格式
    print()
    print("打包为浏览器可用格式...")
    if build_bundle(version_to_download):
        print("[OK] jassub.bundle.js 打包成功")
    else:
        print("[WARN] jassub.bundle.js 打包失败，需手动运行 esbuild")
    
    return 0 if success_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
