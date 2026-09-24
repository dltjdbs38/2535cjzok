from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from .forms import MatchingPreferenceForm
from .models import Like, MatchingPreference


def _require_approved(view_func):
    """
    승인된 회원만 매칭 기능을 쓸 수 있게 막는 최소한의 가드.
    (아직 미들웨어 수준으로 통합하진 않았고, 이 앱의 뷰들에만 개별 적용)
    """

    def wrapped(request, *args, **kwargs):
        if not request.user.is_approved:
            return redirect("home")
        return view_func(request, *args, **kwargs)

    return wrapped


def _candidates_for(viewer, preference):
    """
    txt 6번 매칭 규칙을 그대로 구현하되, 취미는 "내 취미와 겹치는지"가 아니라
    "내가 원하는 상대방 취미 조건에 맞는지"로 변경했다 (다른 조건들과 같은 패턴).
    - 거주지역/키/종교/흡연/취미: 내가 설정한 조건에 맞는 사람만
    - 음악 취향(유사도 매칭)은 프로토타입 범위에서 제외 - 지금은 정보 표시만 하고 필터링엔 안 씀
    """
    opposite_gender = User.Gender.FEMALE if viewer.gender == User.Gender.MALE else User.Gender.MALE

    qs = User.objects.filter(
        approval_status=User.ApprovalStatus.APPROVED,
        gender=opposite_gender,
    ).exclude(id=viewer.id)

    if preference.preferred_regions_list:
        qs = qs.filter(region__in=preference.preferred_regions_list)

    if preference.preferred_religions_list:
        qs = qs.filter(religion__in=preference.preferred_religions_list)

    if preference.preferred_smoking_list:
        # 폼 선택값("SMOKER"/"NON_SMOKER")을 모델의 불리언 필드로 변환해서 필터링.
        wants_smoker = "SMOKER" in preference.preferred_smoking_list
        wants_non_smoker = "NON_SMOKER" in preference.preferred_smoking_list
        smoker_bools = []
        if wants_smoker:
            smoker_bools.append(True)
        if wants_non_smoker:
            smoker_bools.append(False)
        if smoker_bools:
            qs = qs.filter(is_smoker__in=smoker_bools)

    qs = qs.filter(height_cm__isnull=False)
    height_ranges = preference.height_ranges_cm()
    if height_ranges:
        # 여러 키 구간 중 "하나라도" 맞으면 통과해야 하므로 OR로 묶는다.
        height_q = Q()
        for height_min, height_max in height_ranges:
            condition = Q()
            if height_min is not None:
                condition &= Q(height_cm__gte=height_min)
            if height_max is not None:
                condition &= Q(height_cm__lt=height_max)
            height_q |= condition
        qs = qs.filter(height_q)

    if preference.preferred_hobby_dislike:
        qs = qs.filter(hobby_dislike=preference.preferred_hobby_dislike)
    wanted_hobbies = [h for h in (preference.preferred_hobby_first, preference.preferred_hobby_second) if h]
    if wanted_hobbies:
        qs = qs.filter(Q(hobby_first__in=wanted_hobbies) | Q(hobby_second__in=wanted_hobbies))

    return qs.order_by("-id")


@login_required
@_require_approved
def matching_list(request):
    try:
        preference = request.user.matching_preference
    except MatchingPreference.DoesNotExist:
        # 조건을 한 번도 설정 안 했으면, 매칭 리스트를 보여줄 기준 자체가 없으니 설정부터 하게 한다.
        return redirect("matching_preferences")

    candidates = _candidates_for(request.user, preference)
    return render(
        request,
        "matching/matching_list.html",
        {"candidates": candidates, "active_tab": "matching"},
    )


@login_required
@_require_approved
def matching_profile_detail(request, user_id):
    profile = get_object_or_404(User, id=user_id, approval_status=User.ApprovalStatus.APPROVED)
    liked = Like.objects.filter(from_user=request.user, to_user=profile).exists()
    return render(
        request,
        "matching/matching_profile.html",
        {"profile": profile, "liked": liked, "active_tab": "matching"},
    )


@login_required
@_require_approved
def toggle_like(request, user_id):
    if request.method != "POST":
        return redirect("matching_profile", user_id=user_id)

    profile = get_object_or_404(User, id=user_id)
    like, created = Like.objects.get_or_create(from_user=request.user, to_user=profile)
    if not created:
        # 이미 눌렀던 좋아요면 다시 눌렀을 때 취소되게 (토글).
        like.delete()

    return redirect("matching_profile", user_id=user_id)


@login_required
@_require_approved
def preference_setup(request):
    try:
        existing = request.user.matching_preference
    except MatchingPreference.DoesNotExist:
        existing = None

    if request.method == "POST":
        form = MatchingPreferenceForm(request.POST, viewer=request.user)
        if form.is_valid():
            form.save(request.user)
            return redirect("matching_list")
    else:
        form = MatchingPreferenceForm(
            viewer=request.user, initial=MatchingPreferenceForm.initial_from_instance(existing)
        )

    return render(request, "matching/preference_setup.html", {"form": form})
