from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from .models import (
    ChatRoom,
    MannerRating,
    Message,
    Report,
    ReportImage,
    active_room_count_for,
    apply_manner_rating,
    find_unrated_meeting_room,
)
from .utils import date_key, format_chat_timestamp, format_date_divider, format_message_clock

MAX_ACTIVE_CHATS = 3


def _require_approved(view_func):
    def wrapped(request, *args, **kwargs):
        if not request.user.is_approved or request.user.is_blacklisted:
            return redirect("home")
        return view_func(request, *args, **kwargs)

    return wrapped


def _room_or_403(room_id, user):
    room = get_object_or_404(ChatRoom, id=room_id)
    if user.id not in (room.participant_1_id, room.participant_2_id):
        return None
    return room


def _serialize_message(m, viewer):
    reply = None
    if m.reply_to_id:
        # 답장 대상 메시지가 그 사이에 지워졌을 수도 있으니 안전하게 조회.
        target = m.reply_to
        if target:
            reply = {
                "id": target.id,
                "sender_name": target.sender.nickname,
                "snippet": (target.content[:30] if target.content else "(사진)"),
            }
    return {
        "id": m.id,
        "is_mine": m.sender_id == viewer.id,
        "is_system": m.is_system,
        "content": m.content,
        "image_url": m.image.url if m.image else None,
        "time": format_message_clock(m.created_at),
        "date_label": format_date_divider(m.created_at),
        "date_key": date_key(m.created_at),
        "reply": reply,
        "sender_nickname": m.sender.nickname,
        "sender_photo_url": m.sender.profile_photo.url if m.sender.profile_photo else None,
    }


@login_required
@_require_approved
def start_chat(request, user_id):
    """
    매칭 프로필의 "대화하기" 버튼이 호출하는 뷰. 이미 방이 있으면 그 방으로,
    없으면 새로 만들어서 바로 대화방으로 들여보낸다.
    """
    if request.method != "POST":
        return redirect("matching_profile", user_id=user_id)

    target = get_object_or_404(User, id=user_id, approval_status=User.ApprovalStatus.APPROVED)

    # 이미 이 상대랑 방이 있으면(재입장) 매너온도 체크 없이 그냥 들여보낸다.
    existing_room = ChatRoom.objects.filter(
        Q(participant_1=request.user, participant_2=target) | Q(participant_1=target, participant_2=request.user)
    ).first()

    if existing_room is None:
        # 완전히 새로운 상대와 첫 대화방을 만들려는 시점 - 이전에 만난 사람 중
        # 아직 매너온도 평가를 안 준 사람이 있으면, 그 평가부터 하게 막는다.
        pending_room = find_unrated_meeting_room(request.user, only_if_30_days_passed=False)
        if pending_room:
            return redirect("manner_rating", room_id=pending_room.id)

        # 이미 나가지 않은 대화방이 3개면, 새 대화는 못 만들고 누군가를 먼저 나가야 한다.
        if active_room_count_for(request.user) >= MAX_ACTIVE_CHATS:
            messages.error(request, f"최대 {MAX_ACTIVE_CHATS}명까지만 동시에 대화할 수 있어. 다른 채팅방을 먼저 나가줘.")
            return redirect("chat_list")

    room = ChatRoom.get_or_create_between(request.user, target)
    return redirect("chat_room", room_id=room.id)


@login_required
@_require_approved
def chat_list(request):
    rooms = (
        ChatRoom.objects.filter(Q(participant_1=request.user) | Q(participant_2=request.user))
        .annotate(last_message_at=Max("messages__created_at"))
        .order_by("-last_message_at")
    )

    rows = []
    for room in rooms:
        last_message = room.messages.order_by("-created_at").first()
        rows.append(
            {
                "room": room,
                "other": room.other_participant(request.user),
                "last_message": last_message,
                "last_message_time": format_chat_timestamp(last_message.created_at) if last_message else "",
                "unread_count": room.unread_count_for(request.user),
                "is_left": room.is_left_by(request.user),
            }
        )

    return render(request, "chat/chat_list.html", {"rows": rows, "active_tab": "chat"})


