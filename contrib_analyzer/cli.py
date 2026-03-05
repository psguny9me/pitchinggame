"""
CLI 진입점 - 3단계 워크플로우

서브커맨드:
  init      - 대상 repo 스캔 → YAML 설정 초안 생성
  collect   - 설정 + 기간으로 Git/API 분석 → CSV 출력
  dashboard - 기존 CSV → HTML 대시보드 생성
  run       - collect + dashboard 한번에 실행
"""

import argparse
import os
import sys

from contrib_analyzer.collectors import print_header


def main():
    parser = argparse.ArgumentParser(
        prog="contrib-analyzer",
        description="Git 프로젝트 기여도 분석 도구",
    )
    subparsers = parser.add_subparsers(dest="command", help="실행할 명령")

    # ── init ───────────────────────────────────────────────────────
    p_init = subparsers.add_parser("init", help="설정 파일 초기화")
    p_init.add_argument(
        "--repo", required=True,
        help="분석 대상 Git 저장소 경로",
    )
    p_init.add_argument(
        "--output", default="configs/project.yaml",
        help="생성할 설정 파일 경로 (기본: configs/project.yaml)",
    )

    # ── collect ────────────────────────────────────────────────────
    p_collect = subparsers.add_parser("collect", help="데이터 수집")
    p_collect.add_argument("--config", required=True, help="설정 파일 경로")
    p_collect.add_argument(
        "--period",
        choices=["weekly", "monthly", "quarterly", "half", "custom"],
        default=None,
        help="기간 프리셋 (미지정 시 설정 파일의 period 사용)",
    )
    p_collect.add_argument("--since", default=None, help="시작일 (custom 모드)")
    p_collect.add_argument("--until", default=None, help="종료일 (custom 모드)")
    p_collect.add_argument("--reference", default=None, help="기준일 (YYYY-MM-DD)")
    p_collect.add_argument(
        "--skip-api", action="store_true",
        help="GitLab/GitHub API 수집 건너뛰기",
    )
    p_collect.add_argument(
        "--skip-blame", action="store_true",
        help="git blame 분석 건너뛰기",
    )
    p_collect.add_argument(
        "--skip-classify", action="store_true",
        help="커밋 가치 평가 건너뛰기",
    )
    p_collect.add_argument(
        "--skip-slack", action="store_true",
        help="Slack 분석 건너뛰기",
    )

    # ── dashboard ──────────────────────────────────────────────────
    p_dash = subparsers.add_parser("dashboard", help="대시보드 생성")
    p_dash.add_argument("--config", required=True, help="설정 파일 경로")
    p_dash.add_argument("--data-dir", default=None, help="CSV 데이터 디렉토리")

    # ── run ─────────────────────────────────────────────────────────
    p_run = subparsers.add_parser("run", help="수집 + 대시보드 한번에 실행")
    p_run.add_argument("--config", required=True, help="설정 파일 경로")
    p_run.add_argument(
        "--period",
        choices=["weekly", "monthly", "quarterly", "half", "custom"],
        default=None,
    )
    p_run.add_argument("--since", default=None)
    p_run.add_argument("--until", default=None)
    p_run.add_argument("--reference", default=None)
    p_run.add_argument("--skip-api", action="store_true")
    p_run.add_argument("--skip-blame", action="store_true")
    p_run.add_argument("--skip-classify", action="store_true")
    p_run.add_argument("--skip-slack", action="store_true")

    # ── summary ─────────────────────────────────────────────────────
    p_summary = subparsers.add_parser("summary", help="크로스 프로젝트 종합 대시보드 생성")
    p_summary.add_argument(
        "--output-dir", default="output",
        help="프로젝트별 출력이 있는 루트 디렉토리 (기본: output)",
    )
    p_summary.add_argument(
        "--period-label", default=None,
        help="특정 기간 라벨 (미지정 시 각 프로젝트의 최신 사용)",
    )

    # ── run-all ──────────────────────────────────────────────────────
    p_all = subparsers.add_parser("run-all", help="configs 디렉토리의 모든 프로젝트 일괄 실행")
    p_all.add_argument(
        "--configs-dir", default="configs",
        help="설정 파일 디렉토리 (기본: configs)",
    )
    p_all.add_argument(
        "--period",
        choices=["weekly", "monthly", "quarterly", "half", "custom"],
        default=None,
    )
    p_all.add_argument("--since", default=None)
    p_all.add_argument("--until", default=None)
    p_all.add_argument("--reference", default=None)
    p_all.add_argument("--skip-api", action="store_true")
    p_all.add_argument("--skip-blame", action="store_true")
    p_all.add_argument("--skip-classify", action="store_true")
    p_all.add_argument("--skip-slack", action="store_true")

    # ── person ──────────────────────────────────────────────────────
    p_person = subparsers.add_parser("person", help="개인 단위 기여도 대시보드 생성")
    p_person.add_argument(
        "--output-dir", default="output",
        help="프로젝트별 출력이 있는 루트 디렉토리 (기본: output)",
    )
    p_person.add_argument(
        "--service-groups", default="configs/service_groups.yaml",
        help="서비스 그룹 매핑 파일 (기본: configs/service_groups.yaml)",
    )
    p_person.add_argument(
        "--period-label", default=None,
        help="특정 기간 라벨 (미지정 시 각 프로젝트의 최신 사용)",
    )
    p_person.add_argument(
        "--name", default=None,
        help="특정 인물만 생성 (미지정 시 전체)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "init":
        cmd_init(args)
    elif args.command == "collect":
        cmd_collect(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "summary":
        cmd_summary(args)
    elif args.command == "run-all":
        cmd_run_all(args)
    elif args.command == "person":
        cmd_person(args)


# ── 명령 핸들러 ──────────────────────────────────────────────────────────

def cmd_init(args):
    """대상 repo 스캔 → 설정 파일 생성"""
    from contrib_analyzer.config import generate_init_config

    print_header("대상 설정 (init)")
    repo = os.path.abspath(args.repo)
    generate_init_config(repo, args.output)


def cmd_collect(args):
    """데이터 수집 실행"""
    cfg, since, until, output_dir = _prepare_collect(args)

    print_header(f"데이터 수집 ({since} ~ {until})")
    _run_collect(cfg, since, until, output_dir, args)
    print_header("데이터 수집 완료")
    print(f"  ▶ 출력 디렉토리: {os.path.abspath(output_dir)}")


def cmd_dashboard(args):
    """대시보드 생성"""
    from contrib_analyzer.config import load_config
    from contrib_analyzer.output.dashboard import generate_dashboard

    print_header("대시보드 생성")
    cfg = load_config(args.config)
    if args.data_dir:
        data_dirs = [args.data_dir]
    else:
        base_dir = cfg.get("output", {}).get("dir", "output")
        project_id = os.path.basename(cfg["project"]["repo_path"].rstrip("/"))
        project_dir = os.path.join(base_dir, project_id)
        # 기간 하위 폴더들을 찾아서 각각 대시보드 생성
        data_dirs = []
        if os.path.isdir(project_dir):
            for entry in sorted(os.listdir(project_dir)):
                sub = os.path.join(project_dir, entry)
                if os.path.isdir(sub) and os.path.exists(os.path.join(sub, "contribution_summary.csv")):
                    data_dirs.append(sub)
        if not data_dirs:
            data_dirs = [project_dir]
    for data_dir in data_dirs:
        generate_dashboard(cfg, data_dir)


def cmd_summary(args):
    """크로스 프로젝트 종합 대시보드 생성"""
    from contrib_analyzer.output.summary_dashboard import generate_summary_dashboard

    print_header("크로스 프로젝트 종합 대시보드")
    generate_summary_dashboard(args.output_dir, args.period_label)


def cmd_person(args):
    """개인 단위 기여도 대시보드 생성"""
    from contrib_analyzer.output.person_dashboard import generate_person_dashboards

    print_header("개인 단위 기여도 대시보드")
    generate_person_dashboards(
        args.output_dir,
        service_groups_path=args.service_groups,
        period_label=args.period_label,
        target_name=args.name,
    )


def cmd_run(args):
    """수집 + 대시보드 한번에 실행"""
    cfg, since, until, output_dir = _prepare_collect(args)

    print_header(f"전체 실행 ({since} ~ {until})")
    _run_collect(cfg, since, until, output_dir, args)

    from contrib_analyzer.output.dashboard import generate_dashboard
    print_header("대시보드 생성")
    generate_dashboard(cfg, output_dir)

    print_header("전체 실행 완료")
    print(f"  ▶ 출력 디렉토리: {os.path.abspath(output_dir)}")


def cmd_run_all(args):
    """configs 디렉토리의 모든 YAML 설정 파일로 일괄 실행"""
    import glob as glob_mod

    configs_dir = args.configs_dir
    yaml_files = sorted(
        glob_mod.glob(os.path.join(configs_dir, "*.yaml"))
        + glob_mod.glob(os.path.join(configs_dir, "*.yml"))
    )

    if not yaml_files:
        print(f"  ✖ {configs_dir} 디렉토리에 YAML 파일이 없습니다")
        sys.exit(1)

    print_header(f"일괄 실행 ({len(yaml_files)}개 프로젝트)")
    for cfg_path in yaml_files:
        print(f"  ▶ {os.path.basename(cfg_path)}")

    failed = []
    for cfg_path in yaml_files:
        project_name = os.path.splitext(os.path.basename(cfg_path))[0]
        print_header(f"프로젝트: {project_name}")
        try:
            args.config = cfg_path
            cfg, since, until, output_dir = _prepare_collect(args)
            _run_collect(cfg, since, until, output_dir, args)

            from contrib_analyzer.output.dashboard import generate_dashboard
            generate_dashboard(cfg, output_dir)
            print(f"  ✔ 완료: {os.path.abspath(output_dir)}")
        except Exception as e:
            print(f"  ✖ 실패: {e}")
            failed.append(project_name)

    # 종합 대시보드 자동 생성
    from contrib_analyzer.output.summary_dashboard import generate_summary_dashboard
    print_header("크로스 프로젝트 종합 대시보드")
    try:
        base_dir = "output"
        generate_summary_dashboard(base_dir)
    except Exception as e:
        print(f"  ✖ 종합 대시보드 실패: {e}")

    # 개인 대시보드 자동 생성
    from contrib_analyzer.output.person_dashboard import generate_person_dashboards
    print_header("개인 단위 기여도 대시보드")
    try:
        service_groups_path = os.path.join(configs_dir, "service_groups.yaml")
        generate_person_dashboards("output", service_groups_path=service_groups_path)
    except Exception as e:
        print(f"  ✖ 개인 대시보드 실패: {e}")

    print_header("일괄 실행 완료")
    print(f"  ▶ 성공: {len(yaml_files) - len(failed)}개 / 실패: {len(failed)}개")
    if failed:
        print(f"  ▶ 실패 프로젝트: {', '.join(failed)}")


# ── 내부 유틸 ────────────────────────────────────────────────────────────

def _prepare_collect(args):
    """collect / run 공통 준비"""
    from contrib_analyzer.config import load_config
    from contrib_analyzer.period import resolve_period, period_label

    cfg = load_config(args.config)

    # 기간 결정 (CLI --period > config period.preset > config period.since/until)
    period_preset = args.period
    if not period_preset:
        period_preset = cfg.get("period", {}).get("preset")

    if period_preset:
        since, until = resolve_period(
            period_preset,
            reference_date=getattr(args, "reference", None),
            since=getattr(args, "since", None),
            until=getattr(args, "until", None),
        )
        label = period_label(period_preset, since, until)
    else:
        period_cfg = cfg.get("period", {})
        since = period_cfg.get("since")
        until = period_cfg.get("until")
        if not since or not until:
            raise ValueError(
                "--period 를 지정하거나 설정 파일에 period.preset 또는 period.since/until 을 설정하세요"
            )
        label = f"{since}_{until}"

    # 출력 디렉토리 결정 (프로젝트별 분리)
    base_dir = cfg.get("output", {}).get("dir", "output")
    project_id = os.path.basename(cfg["project"]["repo_path"].rstrip("/"))
    output_dir = os.path.join(base_dir, project_id, label)
    os.makedirs(output_dir, exist_ok=True)

    return cfg, since, until, output_dir


def _run_collect(cfg, since, until, output_dir, args):
    """실제 데이터 수집 파이프라인 실행"""
    from contrib_analyzer.collectors.git_collector import collect_git_metrics
    from contrib_analyzer.collectors.blame_collector import collect_blame
    from contrib_analyzer.collectors.platform_api import collect_platform_data
    from contrib_analyzer.collectors.commit_classifier import CommitClassifier
    from contrib_analyzer.output.csv_writer import write_all_csvs
    from contrib_analyzer.collectors import print_header, print_progress

    repo_path = cfg["project"]["repo_path"]
    members = cfg["members"]
    target_dirs = cfg["target_dirs"]
    modules = cfg.get("modules", [])
    merge_patterns = cfg.get("merge_patterns", [])
    exclude_files = cfg.get("exclude_files", [])
    branch = cfg["project"].get("branch", "HEAD")

    # until 날짜를 git log 용으로 +1일
    from datetime import date, timedelta
    until_for_git = (date.fromisoformat(until) + timedelta(days=1)).isoformat()

    all_results = {}

    # A. Git 기반 지표 수집
    print_header("A. Git 기반 지표 수집")
    git_data = collect_git_metrics(
        repo_path, members, target_dirs, modules,
        merge_patterns, since, until_for_git, branch=branch,
    )
    all_results["git"] = git_data

    # B. Git Blame 분석
    if not args.skip_blame:
        print_header("B. Git Blame 분석")
        blame_data = collect_blame(
            repo_path, members, target_dirs, exclude_files, until_for_git,
            branch=branch,
        )
        all_results["blame"] = blame_data
    else:
        print_header("B. Git Blame 분석 (건너뜀)")
        all_results["blame"] = None

    # C. Platform API 분석
    if not args.skip_api:
        print_header("C. Platform API 분석")
        platform_data = collect_platform_data(
            cfg, members, until_for_git,
        )
        all_results["platform"] = platform_data
    else:
        print_header("C. Platform API 분석 (건너뜀)")
        all_results["platform"] = None

    # D. 커밋 가치 평가
    if not args.skip_classify:
        print_header("D. 커밋 가치 다차원 평가")
        classifier = CommitClassifier(
            config=cfg.get("commit_classification", {}).get("value_scoring"),
        )
        member_emails = [m["git_pattern"] for m in members]
        member_name_map = {m["git_pattern"]: m["name"] for m in members}

        print_progress("커밋 수집 중...")
        all_commits = classifier.collect_commits(
            target_dirs[0] if target_dirs else "",
            until_for_git, member_emails,
            since_date=since, cwd=repo_path, branch=branch,
        )
        print_progress(f"{len(all_commits)}개 커밋 수집 완료")

        print_progress("가치 평가 중...")
        def progress_cb(cur, tot):
            print(f"    ... {cur} / {tot} 완료")

        commit_values = classifier.classify_commits(
            all_commits,
            target_dirs[0] if target_dirs else "",
            progress_callback=progress_cb,
            cwd=repo_path,
        )
        author_agg = classifier.aggregate_by_author(commit_values, member_name_map)

        for m in members:
            name = m["name"]
            if name in author_agg:
                a = author_agg[name]
                print(f"    {name}: 평균 {a['평균점수']}점 | "
                      f"S:{a['S']} A:{a['A']} B:{a['B']} C:{a['C']} D:{a['D']}")

        all_results["commit_values"] = commit_values
        all_results["commit_agg"] = author_agg
    else:
        print_header("D. 커밋 가치 평가 (건너뜀)")
        all_results["commit_values"] = None
        all_results["commit_agg"] = None

    # E. Slack 커뮤니케이션 분석
    if not args.skip_slack and cfg.get("slack"):
        print_header("E. Slack 커뮤니케이션 분석")
        from contrib_analyzer.collectors.slack_collector import collect_slack_data
        slack_data = collect_slack_data(cfg, members, since, until)
        all_results["slack"] = slack_data
    else:
        if not args.skip_slack:
            print_header("E. Slack 분석 (설정 없음, 건너뜀)")
        else:
            print_header("E. Slack 분석 (건너뜀)")
        all_results["slack"] = None

    # F. CSV 출력
    print_header("F. CSV 출력")
    write_all_csvs(cfg, all_results, output_dir)
