from django.urls import path

from . import views

urlpatterns = [
    path("", views.chat_list, name="chat_list"),
    path("start/<int:user_id>/", views.start_chat, name="chat_start"),
    path("<int:room_id>/", views.chat_room, name="chat_room"),
    path("<int:room_id>/poll/", views.poll_messages, name="chat_poll"),
]
