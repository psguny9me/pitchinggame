"""
커밋 가치 다차원 평가 시스템 (Commit Value Classifier)

각 커밋을 5가지 차원으로 평가하여 0~100점 Value Score를 산출합니다:
  1. 파일 핵심도 (File Criticality)   - 30%
  2. 변경 고유율 (Change Uniqueness)  - 20%
  3. 변경 유형   (Change Type)        - 25%
  4. 메시지 시그널 (Message Signal)    - 15%
  5. 영향 범위   (Impact Scope)       - 10%

등급: S(80+), A(60~79), B(40~59), C(20~39), D(0~19)

사용법:
  from contrib_analyzer.collectors.commit_classifier import CommitClassifier
  classifier = CommitClassifier(config)
  results = classifier.classify_commits(commit_hashes)
"""

import re
import subprocess
import os
from collections import defaultdict


# ── 기본 설정 ─────────────────────────────────────────────────────────────

DEFAULT_WEIGHTS = {
    "file_criticality": 0.30,
    "change_uniqueness": 0.20,
    "change_type": 0.25,
    "message_signal": 0.15,
    "impact_scope": 0.10,
}

# 파일명 패턴별 핵심도 가중치 (파일 경로에 포함될 때 매칭)
DEFAULT_CRITICAL_PATTERNS = {
    "usecase": 1.0,
    "use_case": 1.0,
    "controller": 0.9,
    "service": 0.9,
    "state": 0.8,
    "provider": 0.8,
    "bloc": 0.8,
    "repository": 0.7,
    "model": 0.6,
    "mixin": 0.6,
    "widget": 0.4,
    "screen": 0.4,
    "page": 0.4,
    "view": 0.3,
    "style": 0.2,
    "theme": 0.2,
    "constant": 0.1,
}

# 자동 생성 파일 패턴
DEFAULT_AUTO_GENERATED = [
    r"\.freezed\.dart$",
    r"\.g\.dart$",
    r"\.generated\.",
    r"\.min\.js$",
    r"\.min\.css$",
]

# 커밋 메시지 유형별 가중치
MESSAGE_WEIGHTS = {
    "fix": 0.9,
    "feat": 0.8,
    "perf": 0.7,
    "test": 0.6,
    "refactor": 0.5,
    "docs": 0.3,
    "chore": 0.2,
    "style": 0.1,
    "typo": 0.1,
    "format": 0.1,
    "lint": 0.1,
    "rename": 0.15,
    "cleanup": 0.15,
    "clean up": 0.15,
}

# 로직/상태 변경 감지용 정규식 패턴
LOGIC_PATTERNS = [
    r"\bif\s*\(",
    r"\belse\b",
    r"\bswitch\s*\(",
    r"\btry\s*\{",
    r"\bcatch\s*\(",
    r"\bthrow\b",
    r"\breturn\b",
    r"\bawait\b",
    r"\byield\b",
    r"\bwhile\s*\(",
    r"\bfor\s*\(",
    r"\bcase\s+",
]

STATE_PATTERNS = [
    r"setState\s*\(",
    r"notifyListeners\s*\(",
    r"\.emit\s*\(",
    r"\.value\s*=",
    r"\.add\s*\(",
    r"\.update\s*\(",
    r"\.notifier",
    r"ValueNotifier",
    r"ChangeNotifier",
    r"\.state\s*=",
]

# import 라인 감지 패턴
IMPORT_PATTERN = re.compile(r"^[+-]\s*(import\s|export\s|part\s|part of\s|library\s)")

# JIRA/이슈 참조 패턴
ISSUE_PATTERN = re.compile(r"(TEST-\d+|JIRA-\d+|#\d+|https?://jira)", re.IGNORECASE)

# 삭제/제거 키워드
REMOVAL_KEYWORDS = ["[remove]", "삭제", "제거", "drop", "deprecat"]

# 등급 임계값
DEFAULT_GRADE_THRESHOLDS = {"S": 80, "A": 60, "B": 40, "C": 20}


