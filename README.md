# 2535cjzok - 1단계 (Django 뼈대 + 카카오 로그인)

## 구조
```
accounts/            # 회원 모델, 카카오 로그인 연동 담당 앱
  models.py           # 커스텀 User 모델 (카카오 프로필 + 매칭 필드)
  adapters.py          # 카카오 로그인 시 원본 데이터를 User 필드로 채워주는 어댑터
  admin.py             # 관리자 페이지에서 회원 목록/승인 상태 확인 (2단계 사전승인 기능의 기반)
  views.py, templates/  # 로그인 테스트용 임시 홈 화면
config/               # 프로젝트 설정 (settings.py, urls.py)
requirements.txt
.env.example
```

## 1. 로컬에서 실행하기

VSCode 터미널에서 이 폴더 기준으로:

```bash
# 1) 가상환경 만들고 켜기
python -m venv venv
source venv/Scripts/activate        # 리눅스면 venv\bin\activate

# 2) 패키지 설치
pip install -r requirements.txt

# 3) .env 파일 만들기
cp .env.example .env
# .env를 열어서 KAKAO_CLIENT_ID, KAKAO_CLIENT_SECRET을 실제 값으로 채워넣기
# (지난 단계에서 카카오 개발자센터 [앱 키]에서 복사해둔 값)

# 4) DB 테이블 만들기
python manage.py migrate

# 5) 관리자 계정 만들기 (Django Admin 접속용, 카카오 계정과는 별개)
python manage.py createsuperuser
(나는 aassdd38@naver.com 과 이름은 super로 만듦. 비번은 늘 하던거 특수기호없는.)

# 6) 서버 실행
python manage.py runserver

# 7) 테스트 유저 만들기
python manage.py create_test_users --count 3 --gender M 
# 남성 3명이 랜덤한 키/몸무게/취미/지역/종교/흡연여부로 바로 승인(APPROVED) 상태로

# 8) 테스트 유저로 실행
http://localhost:8000/dev/login-as/  에서 선택
```

## 2. 카카오 로그인 실제로 붙이기

1. 브라우저에서 `http://localhost:8000/` 접속 → "카카오로 로그인" 링크가 보여야 함
2. 이걸 누르면 카카오 로그인 화면으로 넘어가는데, 여기서 지난 단계에 등록해둔 **Redirect URI**가 정확히 일치해야 함
   - 카카오 개발자센터 > [카카오 로그인] > Redirect URI에 아래 주소가 등록돼 있어야 함:
     `http://localhost:8000/accounts/kakao/login/callback/`
   - 이 프로젝트는 `django-allauth`의 기본 콜백 경로를 그대로 쓰기 때문에 URI가 정확히 이 형태여야 함
3. 로그인에 성공하면 다시 `http://localhost:8000/`로 돌아오면서, 카카오에서 가져온 닉네임/프로필사진/출생연도/성별이 화면에 그대로 출력됨
4. **출생연도/성별이 빈 값으로 나오면** → 아직 카카오 쪽 동의 단계 설정 권한(심사)을 못 받은 상태라 그런 거니 정상. 지난 단계에서 얘기한 대로 심사 통과 전까지는 직접 입력 폴백으로 채워야 함 (2단계에서 구현 예정)

## 3. Django Admin에서 회원 확인하기

`http://localhost:8000/admin/` 접속 → 5번에서 만든 관리자 계정으로 로그인 → [Accounts] > [Users]에서
카카오로 로그인한 회원들의 닉네임/성별/출생연도/승인 상태를 목록으로 바로 확인할 수 있음.
이 화면이 나중에 "가입 사전승인" 기능의 기반이 됨.

## 트러블슈팅

- **`Invalid redirect_uri` 에러(KOE006 등)**: Redirect URI가 카카오 개발자센터에 등록한 값과 한 글자라도 다르면 발생. 위 2번의 URI를 복사해서 그대로 등록했는지 확인.
- **관리자 로그인 후 화면이 이상하게 나오면**: Django Admin > Sites > example.com 항목의 도메인을 `localhost:8000`으로 바꿔주면 됨 (필수는 아니지만 나중에 이메일 링크 등에 쓰일 때 깔끔해짐).
- **`.env`가 반영이 안 되는 것 같으면**: `python manage.py runserver`를 완전히 껐다 다시 켜야 함 (환경변수는 서버 시작 시점에만 읽힘).

## 다음 단계

여기까지 되면 1단계는 끝. 다음은 프로필 등록 화면(얼굴/전신사진 업로드, 키/몸무게/취미/지역/종교/흡연 입력) +
매칭 조건 설정 + 매칭 리스트로 넘어가면 됨.


## 배포 (오라클 프리티어)

오라클로 가면 직접 챙겨야 할 게 많아지는데 하나씩 정리해서 갈게. 먼저 Docker 기반으로 갈 거니까 필요한 설정 파일부터 만들고, 그다음 전체 순서를 안내할게.YAML 문법도 정상 확인했어. 이제 전체 순서를 단계별로 정리할게.`docker-compose.yml`은 프로젝트 루트에, `nginx-2535cjzok.conf`는 그냥 참고용 파일이라 로컬 아무 데나 두면 돼(서버에 올릴 때 내용만 복사해서 쓸 거야).

---

## 전체 그림

