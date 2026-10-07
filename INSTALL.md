# 부하테스트 키트 설치 안내

이 문서 하나만 순서대로 따라가면 **스모크 테스트 통과**까지 간다. (JMeter, 테스트 설계는 `loadtest/README.md`)

## 이 키트는 무엇인가

- 카카오 로그인 없이 JMeter가 로그인할 수 있는 **테스트 전용 통로** (staging에서만 열림, 3중 안전장치)
- 가짜 회원 + 매칭 조건을 **대량 생성/삭제**하는 명령어, JMeter용 CSV 출력
- 사용자 한 명의 전체 흐름을 점검하고 베이스라인을 재는 스크립트 (`flow_check.py`)
- **prod VM 안에서 prod와 완전히 분리된** staging 구성 (별도 컨테이너, 별도 DB 파일, 별도 서브도메인)

prod 앱과 prod DB는 건드리지 않는다. 가짜 회원이 실제 매칭 리스트에 섞이지 않고, 로그인 우회 통로가 운영 서비스에 열리지도 않는다.

## 파일 목록

| 경로 | 구분 | 용도 |
|---|---|---|
| `accounts/loadtest.py` | 새 파일 | 로그인 통로 |
| `accounts/management/commands/seed_loadtest_data.py` | 새 파일 | 가짜 회원/조건 대량 생성 (staging에서만 실행됨) |
| `accounts/management/commands/purge_loadtest_data.py` | 새 파일 | 가짜 회원 삭제 |
| `loadtest/flow_check.py` | 새 파일 | 스모크, 베이스라인 |
| `loadtest/README.md` | 새 파일 | JMeter 명세, 테스트 설계 |
| `docs/2535cjzok_performance_test_report.md` | 새 파일 | 보고서 뼈대 + 테스트 목표 표 (결과는 맨 마지막에 채움) |
| `docker-compose.staging.yml` | 새 파일 | staging 컨테이너 (CPU/메모리 제한, 로그 제한 포함) |
| `env.staging.example` | 새 파일 | staging 환경변수 양식 |
| `nginx-2535cjzok-staging.conf` | 새 파일 | staging nginx 설정 (서버에서 복사해서 사용) |
| `apply_loadtest_kit.sh` | 도구 | 아래 4개 기존 파일에 **자동으로** 추가해주는 스크립트 |
| `config/settings.py` | 기존 파일 + 2줄 (자동) | `LOADTEST_ENABLED`, `LOADTEST_TOKEN` |
| `config/urls.py` | 기존 파일 + 블록 (자동) | 켜져 있을 때만 로그인 통로 라우트 등록 |
| `.gitignore`, `.dockerignore` | 기존 파일 + 4줄 (자동) | `.env.staging`, `staging-data/`, CSV, 결과 폴더 제외 |

---

## 0단계. PC에서 적용 (10분)

프로젝트 루트(`manage.py`가 있는 폴더)에 이 키트 압축을 푼다 (탐색기에서 풀어도 되고, 덮어쓰기 허용). 그다음 Git Bash에서:

```bash
bash apply_loadtest_kit.sh
git status                      # 위 파일 목록에 있는 것들만 바뀌었는지 확인
git add -A && git commit -m "add loadtest kit" && git push
```

- 스크립트는 여러 번 실행해도 안전하다 (이미 있으면 "이미 있음"으로 건너뜀).
- `import os`가 없는 등 예상과 다른 `settings.py`면 **아무것도 바꾸지 않고 중단**하고 이유를 알려준다.

## DNS (추가 비용 없음)

`staging.2535cjzok.com`은 **서브도메인이라 따로 살 필요가 없다.** 이미 가진 도메인의 DNS 관리 화면에서 레코드를 하나 추가하면 끝이다.

| 유형 | 이름(호스트) | 값 | TTL |
|---|---|---|---|
| A | `staging` | **prod와 같은 서버 공인 IP** | 300 (선택) |

- Cloudflare를 쓰면 프록시(주황 구름)를 **끄고 DNS only**로 둔다.
- 확인: `nslookup staging.2535cjzok.com` 결과가 prod IP와 같으면 된다 (반영에 몇 분 걸릴 수 있음).
- 같은 IP를 가리켜도 nginx가 요청의 `Host`(`server_name`)로 prod와 staging을 구분한다.

---

## 1단계. 서버에서 staging 구성 (1~2시간)

SSH 접속 후 순서대로. **DNS가 반영된 뒤에** 인증서 단계를 실행한다.

