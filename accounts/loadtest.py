"""
부하테스트 전용 로그인 통로.

왜 필요한가:
  이 서비스는 카카오 로그인만 되는데, JMeter 같은 도구는 카카오 OAuth 화면(브라우저 리다이렉트 +
  카카오 계정 인증)을 통과할 수 없다. 그렇다고 개발용 `dev_login_as`는 DEBUG=True에서만 열리고,
  배포(DEBUG=False)에서는 막혀 있다. 그래서 "부하테스트용으로 만든 가짜 계정"에 한해서만
  세션을 발급해주는 좁은 통로를 따로 둔다.

이 통로가 위험해지지 않도록 걸어둔 안전장치 (전부 통과해야만 로그인됨):
  1. LOADTEST_ENABLED=True 환경변수가 있을 때만 URL 자체가 등록된다 (평소엔 404, 존재 자체가 안 보임).
  2. LOADTEST_TOKEN(24자 이상)을 X-Loadtest-Token 헤더로 보내야 한다. 짧거나 비어 있으면 통로가 닫힌다.
  3. username이 'loadtest_'로 시작하는 계정만 로그인시킨다. 토큰이 유출돼도 실제 회원 계정은 못 건드린다.

운영(prod) 서버에는 절대 켜지 말고, 별도 staging 환경에서만 켠다.
"""
import hmac

from django.conf import settings
from django.contrib.auth import login
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from .models import User

LOADTEST_USERNAME_PREFIX = "loadtest_"
MIN_TOKEN_LENGTH = 24


@csrf_exempt  # 로그인 요청 자체에는 CSRF 토큰이 아직 없다. 대신 아래 비밀 토큰이 그 역할을 한다.
def loadtest_login(request, user_id):
    # 어떤 이유로 막히든 전부 똑같이 404를 돌려준다 (이 통로가 있다는 사실조차 안 알려주려고).
    token = settings.LOADTEST_TOKEN
    if request.method != "POST" or not settings.LOADTEST_ENABLED or len(token) < MIN_TOKEN_LENGTH:
        raise Http404

    supplied = request.headers.get("X-Loadtest-Token", "")
    # 일반 ==는 앞에서부터 한 글자씩 비교해서 틀린 지점에서 바로 끝나므로 응답 시간 차이로 토큰이
    # 추측될 수 있다. compare_digest는 항상 같은 시간이 걸리게 비교해준다.
    if not hmac.compare_digest(supplied.encode(), token.encode()):
        raise Http404

    user = get_object_or_404(User, id=user_id, username__startswith=LOADTEST_USERNAME_PREFIX)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse({"ok": True, "user_id": user.id})
