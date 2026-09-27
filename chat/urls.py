from django.urls import path

from . import views

urlpatterns = [
    path("", views.chat_list, name="chat_list"),
    path("start/<int:user_id>/", views.start_chat, name="chat_start"),
    path("<int:room_id>/", views.chat_room, name="chat_room"),
    path("<int:room_id>/poll/", views.poll_messages, name="chat_poll"),
    path("<int:room_id>/confirm-meeting/", views.confirm_meeting, name="confirm_meeting"),
    path("<int:room_id>/manner-rating/", views.manner_rating, name="manner_rating"),
    path("<int:room_id>/leave/", views.leave_chat, name="chat_leave"),
    path("<int:room_id>/rejoin/", views.rejoin_chat, name="chat_rejoin"),
]