```bash
# (1) 스왑 2GB - 완충용. 이미 있으면 건너뛴다 (swapon --show 로 확인)
swapon --show
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# (2) nginx 기본 한도 상향 (기본 768은 동시 사용자 수백 명에서 먼저 한계에 걸린다)
sudo sed -i 's/worker_connections 768;/worker_connections 4096;/' /etc/nginx/nginx.conf
grep -q worker_rlimit_nofile /etc/nginx/nginx.conf || sudo sed -i '1i worker_rlimit_nofile 8192;' /etc/nginx/nginx.conf
sudo nginx -t && sudo systemctl reload nginx

# (3) 코드 받기 + staging 폴더/환경변수
cd ~/2535cjzok && git pull
mkdir -p staging-data/media
cp -n env.staging.example .env.staging
sed -i 's/your-domain.com/2535cjzok.com/g' .env.staging
sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_urlsafe(50))')|" .env.staging
sed -i "s|^LOADTEST_TOKEN=.*|LOADTEST_TOKEN=$(python3 -c 'import secrets;print(secrets.token_urlsafe(40))')|" .env.staging
grep '^LOADTEST_TOKEN=' .env.staging     # 이 값을 복사해둔다 (PC에서 쓸 토큰)

# (4) staging nginx + 인증서
sudo cp nginx-2535cjzok-staging.conf /etc/nginx/sites-available/2535cjzok-staging
sudo sed -i 's/your-domain.com/2535cjzok.com/g' /etc/nginx/sites-available/2535cjzok-staging
sudo ln -sf /etc/nginx/sites-available/2535cjzok-staging /etc/nginx/sites-enabled/2535cjzok-staging
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d staging.2535cjzok.com

# (5) 기동 + 마이그레이션
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build
docker compose -f docker-compose.staging.yml --env-file .env.staging run --rm web python manage.py migrate
docker compose -f docker-compose.staging.yml --env-file .env.staging ps     # web이 Up 인지
```

**중요**: `(2)`에서 `nginx.conf`에 `events` 블록을 새로 추가하지 말 것. 이미 있는 줄의 숫자만 바꾸는 명령이다 (`events`가 두 개면 `nginx -t`가 실패한다).

## 2단계. 시드 + 스모크

```bash
# 서버에서: 남 1,500 + 여 1,500 = 3,000명 (목표 회원 규모) + 매칭 조건
docker compose -f docker-compose.staging.yml --env-file .env.staging run --rm web \
  python manage.py seed_loadtest_data --pairs 1500 --density medium --csv staging-data/users.csv
```

출력의 `[점검]` 줄을 확인한다. **리스트가 빈 사람(0명)이 30%를 넘으면** `purge_loadtest_data --yes`로 지운 뒤 `--density high`로 다시 만든다.

```bash
# PC에서: CSV 가져오기 (키 파일을 쓰면 scp -i 키파일 ...)
scp ubuntu@서버주소:~/2535cjzok/staging-data/users.csv loadtest/users.csv

# PC에서: 한 사용자가 전체 흐름을 끝까지 타는지 (토큰은 위 (3)에서 복사한 값)
export LOADTEST_TOKEN=복사한_토큰
python loadtest/flow_check.py --base-url https://staging.2535cjzok.com --csv loadtest/users.csv --rounds 1
```

**통과 기준**: 마지막에 `성공: 1라운드 완료`가 나온다. 이게 나오기 전에는 어떤 부하도 걸지 않는다.

## 3단계 이후

`loadtest/README.md`의 3절(베이스라인)부터 이어간다. 전체 단계와 단계별 판정 기준은 대화에서 정리한 표를 따른다.

---

## 문제가 생기면

| 증상 | 원인 / 조치 |
|---|---|
| `nginx -t` 에서 `events directive is duplicate` | `events` 블록을 직접 추가했는지 확인. 하나만 있어야 한다 |
| certbot 실패 | DNS가 아직 안 퍼졌거나(`nslookup` 확인), 80 포트가 막혀 있음. 몇 분 뒤 재시도 |
| 스모크 `[00 login] ... 404` | `.env.staging`의 `LOADTEST_ENABLED=True`, 토큰 24자 이상, PC의 `LOADTEST_TOKEN` 일치 확인. 수정 후 `up -d`로 다시 기동 |
| 시드에서 `LOADTEST_ENABLED가 꺼진 환경` | `.env.staging` 확인 (`--env-file .env.staging`을 빠뜨렸는지도) |
| 스모크 `[05 chat start] ...` 실패 | 동시 대화 3명 제한이나 매너온도 평가 대기에 걸렸을 수 있음. 또는 채팅 요청 규격 가정이 실제와 다른 것이므로 **출력 전체를 그대로 공유** |
| `docker compose` 변수 경고 | `--env-file .env.staging`을 빠뜨린 것 |

## 테스트가 끝난 뒤

```bash
docker compose -f docker-compose.staging.yml --env-file .env.staging down     # 로그인 통로가 닫힌다
# 필요하면: sudo rm /etc/nginx/sites-enabled/2535cjzok-staging && sudo nginx -t && sudo systemctl reload nginx
# 필요하면: DNS에서 staging 레코드 삭제
```
