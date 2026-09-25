from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from .models import ChatRoom, Message
from .utils import date_key, format_chat_timestamp, format_date_divider


def _require_approved(view_func):
    def wrapped(request, *args, **kwargs):
        if not request.user.is_approved:
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
        "content": m.content,
        "image_url": m.image.url if m.image else None,
        "time": format_chat_timestamp(m.created_at),
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
