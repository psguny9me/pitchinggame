"""
HTML 대시보드 생성 (Jinja2 템플릿 기반)

CSV 데이터를 읽어 templates/dashboard.html 에 주입하여 대시보드 생성
"""

import csv
import json
import os
from collections import defaultdict

from jinja2 import Environment, FileSystemLoader

from contrib_analyzer.collectors import print_progress


def generate_dashboard(cfg, data_dir):
    """
    CSV 파일들을 읽어 HTML 대시보드를 생성

    Args:
        cfg: 설정 딕셔너리
        data_dir: CSV 파일이 있는 디렉토리
    """
    template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("dashboard.html")

    # CSV 데이터 로드
    members_data = _load_summary_csv(data_dir)
    monthly_data = _load_monthly_csv(data_dir)
    modules_data = _load_modules_csv(data_dir)
    quality_data = _load_quality_csv(data_dir)
    cv_data = _load_commit_value_summary_csv(data_dir)
    cv_detail = _load_commit_values_csv(data_dir)
    slack_data = _load_slack_csv(data_dir)

    # 작은 S등급 + 큰 C/D 등급 추출
    small_s_grade = _extract_small_s_grade(cv_detail)
    large_low_grade = _extract_large_low_grade(cv_detail)

    # 5차원 평균 점수 계산 (커밋 가치)
    cv_avg_dimensions = _calc_avg_dimensions(cv_detail, members_data)

    # 커밋 가치 데이터를 JS 형식으로 변환
    commit_value_js = _build_commit_value_js(cv_data, cv_avg_dimensions)

    # 프로젝트 정보
    project_name = cfg.get("project", {}).get("name", "프로젝트")
    period_label = os.path.basename(data_dir)

    # blame 총 라인 수 추출
    total_blame = sum(m.get("blame", 0) for m in members_data)

    # 템플릿 렌더링
    html = template.render(
        project_name=project_name,
        period_label=period_label,
        member_count=len(members_data),
        members_json=json.dumps(members_data, ensure_ascii=False),
        monthly_json=json.dumps(monthly_data, ensure_ascii=False),
        modules_json=json.dumps(modules_data, ensure_ascii=False),
        quality_json=json.dumps(quality_data, ensure_ascii=False),
        total_blame=total_blame,
        commit_value_json=json.dumps(commit_value_js, ensure_ascii=False),
        small_s_grade_json=json.dumps(small_s_grade, ensure_ascii=False),
        large_low_grade_json=json.dumps(large_low_grade, ensure_ascii=False),
        has_commit_values=len(cv_data) > 0,
        has_quality=len(quality_data) > 0,
        slack_json=json.dumps(slack_data, ensure_ascii=False),
        has_slack=len(slack_data) > 0,
    )

    # 출력
    output_path = os.path.join(data_dir, "dashboard.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print_progress(f"대시보드 생성: {output_path}")


# ── CSV 로더 ──────────────────────────────────────────────────────────────

def _read_csv(filepath):
    """CSV 파일을 딕셔너리 리스트로 읽기"""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


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


def _load_summary_csv(data_dir):
    """contribution_summary.csv → JS members 형식"""
    rows = _read_csv(os.path.join(data_dir, "contribution_summary.csv"))
    members = []
    for r in rows:
        members.append({
            "name": r.get("이름", ""),
            "totalCommits": _safe_int(r.get("전체커밋")),
            "codingCommits": _safe_int(r.get("코딩커밋")),
            "added": _safe_int(r.get("추가라인")),
            "deleted": _safe_int(r.get("삭제라인")),
            "net": _safe_int(r.get("순기여")),
            "selfMR": _safe_int(r.get("본인MR머지")),
            "featureMR": _safe_int(r.get("featureMR")),
            "fixMR": _safe_int(r.get("fixMR")),
            "fixRatio": _safe_float(r.get("fix비율(%)")),
            "avgSize": _safe_int(r.get("평균커밋크기")),
            "revert": _safe_int(r.get("revert건수")),
            "reviewerMR": _safe_int(r.get("타인MR머지_리뷰")),
            "focus": _safe_float(r.get("프레젠테이션집중도(%)")),
            "blame": _safe_int(r.get("blame라인수")),
            "blamePct": _safe_float(r.get("blame비율(%)")),
            "glReviewComments": _safe_int(r.get("리뷰코멘트작성수")),
            "glApprovals": _safe_int(r.get("MR승인수")),
            "glReviewedMRs": _safe_int(r.get("리뷰한MR수")),
            "glReceivedComments": _safe_int(r.get("MR받은코멘트수")),
            "ciFail": _safe_float(r.get("CI실패율(%)")),
        })
    return members


def _load_monthly_csv(data_dir):
    """contribution_monthly.csv → {months: [...], data: {name: [...]}}"""
    rows = _read_csv(os.path.join(data_dir, "contribution_monthly.csv"))
    if not rows:
        return {"months": [], "data": {}}

    months_set = set()
    name_months = defaultdict(lambda: defaultdict(int))

    for r in rows:
        month = r.get("월", "")
        name = r.get("이름", "")
        count = _safe_int(r.get("커밋수"))
        months_set.add(month)
        name_months[name][month] = count

    months = sorted(months_set)
    data = {}
    for name, mc in name_months.items():
        data[name] = [mc.get(m, 0) for m in months]

    return {"months": months, "data": data}


def _load_modules_csv(data_dir):
    """contribution_modules.csv → {names: [...], data: {name: [...]}}"""
    rows = _read_csv(os.path.join(data_dir, "contribution_modules.csv"))
    if not rows:
        return {"names": [], "data": {}}

    module_set = set()
    name_modules = defaultdict(lambda: defaultdict(int))

    for r in rows:
        mod = r.get("모듈", "")
        name = r.get("이름", "")
        count = _safe_int(r.get("커밋수"))
        module_set.add(mod)
        name_modules[name][mod] = count

    # 모듈 정렬: 총 커밋 수 기준 내림차순
    module_totals = defaultdict(int)
    for name, mc in name_modules.items():
        for mod, count in mc.items():
            module_totals[mod] += count
    modules = sorted(module_set, key=lambda m: module_totals[m], reverse=True)

    data = {}
    for name, mc in name_modules.items():
        data[name] = [mc.get(m, 0) for m in modules]

    return {"names": modules, "data": data}


def _load_quality_csv(data_dir):
    """contribution_quality.csv → 리스트"""
    rows = _read_csv(os.path.join(data_dir, "contribution_quality.csv"))
    result = []
    for r in rows:
        result.append({
            "name": r.get("이름", ""),
            "iid": r.get("MR_IID", ""),
            "title": r.get("MR제목", ""),
            "comments": _safe_int(r.get("받은코멘트수")),
            "approvers": _safe_int(r.get("승인자수")),
            "ci": r.get("CI결과", ""),
        })
    return result


def _load_commit_value_summary_csv(data_dir):
    """contribution_commit_value_summary.csv → 리스트"""
    rows = _read_csv(os.path.join(data_dir, "contribution_commit_value_summary.csv"))
    result = []
    for r in rows:
        result.append({
            "name": r.get("이름", ""),
            "total": _safe_int(r.get("총커밋")),
            "S": _safe_int(r.get("S등급")),
            "A": _safe_int(r.get("A등급")),
            "B": _safe_int(r.get("B등급")),
            "C": _safe_int(r.get("C등급")),
            "D": _safe_int(r.get("D등급")),
            "avgScore": _safe_float(r.get("평균점수")),
            "valueSum": _safe_int(r.get("가치합산")),
            "criticalPct": _safe_float(r.get("핵심커밋비율(%)")),
        })
    return result


def _load_commit_values_csv(data_dir):
    """contribution_commit_values.csv → 전체 커밋별 데이터"""
    rows = _read_csv(os.path.join(data_dir, "contribution_commit_values.csv"))
    result = []
    for r in rows:
        result.append({
            "hash": r.get("해시", ""),
            "author": r.get("작성자", ""),
            "message": r.get("메시지", ""),
            "date": r.get("날짜", ""),
            "lines": _safe_int(r.get("변경라인")),
            "files": _safe_int(r.get("파일수")),
            "fc": _safe_float(r.get("파일핵심도")),
            "cu": _safe_float(r.get("변경고유율")),
            "ct": _safe_float(r.get("변경유형")),
            "ms": _safe_float(r.get("메시지시그널")),
            "is_": _safe_float(r.get("영향범위")),
            "score": _safe_int(r.get("가치점수")),
            "grade": r.get("등급", ""),
        })
    return result


def _load_slack_csv(data_dir):
    """contribution_slack.csv → 리스트"""
    rows = _read_csv(os.path.join(data_dir, "contribution_slack.csv"))
    result = []
    for r in rows:
        result.append({
            "name": r.get("이름", ""),
            "messages": _safe_int(r.get("메시지수")),
            "threadStarts": _safe_int(r.get("스레드시작")),
            "threadReplies": _safe_int(r.get("스레드답변")),
            "helpReplies": _safe_int(r.get("타인스레드답변")),
            "codeShares": _safe_int(r.get("코드공유수")),
            "reactionsReceived": _safe_int(r.get("받은리액션")),
            "uniqueReactors": _safe_int(r.get("리액션준사람수")),
            "avgResponseMin": _safe_float(r.get("평균응답시간(분)")),
            "medianResponseMin": _safe_float(r.get("중앙값응답시간(분)")),
        })
    return result


def _extract_small_s_grade(cv_detail, max_lines=10, limit=16):
    """작은 커밋(max_lines 이하) 중 S등급 추출"""
    candidates = [
        c for c in cv_detail
        if c["grade"] == "S" and 0 < c["lines"] <= max_lines
    ]
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:limit]


