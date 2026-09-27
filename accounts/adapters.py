import requests
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.core.files.base import ContentFile


def download_kakao_photo(user, image_url):
    """
    카카오 프사 URL에서 실제 이미지를 받아 우리 서버(profile_photo)에 저장한다.
    save_user(신규가입)와 pre_social_login(기존 회원 재로그인) 양쪽에서 재사용한다.
    """
    if not image_url:
        return
    try:
        response = requests.get(image_url, timeout=5)
        response.raise_for_status()
        filename = f"kakao_{user.kakao_id}.jpg"
        user.profile_photo.save(filename, ContentFile(response.content), save=True)
    except Exception:
        # 다운로드가 실패해도(네트워크 오류, 손상된 이미지 등) 로그인 자체는 막지 않는다.
        pass


class AccountAdapter(DefaultAccountAdapter):
    """
    일반(이메일/아이디+비밀번호) 회원가입을 완전히 막는 어댑터.
    django-allauth는 include('allauth.urls')만 붙이면 /accounts/signup/ 같은
    카카오와 무관한 일반 가입 화면을 기본으로 열어주는데, 우리 서비스는
    "카카오톡으로만 로그인 가능"이 원칙이라 이 경로 자체를 막아야 한다.
    (카카오 로그인/가입은 SocialAccountAdapter가 따로 처리하므로 영향 없음)
    """

    def is_open_for_signup(self, request):
        return False


class KakaoSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    카카오 로그인이 성공하면 allauth가 이 어댑터의 populate_user()를 호출한다.
    카카오가 내려준 원본 응답(extra_data)에서 닉네임/프로필사진/출생연도/성별을 꺼내
    우리 User 모델 필드에 채워 넣는 역할.
    """

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)

        if sociallogin.account.provider != "kakao":
            return user

        # extra_data는 "카카오 로그인 - 사용자 정보 조회 API"가 반환하는 JSON 그대로다.
        # 예: {"id": 123, "kakao_account": {"profile": {...}, "birthyear": "1998", "gender": "male"}}
        extra = sociallogin.account.extra_data
        kakao_account = extra.get("kakao_account", {})
        profile = kakao_account.get("profile", {})

        user.kakao_id = str(extra.get("id", ""))
        user.nickname = profile.get("nickname", "")
        user.profile_image_url = profile.get("profile_image_url", "")

        # 출생연도는 아직 카카오 심사(동의 단계 설정 권한)를 통과하기 전이라면
        # 응답 자체에 아예 안 들어있을 수 있다. 그 경우 None으로 남겨두고
        # 회원가입 마무리 화면에서 직접 입력받아 채우면 된다.
        birthyear = kakao_account.get("birthyear")
        if birthyear:
            user.birth_year = int(birthyear)

        gender = kakao_account.get("gender")  # "male" 또는 "female"
        if gender == "male":
            user.gender = user.Gender.MALE
        elif gender == "female":
            user.gender = user.Gender.FEMALE

        # username은 필수 필드라 카카오 회원번호를 기반으로 채워준다 (화면에 노출되지 않음).
        if not user.username:
            user.username = f"kakao_{user.kakao_id}"

        return user

    def pre_social_login(self, request, sociallogin):
        # save_user()는 "완전히 새로 가입하는 순간"에만 호출된다. 이미 가입된 회원이 재로그인할
        # 때는 이 메서드가 대신 매번 불리는데, 여기서 profile_photo가 비어있는 경우(예: 이
        # 다운로드 로직이 생기기 전에 가입했던 회원)를 채워 넣어준다. 이미 채워져 있으면 매번
        # 다시 받아오진 않는다(불필요한 네트워크 요청 방지).
        if sociallogin.is_existing:
            user = sociallogin.user
            if not user.profile_photo:
                extra = sociallogin.account.extra_data
                image_url = extra.get("kakao_account", {}).get("profile", {}).get("profile_image_url", "")
                download_kakao_photo(user, image_url)

    def save_user(self, request, sociallogin, form=None):
        # populate_user()는 아직 저장 전 단계라 여기서(실제로 저장되는 시점) 사진을 다운로드한다.
        # 카카오 프사 URL은 사용자가 나중에 프사를 바꾸면 깨질 수 있어서,
        # 우리 서버 스토리지에 실제 파일로 복사해두고 화면에는 그 사본을 쓴다.
        user = super().save_user(request, sociallogin, form)
        download_kakao_photo(user, user.profile_image_url)
        return user