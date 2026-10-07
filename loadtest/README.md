# 2535cjzok 부하테스트 가이드

대상 구조(실제 배포 기준): `인터넷 → nginx(TLS 종료) → Docker(gunicorn, worker 2개) → SQLite 파일`

## 0~1. 설치와 staging 구성

**같은 폴더의 `INSTALL.md`를 따른다.** 파일 배치, 기존 파일 수정(자동), DNS, 서버 보호 설정, staging 기동까지 거기에 순서대로 있다. 이 문서는 그 이후(데이터, 스모크, JMeter, 테스트 설계) 참고용이다.

## 2. 테스트 데이터 + 스모크

시드(**3,000명** = 목표 회원 규모)와 스모크 명령은 **`INSTALL.md` 2단계**에 있다. 아래는 그 결과를 해석하는 방법이다.

시드 명령어는 **`LOADTEST_ENABLED`가 켜진 환경에서만 실행**된다(staging의 `.env.staging`에는 있으니 자동 통과, prod에서는 막힘). 로컬에서 연습할 땐 `--allow-non-staging`을 붙인다.

시드 직후 출력되는 `[점검]` 줄에서 **0명인 사람이 30%를 넘으면 `--density high`로 다시** 만든다 (리스트가 비면 매칭 → 프로필 → 대화 흐름이 의미가 없어진다). 다시 만들 땐 먼저 `purge_loadtest_data --yes`.

## 3. 베이스라인 (부하 없을 때의 기준값)

```bash
python loadtest/flow_check.py --base-url https://staging.2535cjzok.com --csv loadtest/users.csv --rounds 30
```

단계별 p50/p95를 표로 저장해둔다. 이후 모든 부하 결과는 이 표와 비교한다. 이 값에는 PC↔서버 네트워크 왕복 시간(RTT)이 포함돼 있다는 점을 기록해둔다(`ping`으로 따로 측정).

## 4. JMeter 구성 명세 (Thread Group 2개: 탐색형 / 채팅형)

사용자 유형을 **Thread Group 두 개로 나눠서** 목표 표의 비율(탐색형 60% = 162명, 채팅형 40% = 108명)을 그대로 재현한다. 한 흐름에 모든 행동을 섞으면 단위업무별 TPS를 목표에 맞추기 어렵다. JMeter 5.x 이상 기준이다.

먼저 CSV를 둘로 나눈다 (채팅형은 **짝이 인접한 앞쪽 행**을 쓴다. CSV는 남/여 짝이 번갈아 적혀 있다):

```bash
head -1 loadtest/users.csv > loadtest/users_chat.csv   && sed -n '2,401p'  loadtest/users.csv >> loadtest/users_chat.csv     # 400명(200쌍): 채팅형 최대 400명까지
head -1 loadtest/users.csv > loadtest/users_browse.csv && sed -n '402,$p'  loadtest/users.csv >> loadtest/users_browse.csv   # 나머지 2,600명: 탐색형
```

실행은 항상 CLI(GUI는 스크립트 디버깅 전용 - GUI로 부하를 걸면 JMeter 자체가 병목이 된다):

```bash
JVM_ARGS="-Xms1g -Xmx2g" jmeter -n -t loadtest/2535cjzok.jmx \
  -Jhost=staging.2535cjzok.com -Jtoken=$LOADTEST_TOKEN \
  -Jcsv_browse=$PWD/loadtest/users_browse.csv -Jcsv_chat=$PWD/loadtest/users_chat.csv \
  -Jbrowse_threads=162 -Jchat_threads=108 -Jramp=300 -Jduration=1200 \
  -l loadtest/results/load-270.jtl -e -o loadtest/results/load-270-report
```
(`-o` 폴더는 비어있거나 없어야 한다. 부하 생성기 CPU가 70%를 넘으면 그 결과는 신뢰하지 않는다.)

**플랜 레벨 설정**

