"""
CSV 출력 모듈

수집된 데이터를 CSV 파일로 출력합니다:
  1. contribution_summary.csv              - 종합 요약
  2. contribution_monthly.csv              - 월별 추이
  3. contribution_modules.csv              - 모듈별 기여
  4. contribution_quality.csv              - MR 품질 (GitLab/GitHub)
  5. contribution_commit_values.csv        - 커밋별 가치 평가
  6. contribution_commit_value_summary.csv - 작성자별 가치 집계
  7. contribution_slack.csv                - Slack 커뮤니케이션 활동
"""

import csv
import os

from contrib_analyzer.collectors import print_progress


def write_all_csvs(cfg, all_results, output_dir):
    """
    전체 수집 결과를 CSV로 출력

    Args:
        cfg: 설정 딕셔너리
        all_results: cli._run_collect()에서 생성된 전체 결과
        output_dir: 출력 디렉토리 경로
    """
    os.makedirs(output_dir, exist_ok=True)

    members = cfg["members"]
    git_data = all_results.get("git", {})
    blame_data = all_results.get("blame")
    platform_data = all_results.get("platform")
    commit_values = all_results.get("commit_values")
    commit_agg = all_results.get("commit_agg")
    slack_data = all_results.get("slack")

    git_members = git_data.get("members", {})
    monthly_data = git_data.get("monthly", [])
    module_data = git_data.get("modules", [])

    files_written = []

    # 1. Summary CSV
    summary_path = os.path.join(output_dir, "contribution_summary.csv")
    with open(summary_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "이름", "전체커밋", "코딩커밋", "추가라인", "삭제라인", "순기여",
            "본인MR머지", "featureMR", "fixMR", "fix비율(%)",
            "평균커밋크기", "revert건수", "타인MR머지_리뷰",
            "프레젠테이션집중도(%)", "blame라인수", "blame비율(%)",
            "리뷰코멘트작성수", "MR승인수", "리뷰한MR수",
            "MR받은코멘트수", "CI실패율(%)",
        ])
        for m in members:
            name = m["name"]
            r = git_members.get(name, {})

            # blame 데이터 병합
            blame_member = {}
            if blame_data and blame_data.get("members"):
                blame_member = blame_data["members"].get(name, {})

            # platform 데이터 병합
            platform_member = {}
            if platform_data and platform_data.get("members"):
                platform_member = platform_data["members"].get(name, {})

            writer.writerow([
                name,
                r.get("total_commits", 0), r.get("coding_commits", 0),
                r.get("added", 0), r.get("deleted", 0), r.get("net", 0),
                r.get("self_mr", 0), r.get("feature_mr", 0),
                r.get("fix_mr", 0), r.get("fix_ratio", 0),
                r.get("avg_commit_size", 0), r.get("revert", 0),
                r.get("reviewer_mr", 0), r.get("focus", 0),
                blame_member.get("blame", 0),
                blame_member.get("blame_pct", 0),
                platform_member.get("gl_review_comments", "-"),
                platform_member.get("gl_approvals", "-"),
                platform_member.get("gl_reviewed_mrs", "-"),
                platform_member.get("gl_received_comments", "-"),
                platform_member.get("gl_ci_fail_rate", "-"),
            ])
    files_written.append(summary_path)

    # 2. Monthly CSV
    monthly_path = os.path.join(output_dir, "contribution_monthly.csv")
    with open(monthly_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["이름", "월", "커밋수"])
        for row in monthly_data:
            writer.writerow([row["name"], row["month"], row["count"]])
    files_written.append(monthly_path)

    # 3. Modules CSV
    modules_path = os.path.join(output_dir, "contribution_modules.csv")
    with open(modules_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["이름", "모듈", "커밋수"])
        for row in module_data:
            writer.writerow([row["name"], row["module"], row["count"]])
    files_written.append(modules_path)

    # 4. Quality CSV
    quality_path = os.path.join(output_dir, "contribution_quality.csv")
    quality_data = platform_data.get("quality", []) if platform_data else []
    with open(quality_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["이름", "MR_IID", "MR제목", "받은코멘트수", "승인자수", "CI결과"])
        for row in quality_data:
            writer.writerow([
                row["name"], row["iid"], row["title"],
                row["comments"], row["approvers"], row["ci"],
            ])
    files_written.append(quality_path)

    # 5. Commit Values CSV
    if commit_values:
        member_name_map = {m["git_pattern"]: m["name"] for m in members}
        cv_path = os.path.join(output_dir, "contribution_commit_values.csv")
        with open(cv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "해시", "작성자", "메시지", "날짜",
                "변경라인", "파일수",
                "파일핵심도", "변경고유율", "변경유형", "메시지시그널", "영향범위",
                "가치점수", "등급",
            ])
            for cv in commit_values:
                display_name = cv["author_name"]
                for pattern, name in member_name_map.items():
                    if pattern in cv["author_email"]:
                        display_name = name
                        break

                msg_clean = cv["message"].replace(",", " ")[:100]
                writer.writerow([
                    cv["hash"], display_name, msg_clean,
                    cv.get("date", "")[:10],
                    cv["total_lines"], cv["file_count"],
                    cv["file_criticality"], cv["change_uniqueness"],
                    cv["change_type"], cv["message_signal"], cv["impact_scope"],
                    cv["value_score"], cv["grade"],
                ])
        files_written.append(cv_path)

    # 6. Commit Value Summary CSV
    if commit_agg:
        cvs_path = os.path.join(output_dir, "contribution_commit_value_summary.csv")
        with open(cvs_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "이름", "총커밋", "S등급", "A등급", "B등급", "C등급", "D등급",
                "평균점수", "가치합산", "핵심커밋비율(%)",
            ])
            for m in members:
                name = m["name"]
                if name in commit_agg:
                    agg = commit_agg[name]
                    writer.writerow([
                        name, agg["총커밋"],
                        agg["S"], agg["A"], agg["B"], agg["C"], agg["D"],
                        agg["평균점수"], agg["가치합산"], agg["핵심커밋비율"],
                    ])
        files_written.append(cvs_path)

    # 7. Slack CSV
    if slack_data and slack_data.get("members"):
        slack_path = os.path.join(output_dir, "contribution_slack.csv")
        with open(slack_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "이름", "메시지수", "스레드시작", "스레드답변",
                "타인스레드답변", "코드공유수",
                "받은리액션", "리액션준사람수",
                "평균응답시간(분)", "중앙값응답시간(분)",
            ])
            slack_members = slack_data["members"]
            for m in members:
                name = m["name"]
                sm = slack_members.get(name, {})
                writer.writerow([
                    name,
                    sm.get("messages", 0),
                    sm.get("thread_starts", 0),
                    sm.get("thread_replies", 0),
                    sm.get("help_replies", 0),
                    sm.get("code_shares", 0),
                    sm.get("reactions_received", 0),
                    sm.get("unique_reactors", 0),
                    sm.get("avg_response_min", 0),
                    sm.get("median_response_min", 0),
                ])
        files_written.append(slack_path)

    print_progress("생성된 CSV 파일:")
    for fp in files_written:
        print(f"    {fp}")
