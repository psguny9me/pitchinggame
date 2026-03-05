"""
gh-pages 배포용 이름 익명 처리

한글 이름을 초성 이니셜로 치환 (예: 박세건 → ㅂㅅㄱ)
로컬 대시보드에는 영향 없이, gh-pages 브랜치 파일에만 적용

사용:
    python3 -m contrib_analyzer.anonymize <target_dir> [--configs <configs_dir>]
"""

import argparse
import glob
import os
import shutil

import yaml


# 한글 초성 테이블 (유니코드 순서)
_INITIALS = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"


def to_initial(name):
    """한글 이름을 초성 이니셜로 변환 (비한글 문자는 그대로 유지)"""
    result = []
    for c in name:
        code = ord(c)
        if 0xAC00 <= code <= 0xD7A3:
            result.append(_INITIALS[(code - 0xAC00) // 588])
        else:
            result.append(c)
    return "".join(result)


def get_all_member_names(configs_dir):
    """configs 디렉토리의 모든 YAML에서 멤버 이름 수집"""
    names = set()
    patterns = [
        os.path.join(configs_dir, "*.yaml"),
        os.path.join(configs_dir, "*.yml"),
    ]
    for pattern in patterns:
        for filepath in glob.glob(pattern):
            if "service_groups" in os.path.basename(filepath):
                continue
            with open(filepath, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            for m in cfg.get("members", []):
                name = m.get("name", "").strip()
                if name:
                    names.add(name)
    return names


def build_name_map(names):
    """실명 → 초성 이니셜 매핑 생성 (충돌 시 숫자 접미사 부여)"""
    name_map = {}
    used = {}  # 초성 → 사용 횟수
    for name in sorted(names, key=len, reverse=True):
        initial = to_initial(name)
        if initial == name:
            continue
        count = used.get(initial, 0)
        used[initial] = count + 1
        # 첫 번째는 그대로, 두 번째부터 숫자 접미사
        name_map[name] = initial if count == 0 else f"{initial}{count + 1}"
    return name_map


def anonymize_content(content, name_map):
    """텍스트 내 이름을 초성으로 치환"""
    for real_name, anon_name in name_map.items():
        content = content.replace(real_name, anon_name)
    return content


def anonymize_file(filepath, name_map):
    """단일 파일의 이름을 초성으로 치환"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, IsADirectoryError):
        return False

    new_content = anonymize_content(content, name_map)
    if new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    return False


def rename_person_dirs(target_dir, name_map):
    """persons/{실명}/ 디렉토리를 persons/{초성}/ 으로 변경"""
    persons_dir = os.path.join(target_dir, "persons")
    if not os.path.isdir(persons_dir):
        return []

    renames = []
    for entry in sorted(os.listdir(persons_dir)):
        if entry in name_map:
            old_path = os.path.join(persons_dir, entry)
            new_path = os.path.join(persons_dir, name_map[entry])
            if os.path.isdir(old_path) and not os.path.exists(new_path):
                shutil.move(old_path, new_path)
                renames.append((entry, name_map[entry]))
    return renames


def anonymize_directory(target_dir, configs_dir="configs"):
    """대상 디렉토리 내 모든 HTML/CSV 파일의 이름을 익명 처리"""
    names = get_all_member_names(configs_dir)
    if not names:
        print("  ✖ configs에서 멤버 이름을 찾을 수 없습니다")
        return

    name_map = build_name_map(names)
    print(f"  ▶ {len(name_map)}명 이름 매핑 생성")
    for real, anon in sorted(name_map.items()):
        print(f"    {real} → {anon}")

    # 1. persons 디렉토리 이름 변경 (파일 내용 치환보다 먼저)
    renames = rename_person_dirs(target_dir, name_map)
    if renames:
        print(f"  ▶ persons 디렉토리 {len(renames)}개 이름 변경")

    # 2. 모든 HTML/CSV 파일 내용 치환
    changed = 0
    for root, _dirs, files in os.walk(target_dir):
        for fname in files:
            if not fname.endswith((".html", ".csv")):
                continue
            filepath = os.path.join(root, fname)
            if anonymize_file(filepath, name_map):
                changed += 1

    print(f"  ▶ {changed}개 파일 익명 처리 완료")


def main():
    parser = argparse.ArgumentParser(description="gh-pages 이름 익명 처리")
    parser.add_argument("target_dir", help="익명 처리할 디렉토리 경로")
    parser.add_argument(
        "--configs", default="configs",
        help="멤버 이름을 읽을 configs 디렉토리 (기본: configs)",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.target_dir):
        print(f"  ✖ 디렉토리가 존재하지 않습니다: {args.target_dir}")
        return

    print("━━ gh-pages 이름 익명 처리 ━━")
    anonymize_directory(args.target_dir, args.configs)


if __name__ == "__main__":
    main()