class CommitClassifier:
    """커밋 가치 다차원 평가기"""

    def __init__(self, config=None):
        """
        config 딕셔너리 구조:
        {
            "weights": {"file_criticality": 0.30, ...},
            "critical_file_patterns": {"controller": 0.9, ...},
            "auto_generated_patterns": ["*.freezed.dart", ...],
            "grade_thresholds": {"S": 80, "A": 60, "B": 40, "C": 20},
        }
        """
        config = config or {}

        self.weights = config.get("weights", DEFAULT_WEIGHTS)
        raw_patterns = config.get("critical_file_patterns", DEFAULT_CRITICAL_PATTERNS)
        # 리스트로 들어오면 기본 가중치 딕셔너리에서 매칭, 없으면 0.7 기본값
        if isinstance(raw_patterns, list):
            self.critical_patterns = {}
            for p in raw_patterns:
                self.critical_patterns[p] = DEFAULT_CRITICAL_PATTERNS.get(p, 0.7)
        else:
            self.critical_patterns = raw_patterns
        self.auto_generated_re = [
            re.compile(p)
            for p in config.get("auto_generated_patterns", DEFAULT_AUTO_GENERATED)
        ]
        self.grade_thresholds = config.get(
            "grade_thresholds", DEFAULT_GRADE_THRESHOLDS
        )

        # 정규식 사전 컴파일
        self._logic_re = [re.compile(p) for p in LOGIC_PATTERNS]
        self._state_re = [re.compile(p) for p in STATE_PATTERNS]

    # ── Git 유틸리티 ───────────────────────────────────────────────────

    @staticmethod
    def _run_git(args, cwd=None):
        """git 명령 실행 후 stdout 반환"""
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd or os.getcwd(),
        )
        return result.stdout.strip()

    # ── 커밋 수집 ──────────────────────────────────────────────────────

    def collect_commits(self, target_dir, until_date, member_emails,
                        since_date=None, cwd=None, branch="HEAD"):
        """
        대상 디렉토리의 non-merge 커밋 해시/메타데이터 수집 (지정 브랜치 기준)

        Args:
            target_dir: 대상 디렉토리
            until_date: 종료 날짜
            member_emails: 대상 멤버 이메일 패턴 리스트
            since_date: 시작 날짜 (선택)
            cwd: Git 저장소 경로 (선택)
            branch: 분석 대상 브랜치 (기본: HEAD)

        Returns:
            list[dict]: 커밋 정보 리스트
                {"hash", "author_email", "author_name", "message", "date"}
        """
        fmt = "%H%n%aE%n%aN%n%s%n%ai%n---COMMIT_SEP---"

        git_args = [
            "log", "--no-merges",
            f"--until={until_date}",
            f"--format={fmt}",
        ]
        if since_date:
            git_args.append(f"--since={since_date}")
        path_args = ["--", target_dir] if target_dir else []
        git_args.extend([branch] + path_args)

        out = self._run_git(git_args, cwd=cwd)

        commits = []
        if not out:
            return commits

        entries = out.split("---COMMIT_SEP---")
        for entry in entries:
            lines = [l for l in entry.strip().splitlines() if l.strip()]
            if len(lines) < 4:
                continue

            email = lines[1].strip()
            matched = False
            for me in member_emails:
                if me in email:
                    matched = True
                    break

            if not matched:
                continue

            commits.append({
                "hash": lines[0].strip(),
                "author_email": email,
                "author_name": lines[2].strip(),
                "message": lines[3].strip(),
                "date": lines[4].strip() if len(lines) > 4 else "",
            })

        return commits

    # ── Diff 파싱 ──────────────────────────────────────────────────────

    def _parse_diff(self, commit_hash, target_dir, cwd=None):
        """
        커밋의 diff를 파싱하여 분석 데이터를 반환

        Returns:
            dict: {
                "files": [파일명 리스트],
                "added_lines": [추가 라인들],
                "deleted_lines": [삭제 라인들],
                "all_diff_lines": [모든 변경 라인들],
                "numstat": [(added, deleted, file), ...],
            }
        """
        # numstat으로 파일별 변경 통계
        diff_path_args = ["--", target_dir] if target_dir else []
        numstat_out = self._run_git([
            "diff-tree", "--numstat", "--no-commit-id", "-r",
            commit_hash,
        ] + diff_path_args, cwd=cwd)

        numstat = []
        files = []
        for line in numstat_out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                try:
                    a = int(parts[0]) if parts[0] != "-" else 0
                    d = int(parts[1]) if parts[1] != "-" else 0
                    numstat.append((a, d, parts[2]))
                    files.append(parts[2])
                except ValueError:
                    pass

        # 전체 diff 내용
        diff_out = self._run_git([
            "diff-tree", "-p", "--no-commit-id",
            commit_hash,
        ] + diff_path_args, cwd=cwd)

        added_lines = []
        deleted_lines = []
        all_diff_lines = []

        for line in diff_out.splitlines():
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+"):
                content = line[1:].strip()
                if content:
                    added_lines.append(content)
                    all_diff_lines.append(line)
            elif line.startswith("-"):
                content = line[1:].strip()
                if content:
                    deleted_lines.append(content)
                    all_diff_lines.append(line)

        return {
            "files": files,
            "added_lines": added_lines,
            "deleted_lines": deleted_lines,
            "all_diff_lines": all_diff_lines,
            "numstat": numstat,
        }

    # ── 차원 1: 파일 핵심도 (File Criticality) ────────────────────────

    def _score_file_criticality(self, files):
        """수정된 파일들의 핵심도 점수 (0.0 ~ 1.0)"""
        if not files:
            return 0.0

        max_score = 0.0
        auto_gen_count = 0

        for filepath in files:
            # 자동 생성 파일 체크
            is_auto = any(regex.search(filepath) for regex in self.auto_generated_re)
            if is_auto:
                auto_gen_count += 1
                continue

            # 파일 경로에서 핵심 패턴 매칭
            filepath_lower = filepath.lower()
            for pattern, score in self.critical_patterns.items():
                if pattern.lower() in filepath_lower:
                    max_score = max(max_score, score)
                    break
            else:
                # 패턴 매칭 안 되면 기본 0.3점
                max_score = max(max_score, 0.3)

        # 전부 자동 생성 파일이면 0점
        if auto_gen_count == len(files):
            return 0.0

        return max_score

    # ── 차원 2: 변경 고유율 (Change Uniqueness) ───────────────────────

    @staticmethod
    def _score_change_uniqueness(all_diff_lines):
        """diff 라인의 고유율 (0.0 ~ 1.0)"""
        if not all_diff_lines:
            return 1.0

        total = len(all_diff_lines)
        unique = len(set(all_diff_lines))
        ratio = unique / total

        # 고유율을 0~1 범위의 점수로 변환
        if ratio >= 0.9:
            return 1.0
        elif ratio >= 0.7:
            return 0.6 + (ratio - 0.7) * 2.0
        elif ratio >= 0.5:
            return 0.3 + (ratio - 0.5) * 1.5
        else:
            return ratio * 0.6

    # ── 차원 3: 변경 유형 분석 (Change Type) ──────────────────────────

    def _score_change_type(self, added_lines, deleted_lines, numstat):
        """변경 내용의 유형별 점수 (0.0 ~ 1.0)"""
        if not added_lines and not deleted_lines:
            return 0.0

        total_added = sum(a for a, _, _ in numstat) if numstat else len(added_lines)
        total_deleted = sum(d for _, d, _ in numstat) if numstat else len(deleted_lines)
        total_changes = total_added + total_deleted

        if total_changes == 0:
            return 0.0

        # 삭제 비율 분석
        deletion_ratio = total_deleted / total_changes if total_changes > 0 else 0

        # 순수 삭제 (80%+) → 정리 작업, 낮은 점수
        if deletion_ratio >= 0.8 and total_added < 10:
            return 0.15

        # import 전용 변경 체크
        all_lines = added_lines + deleted_lines
        import_count = sum(
            1 for line in all_lines
            if IMPORT_PATTERN.match("+" + line) or IMPORT_PATTERN.match("-" + line)
        )
        if len(all_lines) > 0 and import_count / len(all_lines) >= 0.8:
            return 0.1

        # 로직/상태 변경 감지
        logic_hits = 0
        state_hits = 0

        for line in added_lines:
            for regex in self._logic_re:
                if regex.search(line):
                    logic_hits += 1
                    break
            for regex in self._state_re:
                if regex.search(line):
                    state_hits += 1
                    break

        # 로직/상태 변경 비율로 점수 산출
        meaningful_ratio = (logic_hits + state_hits) / max(len(added_lines), 1)

        # rename 패턴 감지
        is_rename = self._detect_rename_pattern(added_lines, deleted_lines)
        if is_rename:
            return 0.2

        # 점수 계산
        score = 0.3  # 기본 점수

        if meaningful_ratio >= 0.3:
            score = 0.9
        elif meaningful_ratio >= 0.15:
            score = 0.7
        elif meaningful_ratio >= 0.05:
            score = 0.5
        elif logic_hits > 0 or state_hits > 0:
            score = 0.4

        # 적절한 크기의 추가 코드가 있으면 보너스
        if 5 <= total_added <= 200 and logic_hits > 0:
            score = min(score + 0.1, 1.0)

        return score

    @staticmethod
    def _detect_rename_pattern(added_lines, deleted_lines):
        """추가/삭제 라인이 이름만 바꾼 패턴인지 감지"""
        if len(added_lines) < 2 or len(deleted_lines) < 2:
            return False

        if abs(len(added_lines) - len(deleted_lines)) > max(len(added_lines), 1) * 0.3:
            return False

        pair_count = min(len(added_lines), len(deleted_lines))
        if pair_count == 0:
            return False

        similar_pairs = 0
        for i in range(pair_count):
            added_tokens = set(re.findall(r"\w+", added_lines[i]))
            deleted_tokens = set(re.findall(r"\w+", deleted_lines[i]))

            if not added_tokens or not deleted_tokens:
                continue

            common = added_tokens & deleted_tokens
            total = added_tokens | deleted_tokens

            if len(total) > 0 and len(common) / len(total) >= 0.7:
                similar_pairs += 1

        return similar_pairs / pair_count >= 0.6

    # ── 차원 4: 메시지 시그널 (Message Signal) ────────────────────────

    @staticmethod
    def _score_message_signal(message):
        """커밋 메시지에서 가치 시그널 추출 (0.0 ~ 1.0)"""
        if not message:
            return 0.3

        msg_lower = message.lower().strip()
        score = 0.4  # 기본 점수

        # Conventional Commit prefix 매칭
        for keyword, weight in MESSAGE_WEIGHTS.items():
            if msg_lower.startswith(keyword) or msg_lower.startswith(f"[{keyword}"):
                score = weight
                break

        # 한글 키워드 매칭
        if score == 0.4:
            if "수정" in msg_lower or "fix" in msg_lower:
                score = 0.8
            elif "추가" in msg_lower or "구현" in msg_lower:
                score = 0.7
            elif "개선" in msg_lower or "최적화" in msg_lower:
                score = 0.6
            elif "정리" in msg_lower or "제거" in msg_lower:
                score = 0.3

        # JIRA/이슈 참조 보너스
        if ISSUE_PATTERN.search(message):
            score = min(score + 0.1, 1.0)

        # 삭제/제거 감점
        for kw in REMOVAL_KEYWORDS:
            if kw in msg_lower:
                score = max(score - 0.15, 0.05)
                break

        return score

    # ── 차원 5: 영향 범위 (Impact Scope) ──────────────────────────────

    @staticmethod
    def _score_impact_scope(numstat):
        """변경의 집중도와 영향 범위 (0.0 ~ 1.0)"""
        if not numstat:
            return 0.0

        file_count = len(numstat)
        total_lines = sum(a + d for a, d, _ in numstat)

        if total_lines == 0:
            return 0.0

        avg_per_file = total_lines / file_count

        if file_count == 1:
            if total_lines >= 10:
                return 0.9
            elif total_lines >= 3:
                return 0.7
            else:
                return 0.5

        if file_count <= 3 and avg_per_file >= 20:
            return 0.8

        if file_count <= 5 and avg_per_file >= 10:
            return 0.6

        if file_count >= 10 and avg_per_file < 5:
            return 0.2

        if file_count >= 10 and avg_per_file >= 10:
            return 0.4

        return 0.5

    # ── 종합 평가 ──────────────────────────────────────────────────────

    def classify_single(self, commit_hash, message, target_dir, cwd=None):
        """
        단일 커밋의 가치 평가

        Args:
            commit_hash: 커밋 해시
            message: 커밋 메시지
            target_dir: 대상 디렉토리
            cwd: Git 저장소 경로

        Returns:
            dict: 5차원 점수 + value_score + grade + 통계
        """
        diff_data = self._parse_diff(commit_hash, target_dir, cwd=cwd)

        d1 = self._score_file_criticality(diff_data["files"])
        d2 = self._score_change_uniqueness(diff_data["all_diff_lines"])
        d3 = self._score_change_type(
            diff_data["added_lines"],
            diff_data["deleted_lines"],
            diff_data["numstat"],
        )
        d4 = self._score_message_signal(message)
        d5 = self._score_impact_scope(diff_data["numstat"])

        raw_score = (
            d1 * self.weights["file_criticality"]
            + d2 * self.weights["change_uniqueness"]
            + d3 * self.weights["change_type"]
            + d4 * self.weights["message_signal"]
            + d5 * self.weights["impact_scope"]
        )
        value_score = min(round(raw_score * 100), 100)

        grade = "D"
        for g in ["S", "A", "B", "C"]:
            if value_score >= self.grade_thresholds[g]:
                grade = g
                break

        total_lines = sum(a + d for a, d, _ in diff_data["numstat"]) if diff_data["numstat"] else 0
        file_count = len(diff_data["files"])

        return {
            "file_criticality": round(d1, 3),
            "change_uniqueness": round(d2, 3),
            "change_type": round(d3, 3),
            "message_signal": round(d4, 3),
            "impact_scope": round(d5, 3),
            "value_score": value_score,
            "grade": grade,
            "total_lines": total_lines,
            "file_count": file_count,
        }

    def classify_commits(self, commits, target_dir, progress_callback=None,
                         cwd=None):
        """
        여러 커밋을 일괄 평가

        Args:
            commits: list[dict] - collect_commits()의 반환값
            target_dir: 대상 디렉토리
            progress_callback: callable(current, total) - 진행률 콜백
            cwd: Git 저장소 경로

        Returns:
            list[dict]: 각 커밋의 평가 결과
        """
        results = []
        total = len(commits)

        for i, commit in enumerate(commits):
            if progress_callback and (i + 1) % 50 == 0:
                progress_callback(i + 1, total)

            scores = self.classify_single(
                commit["hash"], commit["message"], target_dir, cwd=cwd,
            )

            results.append({
                "hash": commit["hash"][:12],
                "author_name": commit["author_name"],
                "author_email": commit["author_email"],
                "message": commit["message"],
                "date": commit.get("date", ""),
                **scores,
            })

        return results

    # ── 집계 유틸리티 ──────────────────────────────────────────────────

    @staticmethod
    def aggregate_by_author(results, member_name_map=None):
        """
        작성자별 집계

        Args:
            results: classify_commits()의 반환값
            member_name_map: {email_pattern: display_name} 매핑

        Returns:
            dict[str, dict]: 작성자별 집계 결과
        """
        author_stats = defaultdict(lambda: {
            "총커밋": 0,
            "S": 0, "A": 0, "B": 0, "C": 0, "D": 0,
            "점수합": 0,
        })

        for r in results:
            email = r["author_email"]
            name = r["author_name"]

            display = name
            if member_name_map:
                for pattern, dn in member_name_map.items():
                    if pattern in email:
                        display = dn
                        break

            stats = author_stats[display]
            stats["총커밋"] += 1
            stats[r["grade"]] += 1
            stats["점수합"] += r["value_score"]

        aggregated = {}
        for author, stats in author_stats.items():
            total = stats["총커밋"]
            s_count = stats["S"]
            a_count = stats["A"]

            aggregated[author] = {
                "총커밋": total,
                "S": s_count,
                "A": a_count,
                "B": stats["B"],
                "C": stats["C"],
                "D": stats["D"],
                "평균점수": round(stats["점수합"] / total, 1) if total > 0 else 0,
                "가치합산": stats["점수합"],
                "핵심커밋비율": round((s_count + a_count) / total * 100, 1) if total > 0 else 0,
            }

        return aggregated
