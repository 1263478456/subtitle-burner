#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Docker Hub Pull 数追踪脚本
用法: python track-pulls.py [--repo REPO] [--history] [--csv]
"""

import json
import csv
import os
import sys
import ssl
import argparse
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

# 默认配置
DEFAULT_REPO = "1263478456/subtitle-burner"
DATA_DIR = Path(__file__).parent.parent / "data" / "docker-stats"
HISTORY_FILE = DATA_DIR / "pull_history.json"
CSV_FILE = DATA_DIR / "pull_history.csv"

# 创建不验证 SSL 的 context（用于网络受限环境）
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def fetch_docker_hub_stats(repo: str) -> dict:
    """从 Docker Hub API 获取仓库统计信息"""
    url = f"https://hub.docker.com/v2/repositories/{repo}/"
    
    try:
        req = Request(url, headers={"User-Agent": "subtitle-burner-stats/1.0"})
        with urlopen(req, timeout=15, context=SSL_CONTEXT) as response:
            data = json.loads(response.read().decode())
            return {
                "repo": repo,
                "pull_count": data.get("pull_count", 0),
                "star_count": data.get("star_count", 0),
                "last_updated": data.get("last_updated", ""),
                "date_registered": data.get("date_registered", ""),
                "storage_size": data.get("storage_size", 0),
                "fetched_at": datetime.now().isoformat(),
            }
    except URLError as e:
        print(f"[ERROR] 获取数据失败: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"[ERROR] 解析数据失败: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 未知错误: {e}")
        return None


def load_history() -> list:
    """加载历史数据"""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []


def save_history(history: list):
    """保存历史数据"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # 保存 JSON
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    
    # 保存 CSV
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "timestamp", "repo", "pull_count", "star_count", 
            "daily_pulls", "storage_size_gb"
        ])
        writer.writeheader()
        for i, record in enumerate(history):
            row = {
                "timestamp": record["fetched_at"],
                "repo": record["repo"],
                "pull_count": record["pull_count"],
                "star_count": record["star_count"],
                "storage_size_gb": round(record["storage_size"] / (1024**3), 2),
            }
            # 计算每日增量
            if i > 0:
                row["daily_pulls"] = record["pull_count"] - history[i-1]["pull_count"]
            else:
                row["daily_pulls"] = 0
            writer.writerow(row)


def format_number(num: int) -> str:
    """格式化数字显示"""
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    else:
        return str(num)


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes >= 1024**3:
        return f"{size_bytes/(1024**3):.2f} GB"
    elif size_bytes >= 1024**2:
        return f"{size_bytes/(1024**2):.2f} MB"
    else:
        return f"{size_bytes/1024:.2f} KB"


def show_current_stats(stats: dict):
    """显示当前统计信息"""
    print("\n" + "="*50)
    print(f"[Docker Hub] {stats['repo']}")
    print("="*50)
    print(f"  Pull Count:   {format_number(stats['pull_count'])} ({stats['pull_count']:,})")
    print(f"  Star Count:   {stats['star_count']}")
    print(f"  Storage Size: {format_size(stats['storage_size'])}")
    print(f"  Registered:   {stats['date_registered'][:10]}")
    print(f"  Last Updated: {stats['last_updated'][:19]}")
    print("="*50)


def show_history(history: list, limit: int = 10):
    """显示历史记录"""
    if not history:
        print("\n[INFO] No history records")
        return
    
    print(f"\n[History] (last {min(limit, len(history))} records):")
    print("-"*60)
    print(f"{'Time':<20} {'Pulls':>10} {'Growth':>8} {'Star':>6}")
    print("-"*60)
    
    for i, record in enumerate(history[-limit:]):
        timestamp = record["fetched_at"][:16].replace("T", " ")
        pull_count = record["pull_count"]
        star_count = record["star_count"]
        
        if i > 0 or (i == 0 and len(history) > limit):
            prev_idx = len(history) - limit + i - 1
            if prev_idx >= 0:
                daily = pull_count - history[prev_idx]["pull_count"]
                daily_str = f"+{daily}" if daily >= 0 else str(daily)
            else:
                daily_str = "-"
        else:
            daily_str = "-"
        
        print(f"{timestamp:<20} {format_number(pull_count):>10} {daily_str:>8} {star_count:>6}")
    
    print("-"*60)
    
    # 显示总计
    if len(history) >= 2:
        total_growth = history[-1]["pull_count"] - history[0]["pull_count"]
        days = (datetime.fromisoformat(history[-1]["fetched_at"]) - 
                datetime.fromisoformat(history[0]["fetched_at"])).days or 1
        print(f"\n[Summary]")
        print(f"  Total Growth: {format_number(total_growth)} ({total_growth:,})")
        print(f"  Days Tracked: {days}")
        print(f"  Daily Average: {format_number(total_growth // days)}/day")


def main():
    parser = argparse.ArgumentParser(description="Docker Hub Pull 数追踪工具")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="Docker Hub 仓库名 (默认: 1263478456/subtitle-burner)")
    parser.add_argument("--history", action="store_true", help="显示历史记录")
    parser.add_argument("--csv", action="store_true", help="导出 CSV 文件路径")
    parser.add_argument("--limit", type=int, default=10, help="显示历史记录条数 (默认: 10)")
    parser.add_argument("--quiet", action="store_true", help="静默模式，只输出数字")
    
    args = parser.parse_args()
    
    # 获取当前数据
    stats = fetch_docker_hub_stats(args.repo)
    if not stats:
        sys.exit(1)
    
    # 加载历史数据
    history = load_history()
    
    # 添加新数据（避免重复）
    if not history or history[-1]["pull_count"] != stats["pull_count"]:
        history.append(stats)
        save_history(history)
    
    # 输出结果
    if args.quiet:
        print(stats["pull_count"])
    elif args.history:
        show_current_stats(stats)
        show_history(history, args.limit)
        if args.csv:
            print(f"\n[CSV File]: {CSV_FILE}")
    else:
        show_current_stats(stats)
        
        # 显示简要趋势
        if len(history) >= 2:
            last_pull = history[-2]["pull_count"]
            current_pull = stats["pull_count"]
            growth = current_pull - last_pull
            print(f"\n[Trend] +{format_number(growth)} ({growth:,})")
    
    if args.csv:
        print(f"\n[Data Saved]")
        print(f"  JSON: {HISTORY_FILE}")
        print(f"  CSV:  {CSV_FILE}")


if __name__ == "__main__":
    main()
