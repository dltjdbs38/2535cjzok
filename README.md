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