@login_required
@_require_approved
def chat_room(request, room_id):
    room = _room_or_403(room_id, request.user)
    if room is None:
        return redirect("chat_list")

    if request.method == "POST":
        # 채팅을 나간 상태면 "다시 대화하기"부터 해야 메시지를 보낼 수 있다.
        if room.is_left_by(request.user):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"error": "채팅을 나간 상태야. 다시 대화하기를 먼저 눌러줘."}, status=403)
            return redirect("chat_room", room_id=room.id)

        content = request.POST.get("content", "").strip()
        images = request.FILES.getlist("image")  # 앨범에서 여러 장을 골랐을 수 있다
        reply_to_id = request.POST.get("reply_to") or None

        reply_to = None
        if reply_to_id:
            # 답장 대상이 진짜 이 방에 속한 메시지인지 확인 (다른 방 메시지 id를 끼워넣는 걸 방지).
            reply_to = room.messages.filter(id=reply_to_id).first()

        # 텍스트 + 사진 여러 장을 한 번에 보낼 수 있으니, 사진 한 장당 메시지 하나씩 만든다.
        # 답장 표시는 맨 처음 만들어지는 메시지 하나에만 붙인다.
        created = []
        if content:
            created.append(
                Message.objects.create(room=room, sender=request.user, content=content[:1000], reply_to=reply_to)
            )
            reply_to = None
        for image in images:
            created.append(
                Message.objects.create(room=room, sender=request.user, image=image, reply_to=reply_to)
            )
            reply_to = None

        # JS가 fetch로 보낸 요청이면(페이지 새로고침 없이 연속으로 보내는 방식) 방금 만든 메시지를
        # JSON으로 바로 돌려준다. JS가 없거나 일반 폼 제출이면 예전처럼 리다이렉트.
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            data = [_serialize_message(m, request.user) for m in created]
            return JsonResponse({"messages": data})

        return redirect("chat_room", room_id=room.id)

    # 방에 들어오는 순간 = 상대 메시지를 확인한 시점이므로 읽음 처리.
    room.mark_read(request.user)

    message_list = [
        _serialize_message(m, request.user)
        for m in room.messages.select_related("sender", "reply_to", "reply_to__sender")
    ]

    return render(
        request,
        "chat/chat_room.html",
        {
            "room": room,
            "other": room.other_participant(request.user),
            "message_list": message_list,
            "is_left": room.is_left_by(request.user),
        },
    )


@login_required
@_require_approved
def poll_messages(request, room_id):
    """
    대화방 화면이 몇 초마다 호출하는 폴링 엔드포인트.
    ?after=<마지막으로 받은 메시지 id> 이후에 새로 온 메시지만 JSON으로 돌려준다.
    """
    room = _room_or_403(room_id, request.user)
    if room is None:
        return JsonResponse({"error": "forbidden"}, status=403)

    after_id = request.GET.get("after") or 0
    new_messages = room.messages.filter(id__gt=after_id).select_related("sender", "reply_to", "reply_to__sender")

    if new_messages.exists():
        room.mark_read(request.user)

    data = [_serialize_message(m, request.user) for m in new_messages]
    return JsonResponse({"messages": data})


@login_required
@_require_approved
def confirm_meeting(request, room_id):
    """"실제로 만났어요" 버튼. 둘 중 한 명만 눌러도 그 방은 "만남 확정" 상태가 된다."""
    room = _room_or_403(room_id, request.user)
    if room is None:
        return redirect("chat_list")
    if request.method == "POST" and not room.meeting_confirmed:
        room.confirm_meeting()
    return redirect("chat_room", room_id=room.id)


