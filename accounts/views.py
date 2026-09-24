from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import ProfileSetupForm
from .models import User


def home(request):
    """
    로그인 여부 + 가입 승인 상태에 따라 알맞은 화면으로 안내하는 입구 역할.
    승인된 사용자는 매칭 리스트로 바로 넘겨준다.
    """
    if not request.user.is_authenticated:
        return render(request, "accounts/home.html")

    # 관리자(운영 도구를 쓰는 사람)는 일반 회원 가입 절차 대상이 아니므로
    # 승인 상태를 따질 것 없이 바로 관리자 페이지로 보낸다.
    if request.user.is_staff:
        return redirect("/admin/")

    user = request.user

    # 블랙리스트(영구퇴출)는 심사 거부와 별개의, 훨씬 무거운 영구 차단이라 제일 먼저 체크한다.
    if user.is_blacklisted:
        return render(request, "accounts/blocked.html")

    status = user.approval_status
    if status == User.ApprovalStatus.INCOMPLETE:
        return redirect("profile_setup")
    if status == User.ApprovalStatus.PENDING:
        return render(request, "accounts/pending_approval.html", {"user": user})
    if status == User.ApprovalStatus.REJECTED:
        # 블랙리스트는 위에서 이미 걸렀으니, 여기 도달했다는 건 항상 재도전 가능한 1회 거부 상태.
        return render(request, "accounts/pending_approval.html", {"user": user, "can_retry": True})

    # APPROVED
    return redirect("matching_list")


@login_required
def profile_setup(request):
    """
    얼굴사진/전신사진/신체조건 등을 입력받는 화면.
    최초 가입 때뿐 아니라, 승인된 회원이 정보를 고치고 싶을 때도 이 화면을 그대로 쓴다.
    제출되면 (다시) 심사중(PENDING) 상태로 바뀌고 관리자 승인을 기다리게 된다.
    """
    user = request.user

    # 관리자가 실수로 이 URL에 직접 들어와도 등록을 강요하지 않는다.
    if user.is_staff:
        return redirect("/admin/")

    if user.is_blacklisted:
        return redirect("home")

    # 프로필을 낼 수 있는 상태: 최초 가입(INCOMPLETE), 거부 후 재도전(REJECTED, 블랙리스트 아님),
    # 또는 이미 승인된 회원이 정보를 수정하려는 경우(APPROVED). PENDING(이미 심사 제출함)만 막는다.
    allowed = (
        user.approval_status == User.ApprovalStatus.INCOMPLETE
        or user.can_retry_signup
        or user.approval_status == User.ApprovalStatus.APPROVED
    )
    if not allowed:
        return redirect("home")

    if request.method == "POST":
        form = ProfileSetupForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.approval_status = User.ApprovalStatus.PENDING
            profile.profile_submitted_at = timezone.now()
            profile.save()
            return redirect("home")
    else:
        form = ProfileSetupForm(instance=user)

    return render(request, "accounts/profile_setup.html", {"form": form})