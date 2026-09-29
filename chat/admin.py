from django.contrib import admin
from django.utils.html import format_html_join

from .models import ChatRoom, Message, Report, ReportImage


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ("id", "participant_1", "participant_2", "meeting_confirmed", "created_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "sender", "content", "created_at")


class ReportImageInline(admin.TabularInline):
    model = ReportImage
    extra = 0
    readonly_fields = ("image_preview",)
    fields = ("image_preview",)

    @admin.display(description="증거 사진")
    def image_preview(self, obj):
        if not obj.image:
            return "-"
        return format_html_join("", '<img src="{}" style="height:120px;border-radius:4px;">', [(obj.image.url,)])


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    # 오래 방치되지 않도록 오래된 신고가 위로 오게 정렬.
    ordering = ("status", "created_at")
    list_display = ("id", "reporter", "reported_user", "reason", "status", "created_at")
    list_filter = ("status", "reason")
    search_fields = ("reporter__nickname", "reported_user__nickname")
    actions = ["approve_reports", "dismiss_reports"]
    inlines = [ReportImageInline]

    @admin.action(description="선택한 신고 승인 - 신고당한 회원 즉시 블랙리스트 처리")
    def approve_reports(self, request, queryset):
        count = 0
        for report in queryset.exclude(status=Report.Status.RESOLVED_BLACKLISTED):
            report.reported_user.is_blacklisted = True
            report.reported_user.save(update_fields=["is_blacklisted"])
            report.status = Report.Status.RESOLVED_BLACKLISTED
            report.save(update_fields=["status"])
            count += 1
        self.message_user(request, f"{count}건 승인 처리했어. 신고당한 회원들은 즉시 블랙리스트 처리됐어.")

    @admin.action(description="선택한 신고 반려")
    def dismiss_reports(self, request, queryset):
        updated = queryset.update(status=Report.Status.DISMISSED)
        self.message_user(request, f"{updated}건 반려했어.")
