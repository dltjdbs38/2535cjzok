from django.conf import settings
from django.db import models


class SmokingPreference(models.TextChoices):
    NON_SMOKER = "NON_SMOKER", "비흡연"
    SMOKER = "SMOKER", "흡연"


# 키 조건은 txt 명세상 "내 성별에 따라 상대방 키 선택지가 다르게" 설계되어 있다.
# 여성 유저 -> 원하는 남성 키 선택지 / 남성 유저 -> 원하는 여성 키 선택지.
HEIGHT_CHOICES_FOR_FEMALE = [  # 여성 유저가 고르는, 원하는 남성 키
    ("M_160_170", "160~170"),
    ("M_170_180_UNDER", "170~180 미만"),
    ("M_180_UP", "180 이상"),
]
HEIGHT_CHOICES_FOR_MALE = [  # 남성 유저가 고르는, 원하는 여성 키
    ("F_150_DOWN", "150 이하"),
    ("F_150_160", "150~160"),
    ("F_160_170_UNDER", "160~170 미만"),
    ("F_170_180", "170~180"),
]
HEIGHT_CHOICES = HEIGHT_CHOICES_FOR_FEMALE + HEIGHT_CHOICES_FOR_MALE

# 코드 -> (최소 키 cm, 최대 키 cm 미만) 매핑. 상한이 없으면 None.
HEIGHT_RANGE_CM = {
    "M_160_170": (160, 170),
    "M_170_180_UNDER": (170, 180),
    "M_180_UP": (180, None),
    "F_150_DOWN": (None, 150 + 1),  # 150 이하 -> 150cm까지 포함
    "F_150_160": (150, 160),
    "F_160_170_UNDER": (160, 170),
    "F_170_180": (170, 180 + 1),  # 170~180 -> 180cm까지 포함
}


class MatchingPreference(models.Model):
    """
    "내가 원하는 상대방 조건". 회원 본인의 프로필(accounts.User)과는 별개 정보라
    매칭 도메인 전용 모델로 분리했다.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="matching_preference"
    )

    # 콤마로 구분된 선택값 문자열로 저장한다 (SQLite엔 배열 필드가 없어서 제일 단순한 방식을 씀).
    preferred_regions = models.CharField(max_length=300, blank=True)
    preferred_religions = models.CharField(max_length=200, blank=True)
    preferred_smoking = models.CharField(max_length=100, blank=True)
    preferred_height_code = models.CharField(max_length=20, choices=HEIGHT_CHOICES, blank=True)

    favorite_artists = models.CharField(max_length=200, blank=True)  # 선택 항목, 최대 3명 텍스트로 저장

    updated_at = models.DateTimeField(auto_now=True)

    @property
    def preferred_regions_list(self):
        return [v for v in self.preferred_regions.split(",") if v]

    @property
    def preferred_religions_list(self):
        return [v for v in self.preferred_religions.split(",") if v]

    @property
    def preferred_smoking_list(self):
        return [v for v in self.preferred_smoking.split(",") if v]

    def height_range_cm(self):
        return HEIGHT_RANGE_CM.get(self.preferred_height_code, (None, None))

    def __str__(self):
        return f"{self.user}의 매칭 조건"


class Like(models.Model):
    """
    매칭 프로필 화면에서 누르는 '좋아요'. txt 명세대로 상대에게 알림은 안 가고,
    누른 사람의 MY > 좋아요 프로필 목록에서만 북마크처럼 보인다.
    """

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes_given"
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes_received"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("from_user", "to_user")

    def __str__(self):
        return f"{self.from_user} -> {self.to_user}"