def _extract_large_low_grade(cv_detail, min_lines=100, limit=15):
    """큰 커밋(min_lines 이상) 중 C/D등급 추출"""
    candidates = [
        c for c in cv_detail
        if c["grade"] in ("C", "D") and c["lines"] >= min_lines
    ]
    candidates.sort(key=lambda c: c["lines"], reverse=True)
    return candidates[:limit]


def _calc_avg_dimensions(cv_detail, members_data):
    """멤버별 5차원 평균 점수 계산"""
    member_names = {m["name"] for m in members_data}

    agg = defaultdict(lambda: {"fc": 0, "cu": 0, "ct": 0, "ms": 0, "is_": 0, "count": 0})
    for c in cv_detail:
        if c["author"] in member_names:
            a = agg[c["author"]]
            a["fc"] += c["fc"]
            a["cu"] += c["cu"]
            a["ct"] += c["ct"]
            a["ms"] += c["ms"]
            a["is_"] += c["is_"]
            a["count"] += 1

    result = {}
    for name, a in agg.items():
        n = a["count"] if a["count"] > 0 else 1
        result[name] = {
            "avgFC": round(a["fc"] / n, 2),
            "avgCU": round(a["cu"] / n, 2),
            "avgCT": round(a["ct"] / n, 2),
            "avgMS": round(a["ms"] / n, 2),
            "avgIS": round(a["is_"] / n, 2),
        }
    return result


def _build_commit_value_js(cv_data, cv_avg_dimensions):
    """커밋 가치 데이터를 JS 오브젝트 형식으로 변환"""
    result = []
    for d in cv_data:
        name = d["name"]
        dims = cv_avg_dimensions.get(name, {})
        result.append({
            **d,
            "avgFC": dims.get("avgFC", 0),
            "avgCU": dims.get("avgCU", 0),
            "avgCT": dims.get("avgCT", 0),
            "avgMS": dims.get("avgMS", 0),
            "avgIS": dims.get("avgIS", 0),
        })
    return result
