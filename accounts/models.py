from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    2535cjzok 회원 모델.
    Django 기본 User(AbstractUser)를 상속해서 카카오 프로필 정보와
    매칭에 필요한 프로필 필드를 추가했다.
    """

    class Gender(models.TextChoices):
        MALE = "M", "남성"
        FEMALE = "F", "여성"

    class Hobby(models.TextChoices):
        GAME = "GAME", "게임"
        GYM = "GYM", "헬스"
        SPORTS = "SPORTS", "스포츠 직접하기"
        CAFE = "CAFE", "분위기 좋은 카페가기"
        NETFLIX = "NETFLIX", "넷플릭스보기"
        BASEBALL = "BASEBALL", "야구보기"
        SOCCER = "SOCCER", "축구보기"
        WEBTOON = "WEBTOON", "만화보기"
        READING = "READING", "책읽기"
        COOKING = "COOKING", "요리하기"

    class Religion(models.TextChoices):
        NONE = "NONE", "무교"
        CHRISTIAN = "CHRISTIAN", "기독교"
        BUDDHIST = "BUDDHIST", "불교"
        CATHOLIC = "CATHOLIC", "성당"

    class Region(models.TextChoices):
        # 매칭 조건에서 체크박스로 선택하는 목록이랑 정확히 값이 일치해야 필터링이 되므로,
        # 자유 텍스트가 아니라 고정 선택지로 관리한다. (필요하면 나중에 목록만 추가하면 됨)
        GYEONGGI_SEOUL_EAST = "GYEONGGI_SEOUL_EAST", "경기/서울 동부"
        GYEONGGI_SEOUL_WEST = "GYEONGGI_SEOUL_WEST", "경기/서울 서부"
        GANGWON = "GANGWON", "강원"
        CHUNGBUK = "CHUNGBUK", "충북"
        CHUNGNAM = "CHUNGNAM", "충남"
        DAEJEON = "DAEJEON", "대전"
        GYEONGBUK = "GYEONGBUK", "경북"
        GYEONGNAM = "GYEONGNAM", "경남"
        DAEGU = "DAEGU", "대구"
        BUSAN = "BUSAN", "부산"
        ULSAN = "ULSAN", "울산"
        JEONBUK = "JEONBUK", "전북"
        JEONNAM = "JEONNAM", "전남"
        GWANGJU = "GWANGJU", "광주"
        JEJU = "JEJU", "제주"

    class ApprovalStatus(models.TextChoices):
        # 프로필(얼굴/전신사진 등)을 아직 안 낸 상태. 카카오 로그인만 한 직후 기본값.
        INCOMPLETE = "INCOMPLETE", "프로필 미입력"
        PENDING = "PENDING", "심사중"
        APPROVED = "APPROVED", "승인"
        REJECTED = "REJECTED", "거부"

    # --- 카카오 로그인으로 채워지는 필드 ---
    # 카카오 회원번호(고유 id). 카카오 쪽 값이므로 문자열로 저장하고 유니크 제약을 건다.
    kakao_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    nickname = models.CharField(max_length=50, blank=True)  # 카카오톡 닉네임
    profile_image_url = models.URLField(blank=True)  # 카카오가 준 원본 URL (참고 기록용, 화면 표시엔 안 씀)
    # 위 URL은 카톡 프사가 바뀌면 깨질 수 있어서, 실제 화면에 보여줄 땐 이 필드(우리 서버에 저장한 사본)를 쓴다.
    profile_photo = models.ImageField(upload_to="kakao_profile/", blank=True)
    # 카카오에서 출생연도(birthyear)를 못 받아오면 None으로 두고,
    # 회원가입 화면에서 직접 입력받아 채운다. (지난 대화에서 정한 폴백 플랜)
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True)

    # --- 사용자가 직접 입력하는 프로필 필드 ---
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    weight_kg = models.PositiveSmallIntegerField(null=True, blank=True)
    hobby_first = models.CharField(max_length=20, choices=Hobby.choices, blank=True)
    hobby_second = models.CharField(max_length=20, choices=Hobby.choices, blank=True)
    hobby_dislike = models.CharField(max_length=20, choices=Hobby.choices, blank=True)
    region = models.CharField(max_length=30, choices=Region.choices, blank=True)  # 거주 및 활동 지역
    religion = models.CharField(max_length=20, choices=Religion.choices, blank=True)
    is_smoker = models.BooleanField(null=True, blank=True)  # 흡연 여부
    intro = models.CharField(max_length=20, blank=True, default="-")  # 소개 한마디, 최대 20자

    # --- 가입 승인 심사용 업로드 사진 (카카오톡 프사와 대조해서 본인 확인하는 용도) ---
    face_photo = models.ImageField(upload_to="approval/face/", null=True, blank=True)
    body_photo = models.ImageField(upload_to="approval/body/", null=True, blank=True)

    # --- 가입 승인/신뢰도 관련 ---
    approval_status = models.CharField(
        max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.INCOMPLETE
    )
    rejected_reason = models.CharField(max_length=200, blank=True)  # 거부 시 사유(내부 기록용)
    # 심사 거부 누적 횟수. 승인될 때마다 0으로 초기화되고(승인마다 "2번" 기회가 새로 주어짐),
    # 한 심사 사이클(최초 가입이든, 승인 후 정보 수정으로 인한 재심사든) 안에서 2번 거부되면
    # 그 즉시 is_blacklisted가 True로 바뀌며 영구퇴출된다.
    rejection_count = models.PositiveSmallIntegerField(default=0)
    # 영구퇴출. 심사 2회 거부로 자동으로 켜지거나, 가입 이후 신고 누적 등으로 관리자가 직접 켤 수도 있다.
    # 한 번이라도 True가 되면 동일 카카오 계정으로는 영원히 재가입/재심사가 불가능해진다.
    is_blacklisted = models.BooleanField(default=False)
    profile_submitted_at = models.DateTimeField(null=True, blank=True)  # 프로필 제출 시각 (3일 SLA 기준)
    manner_temp = models.DecimalField(max_digits=4, decimal_places=1, default=36.5)  # 매너온도

    @property
    def is_approved(self):
        # 예전 코드(대화방 접근 체크 등)와의 호환, 그리고 템플릿에서 쓰기 편하게 남겨둔 헬퍼.
        return self.approval_status == self.ApprovalStatus.APPROVED

    @property
    def can_retry_signup(self):
        # 거부됐지만 아직 영구퇴출(블랙리스트)까지는 안 간 상태 - 다시 프로필을 낼 수 있다.
        # (영구퇴출은 거부 2회째에 자동으로 켜지므로, 여기 도달했다는 건 항상 1회째 거부라는 뜻)
        return self.approval_status == self.ApprovalStatus.REJECTED and not self.is_blacklisted

    def __str__(self):
        return self.nickname or self.username