| 요소 | 설정 |
|---|---|
| User Defined Variables | `last_id=0` |
| HTTP Request Defaults | Protocol `https`, Server `${__P(host)}`, Port 443, **Retrieve All Embedded Resources 끔**(이미지/CSS 제외 - 처음엔 API 성능만), KeepAlive 켬 |
| HTTP Cookie Manager | **Clear cookies each iteration 끔** (로그인 세션을 스레드 내내 유지) |
| HTTP Header Manager | `Referer: https://${__P(host)}/` (HTTPS에서 Django CSRF가 Referer를 검사한다. 브라우저는 자동으로 붙이지만 JMeter는 안 붙인다) |
| CSV Data Set Config | **그룹마다 하나씩**. 탐색형은 `${__P(csv_browse)}`, 채팅형은 `${__P(csv_chat)}`. 변수 `user_id,username,gender,partner_id`, **Ignore first line 켬**, Recycle on EOF 켬, Sharing mode `All threads` (스레드마다 서로 다른 사용자) |
| Thread Group: 탐색형 | Threads `${__P(browse_threads,162)}`, Ramp-up `${__P(ramp,300)}`, Loop 무한 + Scheduler Duration `${__P(duration,1200)}` |
| Thread Group: 채팅형 | Threads `${__P(chat_threads,108)}`, 나머지 동일 |

**샘플러** (HTTP Request는 모두 **Follow Redirects 켬 / Redirect Automatically 끔**. 두 그룹 모두 맨 앞에 Once Only Controller로 로그인)

| 그룹 | 이름 | 요청 | 추출/검증 |
|---|---|---|---|
| 공통 | `login` (Once Only Controller 안) | POST `/loadtest/login/${user_id}/` + 헤더 `X-Loadtest-Token: ${__P(token)}` | 응답코드 200, JSON `$.ok`==true |
| 탐색형 | `home` | GET `/` | 최종 200 |
| 탐색형 | `matching_list` | GET `/matching/` | **Regex Extractor** `/matching/profile/(\d+)/` → `target_id`, Match No. `0`(랜덤), Default `${partner_id}` |
| 탐색형 | `profile_detail` | GET `/matching/profile/${target_id}/` | **Regex Extractor** `name="csrfmiddlewaretoken"\s+value="([^"]+)"` → `csrf` |
| 탐색형 | `like` (Throughput Controller 30%) | POST `/matching/like/${target_id}/` 파라미터 `csrfmiddlewaretoken=${csrf}` | 최종 200 |
| 채팅형 | `chat_start` (Loop 밖, 1회) | POST `/chat/start/${partner_id}/` 파라미터 `csrfmiddlewaretoken=${csrf}` (먼저 프로필 상세 GET으로 csrf를 얻거나, `/chat/` GET의 토큰을 추출) | Regex `data-room-id="(\d+)"` → `room_id`, Regex `name="csrfmiddlewaretoken"\s+value="([^"]+)"` → `room_csrf`, 직전에 `last_id=0` 초기화(User Parameters) |
| 채팅형 | `chat_poll` (**Loop Controller 600회 ≈ 30분**) | GET `/chat/${room_id}/poll/?after=${last_id}` | **JSON Extractor** `$.messages[-1:].id` → `last_id`, Default `${last_id}` |
| 채팅형 | `chat_send` (Loop 안, If Controller `${__jexl3(${pollNo} % 7 == 0)}`) | POST `/chat/${room_id}/` 파라미터 `content=loadtest`, `reply_to=`(빈값), `csrfmiddlewaretoken=${room_csrf}` + 헤더 `X-Requested-With: XMLHttpRequest` | JSON `$.messages` 길이 ≥ 1 |
| 채팅형 | `chat_list` (Loop 안, If Controller `${__jexl3(${pollNo} % 40 == 0)}`) | GET `/chat/` | 최종 200 |

Loop 안에는 **Counter 설정 요소**(Per User 독립 카운트, Reference Name `pollNo`, 시작 1, 증가 1)를 둔다. 이러면 폴링 7회(약 21초)마다 메시지 1건, 40회(약 2분)마다 대화 목록 1건이 목표 표대로 나간다.

**타이머**
- 탐색형: Thread Group에 Gaussian Random Timer(Constant Delay Offset 약 7000ms, Deviation 2000ms)를 붙이고, **한 사이클이 약 30초**가 되도록 맞춘다. 정확한 값은 4단계 캘리브레이션에서 라벨별 TPS를 보고 조정한다 (사이클이 길면 줄이고, 짧으면 늘린다).
- 채팅형: `chat_poll`에 Uniform Random Timer(2800ms + 랜덤 400ms) - **실제 화면이 3초마다 폴링하기 때문**이다. 이 값을 0으로 두면 현실에 없는 부하가 걸린다.

