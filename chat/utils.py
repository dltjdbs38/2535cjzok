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


def format_message_clock(dt):
    """
    대화방 안 메시지 하나하나에 붙는 시간 - 며칠이 지났든 그냥 '오후 3:27' 형식으로 고정.
    날짜 자체는 이미 날짜 구분선이 보여주고 있어서, 메시지 시간까지 날짜를 반복할 필요가 없다.
    (대화 목록의 마지막 메시지 시각 표시는 format_chat_timestamp를 그대로 쓴다 - 거기는 구분선이 없으니까)
    """
    local_dt = timezone.localtime(dt)
    period = "오전" if local_dt.hour < 12 else "오후"
    hour12 = local_dt.hour % 12 or 12
    return f"{period} {hour12}:{local_dt.minute:02d}"


def date_key(dt):
    """날짜가 바뀌었는지 비교할 때 쓰는 키 (문자열 비교로 충분하게)."""
    return timezone.localtime(dt).date().isoformat()
