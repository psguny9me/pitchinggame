"""
GitLab / GitHub API 클라이언트 (C섹션)

MR 정보, 코드리뷰 코멘트, 승인, CI 상태 수집
"""

import json
import os
import time
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import URLError, HTTPError

from contrib_analyzer.collectors import print_progress


def collect_platform_data(cfg, members, until):
    """
    GitLab/GitHub API 기반 데이터 수집

    Returns:
        dict: {
            "members": {name: {gl_review_comments, gl_approvals, ...}},
            "quality": [{name, iid, title, comments, approvers, ci}],
        }
    """
    platform = cfg.get("git_platform", {})
    ptype = platform.get("type", "unknown")

    if ptype == "gitlab":
        return _collect_gitlab(platform, members, until)
    elif ptype == "github":
        print_progress("GitHub API는 아직 미구현입니다")
        return _empty_result(members)
    else:
        print_progress(f"알 수 없는 플랫폼: {ptype}")
        return _empty_result(members)


def _empty_result(members):
    """API 미사용 시 기본 결과"""
    member_data = {}
    for m in members:
        member_data[m["name"]] = {
            "gl_review_comments": "-",
            "gl_approvals": "-",
            "gl_reviewed_mrs": "-",
            "gl_received_comments": "-",
            "gl_ci_fail_rate": "-",
        }
    return {"members": member_data, "quality": []}


# ── GitLab ────────────────────────────────────────────────────────────

def _gitlab_get(url_base, token, path):
    """GitLab API GET 요청"""
    url = f"{url_base}/api/v4{path}"
    req = Request(url)
    req.add_header("PRIVATE-TOKEN", token)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except (URLError, HTTPError) as e:
        print(f"    ⚠ API 오류: {e}")
        return None


def _gitlab_get_all(url_base, token, path):
    """GitLab API 페이지네이션 처리"""
    results = []
    page = 1
    while True:
        sep = "&" if "?" in path else "?"
        data = _gitlab_get(url_base, token, f"{path}{sep}page={page}&per_page=100")
        if not data or not isinstance(data, list) or len(data) == 0:
            break
        results.extend(data)
        if len(data) < 100:
            break
        page += 1
        time.sleep(0.2)
    return results


def _collect_gitlab(platform, members, until):
    """GitLab API 수집 전체 로직"""
    # config의 token 직접 지정 > config의 token_env 환경변수명 > 기본 환경변수
    token = platform.get("token", "")
    if not token:
        token_env = platform.get("token_env", "GITLAB_TOKEN")
        token = os.environ.get(token_env, "")
    if not token:
        print_progress("GitLab 토큰이 없습니다. git_platform.token 또는 GITLAB_TOKEN 환경변수를 설정하세요.")
        return _empty_result(members)

    url_base = platform.get("url", "")
    project_path = platform.get("project", "")

    if not url_base or not project_path:
        print_progress("git_platform.url 또는 project 가 설정되지 않았습니다")
        return _empty_result(members)

    encoded_project = quote(project_path, safe="")
    project_data = _gitlab_get(url_base, token, f"/projects/{encoded_project}")
    project_id = project_data.get("id") if project_data else None

    if not project_id:
        print_progress("프로젝트 ID를 가져올 수 없습니다")
        return _empty_result(members)

    print_progress(f"프로젝트 ID: {project_id}")

    member_results = {}
    quality_data = []

    for m in members:
        name = m["name"]
        gl_user = m.get("git_platform_user", "")
        if not gl_user:
            member_results[name] = _empty_result([m])["members"][name]
            continue

        print_progress(f"{name} GitLab 분석 중 ({gl_user})...")

        # 1) 본인 머지된 MR
        merged_mrs = _gitlab_get_all(
            url_base, token,
            f"/projects/{project_id}/merge_requests"
            f"?author_username={gl_user}&state=merged"
            f"&created_before={until}T00:00:00Z",
        )
        print_progress(f"  {name}: 머지된 MR {len(merged_mrs)}개")

        # 2) 본인 MR에 받은 코멘트 + CI 상태
        received_comments = 0
        ci_total = 0
        ci_fail = 0

        for mr in merged_mrs:
            iid = mr.get("iid")
            if not iid:
                continue

            notes = _gitlab_get(
                url_base, token,
                f"/projects/{project_id}/merge_requests/{iid}/notes?per_page=100",
            )
            if notes and isinstance(notes, list):
                for n in notes:
                    if (not n.get("system", False)
                            and n.get("author", {}).get("username", "") != gl_user):
                        received_comments += 1

            pipeline = mr.get("pipeline") or {}
            p_status = pipeline.get("status", "unknown")
            ci_total += 1
            if p_status == "failed":
                ci_fail += 1

            approvals = _gitlab_get(
                url_base, token,
                f"/projects/{project_id}/merge_requests/{iid}/approvals",
            )
            approver_count = len(approvals.get("approved_by", [])) if approvals else 0

            mr_title = mr.get("title", "").replace(",", " ")[:80]
            comment_count_for_mr = 0
            if notes and isinstance(notes, list):
                comment_count_for_mr = sum(
                    1 for n in notes
                    if (not n.get("system", False)
                        and n.get("author", {}).get("username", "") != gl_user)
                )

            quality_data.append({
                "name": name,
                "iid": iid,
                "title": mr_title,
                "comments": comment_count_for_mr,
                "approvers": approver_count,
                "ci": p_status,
            })
            time.sleep(0.1)

        # 3) 리뷰어로 참여한 MR
        reviewed_mrs = _gitlab_get_all(
            url_base, token,
            f"/projects/{project_id}/merge_requests"
            f"?state=merged&created_before={until}T00:00:00Z"
            f"&reviewer_username={gl_user}",
        )
        other_mrs = [
            mr for mr in reviewed_mrs
            if mr.get("author", {}).get("username", "") != gl_user
        ]

        review_comments = 0
        approval_count = 0

        for mr in other_mrs:
            iid = mr.get("iid")
            if not iid:
                continue

            notes = _gitlab_get(
                url_base, token,
                f"/projects/{project_id}/merge_requests/{iid}/notes?per_page=100",
            )
            if notes and isinstance(notes, list):
                for n in notes:
                    if (not n.get("system", False)
                            and n.get("author", {}).get("username", "") == gl_user):
                        review_comments += 1

            approvals = _gitlab_get(
                url_base, token,
                f"/projects/{project_id}/merge_requests/{iid}/approvals",
            )
            if approvals:
                for a in approvals.get("approved_by", []):
                    if a.get("user", {}).get("username", "") == gl_user:
                        approval_count += 1
                        break

            time.sleep(0.1)

        member_results[name] = {
            "gl_review_comments": review_comments,
            "gl_approvals": approval_count,
            "gl_reviewed_mrs": len(other_mrs),
            "gl_received_comments": received_comments,
            "gl_ci_fail_rate": round(ci_fail / ci_total * 100, 1) if ci_total > 0 else 0,
        }

        print(f"    ✓ {name} 완료 (코멘트: {review_comments}, 승인: {approval_count})")

    return {"members": member_results, "quality": quality_data}