```
[핸드폰/PC 브라우저] → [nginx (80/443)] → [gunicorn (127.0.0.1:8000, Docker 컨테이너)] → [SQLite]
                              ↑
                        Let's Encrypt SSL
```

nginx는 서버에 직접 설치(컨테이너 아님), Django 앱은 Docker 컨테이너로 돌리는 구조야. 이렇게 나누는 이유는: SSL 인증서 자동 갱신(certbot)이 nginx가 호스트에 직접 있을 때 제일 간단하고 안정적이라서야.

## Phase 1 — 오라클 클라우드 인스턴스 만들기

1. [oracle.com/cloud/free](https://oracle.com/cloud/free)에서 Always Free 계정 가입 (카드 등록은 필요하지만 실제 결제는 안 됨 — Free 티어 안에서만 쓰면)
2. 콘솔 → Compute → Instances → "Create Instance"
3. Image: **Ubuntu** (최신 LTS) / Shape: **Ampere (ARM) A1.Flex** — Always Free 안에서 제일 넉넉한 사양(최대 4 OCPU, 24GB RAM 무료)
4. SSH 키 페어 생성 → **개인키(.key 파일) 다운로드 꼭 받아두기** (이게 없으면 서버에 못 들어감)
5. 생성 완료되면 콘솔에 **공인 IP 주소**가 뜸 — 이거 메모

**참고**: ARM 인스턴스가 가끔 "용량 부족(Out of capacity)"으로 생성이 바로 안 될 때가 있어. 그럴 땐 몇 분~몇 시간 뒤에 다시 시도하면 되는 경우가 많아 — 오라클 프리티어 인기가 많아서 생기는 흔한 현상이야.

## Phase 2 — 방화벽 두 군데 다 열기 (오라클은 이게 자주 놓치는 함정이야)

오라클은 **클라우드 레벨 방화벽**이랑 **서버 안 OS 방화벽**이 따로 있어서, 둘 다 열어야 접속이 돼.

**① 클라우드 콘솔에서**: 인스턴스 상세 → 서브넷 클릭 → Security List → "Add Ingress Rules"에서 **80번, 443번 포트**를 `0.0.0.0/0`으로 추가.

**② 서버 접속해서 OS 방화벽도**:
```bash
ssh -i 다운받은키.key ubuntu@공인IP주소

sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```
(오라클 우분투 이미지는 기본적으로 22번 포트 말고 다 막혀있어서, 이 단계를 빼먹으면 ①만 해도 계속 접속이 안 돼.)

## Phase 3 — 서버에 Docker 설치 + 프로젝트 올리기

```bash
# Docker 설치
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# 여기서 한 번 로그아웃 후 재접속해야 docker 명령어에 sudo 안 붙여도 됨

# 프로젝트 가져오기 (GitHub에 올려놨다면)
git clone https://github.com/너의계정/2535cjzok.git
cd 2535cjzok

# .env 파일은 git에 안 올라가 있으니 서버에서 직접 새로 만들기
nano .env
# (KAKAO_CLIENT_ID, KAKAO_CLIENT_SECRET, DJANGO_SECRET_KEY, DJANGO_DEBUG=False,
#  DJANGO_ALLOWED_HOSTS=도메인, DJANGO_CSRF_TRUSTED_ORIGINS=https://도메인 채워넣기)

# SQLite 파일을 미리 만들어둬야 함 (안 그러면 Docker가 파일 대신 폴더를 만들어버림)
touch db.sqlite3
mkdir -p media

docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

## Phase 4 — 도메인 연결

1. 도메인 구입 (가비아/Namecheap 등, 연 1~2만원)
2. 그 도메인 관리 화면에서 **A 레코드**를 오라클 인스턴스의 **공인 IP**로 연결
3. 반영되는 데 몇 분~몇 시간 걸릴 수 있음 (`nslookup 도메인` 으로 확인 가능)

## Phase 5 — nginx + 무료 SSL(Let's Encrypt)

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx

# 아까 만든 nginx-2535cjzok.conf 내용을 서버에 붙여넣기 (server_name만 실제 도메인으로 바꿔서)
sudo nano /etc/nginx/sites-available/2535cjzok
sudo ln -s /etc/nginx/sites-available/2535cjzok /etc/nginx/sites-enabled/
sudo nginx -t   # 문법 체크
sudo systemctl restart nginx

# SSL 인증서 발급 - 이 한 줄이 nginx 설정에 https 블록까지 자동으로 추가해줌
sudo certbot --nginx -d 너의도메인.com
```

certbot이 인증서 자동 갱신도 알아서 등록해줘서, 갱신은 신경 안 써도 돼.

## Phase 6 — 카카오 개발자센터 갱신

[카카오 로그인] > [플랫폼]에 `https://너의도메인.com` 추가, Redirect URI에 `https://너의도메인.com/accounts/kakao/login/callback/` 추가 (localhost용은 그대로 둬도 됨).

## Phase 7 — 핸드폰으로 테스트

`https://너의도메인.com` 을 핸드폰 크롬에 쳐서 카카오 로그인부터 끝까지 해보면 끝.

---

## 나중에 코드 수정하고 다시 올릴 때

```bash
git pull
docker compose up -d --build
docker compose exec web python manage.py migrate   # 모델 바뀐 게 있으면
```
