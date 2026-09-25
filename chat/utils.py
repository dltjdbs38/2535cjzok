from django.utils import timezone

_WEEKDAY_KO = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


def format_chat_timestamp(dt):
    """
    오늘이면 '오후 8:08', 어제면 '어제', 그 이전이면 '2026-09-22' 형식으로 변환.
    dt는 UTC로 저장된 aware datetime이라, 반드시 localtime()으로 한국 시간으로
    바꾼 다음 계산해야 한다 (안 그러면 그냥 .strftime()은 UTC 기준으로 나와버림).
    """
    local_dt = timezone.localtime(dt)
    today = timezone.localtime(timezone.now()).date()
    delta_days = (today - local_dt.date()).days

    if delta_days <= 0:
        hour = local_dt.hour
        period = "오전" if hour < 12 else "오후"
        hour12 = hour % 12 or 12
        return f"{period} {hour12}:{local_dt.minute:02d}"
    elif delta_days == 1:
        return "어제"
    else:
        return local_dt.strftime("%Y-%m-%d")


def format_date_divider(dt):
    """대화방 안 날짜 구분선용 - '2026년 1월 15일 목요일' 형식."""
    local_dt = timezone.localtime(dt)
    weekday = _WEEKDAY_KO[local_dt.weekday()]
    return f"{local_dt.year}년 {local_dt.month}월 {local_dt.day}일 {weekday}"


def date_key(dt):
    """날짜가 바뀌었는지 비교할 때 쓰는 키 (문자열 비교로 충분하게)."""
    return timezone.localtime(dt).date().isoformat()
