"""
개인 단위 교차 프로젝트 데이터 집계

모든 프로젝트의 CSV 데이터를 읽어 개인(이름) 기준으로 교차 집계합니다.
"""

import csv
import os
import re
from collections import defaultdict


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


# 커밋 메시지에서 업무 유형 추출
_TYPE_PATTERNS = [
    ("feat", re.compile(r"^(feat|feature|추가|구현|\* feat)", re.IGNORECASE)),
    ("fix", re.compile(r"^(fix|bugfix|hotfix|수정|\* fix)", re.IGNORECASE)),
    ("refactor", re.compile(r"^(refactor|개선|리팩)", re.IGNORECASE)),
    ("test", re.compile(r"^(test|테스트|\* test)", re.IGNORECASE)),
    ("chore", re.compile(r"^(chore|build|ci|설정|\* chore)", re.IGNORECASE)),
    ("docs", re.compile(r"^(docs|문서)", re.IGNORECASE)),
    ("style", re.compile(r"^(style|format|lint|정리)", re.IGNORECASE)),
    ("perf", re.compile(r"^(perf|최적화)", re.IGNORECASE)),
]


def _classify_message(message):
    """커밋 메시지에서 업무 유형 분류"""
    msg = message.strip()
    for type_name, pattern in _TYPE_PATTERNS:
        if pattern.search(msg):
            return type_name
    return "other"


def _find_data_dir(project_dir, period_label=None):
    """프로젝트 디렉토리에서 데이터 디렉토리 찾기"""
    if period_label:
        d = os.path.join(project_dir, period_label)
        return d if os.path.isdir(d) else None

    subdirs = sorted([
        s for s in os.listdir(project_dir)
        if os.path.isdir(os.path.join(project_dir, s))
    ])
    if not subdirs:
        return None
    return os.path.join(project_dir, subdirs[-1])


