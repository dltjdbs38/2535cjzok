"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.views import dev_login_as, dev_login_as_list, home, profile_setup

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),  # 카카오 로그인 관련 URL이 전부 여기서 나온다
    path('profile/setup/', profile_setup, name='profile_setup'),  # 얼굴/전신사진 등 프로필 등록
    path('matching/', include('matching.urls')),  # 매칭 리스트/프로필/조건설정/좋아요
    path('chat/', include('chat.urls')),  # 대화 목록/대화방
    path('dev/login-as/', dev_login_as_list, name='dev_login_as_list'),  # 테스트 계정 로그인 전환 (DEBUG 전용)
    path('dev/login-as/<int:user_id>/', dev_login_as, name='dev_login_as'),
    path('', home, name='home'),
]

if settings.DEBUG:
    # 개발 중에만 업로드된 이미지(얼굴/전신사진)를 서버가 직접 서빙해준다.
    # 실제 배포 시엔 R2/S3 같은 외부 스토리지가 이 역할을 대신하게 됨.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
