"""
YAML 설정 로드 + 자동 감지 + 검증

주요 기능:
  - YAML 파일에서 프로젝트 설정 로드
  - repo_path로 대상 Git 저장소 지정
  - members, modules, git_platform 자동 감지
  - init 명령으로 YAML 초안 생성
"""

import os
import re
import subprocess

import yaml


# 기본값 상수
DEFAULT_MERGE_PATTERNS = [
    "into 'develop'",
    "into 'app-develop'",
    "into 'main'",
    "into 'master'",
]

DEFAULT_EXCLUDE_FILES = [
    "*.freezed.dart",
    "*.g.dart",
    "*.generated.*",
    "*.min.js",
    "*.min.css",
]


def load_config(config_path):
    """
    YAML 설정 파일을 로드하고, 누락된 항목을 자동 감지로 채움

    Returns:
        dict: 완성된 설정 딕셔너리
    """
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # 필수 항목 검증
    project = cfg.get("project", {})
    repo_path = project.get("repo_path", "")
    if not repo_path:
        raise ValueError("설정 파일에 project.repo_path 가 필요합니다")
    if not os.path.isdir(repo_path):
        raise ValueError(f"repo_path가 존재하지 않습니다: {repo_path}")

    # Git 저장소인지 확인
    git_dir = os.path.join(repo_path, ".git")
    if not os.path.isdir(git_dir):
        raise ValueError(f"Git 저장소가 아닙니다: {repo_path}")

    cfg["project"] = project
    cfg["project"].setdefault("name", os.path.basename(repo_path))

    # target_dirs 기본값
    cfg.setdefault("target_dirs", [])
    if not cfg["target_dirs"]:
        cfg["target_dirs"] = [""]

    # period 기본값 (CLI에서 오버라이드 가능)
    cfg.setdefault("period", {})

    # members 자동 감지
    if not cfg.get("members"):
        cfg["members"] = _auto_detect_members(
            repo_path,
            cfg["target_dirs"],
            cfg.get("exclude_members", []),
        )
        print(f"  ▶ members 자동 감지: {len(cfg['members'])}명")

    # modules 자동 감지
    if not cfg.get("modules"):
        cfg["modules"] = _auto_detect_modules(
            repo_path,
            cfg["target_dirs"],
        )
        print(f"  ▶ modules 자동 감지: {len(cfg['modules'])}개")

    # git_platform 자동 감지
    if not cfg.get("git_platform"):
        cfg["git_platform"] = _auto_detect_platform(repo_path)
        ptype = cfg["git_platform"].get("type", "unknown")
        print(f"  ▶ git_platform 자동 감지: {ptype}")

    # 분석 대상 브랜치 (미지정 시 자동 감지)
    if not project.get("branch"):
        cfg["project"]["branch"] = _auto_detect_branch(repo_path)
        print(f"  ▶ 분석 브랜치 자동 감지: {cfg['project']['branch']}")

    # 기본값 적용
    cfg.setdefault("merge_patterns", DEFAULT_MERGE_PATTERNS)
    cfg.setdefault("exclude_files", DEFAULT_EXCLUDE_FILES)
    cfg.setdefault("exclude_members", [])
    cfg.setdefault("commit_classification", {})
    cfg.setdefault("scoring_weights", {})
    cfg.setdefault("output", {"dir": "output", "dashboard": True})

    return cfg


def _run_git(args, cwd):
    """간단한 git 명령 실행"""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, cwd=cwd,
    )
    return result.stdout.strip()


def _auto_detect_members(repo_path, target_dirs, exclude_patterns):
    """git log에서 기여자 자동 추출"""
    seen = {}
    for td in target_dirs:
        args = ["log", "--format=%aN|%aE", "--", td] if td else ["log", "--format=%aN|%aE"]
        out = _run_git(args, repo_path)
        for line in out.splitlines():
            parts = line.strip().split("|", 1)
            if len(parts) == 2:
                name, email = parts
                # 제외 패턴 확인
                excluded = any(ep in email for ep in exclude_patterns)
                if not excluded and email not in seen:
                    seen[email] = name

    members = []
    for email, name in seen.items():
        members.append({
            "name": name,
            "git_pattern": email,
            "git_platform_user": email.split("@")[0] if "@" in email else email,
        })
    return members


_MODULE_EXCLUDE_DIRS = {
    # 공통
    ".git", "__pycache__", ".vscode", ".idea",
    # FE / Node
    "node_modules", ".next", "dist", "build", ".cache", "coverage",
    ".husky", ".turbo", ".storybook", ".yarn", ".pnp",
    # iOS
    "Pods", "fastlane", "docs",
    # Android
    "gradle", ".gradle",
}

_MODULE_EXCLUDE_SUFFIXES = (
    ".xcodeproj", ".xcworkspace", ".bundle", ".framework",
    ".app", ".build",
)


