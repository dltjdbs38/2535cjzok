from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


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
