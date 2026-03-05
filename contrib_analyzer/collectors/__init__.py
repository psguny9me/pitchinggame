"""데이터 수집 모듈"""

import subprocess
import os


def run_git(args, cwd=None):
    """git 명령 실행 후 stdout 반환"""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        encoding="utf-8", errors="replace",
        cwd=cwd or os.getcwd(),
    )
    return result.stdout.strip()


def count_lines(text):
    """비어있지 않은 라인 수 반환"""
    if not text:
        return 0
    return len([line for line in text.splitlines() if line.strip()])


def print_header(title):
    print()
    print("━" * 70)
    print(f"  {title}")
    print("━" * 70)


def print_progress(msg):
    print(f"  ▶ {msg}")
