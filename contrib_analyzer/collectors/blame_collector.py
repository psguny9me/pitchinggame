"""
Git Blame 분석 (B섹션)

특정 시점의 코드 소유권 분석
"""

from collections import defaultdict
from contrib_analyzer.collectors import run_git, print_progress


def collect_blame(repo_path, members, target_dirs, exclude_files, until,
                  branch="HEAD"):
    """
    Git Blame 기반 코드 소유권 분석 (지정 브랜치 기준)

    Returns:
        dict: {
            "members": {name: {"blame": N, "blame_pct": X.X}},
            "total_lines": int,
        }
    """
    target_dir = target_dirs[0] if target_dirs else ""
    path_args = ["--", target_dir] if target_dir else []

    # 대상 커밋 찾기 (지정 브랜치에서)
    target_commit = run_git(
        ["rev-list", "-1", f"--before={until}", branch],
        cwd=repo_path,
    )
    if not target_commit:
        print_progress("대상 커밋을 찾을 수 없습니다")
        return {"members": {}, "total_lines": 0}

    print_progress(f"대상 커밋: {target_commit[:12]}")

    # 파일 목록 수집 (자동생성 파일 제외)
    out = run_git(
        ["ls-tree", "-r", "--name-only", target_commit] + path_args,
        cwd=repo_path,
    )

    all_files = []
    for f in out.splitlines():
        excluded = False
        for pattern in exclude_files:
            # 간단한 glob 매칭: *.freezed.dart -> endswith('.freezed.dart')
            clean = pattern.lstrip("*")
            if f.endswith(clean):
                excluded = True
                break
        if not excluded and f.strip():
            all_files.append(f)

    print_progress(f"대상 파일: {len(all_files)}개")

    # blame 실행
    print_progress("git blame 실행 중...")
    blame_counts = defaultdict(int)
    total_blame = 0

    for i, filepath in enumerate(all_files):
        if (i + 1) % 50 == 0:
            print(f"    ... {i + 1} / {len(all_files)} 파일 처리 중")

        out = run_git(
            ["blame", "--line-porcelain", target_commit, "--", filepath],
            cwd=repo_path,
        )
        for line in out.splitlines():
            if line.startswith("author-mail"):
                email_val = (
                    line.split("<")[-1].rstrip(">").strip()
                    if "<" in line else ""
                )
                blame_counts[email_val] += 1
                total_blame += 1

    print_progress(f"전체 라인 수: {total_blame}")

    # 멤버별 blame 집계
    member_blame = {}
    for m in members:
        name = m["name"]
        pattern = m["git_pattern"]
        blame_lines = 0

        if "@" in pattern:
            blame_lines = blame_counts.get(pattern, 0)
        else:
            for email_key, count in blame_counts.items():
                if pattern in email_key:
                    blame_lines += count

        pct = round(blame_lines / total_blame * 100, 1) if total_blame > 0 else 0
        member_blame[name] = {"blame": blame_lines, "blame_pct": pct}
        print(f"    {name}: {blame_lines} 라인 ({pct}%)")

    return {
        "members": member_blame,
        "total_lines": total_blame,
    }