@login_required
@_require_approved
def manner_rating(request, room_id):
    """
    후기(매너온도 평가) 화면. 여기 들어오는 것 자체가 "실제로 만났다"는 뜻이므로,
    아직 만남 확정이 안 된 방이면 여기서 자동으로 확정 처리한다.
    강제로(새 대화 시작 시 / 30일 경과 후 접속 시) 여기로 보내질 수도 있고, 직접 들어올 수도 있다.
    """
    room = _room_or_403(room_id, request.user)
    if room is None:
        return redirect("chat_list")
    if not room.meeting_confirmed:
        room.confirm_meeting()

    other = room.other_participant(request.user)
    already_rated = MannerRating.objects.filter(room=room, rater=request.user).exists()

    if request.method == "POST":
        if not already_rated:
            stars = int(request.POST.get("stars", 3))
            apply_manner_rating(
                rater=request.user,
                ratee=other,
                room=room,
                stars=stars,
                flag_photo_mismatch=bool(request.POST.get("flag_photo_mismatch")),
                flag_condition_mismatch=bool(request.POST.get("flag_condition_mismatch")),
                flag_abusive_or_noshow=bool(request.POST.get("flag_abusive_or_noshow")),
            )
        return redirect("home")

    return render(
        request,
        "chat/manner_rating.html",
        {"room": room, "other": other, "already_rated": already_rated},
    )


@login_required
@_require_approved
def leave_chat(request, room_id):
    room = _room_or_403(room_id, request.user)
    if room is None:
        return redirect("chat_list")
    if request.method == "POST" and not room.is_left_by(request.user):
        room.leave(request.user)
    return redirect("chat_list")


@login_required
@_require_approved
def rejoin_chat(request, room_id):
    room = _room_or_403(room_id, request.user)
    if room is None:
        return redirect("chat_list")
    if request.method == "POST" and room.is_left_by(request.user):
        # 재입장도 "새 대화방 만들기"랑 똑같이 3명 제한에 걸린다 - 이미 3명이면 재입장도 막는다.
        if active_room_count_for(request.user) >= MAX_ACTIVE_CHATS:
            messages.error(request, f"최대 {MAX_ACTIVE_CHATS}명까지만 동시에 대화할 수 있어. 다른 채팅방을 먼저 나가줘.")
            return redirect("chat_list")
        room.rejoin(request.user)
    return redirect("chat_room", room_id=room.id)


@login_required
@_require_approved
def report_user(request, room_id):
    """
    신고하기. 매너온도랑 마찬가지로 "만남이 성사된(meeting_confirmed) 방"에서만 가능하다.
    관리자가 승인하면 신고 1건만으로 즉시 블랙리스트 처리된다 (매너온도 체크항목의 "2회 누적"
    규칙보다 훨씬 무거운 사안을 다루기 때문).
    """
    room = _room_or_403(room_id, request.user)
    if room is None:
        return redirect("chat_list")
    if not room.meeting_confirmed:
        # 아직 만난 적 없다고 표시된 방에서는 신고 자체가 안 열린다.
        return redirect("chat_room", room_id=room.id)

    other = room.other_participant(request.user)
    errors = {}

    if request.method == "POST":
        reason = request.POST.get("reason", "")
        detail = request.POST.get("detail", "").strip()
        evidence_images = request.FILES.getlist("evidence")

        if reason not in Report.Reason.values:
            errors["reason"] = "모든 항목에 응답해주세요"
        if not detail:
            errors["detail"] = "모든 항목에 응답해주세요"
        if not evidence_images:
            errors["evidence"] = "모든 항목에 응답해주세요"

        if not errors:
            report = Report.objects.create(
                room=room, reporter=request.user, reported_user=other, reason=reason, detail=detail[:500]
            )
            for image in evidence_images:
                ReportImage.objects.create(report=report, image=image)
            return redirect("chat_room", room_id=room.id)

        return render(
            request,
            "chat/report_user.html",
            {
                "room": room,
                "other": other,
                "reasons": Report.Reason.choices,
                "errors": errors,
                "selected_reason": reason,
                "detail_value": detail,
            },
        )

    return render(
        request,
        "chat/report_user.html",
        {"room": room, "other": other, "reasons": Report.Reason.choices, "errors": errors},
    )
