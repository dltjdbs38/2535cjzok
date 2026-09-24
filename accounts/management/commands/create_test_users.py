import random

from django.core.management.base import BaseCommand

from accounts.models import User

MALE_NAMES = ["민수", "철수", "경훈", "지훈", "성민", "동현", "재현", "우진"]
FEMALE_NAMES = ["서윤", "지은", "수빈", "하은", "예진", "다은", "나연", "소율"]


class Command(BaseCommand):
    help = "카카오 로그인 없이, 매칭 테스트용 승인된 가짜 회원을 만든다."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=3, help="만들 인원 수 (기본 3명)")
        parser.add_argument(
            "--gender", choices=["M", "F"], default="M", help="성별 (M=남성, F=여성, 기본 M)"
        )

    def handle(self, *args, **options):
        count = options["count"]
        gender = options["gender"]
        names = MALE_NAMES if gender == User.Gender.MALE else FEMALE_NAMES
        hobbies = list(User.Hobby.values)
        regions = list(User.Region.values)
        religions = list(User.Religion.values)

        created = []
        for _ in range(count):
            name = f"{random.choice(names)}{random.randint(1, 999)}"
            user = User.objects.create(
                username=f"test_{gender.lower()}_{name}",
                nickname=name,
                gender=gender,
                birth_year=random.randint(1991, 2001),  # 25~35세 범위
                height_cm=random.randint(177, 190) if gender == User.Gender.MALE else random.randint(155, 170),
                weight_kg=random.randint(55, 90),
                hobby_first=random.choice(hobbies),
                hobby_second=random.choice(hobbies),
                hobby_dislike=random.choice(hobbies),
                region=random.choice(regions),
                religion=random.choice(religions),
                is_smoker=random.choice([True, False]),
                intro="테스트 계정",
                approval_status=User.ApprovalStatus.APPROVED,  # 바로 매칭 대상이 되도록 승인 상태로 생성
            )
            created.append(user)

        self.stdout.write(
            self.style.SUCCESS(f"{count}명 생성 완료: " + ", ".join(u.nickname for u in created))
        )