**주의 두 가지** (처음 실행 때 Debug Sampler + View Results Tree로 확인, 확인 후엔 반드시 끄기)
1. Regex Extractor의 Default 칸에 쓴 `${변수}`가 실제로 치환되는지.
2. `chat_start` 응답이 `/chat/<id>/`로 끝나는지. 동시 대화 3명 제한이나 매너온도 평가 대기에 걸리면 `/chat/`로 끝난다.

**closed 모델이라는 점**: JMeter 스레드는 응답을 받아야 다음 요청을 보낸다. 서버가 느려지면 요청률이 *스스로 줄어들어* 과부하가 실제보다 덜 보일 수 있다(coordinated omission). 도착률 고정 테스트가 필요하면 Constant Throughput Timer를 쓰거나 k6의 arrival-rate executor를 쓴다. 레포트에 한계로 적어둔다.

## 5. 테스트 종류별 계획 (확정 가정: 가입자 3,000 / DAU 30% = 900 / 피크 동시접속 30% = 270명)

목표 표(약 55 TPS, 단위업무별 응답시간, 오류율, 자원 기준)는 `docs/2535cjzok_performance_test_report.md` 6~7절에 있다. 숫자는 출발점이고 베이스라인을 본 뒤 조정한다.

| 종류 | 목적 | 부하 | 판정 |
|---|---|---|---|
| 통합 | 흐름 전체가 오류 없이 도는지 | 1 스레드 × 5 루프 | 에러 0 |
| 부하(Load) | 예상 피크에서 목표 만족? | 270명(탐색 162 + 채팅 108), 램프업 5분 후 15분 유지 | 목표 표 전 항목 |
| 임계치(Threshold) | 무너지는 지점(knee) 찾기 | 135 → 270 → 405 → 540 (→ 810), 단계당 5분 (Stepping/Ultimate Thread Group 플러그인) | 응답시간·오류율 목표를 처음 넘는 단계 |
| 스파이크 | 급증 + 회복 | 27명 유지 → 10초 만에 540명 → 3분 → 27명. **사다리 방식으로**, 앞 단계 복구 확인 후 다음 단계 | 오류율, **원래 응답시간으로 돌아오는 데 걸린 시간** |
| 내구성(Soak) | 시간이 지나며 새는 것 | 목표(270명)와 임계점의 70% 중 작은 값으로 2시간 | p95 증가 20% 이내, 메모리 증가 추세 없음, DB 크기 |
| 가용성 | 부하 중 서비스가 살아있나 | 위 테스트 내내 별도 프로브 | 연속 실패 3회 미만, 오류율 1% 미만 |

**캘리브레이션(본 테스트 전 필수)**: 270명으로 5분만 돌려서 **라벨별 Throughput이 목표 표(탐색 5.4 / 폴링 36 / 전송 5.4 등)와 ±10% 안인지** 확인하고, 안 맞으면 타이머를 조정한다. 이걸 건너뛰면 "270명을 넣었는데 TPS는 목표에 못 미치는" 테스트가 돼서, 통과해도 의미가 없다.

가용성 프로브(다른 터미널에서 1초마다): `while true; do curl -s -o /dev/null -w "%{time_total} %{http_code}\n" https://staging.2535cjzok.com/; sleep 1; done`

**중단 기준**: 프로브가 5회 연속 실패 / JMeter 30초 요약에서 오류율 20% 초과가 지속 / 서버 메모리 90% 초과 또는 스왑 증가 중 하나라도 걸리면 JMeter를 즉시 멈춘다. SSH 세션과 `tmux`(`vmstat 1`, `docker stats`)는 **테스트 시작 전에 미리** 열어둔다.

## 6. 테스트 중 관찰할 것 (서버)

```bash
docker stats                                                        # 컨테이너 CPU/메모리
vmstat 1                                                            # 호스트 CPU, run queue(r), 대기(wa)
docker compose -f docker-compose.staging.yml --env-file .env.staging logs -f web | grep -i "locked\|error\|timeout"
ls -lh staging-data/db.sqlite3                                      # DB 크기 증가
# nginx 로그에서 Django 처리시간(urt) 분포
awk '{for(i=1;i<=NF;i++) if($i ~ /^urt=/){split($i,a,"="); print a[2]}}' /var/log/nginx/2535cjzok-staging.access.log \
  | sort -n | awk '{v[NR]=$1} END{print "p50",v[int(NR*0.5)],"p95",v[int(NR*0.95)],"p99",v[int(NR*0.99)]}'
```

