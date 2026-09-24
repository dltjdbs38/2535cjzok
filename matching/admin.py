from django.contrib import admin

from .models import Like, MatchingPreference


@admin.register(MatchingPreference)
class MatchingPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "preferred_regions", "preferred_height_codes", "preferred_religions", "preferred_smoking")


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("from_user", "to_user", "created_at")
