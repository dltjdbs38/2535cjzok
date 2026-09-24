from django.urls import path

from . import views

urlpatterns = [
    path("", views.matching_list, name="matching_list"),
    path("preferences/", views.preference_setup, name="matching_preferences"),
    path("profile/<int:user_id>/", views.matching_profile_detail, name="matching_profile"),
    path("like/<int:user_id>/", views.toggle_like, name="matching_like"),
]