def aggregate_person_data(output_base_dir, service_groups=None, period_label=None):
    """
    모든 프로젝트 CSV를 스캔하여 개인 기준으로 교차 집계

    Args:
        output_base_dir: output 루트 디렉토리
        service_groups: {"그룹명": ["project_id", ...]} 서비스 영역 매핑
        period_label: 특정 기간 라벨 (None이면 최신)

    Returns:
        dict: {
            "persons": {이름: PersonData},
            "all_projects": [프로젝트 목록],
            "all_months": [월 목록],
        }
    """
    service_groups = service_groups or {}

    # project_id → 서비스 그룹 역방향 매핑
    project_to_service = {}
    for group_name, project_ids in service_groups.items():
        for pid in project_ids:
            project_to_service[pid] = group_name

    persons = defaultdict(lambda: {
        "name": "",
        # 프로젝트별 요약
        "projects": {},
        # 월별 x 프로젝트 매트릭스
        "monthly_matrix": defaultdict(lambda: defaultdict(int)),
        # 업무 유형 카운트
        "work_types": defaultdict(int),
        # 프로젝트별 등급 분포
        "grade_by_project": {},
        # 서비스 레벨 기여도
        "service_contrib": defaultdict(lambda: {
            "commits": 0, "net": 0, "mr": 0, "reviews": 0,
        }),
        # KPI 집계용
        "total_commits": 0,
        "total_coding_commits": 0,
        "total_added": 0,
        "total_deleted": 0,
        "total_net": 0,
        "total_mr": 0,
        "total_reviews": 0,
        "total_approvals": 0,
        "total_blame": 0,
        "project_count": 0,
        # 커밋 가치 집계
        "cv_total": 0,
        "cv_value_sum": 0,
        "cv_S": 0,
        "cv_A": 0,
        "cv_B": 0,
        "cv_C": 0,
        "cv_D": 0,
    })

    all_projects = []
    all_months = set()

    # 프로젝트 디렉토리 스캔
    for project_id in sorted(os.listdir(output_base_dir)):
        project_dir = os.path.join(output_base_dir, project_id)
        if not os.path.isdir(project_dir) or project_id == "persons":
            continue

        data_dir = _find_data_dir(project_dir, period_label)
        if not data_dir:
            continue

        summary_csv = os.path.join(data_dir, "contribution_summary.csv")
        if not os.path.exists(summary_csv):
            continue

        period_used = os.path.basename(data_dir)
        all_projects.append({"id": project_id, "period": period_used})

        # 1) contribution_summary.csv → 프로젝트별 요약
        for row in _read_csv(summary_csv):
            name = row.get("이름", "")
            if not name:
                continue

            p = persons[name]
            p["name"] = name

            proj_data = {
                "commits": _safe_int(row.get("전체커밋")),
                "coding_commits": _safe_int(row.get("코딩커밋")),
                "added": _safe_int(row.get("추가라인")),
                "deleted": _safe_int(row.get("삭제라인")),
                "net": _safe_int(row.get("순기여")),
                "mr": _safe_int(row.get("본인MR머지")),
                "reviews": _safe_int(row.get("리뷰코멘트작성수")),
                "approvals": _safe_int(row.get("MR승인수")),
                "blame": _safe_int(row.get("blame라인수")),
            }
            p["projects"][project_id] = proj_data

            # KPI 누적
            p["total_commits"] += proj_data["commits"]
            p["total_coding_commits"] += proj_data["coding_commits"]
            p["total_added"] += proj_data["added"]
            p["total_deleted"] += proj_data["deleted"]
            p["total_net"] += proj_data["net"]
            p["total_mr"] += proj_data["mr"]
            p["total_reviews"] += proj_data["reviews"]
            p["total_approvals"] += proj_data["approvals"]
            p["total_blame"] += proj_data["blame"]

            # 서비스 레벨 기여도
            svc = project_to_service.get(project_id, "기타")
            sc = p["service_contrib"][svc]
            sc["commits"] += proj_data["commits"]
            sc["net"] += proj_data["net"]
            sc["mr"] += proj_data["mr"]
            sc["reviews"] += proj_data["reviews"]

        # 2) contribution_monthly.csv → 월별 x 프로젝트 매트릭스
        monthly_csv = os.path.join(data_dir, "contribution_monthly.csv")
        for row in _read_csv(monthly_csv):
            name = row.get("이름", "")
            month = row.get("월", "")
            count = _safe_int(row.get("커밋수"))
            if name and month:
                persons[name]["monthly_matrix"][month][project_id] += count
                all_months.add(month)

        # 3) contribution_commit_values.csv → 업무 유형
        cv_csv = os.path.join(data_dir, "contribution_commit_values.csv")
        for row in _read_csv(cv_csv):
            name = row.get("작성자", "")
            message = row.get("메시지", "")
            if name:
                work_type = _classify_message(message)
                persons[name]["work_types"][work_type] += 1

        # 4) contribution_commit_value_summary.csv → 등급 분포
        cvs_csv = os.path.join(data_dir, "contribution_commit_value_summary.csv")
        for row in _read_csv(cvs_csv):
            name = row.get("이름", "")
            if not name:
                continue

            grade_data = {
                "total": _safe_int(row.get("총커밋")),
                "S": _safe_int(row.get("S등급")),
                "A": _safe_int(row.get("A등급")),
                "B": _safe_int(row.get("B등급")),
                "C": _safe_int(row.get("C등급")),
                "D": _safe_int(row.get("D등급")),
                "avg_score": _safe_float(row.get("평균점수")),
                "value_sum": _safe_int(row.get("가치합산")),
            }
            persons[name]["grade_by_project"][project_id] = grade_data

            # 전체 등급 누적
            p = persons[name]
            p["cv_total"] += grade_data["total"]
            p["cv_value_sum"] += grade_data["value_sum"]
            p["cv_S"] += grade_data["S"]
            p["cv_A"] += grade_data["A"]
            p["cv_B"] += grade_data["B"]
            p["cv_C"] += grade_data["C"]
            p["cv_D"] += grade_data["D"]

    # 후처리: project_count, 평균 점수 계산
    for name, p in persons.items():
        p["project_count"] = len(p["projects"])
        if p["cv_total"] > 0:
            p["cv_avg_score"] = round(p["cv_value_sum"] / p["cv_total"], 1)
            p["cv_critical_pct"] = round(
                (p["cv_S"] + p["cv_A"]) / p["cv_total"] * 100, 1
            )
        else:
            p["cv_avg_score"] = 0
            p["cv_critical_pct"] = 0

        # defaultdict → dict 변환 (JSON 직렬화용)
        p["monthly_matrix"] = {
            m: dict(projs) for m, projs in p["monthly_matrix"].items()
        }
        p["work_types"] = dict(p["work_types"])
        p["service_contrib"] = {
            k: dict(v) for k, v in p["service_contrib"].items()
        }

    sorted_months = sorted(all_months)

    return {
        "persons": dict(persons),
        "all_projects": all_projects,
        "all_months": sorted_months,
    }
