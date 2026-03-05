"""
기간 프리셋 계산 모듈

지원 프리셋:
  - weekly:    지난주 (월~일)
  - monthly:   지난달 (1일~말일)
  - quarterly: 지난 분기 (Q1~Q4)
  - half:      지난 반기 (상반기/하반기)
  - custom:    직접 지정 (--since, --until)
"""

from datetime import date, timedelta
import calendar


def resolve_period(preset, reference_date=None, since=None, until=None):
    """
    기간 프리셋 -> (since_str, until_str) 반환

    Args:
        preset: 프리셋 이름 (weekly, monthly, quarterly, half, custom)
        reference_date: 기준 날짜 (기본값: 오늘). date 객체 또는 "YYYY-MM-DD" 문자열
        since: custom 모드에서 시작일 문자열
        until: custom 모드에서 종료일 문자열

    Returns:
        tuple[str, str]: (since "YYYY-MM-DD", until "YYYY-MM-DD")
    """
    if isinstance(reference_date, str):
        reference_date = date.fromisoformat(reference_date)
    ref = reference_date or date.today()

    if preset == "weekly":
        return _resolve_weekly(ref)
    elif preset == "monthly":
        return _resolve_monthly(ref)
    elif preset == "quarterly":
        return _resolve_quarterly(ref)
    elif preset == "half":
        return _resolve_half(ref)
    elif preset == "custom":
        if not since or not until:
            raise ValueError("custom 모드에서는 --since 와 --until 이 필요합니다")
        return (since, until)
    else:
        raise ValueError(f"알 수 없는 기간 프리셋: {preset}")


def _resolve_weekly(ref):
    """지난주 월~일"""
    # 이번주 월요일
    this_monday = ref - timedelta(days=ref.weekday())
    # 지난주 월~일
    last_monday = this_monday - timedelta(weeks=1)
    last_sunday = last_monday + timedelta(days=6)
    return (last_monday.isoformat(), last_sunday.isoformat())


def _resolve_monthly(ref):
    """지난달 1일~말일"""
    first_of_this_month = ref.replace(day=1)
    last_of_prev_month = first_of_this_month - timedelta(days=1)
    first_of_prev_month = last_of_prev_month.replace(day=1)
    return (first_of_prev_month.isoformat(), last_of_prev_month.isoformat())


def _resolve_quarterly(ref):
    """지난 분기"""
    current_quarter = (ref.month - 1) // 3 + 1
    current_year = ref.year

    # 지난 분기 계산
    if current_quarter == 1:
        q_year = current_year - 1
        q_num = 4
    else:
        q_year = current_year
        q_num = current_quarter - 1

    q_start_month = (q_num - 1) * 3 + 1
    q_end_month = q_num * 3
    last_day = calendar.monthrange(q_year, q_end_month)[1]

    start = date(q_year, q_start_month, 1)
    end = date(q_year, q_end_month, last_day)
    return (start.isoformat(), end.isoformat())


def _resolve_half(ref):
    """지난 반기 (상반기=1~6월, 하반기=7~12월)"""
    if ref.month <= 6:
        # 현재 상반기 -> 지난해 하반기
        start = date(ref.year - 1, 7, 1)
        end = date(ref.year - 1, 12, 31)
    else:
        # 현재 하반기 -> 올해 상반기
        start = date(ref.year, 1, 1)
        end = date(ref.year, 6, 30)
    return (start.isoformat(), end.isoformat())


def period_label(preset, since, until):
    """기간 표시용 라벨 생성 (출력 디렉토리명 등에 사용)"""
    s = date.fromisoformat(since)

    if preset == "weekly":
        week_num = s.isocalendar()[1]
        return f"{s.year}-W{week_num:02d}"
    elif preset == "monthly":
        return f"{s.year}-{s.month:02d}"
    elif preset == "quarterly":
        q = (s.month - 1) // 3 + 1
        return f"{s.year}-Q{q}"
    elif preset == "half":
        h = "H1" if s.month <= 6 else "H2"
        return f"{s.year}-{h}"
    else:
        return f"{since}_{until}"