def _auto_detect_modules(repo_path, target_dirs):
    """target_dirs 하위 1-depth 디렉토리 스캔 (비어있으면 repo 루트 기준)

    path 규칙:
      - target_dirs가 있으면: target_dir 기준 상대 경로 (git_collector에서 target_dir + path로 조합)
      - target_dirs가 비어있으면: repo 루트 기준 전체 상대 경로 (git_collector에서 "" + path로 조합)
    """
    scan_entries = []  # (scan_root, path_prefix)
    has_real_target = False
    for td in target_dirs:
        if td:
            has_real_target = True
            # target_dir 하위 스캔 → path에 target_dir 접두어 불필요 (git_collector가 붙임)
            scan_entries.append((os.path.join(repo_path, td), ""))

    # target_dirs가 비어있거나 ['']이면 repo 루트를 기준으로 스캔
    if not has_real_target:
        src_path = os.path.join(repo_path, "src")
        if os.path.isdir(src_path):
            # src/ 하위 스캔 → path에 "src/" 접두어 필요 (target_dir이 ""이므로)
            scan_entries.append((src_path, "src/"))
        else:
            scan_entries.append((repo_path, ""))

    modules = []
    seen = set()
    for root, prefix in scan_entries:
        if not os.path.isdir(root):
            continue
        for item in sorted(os.listdir(root)):
            if item.startswith("."):
                continue
            if item in _MODULE_EXCLUDE_DIRS:
                continue
            if any(item.endswith(s) for s in _MODULE_EXCLUDE_SUFFIXES):
                continue
            sub_path = os.path.join(root, item)
            if os.path.isdir(sub_path) and item not in seen:
                seen.add(item)
                modules.append({"path": f"{prefix}{item}", "name": item})
    return modules


def _auto_detect_branch(repo_path):
    """기본 브랜치 자동 감지 (master/main/develop 순서)"""
    # origin/HEAD 확인
    head_ref = _run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], repo_path)
    if head_ref:
        return head_ref.replace("refs/remotes/origin/", "")

    # 브랜치 목록에서 탐색
    branches = _run_git(["branch", "-r"], repo_path)
    for candidate in ["master", "main", "develop", "app-develop"]:
        if f"origin/{candidate}" in branches:
            return candidate

    return "HEAD"


def _auto_detect_platform(repo_path):
    """git remote -v 에서 GitLab/GitHub 자동 감지"""
    out = _run_git(["remote", "-v"], repo_path)
    platform = {"type": "unknown", "url": "", "project": ""}

    for line in out.splitlines():
        if "(fetch)" not in line:
            continue

        url = line.split()[1] if len(line.split()) >= 2 else ""

        if "github.com" in url:
            platform["type"] = "github"
        elif "gitlab" in url.lower() or "git." in url.lower():
            platform["type"] = "gitlab"

        # URL에서 프로젝트 경로 추출
        # SSH: git@host:group/project.git
        # HTTPS: https://host/group/project.git
        ssh_match = re.search(r"[:\s]([^/]+/[^/]+?)(?:\.git)?$", url)
        https_match = re.search(r"https?://[^/]+/(.+?)(?:\.git)?$", url)

        if https_match:
            platform["project"] = https_match.group(1)
            platform["url"] = re.match(r"(https?://[^/]+)", url).group(1)
        elif ssh_match:
            platform["project"] = ssh_match.group(1)
            host_match = re.search(r"@([^:]+):", url)
            if host_match:
                platform["url"] = f"https://{host_match.group(1)}"

        break

    return platform


def generate_init_config(repo_path, output_path=None):
    """
    repo를 스캔하여 YAML 설정 초안을 생성

    Args:
        repo_path: Git 저장소 절대 경로
        output_path: 출력 YAML 경로 (None이면 stdout)

    Returns:
        dict: 생성된 설정
    """
    repo_path = os.path.abspath(repo_path)
    print(f"  ▶ 대상 저장소: {repo_path}")

    # 기본 구조
    cfg = {
        "project": {
            "name": os.path.basename(repo_path),
            "repo_path": repo_path,
        },
        "target_dirs": [""],
        "period": {
            "since": None,
            "until": None,
        },
    }

    # 첫 커밋 날짜
    first_date = _run_git(
        ["log", "--reverse", "--format=%ai", "--max-count=1"],
        repo_path,
    )
    if first_date:
        cfg["period"]["since"] = first_date[:10]
    cfg["period"]["until"] = None

    # members 자동 감지
    cfg["members"] = _auto_detect_members(repo_path, [""], [])
    print(f"  ▶ {len(cfg['members'])}명 기여자 감지")

    # git_platform 감지
    cfg["git_platform"] = _auto_detect_platform(repo_path)
    print(f"  ▶ 플랫폼: {cfg['git_platform']['type']}")

    # 기본 설정
    cfg["merge_patterns"] = DEFAULT_MERGE_PATTERNS
    cfg["exclude_files"] = DEFAULT_EXCLUDE_FILES
    cfg["exclude_members"] = []
    cfg["output"] = {"dir": "output", "dashboard": True}

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(
                cfg, f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
        print(f"  ▶ 설정 파일 생성: {output_path}")
        print(f"  ▶ members, target_dirs, exclude_members 등을 수정한 후 collect 를 실행하세요")

    return cfg
