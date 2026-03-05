"""
Git 기반 지표 수집 (A섹션)

커밋 수, 추가/삭제 라인, MR 머지, 모듈별 기여, 월별 추이 등
"""

from collections import defaultdict
from contrib_analyzer.collectors import run_git, count_lines, print_progress


def collect_git_metrics(repo_path, members, target_dirs, modules,
                        merge_patterns, since, until, branch="HEAD"):
    """
    Git 기반 지표 수집 (지정 브랜치에 머지된 커밋만 분석)

    Returns:
        dict: {
            "members": {name: {...metrics}},
            "monthly": [{"name", "month", "count"}],
            "modules": [{"name", "module", "count"}],
        }
    """
    results = {}
    monthly_data = []
    module_data = []

    target_dir = target_dirs[0] if target_dirs else ""
    # 빈 pathspec은 git에서 오류를 발생시키므로, 비어있으면 생략
    path_args = ["--", target_dir] if target_dir else []

    print_progress(f"분석 브랜치: {branch}")

    for m in members:
        name = m["name"]
        email = m["git_pattern"]
        print_progress(f"{name} 분석 중...")

        r = {}

        # 공통 인자: 브랜치 + 기간
        since_args = [f"--since={since}"] if since else []
        base_args = [f"--author={email}", f"--until={until}"] + since_args

        # 전체 커밋 수
        out = run_git(
            ["log"] + base_args + ["--oneline", branch, ] + path_args,
            cwd=repo_path,
        )
        r["total_commits"] = count_lines(out)

        # 순수 코딩 커밋
        out = run_git(
            ["log", "--no-merges"] + base_args + ["--oneline", branch, ] + path_args,
            cwd=repo_path,
        )
        r["coding_commits"] = count_lines(out)

        # 추가/삭제 라인
        out = run_git(
            ["log"] + base_args + ["--numstat", "--format=", branch, ] + path_args,
            cwd=repo_path,
        )
        added, deleted = 0, 0
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                try:
                    added += int(parts[0])
                    deleted += int(parts[1])
                except ValueError:
                    pass
        r["added"] = added
        r["deleted"] = deleted
        r["net"] = added - deleted

        # 본인 MR 머지
        out = run_git(
            ["log", "--merges"] + base_args + ["--format=%s", branch, ] + path_args,
            cwd=repo_path,
        )
        merge_subjects = [
            line for line in out.splitlines()
            if any(mp in line for mp in merge_patterns)
        ]
        r["self_mr"] = len(merge_subjects)

        # feature / fix 분류
        r["feature_mr"] = sum(
            1 for s in merge_subjects
            if "feature/" in s.lower() or "feat/" in s.lower()
        )
        r["fix_mr"] = sum(
            1 for s in merge_subjects
            if "fix/" in s.lower() or "bugfix/" in s.lower() or "hotfix/" in s.lower()
        )
        r["fix_ratio"] = round(r["fix_mr"] / r["self_mr"] * 100, 1) if r["self_mr"] > 0 else 0

        # Revert 건수
        out = run_git(
            ["log"] + base_args + ["--format=%s", branch, ] + path_args,
            cwd=repo_path,
        )
        r["revert"] = sum(1 for l in out.splitlines() if "revert" in l.lower())

        # 평균 커밋 크기
        if r["coding_commits"] > 0:
            out = run_git(
                ["log", "--no-merges"] + base_args + ["--numstat", "--format=", branch, ] + path_args,
                cwd=repo_path,
            )
            total_changes = 0
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        total_changes += int(parts[0]) + int(parts[1])
                    except ValueError:
                        pass
            r["avg_commit_size"] = total_changes // r["coding_commits"]
        else:
            r["avg_commit_size"] = 0

        # 타인 MR 머지 (committer로 조회)
        committer_args = [f"--committer={email}", f"--until={until}"] + since_args
        out = run_git(
            ["log", "--merges"] + committer_args + ["--format=%s", branch, ] + path_args,
            cwd=repo_path,
        )
        r["reviewer_mr"] = sum(
            1 for l in out.splitlines()
            if any(mp in l for mp in merge_patterns)
        )

        # 프레젠테이션 집중도
        out_all = run_git(
            ["log"] + base_args + ["--oneline", branch],
            cwd=repo_path,
        )
        total_all = count_lines(out_all)
        r["focus"] = round(
            r["total_commits"] / total_all * 100, 1
        ) if total_all > 0 else 0

        # 월별 커밋 추이
        out = run_git(
            ["log"] + base_args + ["--format=%ai", branch, ] + path_args,
            cwd=repo_path,
        )
        month_counts = defaultdict(int)
        for line in out.splitlines():
            if line.strip():
                month_counts[line[:7]] += 1
        for month, count in sorted(month_counts.items()):
            monthly_data.append({"name": name, "month": month, "count": count})

        # 모듈별 기여
        if modules:
            for mod in modules:
                mod_path = mod.get("path", mod.get("name", ""))
                mod_name = mod.get("name", mod_path)
                mod_count = 0

                for prefix in [f"{target_dir}screen/{mod_path}/", f"{target_dir}{mod_path}/"]:
                    out = run_git(
                        ["log"] + base_args + ["--oneline", branch, "--", prefix],
                        cwd=repo_path,
                    )
                    mod_count += count_lines(out)

                if mod_count > 0:
                    module_data.append({
                        "name": name, "module": mod_name, "count": mod_count,
                    })

        results[name] = r
        print(f"    ✓ {name} 완료 (커밋: {r['total_commits']}, 순기여: {r['net']}줄)")

    return {
        "members": results,
        "monthly": monthly_data,
        "modules": module_data,
    }
