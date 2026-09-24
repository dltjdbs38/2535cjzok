from django.conf import settings
from django.db import models

from accounts.models import User


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
    preferred_height_codes = models.CharField(max_length=100, blank=True)  # 복수선택, 콤마구분

    # 상대방에게 원하는 취미. (참고: 회원 본인의 취미는 accounts.User.hobby_first 등에 따로 저장돼 있음 -
    # 그건 "내 취미가 뭔지"고, 이건 "상대 취미가 뭐였으면 좋겠는지"라 서로 다른 정보임)
    preferred_hobby_first = models.CharField(max_length=20, choices=User.Hobby.choices, blank=True)
    preferred_hobby_second = models.CharField(max_length=20, choices=User.Hobby.choices, blank=True)
    preferred_hobby_dislike = models.CharField(max_length=20, choices=User.Hobby.choices, blank=True)

    # 음악 취향(선택) - 최근 자주 듣거나 좋아하는 가수 최대 3명, 항목별로 따로 저장.
    favorite_artist_1 = models.CharField(max_length=50, blank=True)
    favorite_artist_2 = models.CharField(max_length=50, blank=True)
    favorite_artist_3 = models.CharField(max_length=50, blank=True)

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

    @property
    def preferred_height_codes_list(self):
        return [v for v in self.preferred_height_codes.split(",") if v]

    def height_ranges_cm(self):
        # 선택된 키 코드 각각의 (최소, 최대미만) 범위를 리스트로 돌려준다.
        # 매칭할 때는 이 여러 범위 중 "하나라도" 맞으면 통과(OR)시키면 된다.
        return [HEIGHT_RANGE_CM[code] for code in self.preferred_height_codes_list if code in HEIGHT_RANGE_CM]

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
