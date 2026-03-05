"""
크로스 프로젝트 종합 대시보드 생성

여러 프로젝트의 CSV 결과를 읽어 개발자별 전체 기여도를 통합 표시
"""

import csv
import json
import os
from collections import defaultdict

from jinja2 import Environment, FileSystemLoader

from contrib_analyzer.collectors import print_progress


def generate_summary_dashboard(output_base_dir, period_label=None):
    """
    output_base_dir 하위의 프로젝트별 CSV를 모두 읽어 종합 대시보드 생성

    Args:
        output_base_dir: output 루트 (예: "output")
        period_label: 특정 기간 라벨 (None이면 각 프로젝트의 최신 디렉토리 사용)
    """
    template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("summary_dashboard.html")

    # 프로젝트 디렉토리 스캔
    projects = []
    for project_id in sorted(os.listdir(output_base_dir)):
        project_dir = os.path.join(output_base_dir, project_id)
        if not os.path.isdir(project_dir):
            continue

        # 기간 디렉토리 찾기
        if period_label:
            data_dir = os.path.join(project_dir, period_label)
        else:
            # 최신 디렉토리 사용
            subdirs = [
                d for d in sorted(os.listdir(project_dir))
                if os.path.isdir(os.path.join(project_dir, d))
            ]
            if not subdirs:
                continue
            data_dir = os.path.join(project_dir, subdirs[-1])
            period_label_used = subdirs[-1]

        summary_csv = os.path.join(data_dir, "contribution_summary.csv")
        if not os.path.exists(summary_csv):
            continue

        members = _read_summary(data_dir)
        cv_data = _read_commit_value_summary(data_dir)
        label = period_label or period_label_used

        # 프로젝트별 대시보드 상대 경로 (summary_dashboard.html 기준)
        dashboard_path = os.path.join(project_id, label, "dashboard.html")
        has_dashboard = os.path.exists(os.path.join(output_base_dir, dashboard_path))

        projects.append({
            "id": project_id,
            "period": label,
            "members": members,
            "cv_data": cv_data,
            "dashboard_link": dashboard_path if has_dashboard else None,
        })

    if not projects:
        print_progress("종합 대시보드: 분석 데이터가 없습니다")
        return

    # 개발자별 전체 프로젝트 통합
    all_members = _merge_members(projects)
    all_cv = _merge_cv_data(projects)

    # 프로젝트별 멤버 기여 매트릭스
    project_matrix = _build_project_matrix(projects)

    used_label = period_label or projects[0]["period"]

    # 프로젝트 링크 목록
    project_links = [
        {"id": p["id"], "period": p["period"], "link": p["dashboard_link"]}
        for p in projects
    ]

    html = template.render(
        period_label=used_label,
        project_count=len(projects),
        project_names=json.dumps([p["id"] for p in projects], ensure_ascii=False),
        member_count=len(all_members),
        members_json=json.dumps(all_members, ensure_ascii=False),
        cv_json=json.dumps(all_cv, ensure_ascii=False),
        project_matrix_json=json.dumps(project_matrix, ensure_ascii=False),
        project_links_json=json.dumps(project_links, ensure_ascii=False),
        has_cv=len(all_cv) > 0,
    )

    output_path = os.path.join(output_base_dir, "summary_dashboard.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print_progress(f"종합 대시보드 생성: {output_path}")


def _read_csv(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _safe_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _read_summary(data_dir):
    rows = _read_csv(os.path.join(data_dir, "contribution_summary.csv"))
    result = []
    for r in rows:
        result.append({
            "name": r.get("이름", ""),
            "totalCommits": _safe_int(r.get("전체커밋")),
            "codingCommits": _safe_int(r.get("코딩커밋")),
            "added": _safe_int(r.get("추가라인")),
            "deleted": _safe_int(r.get("삭제라인")),
            "net": _safe_int(r.get("순기여")),
            "selfMR": _safe_int(r.get("본인MR머지")),
            "blame": _safe_int(r.get("blame라인수")),
            "glReviewComments": _safe_int(r.get("리뷰코멘트작성수")),
            "glApprovals": _safe_int(r.get("MR승인수")),
        })
    return result


def _read_commit_value_summary(data_dir):
    rows = _read_csv(os.path.join(data_dir, "contribution_commit_value_summary.csv"))
    result = []
    for r in rows:
        result.append({
            "name": r.get("이름", ""),
            "total": _safe_int(r.get("총커밋")),
            "S": _safe_int(r.get("S등급")),
            "A": _safe_int(r.get("A등급")),
            "avgScore": _safe_float(r.get("평균점수")),
            "valueSum": _safe_int(r.get("가치합산")),
        })
    return result


def _merge_members(projects):
    """개발자별 전체 프로젝트 합산"""
    merged = defaultdict(lambda: {
        "name": "", "totalCommits": 0, "codingCommits": 0,
        "added": 0, "deleted": 0, "net": 0, "selfMR": 0, "blame": 0,
        "glReviewComments": 0, "glApprovals": 0, "projectCount": 0,
    })
    for p in projects:
        for m in p["members"]:
            name = m["name"]
            merged[name]["name"] = name
            for key in ["totalCommits", "codingCommits", "added", "deleted",
                        "net", "selfMR", "blame", "glReviewComments", "glApprovals"]:
                merged[name][key] += m.get(key, 0)
            merged[name]["projectCount"] += 1

    return sorted(merged.values(), key=lambda x: x["totalCommits"], reverse=True)


def _merge_cv_data(projects):
    """개발자별 커밋 가치 합산"""
    merged = defaultdict(lambda: {
        "name": "", "total": 0, "S": 0, "A": 0,
        "valueSum": 0, "scoreWeighted": 0,
    })
    for p in projects:
        for cv in p["cv_data"]:
            name = cv["name"]
            merged[name]["name"] = name
            merged[name]["total"] += cv["total"]
            merged[name]["S"] += cv["S"]
            merged[name]["A"] += cv["A"]
            merged[name]["valueSum"] += cv["valueSum"]
            merged[name]["scoreWeighted"] += cv["avgScore"] * cv["total"]

    result = []
    for v in merged.values():
        v["avgScore"] = round(v["scoreWeighted"] / v["total"], 1) if v["total"] > 0 else 0
        del v["scoreWeighted"]
        v["criticalPct"] = round((v["S"] + v["A"]) / v["total"] * 100, 1) if v["total"] > 0 else 0
        result.append(v)

    return sorted(result, key=lambda x: x["valueSum"], reverse=True)


def _build_project_matrix(projects):
    """프로젝트 x 멤버 커밋 수 매트릭스"""
    all_names = set()
    for p in projects:
        for m in p["members"]:
            all_names.add(m["name"])

    matrix = {}
    for name in sorted(all_names):
        matrix[name] = {}
        for p in projects:
            commits = 0
            for m in p["members"]:
                if m["name"] == name:
                    commits = m["totalCommits"]
                    break
            matrix[name][p["id"]] = commits

    return matrix
