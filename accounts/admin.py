from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe

from .models import User


class DormantFilter(admin.SimpleListFilter):
    # is_dormant는 저장된 필드가 아니라 그때그때 계산되는 프로퍼티라서, list_filter에
    # 바로 못 넣는다. 대신 이렇게 SimpleListFilter로 last_login 기준을 직접 계산해서 걸러준다.
    title = "휴면 여부"
    parameter_name = "dormant"

    def lookups(self, request, model_admin):
        return (("yes", "휴면계정 (180일 이상 미접속)"), ("no", "정상"))

    def queryset(self, request, queryset):
        cutoff = timezone.now() - timezone.timedelta(days=User.DORMANT_AFTER_DAYS)
        if self.value() == "yes":
            return queryset.filter(last_login__lt=cutoff)
        if self.value() == "no":
            return queryset.filter(last_login__gte=cutoff) | queryset.filter(last_login__isnull=True)
        return queryset


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    # 심사가 오래 밀리지 않도록, 프로필을 먼저 제출한 사람이 위로 오게 정렬.
    ordering = ("profile_submitted_at",)

    list_display = (
        "id",
        "nickname",
        "is_superuser",
        "photo_preview",
        "gender",
        "birth_year",
        "region",
        "approval_status",
        "rejection_count",
        "blacklist_badge",
        "dormant_badge",
        "withdrawal_count",
        "manner_temp",
        "profile_submitted_at",
    )
    list_filter = ("approval_status", "is_blacklisted", DormantFilter, "gender", "religion", "is_smoker")
    search_fields = ("nickname", "kakao_id", "username")
    actions = ["approve_users", "reject_users", "blacklist_users", "redownload_kakao_photo"]

    fieldsets = UserAdmin.fieldsets + (
        (
            "카카오 프로필",
            {"fields": ("kakao_id", "nickname", "profile_image_url", "profile_photo", "birth_year", "gender")},
        ),
        (
            "심사용 업로드 사진",
            {"fields": ("face_photo", "body_photo", "showcase_photo", "photo_preview")},
        ),
        (
            "매칭 프로필",
            {
                "fields": (
                    "height_cm",
                    "weight_kg",
                    "hobby_first",
                    "hobby_second",
                    "hobby_dislike",
                    "region",
                    "religion",
                    "is_smoker",
                    "intro",
                )
            },
        ),
        (
            "승인 및 신뢰도",
            {
                "fields": (
                    "approval_status",
                    "rejected_reason",
                    "rejection_count",
                    "is_blacklisted",
                    "withdrawal_count",
                    "profile_submitted_at",
                    "manner_temp",
                )
            },
        ),
    )
    readonly_fields = UserAdmin.readonly_fields + ("photo_preview",)

    @admin.display(description="사진 비교(카톡프사 / 얼굴 / 전신 / 취향사진)")
    def photo_preview(self, obj):
        # 카톡 프로필사진과 사용자가 직접 올린 얼굴/전신/취향사진을 한 줄로 보여줘서
        # 사진 도용 여부를 눈으로 바로 비교할 수 있게 한다.
        items = [
            (url, label)
            for url, label in [
                (obj.profile_photo.url if obj.profile_photo else "", "카톡(우리서버 사본)"),
                (obj.face_photo.url if obj.face_photo else "", "얼굴"),
                (obj.body_photo.url if obj.body_photo else "", "전신"),
                (obj.showcase_photo.url if obj.showcase_photo else "", "취향사진"),
            ]
            if url
        ]
        if not items:
            return "-"
        return format_html_join(
            "",
            '<div style="display:inline-block;text-align:center;margin-right:8px;">'
            '<img src="{}" style="height:80px;border-radius:4px;"><br>{}</div>',
            items,
        )

    @admin.display(description="블랙리스트", boolean=False)
    def blacklist_badge(self, obj):
        # 기본 체크박스 아이콘보다 눈에 확 띄게, 색깔 있는 배지로 보여준다.
        if obj.is_blacklisted:
            return mark_safe(
                '<span style="background:#FCEBEB; color:#A32D2D; padding:2px 8px; border-radius:8px; font-size:11px; font-weight:500;">블랙리스트</span>'
            )
        return mark_safe('<span style="color:#b3b1a8; font-size:11px;">-</span>')

    @admin.display(description="휴면")
    def dormant_badge(self, obj):
        if obj.is_dormant:
            return mark_safe(
                '<span style="background:#FAEEDA; color:#854F0B; padding:2px 8px; border-radius:8px; font-size:11px; font-weight:500;">휴면</span>'
            )
        return mark_safe('<span style="color:#b3b1a8; font-size:11px;">-</span>')

    @admin.action(description="선택한 회원 승인 처리 (거부 횟수 초기화)")
    def approve_users(self, request, queryset):
        # 승인될 때마다 거부 횟수를 0으로 되돌려서, 다음 심사 사이클에서 다시 2번의 기회가 주어지게 한다.
        updated = queryset.update(approval_status=User.ApprovalStatus.APPROVED, rejection_count=0)
        self.message_user(request, f"{updated}명 승인 처리했어.")

    @admin.action(description="선택한 회원 거부 처리 (거부 2회째부터 자동 영구퇴출)")
    def reject_users(self, request, queryset):
        # 회원마다 현재 거부 횟수가 다를 수 있어서, 일괄 update가 아니라 한 명씩 처리한다.
        blacklisted = 0
        for user in queryset:
            user.rejection_count += 1
            user.approval_status = User.ApprovalStatus.REJECTED
            if user.rejection_count >= 2:
                user.is_blacklisted = True
                blacklisted += 1
            user.save(update_fields=["rejection_count", "approval_status", "is_blacklisted"])

        message = f"{queryset.count()}명 거부 처리했어."
        if blacklisted:
            message += f" 그 중 {blacklisted}명은 이번 거부로 2회가 되어 영구퇴출 처리됐어."
        self.message_user(request, message)

    @admin.action(description="선택한 회원 블랙리스트(영구퇴출) 처리 - 동일 카카오 계정 영구 재가입/재심사 불가")
    def blacklist_users(self, request, queryset):
        updated = queryset.update(is_blacklisted=True)
        self.message_user(request, f"{updated}명 블랙리스트 처리했어. 이제 동일 카카오 계정으로 다시는 가입/심사를 받을 수 없어.")

    @admin.action(description="선택한 회원의 카카오 프로필사진 다시 다운로드")
    def redownload_kakao_photo(self, request, queryset):
        # 다운로드 로직이 생기기 전에 가입했던 회원처럼 profile_photo가 비어있는 경우를
        # 재로그인 없이 관리자가 바로 채워줄 수 있게 하는 수동 액션.
        from .adapters import download_kakao_photo

        succeeded = 0
        for user in queryset:
            before = bool(user.profile_photo)
            download_kakao_photo(user, user.profile_image_url)
            user.refresh_from_db()
            if user.profile_photo and not before:
                succeeded += 1
        self.message_user(request, f"{queryset.count()}명 중 {succeeded}명 다운로드 성공.")
