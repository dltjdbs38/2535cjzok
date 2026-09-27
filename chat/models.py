from django.conf import settings
from django.db import models
from django.utils import timezone


class ChatRoom(models.Model):
    """
    1:1 대화방. 참여자 두 명을 참여자1/2으로 고정 저장해두고,
    항상 id가 작은 쪽을 participant_1로 정렬해서 저장한다 -
    이렇게 해야 "A가 먼저 만들었든 B가 먼저 만들었든" 같은 방으로 취급돼서
    같은 두 사람 사이에 방이 중복 생성되는 걸 막을 수 있다.
    """

    participant_1 = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_rooms_as_1"
    )
    participant_2 = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_rooms_as_2"
    )
    # 메시지마다 읽음 여부를 저장하지 않고, "이 사람이 이 방을 마지막으로 확인한 시각"만 저장한다.
    # 그 시각 이후에 상대가 보낸 메시지 수 = 안읽은 개수.
    participant_1_last_read_at = models.DateTimeField(null=True, blank=True)
    participant_2_last_read_at = models.DateTimeField(null=True, blank=True)
    # "실제로 만났어요" 버튼으로 둘 중 한 명이 표시하면 True. 매너온도 평가는 이 상태인
    # 방에서만 가능하다 (신고/평가는 만남이 성사된 이후에만 가능하다는 원칙).
    meeting_confirmed = models.BooleanField(default=False)
    meeting_confirmed_at = models.DateTimeField(null=True, blank=True)
    # "채팅 나가기"를 누르면 그 사람 쪽만 True가 된다. 방 자체는 안 지워지고,
    # 안 나간 쪽은 계속 메시지를 보낼 수 있다. "다시 대화하기"를 누르면 다시 False로.
    participant_1_left = models.BooleanField(default=False)
    participant_2_left = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("participant_1", "participant_2")

    @classmethod
    def get_or_create_between(cls, user_a, user_b):
        p1, p2 = sorted([user_a, user_b], key=lambda u: u.id)
        room, _ = cls.objects.get_or_create(participant_1=p1, participant_2=p2)
        return room

    def other_participant(self, user):
        return self.participant_2 if user.id == self.participant_1_id else self.participant_1

    def last_read_at_for(self, user):
        if user.id == self.participant_1_id:
            return self.participant_1_last_read_at
        return self.participant_2_last_read_at

    def mark_read(self, user):
        now = timezone.now()
        if user.id == self.participant_1_id:
            self.participant_1_last_read_at = now
            self.save(update_fields=["participant_1_last_read_at"])
        else:
            self.participant_2_last_read_at = now
            self.save(update_fields=["participant_2_last_read_at"])

    def unread_count_for(self, user):
        last_read = self.last_read_at_for(user)
        qs = self.messages.exclude(sender=user)
        if last_read:
            qs = qs.filter(created_at__gt=last_read)
        return qs.count()

    def confirm_meeting(self):
        self.meeting_confirmed = True
        self.meeting_confirmed_at = timezone.now()
        self.save(update_fields=["meeting_confirmed", "meeting_confirmed_at"])

    def last_activity_at(self):
        last_message = self.messages.order_by("-created_at").first()
        if last_message:
            return last_message.created_at
        return self.meeting_confirmed_at or self.created_at

    def is_left_by(self, user):
        return self.participant_1_left if user.id == self.participant_1_id else self.participant_2_left

    def leave(self, user):
        if user.id == self.participant_1_id:
            self.participant_1_left = True
        else:
            self.participant_2_left = True
        self.save(update_fields=["participant_1_left", "participant_2_left"])
        Message.objects.create(
            room=self, sender=user, content=f"{user.nickname}님이 채팅에서 퇴장하였습니다.", is_system=True
        )

    def rejoin(self, user):
        if user.id == self.participant_1_id:
            self.participant_1_left = False
        else:
            self.participant_2_left = False
        self.save(update_fields=["participant_1_left", "participant_2_left"])
        Message.objects.create(
            room=self, sender=user, content=f"{user.nickname}님이 재입장하였습니다.", is_system=True
        )


