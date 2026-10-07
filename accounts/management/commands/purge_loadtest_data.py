"""
seed_loadtest_data로 만든 가짜 회원(loadtest_*)과, 그 계정들에 딸린 데이터(매칭조건/좋아요/대화방/메시지 등)를
한 번에 지운다. 테스트를 다시 처음부터 돌리기 전에, 혹은 실수로 prod DB에 시드를 넣었을 때 정리용으로 쓴다.

  python manage.py purge_loadtest_data --yes
"""
from django.core.management.base import BaseCommand

from accounts.models import User

PREFIX = "loadtest_"


class Command(BaseCommand):
    help = "loadtest_ 로 시작하는 부하테스트용 회원과 딸린 데이터를 전부 삭제한다."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="확인 없이 바로 삭제 (없으면 개수만 보여주고 끝)")

    def handle(self, *args, **opts):
        qs = User.objects.filter(username__startswith=PREFIX)
        count = qs.count()
        if not opts["yes"]:
            self.stdout.write(f"삭제 대상 {count}명. 실제로 지우려면 --yes를 붙여줘.")
            return
        # FK가 CASCADE라 딸린 매칭조건/좋아요/대화방/메시지/평가/신고도 같이 지워진다.
        deleted, detail = qs.delete()
        self.stdout.write(self.style.SUCCESS(f"총 {deleted}개 행 삭제 (회원 {count}명 포함): {detail}"))
