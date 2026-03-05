"""
Slack 업무 커뮤니케이션 분석 (E섹션)

Slack Web API를 통해 채널 메시지를 수집하고 멤버별 커뮤니케이션 기여도 측정

필요한 Bot Token 스코프:
  - channels:history, channels:read (공개 채널)
  - groups:history, groups:read (비공개 채널 포함 시)
  - reactions:read
  - users:read
"""

import json
import os
import statistics
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime

from contrib_analyzer.collectors import print_progress


_SLACK_API = "https://slack.com/api"


def collect_slack_data(cfg, members, since, until):
    """
    Slack 채널 메시지를 분석하여 멤버별 커뮤니케이션 메트릭 수집

    Args:
        cfg: 설정 딕셔너리 (slack 섹션 포함)
        members: 멤버 리스트
        since: 시작일 (YYYY-MM-DD)
        until: 종료일 (YYYY-MM-DD)

    Returns:
        dict: {
            "members": {name: {...metrics}},
            "channel_stats": [{channel, messages, threads}],
        }
    """
    slack_cfg = cfg.get("slack", {})
    token_env = slack_cfg.get("token_env", "SLACK_BOT_TOKEN")
    token = os.environ.get(token_env)

    if not token:
        print_progress(f"환경변수 {token_env} 이 설정되지 않았습니다. Slack 분석을 건너뜁니다.")
        return None

    channel_names = slack_cfg.get("channels", [])
    if not channel_names:
        print_progress("slack.channels 가 설정되지 않았습니다.")
        return None

    # Slack 유저 매핑 구축
    user_map = _build_user_map(token, members)
    print_progress(f"Slack 유저 매핑: {len(user_map)}명")

    # 기간을 Unix timestamp로 변환
    ts_since = datetime.strptime(since, "%Y-%m-%d").timestamp()
    ts_until = datetime.strptime(until, "%Y-%m-%d").timestamp()

    # 채널 ID 조회
    channels = _resolve_channels(token, channel_names)
    print_progress(f"분석 대상 채널: {len(channels)}개")

    # 멤버별 메트릭 초기화
    member_metrics = {}
    for m in members:
        member_metrics[m["name"]] = _empty_metrics()

    channel_stats = []

    for ch_name, ch_id in channels.items():
        print_progress(f"채널 수집 중: #{ch_name}")

        # 채널 메시지 수집
        messages = _fetch_channel_messages(token, ch_id, ts_since, ts_until)
        thread_count = sum(1 for msg in messages if msg.get("reply_count", 0) > 0)
        channel_stats.append({
            "channel": ch_name,
            "messages": len(messages),
            "threads": thread_count,
        })

        # 스레드 답글 수집
        thread_replies = {}
        for msg in messages:
            if msg.get("reply_count", 0) > 0:
                thread_ts = msg["ts"]
                replies = _fetch_thread_replies(token, ch_id, thread_ts)
                thread_replies[thread_ts] = replies

        # 메시지별 분석
        _analyze_messages(
            messages, thread_replies, user_map, member_metrics, ts_since, ts_until,
        )

    # 응답 시간 통계 계산
    for name, metrics in member_metrics.items():
        response_times = metrics.pop("_response_times", [])
        if response_times:
            metrics["avg_response_min"] = round(statistics.mean(response_times), 1)
            metrics["median_response_min"] = round(statistics.median(response_times), 1)

    # 결과 출력
    for m in members:
        name = m["name"]
        mt = member_metrics[name]
        print(f"    {name}: 메시지 {mt['messages']}건 | "
              f"스레드답변 {mt['help_replies']}건 | "
              f"리액션 {mt['reactions_received']}건 | "
              f"응답 {mt['avg_response_min']}분")

    return {
        "members": member_metrics,
        "channel_stats": channel_stats,
    }


def _empty_metrics():
    return {
        "messages": 0,
        "thread_starts": 0,
        "thread_replies": 0,
        "help_replies": 0,
        "code_shares": 0,
        "reactions_received": 0,
        "unique_reactors": set(),
        "avg_response_min": 0,
        "median_response_min": 0,
        "_response_times": [],
    }


# ── Slack API 호출 ──────────────────────────────────────────────────────

def _slack_api(token, method, params=None):
    """Slack Web API 호출"""
    url = f"{_SLACK_API}/{method}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"

    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    })

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data.get("ok"):
                error = data.get("error", "unknown")
                print_progress(f"Slack API 오류 ({method}): {error}")
            return data
    except urllib.error.URLError as e:
        print_progress(f"Slack API 연결 실패: {e}")
        return {"ok": False}


