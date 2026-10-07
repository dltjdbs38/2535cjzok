"""
부하테스트용 가짜 회원을 대량으로 만든다.

기존 create_test_users와 다른 점:
  - MatchingPreference(매칭 조건)까지 같이 만든다. 이 서비스는 "상호 매칭"이라 상대도 조건을 저장해둬야
    리스트에 뜨는데, 조건이 없으면 매칭 리스트가 항상 텅 비어서 부하테스트가 의미가 없어진다.
  - username이 'loadtest_'로 시작한다 -> 로그인 통로(accounts/loadtest.py)가 이 계정들만 허용하고,
    purge_loadtest_data로 한 번에 지울 수 있다.
  - JMeter가 읽을 CSV(user_id, username, gender, partner_id)를 만들어준다.
  - 같은 --seed면 항상 똑같은 데이터가 나온다 (재현 가능한 테스트 = 개선 전/후 비교가 공정해짐).

사용 예:
  python manage.py seed_loadtest_data --pairs 250 --density medium --csv loadtest/users.csv
"""
import csv
import os
import random
import time

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from matching.models import MatchingPreference

PREFIX = "loadtest_"

# 성별에 따라 상대 키 선택지가 다르다 (여성 -> 원하는 남성 키 / 남성 -> 원하는 여성 키).
HEIGHT_CODES_WANTED_BY_MALE = ["F_150_DOWN", "F_150_160", "F_160_170_UNDER", "F_170_180"]
HEIGHT_CODES_WANTED_BY_FEMALE = ["M_160_170", "M_170_180_UNDER", "M_180_UP"]

# density = 매칭 조건이 얼마나 넓은지. 넓을수록 한 사람 화면에 뜨는 후보 수가 늘어난다.
# 실제 서비스는 조건을 전부 필수로 입력받아 리스트가 비교적 좁게 나오므로 medium을 기본으로 둔다.
DENSITY = {
    #          지역 개수      취미싫어 조건 비율  취미선호 조건 비율  종교 개수     비흡연만 원하는 비율
    "low": dict(regions=(1, 3), p_dislike=0.6, p_hobbies=0.8, religions=(1, 2), p_nonsmoker_only=0.8),
    "medium": dict(regions=(3, 6), p_dislike=0.3, p_hobbies=0.5, religions=(2, 3), p_nonsmoker_only=0.6),
    "high": dict(regions=(6, 10), p_dislike=0.1, p_hobbies=0.2, religions=(3, 4), p_nonsmoker_only=0.4),
}


