#!/usr/bin/env bash
# 부하테스트 키트 적용 스크립트. 프로젝트 루트(manage.py가 있는 폴더)에서 실행:  bash apply_loadtest_kit.sh
# 이미 적용돼 있으면 건너뛰므로 여러 번 실행해도 안전하다 (중복으로 추가되지 않음).
set -euo pipefail

[ -f manage.py ] || { echo "ERROR: manage.py가 있는 프로젝트 루트에서 실행해줘."; exit 1; }
[ -f config/settings.py ] || { echo "ERROR: config/settings.py를 못 찾았어."; exit 1; }
[ -f config/urls.py ] || { echo "ERROR: config/urls.py를 못 찾았어."; exit 1; }
[ -f accounts/loadtest.py ] || { echo "ERROR: accounts/loadtest.py가 없어. 키트 압축을 프로젝트 루트에 먼저 풀어줘."; exit 1; }

# 파일 안에 marker 문자열이 없을 때만 text를 맨 아래에 추가한다.
append_once() {
  local file="$1" marker="$2" text="$3"
  if grep -qF -- "$marker" "$file" 2>/dev/null; then
    echo "  = 이미 있음 : $file  ($marker)"
  else
    printf '\n%s\n' "$text" >> "$file"
    echo "  + 추가함    : $file  ($marker)"
  fi
}

echo "[1/4] config/settings.py"
grep -qE '^import os' config/settings.py || { echo "ERROR: settings.py에 'import os'가 없어서 중단 (os.environ을 쓰는 줄을 추가할 수 없음)."; exit 1; }
append_once config/settings.py "LOADTEST_ENABLED" '# ===== 부하테스트 전용 로그인 통로 (staging의 .env.staging에서만 켠다. prod .env에는 넣지 말 것) =====
LOADTEST_ENABLED = os.environ.get("LOADTEST_ENABLED", "False") == "True"
LOADTEST_TOKEN = os.environ.get("LOADTEST_TOKEN", "")'

echo "[2/4] config/urls.py"
grep -qE 'from django.conf import settings' config/urls.py || { echo "ERROR: urls.py에 'from django.conf import settings'가 없어서 중단."; exit 1; }
grep -qE 'import .*\bpath\b' config/urls.py || { echo "ERROR: urls.py에서 path import를 못 찾아서 중단."; exit 1; }
append_once config/urls.py "loadtest_login" '# ===== 부하테스트 전용 로그인 통로: LOADTEST_ENABLED=True일 때만 라우트가 등록된다 (꺼져 있으면 이 주소는 404) =====
if settings.LOADTEST_ENABLED:
    from accounts.loadtest import loadtest_login

    urlpatterns += [path("loadtest/login/<int:user_id>/", loadtest_login, name="loadtest_login")]'

echo "[3/4] .gitignore"
touch .gitignore
for line in ".env.staging" "staging-data/" "loadtest/users*.csv" "loadtest/results/"; do
  append_once .gitignore "$line" "$line"
done

echo "[4/4] .dockerignore (빌드 컨텍스트에 DB/미디어/비밀값이 딸려 들어가지 않게)"
touch .dockerignore
for line in ".env.staging" "staging-data/" "loadtest/users*.csv" "loadtest/results/"; do
  append_once .dockerignore "$line" "$line"
done

echo
echo "완료. 다음: git add -A && git commit -m 'add loadtest kit' && git push"
