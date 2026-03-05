# Contribution Analyzer

Git 프로젝트의 기여도를 정량적으로 분석하는 도구입니다. 멀티 프로젝트 일괄 분석과 종합 대시보드를 지원합니다.

## 기능

- **Git 기반 분석**: 커밋 수, 추가/삭제 라인, MR 머지, blame 코드 소유권
- **코드리뷰 분석**: GitLab API 연동 (리뷰 코멘트, MR 승인, CI 상태)
- **커밋 가치 평가**: 5차원 평가 (파일 핵심도, 변경 고유율, 변경 유형, 메시지 시그널, 영향 범위)
- **Slack 커뮤니케이션 분석**: 메시지 활동, 스레드 참여, 응답 속도, 리액션
- **멀티 프로젝트**: 여러 프로젝트 일괄 분석 + 크로스 프로젝트 종합 대시보드
- **브랜치 필터링**: 지정 브랜치(master/develop 등)에 머지된 커밋만 분석
- **기간 프리셋**: 주간/월간/분기/상하반기/커스텀

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

### 단일 프로젝트 실행

```bash
# 설정 파일 초기화 (자동 감지: members, modules, branch)
python3 -m contrib_analyzer init --repo /path/to/repo --output configs/my_project.yaml

# 수집 + 대시보드 한번에 실행
python3 -m contrib_analyzer run --config configs/my_project.yaml --period weekly
```

### 전체 프로젝트 일괄 실행

```bash
# configs/ 디렉토리의 모든 YAML 파일을 순회하며 분석 + 종합 대시보드 자동 생성
python3 -m contrib_analyzer run-all
```

### 종합 대시보드만 재생성

```bash
python3 -m contrib_analyzer summary
```

### CLI 옵션

| 옵션 | 설명 |
|------|------|
| `--period` | 기간 프리셋 (weekly, monthly, quarterly, half, custom) |
| `--since`, `--until` | 직접 기간 지정 (custom 모드) |
| `--skip-api` | GitLab/GitHub API 분석 건너뛰기 |
| `--skip-blame` | git blame 분석 건너뛰기 |
| `--skip-classify` | 커밋 가치 평가 건너뛰기 |
| `--skip-slack` | Slack 분석 건너뛰기 |

### 기간 프리셋

| 프리셋 | 설명 |
|--------|------|
| `weekly` | 지난주 (월~일) |
| `monthly` | 지난달 |
| `quarterly` | 지난 분기 |
| `half` | 지난 반기 |
| `custom` | `--since`/`--until`로 직접 지정 |

## 설정 (YAML)

```yaml
project:
  name: "프로젝트명"
  repo_path: "/path/to/repo"
  branch: master           # 분석 대상 브랜치 (미지정 시 자동 감지)

period:
  preset: weekly            # 기본 기간 프리셋
  # 또는 고정 기간:
  # since: "2025-01-01"
  # until: "2025-12-31"

target_dirs:
  - src/

members:
  - name: 홍길동
    git_pattern: "hong@example.com"
    git_platform_user: hong
    slack_user: "홍길동"

git_platform:
  type: gitlab
  url: "https://gitlab.example.com"
  project: "group/project"
  token: "glpat-xxxxx"     # 또는 token_env로 환경변수명 지정

slack:
  token_env: "SLACK_BOT_TOKEN"
  channels:
    - "개발팀"
```

`members`, `modules`, `branch`는 미지정 시 자동 감지됩니다.

## 출력 구조

```
output/
├── summary_dashboard.html          # 크로스 프로젝트 종합 대시보드
├── app_platform/
│   └── 2026-W09/
│       ├── dashboard.html          # 프로젝트별 대시보드
│       ├── contribution_summary.csv
│       ├── contribution_monthly.csv
│       ├── contribution_modules.csv
│       ├── contribution_quality.csv
│       ├── contribution_commit_values.csv
│       ├── contribution_commit_value_summary.csv
│       └── contribution_slack.csv
├── jobkorea_ios/
│   └── 2025-01-01_2025-12-31/
│       └── ...
└── ...
```

## 등록된 프로젝트

| 프로젝트 | 설정 파일 | 분석 브랜치 |
|----------|-----------|------------|
| App Platform | `configs/app_platform.yaml` | app-develop |
| 알바몬 iOS | `configs/albamon_ios.yaml` | master |
| 알바몬 Android | `configs/albamon_android.yaml` | master |
| 알바맵 모듈 | `configs/albamap2_module.yaml` | develop |
| 잡코리아 iOS (추천2.0) | `configs/jobkorea_ios.yaml` | master |
| 잡코리아 Android (추천2.0) | `configs/jobkorea_android.yaml` | master |
