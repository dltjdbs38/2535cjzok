#!/usr/bin/env python3
"""
부하테스트 전에 돌리는 "사용자 한 명 흐름" 점검 + 베이스라인(부하 없을 때 응답시간) 측정 스크립트.

왜 JMeter 전에 이걸 먼저 돌리나:
  JMeter 스크립트가 실패했을 때 원인이 "서버 문제"인지 "스크립트(CSRF, 쿠키, 리다이렉트) 실수"인지 구분하기
  어렵다. 이 스크립트로 먼저 한 명이 끝까지 흐름을 타는 걸 확인해두면, JMeter에서 에러가 나면 스크립트
  쪽을 의심하면 된다. 또 --rounds로 반복하면 "부하 없을 때의 기준 응답시간(베이스라인)"이 나오는데,
  이후 부하 결과를 비교할 기준이 된다.

사용 예 (staging 서버에 대해):
  export LOADTEST_TOKEN=서버에_설정한_토큰
  python loadtest/flow_check.py --base-url https://staging.example.com --csv loadtest/users.csv --row 0 --rounds 20

필요한 것: pip install requests
"""
import argparse
import csv
import os
import re
import sys
import time

import requests

CSRF_RE = re.compile(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"')
PROFILE_RE = re.compile(r"/matching/profile/(\d+)/")
ROOM_ID_RE = re.compile(r'data-room-id="(\d+)"')
ROOM_URL_RE = re.compile(r"/chat/(\d+)/$")


class StepFailed(Exception):
    pass


class Flow:
    def __init__(self, base_url, token):
        self.base = base_url.rstrip("/")
        self.token = token
        self.session = requests.Session()
        self.samples = []  # (step, status, ms)

    def call(self, step, method, path, expect=(200,), **kwargs):
        headers = kwargs.pop("headers", {})
        if method == "POST":
            # HTTPS에서는 Django가 CSRF 검증 때 Referer 헤더까지 확인한다. 브라우저는 자동으로 붙이지만
            # requests/JMeter는 안 붙이므로 직접 넣어야 한다. (JMeter도 똑같이 HTTP Header Manager에 넣어야 함)
            headers.setdefault("Referer", self.base + "/")
        started = time.perf_counter()
        resp = self.session.request(method, self.base + path, headers=headers, timeout=30, **kwargs)
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.samples.append((step, resp.status_code, elapsed_ms))
        if resp.status_code not in expect:
            raise StepFailed(f"[{step}] 예상 {expect} 인데 {resp.status_code} (URL: {resp.url})")
        return resp

    # ---- 1) 로그인: 한 번만 ----
    def login(self, user_id):
        resp = self.call("00 login", "POST", f"/loadtest/login/{user_id}/", headers={"X-Loadtest-Token": self.token})
        if not resp.json().get("ok"):
            raise StepFailed("[00 login] 응답에 ok가 없음")

    # ---- 2) 로그인 이후 사용자 흐름: 반복 ----
    def round(self, partner_id, polls, poll_interval, do_like):
        resp = self.call("01 home(redirect)", "GET", "/")
        if "/matching/" not in resp.url:
            raise StepFailed(f"[01 home] 매칭 화면으로 안 갔어: {resp.url} (승인/블랙리스트 상태 확인)")

        resp = self.call("02 matching list", "GET", "/matching/")
        candidates = list(dict.fromkeys(PROFILE_RE.findall(resp.text)))  # 순서 유지 + 중복 제거
        target = candidates[0] if candidates else partner_id  # 리스트가 비면 짝(partner)으로 대체
        if not candidates:
            print("  (경고: 이 사용자의 매칭 리스트가 비어 있음 - 시드 --density를 높여보세요)")
        if target is None:
            return  # 열어볼 프로필이 없으면(리스트 비어있고 짝도 없음) 이후 단계는 건너뛴다

        resp = self.call("03 profile detail", "GET", f"/matching/profile/{target}/")
        csrf = CSRF_RE.search(resp.text)
        if not csrf:
            raise StepFailed("[03 profile] 페이지에서 csrfmiddlewaretoken을 못 찾음")

        if do_like:
            # 좋아요는 토글이라 실행할 때마다 켜졌다 꺼졌다 한다 (상태가 쌓이지 않아 반복 실행에 안전).
            self.call("04 like(toggle)", "POST", f"/matching/like/{target}/", data={"csrfmiddlewaretoken": csrf.group(1)})

        if partner_id is None:
            return

        resp = self.call("05 chat start", "POST", f"/chat/start/{partner_id}/", data={"csrfmiddlewaretoken": csrf.group(1)})
        room_match = ROOM_URL_RE.search(resp.url)
        if not room_match or not ROOM_ID_RE.search(resp.text):
            raise StepFailed(f"[05 chat start] 대화방으로 못 들어감: {resp.url} (동시 대화 3명 제한이나 매너온도 평가 대기에 걸렸을 수 있음)")
        room_id = room_match.group(1)
        room_csrf = CSRF_RE.search(resp.text)
        if not room_csrf:
            raise StepFailed("[05 chat start] 대화방 페이지에서 csrf 토큰을 못 찾음")

        resp = self.call("06 chat poll(first)", "GET", f"/chat/{room_id}/poll/", params={"after": 0})
        last_id = max([m["id"] for m in resp.json()["messages"]] or [0])

        resp = self.call(
            "07 chat send", "POST", f"/chat/{room_id}/",
            data={"content": f"loadtest {time.time():.0f}", "reply_to": "", "csrfmiddlewaretoken": room_csrf.group(1)},
            headers={"X-Requested-With": "XMLHttpRequest"},  # 실제 화면의 JS가 보내는 헤더 (이게 있어야 JSON으로 응답)
        )
        sent = resp.json()["messages"]
        if not sent:
            raise StepFailed("[07 chat send] 응답에 방금 보낸 메시지가 없음")
        last_id = max(last_id, sent[-1]["id"])

        for _ in range(polls):
            if poll_interval:
                time.sleep(poll_interval)  # 실제 화면은 3초마다 폴링한다
            resp = self.call("08 chat poll", "GET", f"/chat/{room_id}/poll/", params={"after": last_id})
            resp.json()

        self.call("09 chat list", "GET", "/chat/")


def percentile(sorted_values, pct):
    if not sorted_values:
        return 0.0
    rank = max(1, int(round(pct / 100 * len(sorted_values) + 0.4999)))  # nearest-rank 방식
    return sorted_values[min(rank, len(sorted_values)) - 1]


def print_summary(samples):
    by_step = {}
    for step, status, ms in samples:
        by_step.setdefault(step, []).append(ms)
    print(f"\n{'step':22s}{'n':>5s}{'avg':>9s}{'p50':>9s}{'p95':>9s}{'max':>9s}  (ms)")
    for step in sorted(by_step):
        v = sorted(by_step[step])
        print(f"{step:22s}{len(v):5d}{sum(v) / len(v):9.1f}{percentile(v, 50):9.1f}{percentile(v, 95):9.1f}{v[-1]:9.1f}")


def pick_user(csv_path, row):
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    r = rows[row % len(rows)]
    return int(r["user_id"]), int(r["partner_id"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", required=True, help="예: https://staging.example.com")
    ap.add_argument("--token", default=os.environ.get("LOADTEST_TOKEN", ""), help="기본값: 환경변수 LOADTEST_TOKEN")
    ap.add_argument("--csv", help="seed_loadtest_data가 만든 CSV (user_id, partner_id를 여기서 읽음)")
    ap.add_argument("--row", type=int, default=0, help="CSV에서 몇 번째 행의 사용자로 돌릴지")
    ap.add_argument("--user-id", type=int, help="CSV 대신 직접 지정")
    ap.add_argument("--partner-id", type=int, help="CSV 대신 직접 지정 (없으면 채팅 단계 생략)")
    ap.add_argument("--rounds", type=int, default=1, help="로그인 이후 흐름을 몇 번 반복할지 (베이스라인은 20 정도)")
    ap.add_argument("--polls", type=int, default=3, help="라운드당 채팅 폴링 횟수")
    ap.add_argument("--poll-interval", type=float, default=0.0, help="폴링 간격(초). 실제 화면은 3. 기본 0(빨리 확인용)")
    ap.add_argument("--no-like", action="store_true", help="좋아요 단계 생략")
    args = ap.parse_args()

    if not args.token:
        sys.exit("토큰이 없어. --token 또는 환경변수 LOADTEST_TOKEN을 설정해줘.")
    if args.csv:
        user_id, partner_id = pick_user(args.csv, args.row)
    elif args.user_id:
        user_id, partner_id = args.user_id, args.partner_id
    else:
        sys.exit("--csv 또는 --user-id 중 하나는 필요해.")

    flow = Flow(args.base_url, args.token)
    print(f"대상: {args.base_url} / user_id={user_id} partner_id={partner_id} / rounds={args.rounds}")
    try:
        flow.login(user_id)
        for i in range(args.rounds):
            flow.round(partner_id, args.polls, args.poll_interval, not args.no_like)
    except StepFailed as e:
        print_summary(flow.samples)
        print(f"\n실패: {e}")
        sys.exit(1)
    except requests.RequestException as e:
        print(f"\n네트워크 오류: {e}")
        sys.exit(2)

    print_summary(flow.samples)
    print(f"\n성공: {args.rounds}라운드 완료 (총 요청 {len(flow.samples)}건)")


if __name__ == "__main__":
    main()