class Command(BaseCommand):
    help = "부하테스트용 가짜 회원(+매칭 조건)을 대량 생성하고 JMeter용 CSV를 만든다."

    def add_arguments(self, parser):
        parser.add_argument("--pairs", type=int, default=100, help="남/여 각각 몇 명 (총 인원은 2배). 기본 100")
        parser.add_argument("--density", choices=list(DENSITY), default="medium", help="매칭 조건의 넓이")
        parser.add_argument("--seed", type=int, default=2535, help="같은 값이면 항상 같은 데이터가 나온다")
        parser.add_argument("--csv", default="loadtest/users.csv", help="JMeter가 읽을 CSV 저장 경로")
        parser.add_argument("--report-sample", type=int, default=20, help="매칭 리스트 크기 점검에 쓸 표본 수 (0이면 생략)")
        parser.add_argument(
            "--allow-non-staging", action="store_true",
            help="LOADTEST_ENABLED가 꺼진 환경(=prod일 수 있음)에서도 강제로 실행. 로컬 연습용 외에는 쓰지 말 것",
        )

    def handle(self, *args, **opts):
        # 실수로 prod DB에서 돌려 실제 회원 매칭 리스트에 가짜 회원이 섞이는 사고를 막는 가드.
        # staging(.env.staging)에는 LOADTEST_ENABLED=True가 있고 prod에는 없으니, 그 차이로 구분한다.
        if not getattr(settings, "LOADTEST_ENABLED", False) and not opts["allow_non_staging"]:
            raise CommandError(
                "LOADTEST_ENABLED가 꺼진 환경이야 (prod일 수 있음). staging에서 돌리는 게 맞다면 "
                "LOADTEST_ENABLED=True를 설정해줘. 로컬 연습이면 --allow-non-staging."
            )
        if User.objects.filter(username__startswith=PREFIX).exists():
            raise CommandError("이미 loadtest_ 계정이 있어. 먼저 `python manage.py purge_loadtest_data --yes`로 지워줘.")

        rng = random.Random(opts["seed"])
        n = opts["pairs"]
        cfg = DENSITY[opts["density"]]
        regions = list(User.Region.values)
        # 실제 서비스처럼 수도권에 몰려 있게 가중치를 준다 (전 지역 균등 분포는 비현실적).
        region_weights = [30 if r.startswith("GYEONGGI") else 40 / (len(regions) - 2) for r in regions]
        hobbies = list(User.Hobby.values)
        religions = list(User.Religion.values)

        unusable_password = make_password(None)  # 비밀번호 해시 계산은 느리니 한 번만 만들어 재사용
        now = timezone.now()

        users, profile_of = [], {}
        for gender, tag in ((User.Gender.MALE, "m"), (User.Gender.FEMALE, "f")):
            for i in range(1, n + 1):
                h_first, h_second, h_dislike = rng.sample(hobbies, 3)  # 서로 다른 3개
                profile = dict(
                    username=f"{PREFIX}{tag}_{i:05d}",
                    nickname=f"{'남' if tag == 'm' else '여'}{i:05d}",
                    gender=gender,
                    birth_year=rng.randint(1991, 2001),
                    height_cm=rng.randint(168, 190) if tag == "m" else rng.randint(150, 175),
                    weight_kg=rng.randint(45, 90),
                    hobby_first=h_first,
                    hobby_second=h_second,
                    hobby_dislike=h_dislike,
                    region=rng.choices(regions, weights=region_weights)[0],
                    religion=rng.choice(religions),
                    is_smoker=rng.random() < 0.25,
                    intro="loadtest",
                    approval_status=User.ApprovalStatus.APPROVED,
                    password=unusable_password,
                    last_login=now,  # 휴면(180일 미접속)으로 분류돼 매칭에서 빠지지 않게
                )
                profile_of[profile["username"]] = profile
                users.append(User(**profile))

        User.objects.bulk_create(users, batch_size=500)
        by_username = {u.username: u for u in User.objects.filter(username__startswith=PREFIX)}

        prefs = []
        for username, p in profile_of.items():
            is_male = p["gender"] == User.Gender.MALE
            wanted_regions = {p["region"]}  # 보통 본인과 같은 지역을 원한다
            k = rng.randint(*cfg["regions"])
            wanted_regions.update(rng.sample(regions, min(k, len(regions))))
            wanted_religions = {p["religion"]}
            wanted_religions.update(rng.sample(religions, rng.randint(*cfg["religions"])))
            pool = HEIGHT_CODES_WANTED_BY_MALE if is_male else HEIGHT_CODES_WANTED_BY_FEMALE
            height_codes = rng.sample(pool, rng.randint(2, min(3, len(pool))))
            smoking = ["NON_SMOKER"] if rng.random() < cfg["p_nonsmoker_only"] else ["NON_SMOKER", "SMOKER"]

            pref = MatchingPreference(
                user=by_username[username],
                preferred_regions=",".join(sorted(wanted_regions)),
                preferred_religions=",".join(sorted(wanted_religions)),
                preferred_smoking=",".join(smoking),
                preferred_height_codes=",".join(height_codes),
            )
            if rng.random() < cfg["p_dislike"]:
                pref.preferred_hobby_dislike = rng.choice(hobbies)
            if rng.random() < cfg["p_hobbies"]:
                pref.preferred_hobby_first, pref.preferred_hobby_second = rng.sample(hobbies, 2)
            prefs.append(pref)
        MatchingPreference.objects.bulk_create(prefs, batch_size=500)

        self._write_csv(opts["csv"], by_username, n)
        self.stdout.write(self.style.SUCCESS(f"회원 {2 * n}명 + 매칭조건 {len(prefs)}건 생성, CSV: {opts['csv']}"))

        if opts["report_sample"] > 0:
            self._report_list_sizes(by_username, opts["report_sample"])

    def _write_csv(self, path, by_username, n):
        """남/여를 번갈아 적는다. 스레드 수가 적을 때도 성별이 한쪽으로 쏠리지 않게 + 짝(partner)을 같이 적는다."""
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")  # \r\n이면 JMeter에서 마지막 컬럼 값 끝에 \r이 섞일 수 있다
            w.writerow(["user_id", "username", "gender", "partner_id"])
            for i in range(1, n + 1):
                m, fe = by_username[f"{PREFIX}m_{i:05d}"], by_username[f"{PREFIX}f_{i:05d}"]
                w.writerow([m.id, m.username, "M", fe.id])
                w.writerow([fe.id, fe.username, "F", m.id])

    def _report_list_sizes(self, by_username, sample_size):
        """실제 매칭 로직(_candidates_for)으로 표본 사용자들의 리스트 크기를 재본다. 0이 많으면 데이터가 너무 빡빡한 것."""
        from matching.views import _candidates_for

        usernames = sorted(by_username)
        step = max(1, len(usernames) // sample_size)
        sizes, elapsed = [], []
        for username in usernames[::step][:sample_size]:
            viewer = by_username[username]
            started = time.perf_counter()
            sizes.append(len(_candidates_for(viewer, viewer.matching_preference)))
            elapsed.append((time.perf_counter() - started) * 1000)
        zero = sum(1 for s in sizes if s == 0)
        self.stdout.write(
            f"[점검] 표본 {len(sizes)}명의 매칭 리스트 크기: 평균 {sum(sizes) / len(sizes):.1f}명 "
            f"(최소 {min(sizes)}, 최대 {max(sizes)}), 0명인 사람 {zero}명 / "
            f"_candidates_for 평균 {sum(elapsed) / len(elapsed):.1f}ms"
        )
        if zero > len(sizes) * 0.3:
            self.stdout.write(self.style.WARNING("리스트가 빈 사람이 30%를 넘어. --density high로 다시 만들어보는 걸 추천해."))