def _build_user_map(token, members):
    """
    Slack 유저 목록을 조회하여 user_id -> member_name 매핑 구축

    Returns:
        dict: {slack_user_id: member_name}
    """
    data = _slack_api(token, "users.list")
    if not data.get("ok"):
        return {}

    slack_users = {}
    for user in data.get("members", []):
        if user.get("is_bot") or user.get("deleted"):
            continue
        uid = user["id"]
        display_name = (
            user.get("profile", {}).get("display_name")
            or user.get("profile", {}).get("real_name")
            or user.get("real_name")
            or ""
        )
        real_name = user.get("profile", {}).get("real_name") or ""
        slack_users[uid] = {
            "display_name": display_name,
            "real_name": real_name,
        }

    # members 설정의 slack_user 와 매칭
    user_map = {}
    for m in members:
        slack_user = m.get("slack_user", m["name"])
        for uid, info in slack_users.items():
            if (slack_user == info["display_name"]
                    or slack_user == info["real_name"]
                    or slack_user == uid):
                user_map[uid] = m["name"]
                break

    return user_map


def _resolve_channels(token, channel_names):
    """채널 이름 -> ID 매핑"""
    result = {}

    # 공개 채널 조회
    data = _slack_api(token, "conversations.list", {
        "types": "public_channel,private_channel",
        "limit": "1000",
        "exclude_archived": "true",
    })
    if not data.get("ok"):
        return result

    for ch in data.get("channels", []):
        if ch["name"] in channel_names:
            result[ch["name"]] = ch["id"]

    for name in channel_names:
        if name not in result:
            print_progress(f"  채널을 찾을 수 없음: #{name}")

    return result


def _fetch_channel_messages(token, channel_id, ts_since, ts_until):
    """채널의 기간 내 메시지 수집 (페이지네이션 포함)"""
    messages = []
    cursor = None

    while True:
        params = {
            "channel": channel_id,
            "oldest": str(ts_since),
            "latest": str(ts_until),
            "limit": "200",
        }
        if cursor:
            params["cursor"] = cursor

        data = _slack_api(token, "conversations.history", params)
        if not data.get("ok"):
            break

        for msg in data.get("messages", []):
            # bot 메시지 제외
            if msg.get("subtype") in ("bot_message", "channel_join", "channel_leave"):
                continue
            messages.append(msg)

        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    return messages


def _fetch_thread_replies(token, channel_id, thread_ts):
    """스레드의 답글 수집"""
    params = {
        "channel": channel_id,
        "ts": thread_ts,
        "limit": "200",
    }
    data = _slack_api(token, "conversations.replies", params)
    if not data.get("ok"):
        return []

    # 첫 번째 메시지(원본)는 제외하고 답글만 반환
    replies = data.get("messages", [])
    return [r for r in replies if r.get("ts") != thread_ts]


def _analyze_messages(messages, thread_replies, user_map, member_metrics, ts_since, ts_until):
    """메시지 데이터 분석하여 멤버별 메트릭 집계"""
    for msg in messages:
        user_id = msg.get("user", "")
        member_name = user_map.get(user_id)
        if not member_name:
            continue

        mt = member_metrics[member_name]

        # 메시지 수
        mt["messages"] += 1

        # 코드 스니펫 공유 여부
        text = msg.get("text", "")
        if "```" in text:
            mt["code_shares"] += 1

        # 스레드 시작 여부
        if msg.get("reply_count", 0) > 0:
            mt["thread_starts"] += 1

        # 리액션 수집
        for reaction in msg.get("reactions", []):
            count = reaction.get("count", 0)
            mt["reactions_received"] += count
            for reactor_id in reaction.get("users", []):
                if reactor_id != user_id:
                    mt["unique_reactors"].add(reactor_id)

    # 스레드 답글 분석
    for thread_ts, replies in thread_replies.items():
        # 원본 메시지 작성자 찾기
        original_user = None
        for msg in messages:
            if msg.get("ts") == thread_ts:
                original_user = msg.get("user")
                break

        first_reply_by_member = {}

        for reply in replies:
            reply_user = reply.get("user", "")
            reply_name = user_map.get(reply_user)
            if not reply_name:
                continue

            mt = member_metrics[reply_name]
            mt["thread_replies"] += 1

            # 타인의 스레드에 답변 = help_replies
            if reply_user != original_user:
                mt["help_replies"] += 1

            # 첫 답변 시간 기록 (응답 속도 측정용)
            if reply_name not in first_reply_by_member:
                first_reply_by_member[reply_name] = float(reply.get("ts", "0"))

        # 응답 속도 계산
        thread_ts_float = float(thread_ts)
        for name, first_ts in first_reply_by_member.items():
            response_sec = first_ts - thread_ts_float
            if 0 < response_sec < 86400:  # 24시간 이내만 유효
                response_min = response_sec / 60
                member_metrics[name]["_response_times"].append(response_min)

    # unique_reactors를 count로 변환 (set은 JSON 직렬화 불가)
    for name, mt in member_metrics.items():
        mt["unique_reactors"] = len(mt["unique_reactors"])