판독법: nginx 로그의 `rt`와 `urt` 차이가 크면 네트워크/nginx/클라이언트 쪽, `urt` 자체가 크면 Django/DB 쪽이다. `database is locked`가 보이면 SQLite 쓰기 경합이다.

> 참고: Scouter는 JVM(Java) 중심 APM이라 Django 앱에는 잘 안 맞는다. 이 서비스는 위의 로그/`docker stats`로 시작하고, 시각화가 필요해지면 Prometheus + node_exporter + cAdvisor → Grafana 구성이 맞다.

## 7. 병목 가설 목록 (측정으로 확인/기각)

| # | 가설 | 근거 | 상태 |
|---|---|---|---|
| H1 | SQLite 쓰기 잠금: 채팅 전송·좋아요·세션 저장이 동시에 몰리면 `database is locked` | SQLite는 쓰기 1개씩 직렬화 | 미검증 |
| H2 | sync worker 2개 포화: 처리량 ≈ worker 수 ÷ 평균 처리시간. 3초 폴링이라 채팅창 열어둔 N명 = 초당 N/3 요청이 상시 발생 | 구조 | 미검증 |
| H3 | 매칭 리스트가 회원 수에 비례해 느려짐 (페이지네이션 없음) | **측정함**: 회원 500→10,000명에서 요청당 5.9→38.7ms, 리스트 3→102명 | **확인됨(선형 증가)** |
| H4 | 매칭 리스트 N+1 쿼리 | **측정함**: 회원 수와 무관하게 쿼리 4개 고정 | **기각** |
| H5 | 대화 목록(`chat_list`)이 방마다 쿼리 여러 개 (마지막 메시지·안읽음 수) | 코드 구조상 의심 | 미검증 (staging에서 쿼리 수 측정) |
| H6 | 사진이 큰 화면에서 대역폭/렌더가 병목 (현재 테스트는 이미지 제외) | 이미지 서빙은 nginx | 후속 시나리오 |

H3, H4는 복원한 코드로 측정한 값이며 절대값(ms)은 해당 환경 CPU 기준이라 **추세만** 근거로 쓴다. staging에서 같은 측정을 다시 해서 실제 서버 값으로 교체한다.

## 8. 개선 → 재측정 후보 (한 번에 하나씩만 바꾼다)

1. gunicorn `GUNICORN_THREADS=4` (gthread로 전환)
2. `GUNICORN_WORKERS=4` (nproc 범위 안에서)
3. SQLite WAL 모드 + `timeout` 옵션 (H1 완화)
4. Postgres 전환 (`docker-compose.staging.yml`의 `pg` 프로필)
5. 매칭 리스트 페이지네이션 (H3)
6. VM OCPU 1 → 2 증설 (Flex 쉐이프 편집, 재부팅 필요, 시간 과금이라 실험 시간만큼만 비용 발생) - scale-up 효과 확인

**한 번에 하나만 바꾸고, 같은 시드 데이터(`--seed` 동일)와 같은 부하 프로파일로 다시 측정**해야 개선 효과를 숫자로 주장할 수 있다.

## 9. 시작 전 합의서 (본인이 시스템 담당자/테스터 두 역할로 작성)

대상 시스템 · 테스트 목적 · 범위(포함: 로그인 이후 핵심 흐름 / 제외: 카카오 OAuth, 이미지 업로드, 관리자 화면) · 성공 기준(SLO) · 일정 · 위험(운영 영향, 데이터 오염) · 중단 기준(에러율 5% 초과, 서버 CPU 95% 5분 지속 시 즉시 중단).

## 10. 안전 체크리스트

- [ ] `LOADTEST_ENABLED`는 staging `.env.staging`에만 있다 (prod `.env`에는 없음)
- [ ] 테스트가 끝나면 `docker compose -f docker-compose.staging.yml --env-file .env.staging down`
- [ ] prod와 같은 VM이라면 prod를 안 쓰는 시간에만 돌린다 (CPU를 나눠 쓰므로 prod도 느려진다)
- [ ] JMeter는 서버 VM이 아니라 다른 PC에서 돌린다
- [ ] 실수로 prod DB에 시드가 들어갔다면 `purge_loadtest_data --yes` (시드 명령어 자체는 가드로 prod에서 막혀 있다)
