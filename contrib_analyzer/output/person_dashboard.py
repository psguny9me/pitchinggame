"""
개인 단위 기여도 대시보드 생성

모든 프로젝트의 CSV 데이터를 개인 기준으로 교차 집계하여
엔지니어별 대시보드와 인덱스 페이지를 생성합니다.
"""

import json
import os

import yaml
from jinja2 import Environment, FileSystemLoader

from contrib_analyzer.collectors import print_progress
from contrib_analyzer.output.person_aggregator import aggregate_person_data


def _load_service_groups(config_path=None):
    """서비스 그룹 매핑 로드"""
    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("groups", {})
    return {}


def generate_person_dashboards(output_base_dir, service_groups_path=None,
                                period_label=None, target_name=None):
    """
    개인 단위 대시보드 생성

    Args:
        output_base_dir: output 루트 디렉토리
        service_groups_path: service_groups.yaml 경로
        period_label: 특정 기간 라벨 (None이면 최신)
        target_name: 특정 인물만 생성 (None이면 전체)
    """
    template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    env = Environment(loader=FileSystemLoader(template_dir))

    # 서비스 그룹 로드
    service_groups = _load_service_groups(service_groups_path)
    print_progress(f"서비스 그룹: {len(service_groups)}개 영역")

    # 데이터 집계
    print_progress("전체 프로젝트 데이터 교차 집계 중...")
    data = aggregate_person_data(output_base_dir, service_groups, period_label)

    persons = data["persons"]
    all_months = data["all_months"]
    all_projects = data["all_projects"]

    if not persons:
        print_progress("분석 데이터가 없습니다")
        return

    print_progress(f"{len(persons)}명 엔지니어, {len(all_projects)}개 프로젝트 집계 완료")

    # 출력 디렉토리
    persons_dir = os.path.join(output_base_dir, "persons")
    os.makedirs(persons_dir, exist_ok=True)

    # 대상 인물 필터링
    if target_name:
        if target_name not in persons:
            print_progress(f"'{target_name}'을 찾을 수 없습니다")
            return
        target_persons = {target_name: persons[target_name]}
    else:
        target_persons = persons

    # 개인별 대시보드 생성
    person_template = env.get_template("person_dashboard.html")
    for name, pdata in target_persons.items():
        person_dir = os.path.join(persons_dir, name)
        os.makedirs(person_dir, exist_ok=True)

        used_label = period_label or (all_projects[0]["period"] if all_projects else "")

        html = person_template.render(
            person_name=name,
            period_label=used_label,
            project_count=pdata["project_count"],
            person_json=json.dumps(pdata, ensure_ascii=False),
            months_json=json.dumps(all_months, ensure_ascii=False),
        )

        out_path = os.path.join(person_dir, "dashboard.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"    {name}: {out_path}")

    # 인덱스 페이지 생성
    index_template = env.get_template("person_index.html")

    # 커밋 수 기준 정렬
    persons_list = sorted(
        persons.values(),
        key=lambda p: p["total_commits"],
        reverse=True,
    )
    used_label = period_label or (all_projects[0]["period"] if all_projects else "")

    index_html = index_template.render(
        person_count=len(persons),
        project_count=len(all_projects),
        period_label=used_label,
        persons_json=json.dumps(persons_list, ensure_ascii=False),
    )

    index_path = os.path.join(persons_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)

    print_progress(f"인덱스 페이지 생성: {index_path}")
    print_progress(f"개인 대시보드 {len(target_persons)}명 생성 완료")
