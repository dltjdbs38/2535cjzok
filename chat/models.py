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


class Message(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.CharField(max_length=1000, blank=True)  # 사진만 보내는 경우 비어있을 수 있음
    image = models.ImageField(upload_to="chat_images/", blank=True, null=True)
    # 답장 대상 메시지. 상대 메시지가 지워져도(관리자 삭제 등) 이 메시지 자체는 남아야 하니 SET_NULL.
    reply_to = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replies"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