class Message(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.CharField(max_length=1000, blank=True)  # 사진만 보내는 경우 비어있을 수 있음
    image = models.ImageField(upload_to="chat_images/", blank=True, null=True)
    # 답장 대상 메시지. 상대 메시지가 지워져도(관리자 삭제 등) 이 메시지 자체는 남아야 하니 SET_NULL.
    reply_to = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replies"
    )
    is_system = models.BooleanField(default=False)  # 퇴장/재입장 안내 같은 시스템 메시지 (말풍선이 아니라 배지로 표시)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class MannerRating(models.Model):
    """
    당근마켓 스타일 매너온도 평가. 만남이 확정된 대화방(room.meeting_confirmed=True)에서만
    만들어질 수 있고, 한 방에 대해 한 사람당 한 번만 평가할 수 있다.
    """

    room = models.ForeignKey(ChatRoom, on_delete=models.SET_NULL, null=True, related_name="manner_ratings")
    rater = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="manner_ratings_given")
    ratee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="manner_ratings_received"
    )
    stars = models.PositiveSmallIntegerField(choices=[(1, "1점"), (3, "3점"), (5, "5점")])
    # 세 가지 체크항목 - 같은 항목이 누적 2회가 되면 관리 로직에서 자동으로 블랙리스트 처리한다.
    flag_photo_mismatch = models.BooleanField(default=False)  # 사진/외모 스펙과 실물이 동일하지 않았어요
    flag_condition_mismatch = models.BooleanField(default=False)  # 나이 및 직업/조건이 동일하지 않았어요
    flag_abusive_or_noshow = models.BooleanField(default=False)  # 욕설/성적인 만남 제안/당일 파토
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("room", "rater")


def active_room_count_for(user):
    """지금 "나가지 않은" 대화방이 몇 개인지. 동시 대화 최대 3명 제한에 쓰인다."""
    from django.db.models import Q

    count = 0
    rooms = ChatRoom.objects.filter(Q(participant_1=user) | Q(participant_2=user))
    for room in rooms:
        if not room.is_left_by(user):
            count += 1
    return count


def find_unrated_meeting_room(user, only_if_30_days_passed):
    """
    아직 매너온도를 안 준, 만남 확정된 방을 하나 찾아 돌려준다 (없으면 None).
    only_if_30_days_passed=False면 "무조건"(새 대화 시작 시 강제하는 규칙),
    True면 "마지막 활동 후 30일 지났을 때만"(오랜만에 접속 시 강제하는 규칙) 찾는다.
    """
    from django.db.models import Q

    rooms = ChatRoom.objects.filter(
        Q(participant_1=user) | Q(participant_2=user), meeting_confirmed=True
    )
    for room in rooms:
        if MannerRating.objects.filter(room=room, rater=user).exists():
            continue
        if not only_if_30_days_passed:
            return room
        last_activity = room.last_activity_at()
        if last_activity and (timezone.now() - last_activity).days >= 30:
            return room
    return None


def apply_manner_rating(rater, ratee, room, stars, flag_photo_mismatch, flag_condition_mismatch, flag_abusive_or_noshow):
    """
    평가를 저장하고, 매너온도 점수를 갱신하고, 체크항목이 2회 누적되면 자동으로 블랙리스트 처리한다.
    """
    rating, _ = MannerRating.objects.update_or_create(
        room=room,
        rater=rater,
        defaults={
            "ratee": ratee,
            "stars": stars,
            "flag_photo_mismatch": flag_photo_mismatch,
            "flag_condition_mismatch": flag_condition_mismatch,
            "flag_abusive_or_noshow": flag_abusive_or_noshow,
        },
    )

    # 별점을 매너온도 델타로 단순 환산 (당근마켓처럼 36.5도를 기준으로 오르내리는 방식).
    delta = {1: -1.0, 3: 0.0, 5: 0.5}[stars]
    new_temp = float(ratee.manner_temp) + delta
    ratee.manner_temp = max(0.0, min(99.9, new_temp))
    ratee.save(update_fields=["manner_temp"])

    for field in ("flag_photo_mismatch", "flag_condition_mismatch", "flag_abusive_or_noshow"):
        count = MannerRating.objects.filter(ratee=ratee, **{field: True}).count()
        if count >= 2:
            ratee.is_blacklisted = True
            ratee.save(update_fields=["is_blacklisted"])
            break

    return rating
