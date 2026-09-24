from django import forms

from .models import User


class ProfileSetupForm(forms.ModelForm):
    """
    카카오 로그인 직후 사용자가 채워야 하는 프로필 등록 폼.
    txt 2번 요구사항: 얼굴사진/전신사진/신체조건을 여기서 받는다.
    """

    class Meta:
        model = User
        fields = [
            "face_photo",
            "body_photo",
            "birth_year",  # 카카오에서 못 가져왔으면(None) 여기서 직접 입력받는다
            "gender",      # 마찬가지로 카카오에서 못 가져왔을 때의 폴백
            "height_cm",
            "weight_kg",
            "hobby_first",
            "hobby_second",
            "hobby_dislike",
            "region",
            "religion",
            "is_smoker",
            "intro",
        ]
        widgets = {
            "intro": forms.TextInput(attrs={"maxlength": 20, "placeholder": "최대 20자, 비우면 '-'로 표시"}),
        }

    def clean(self):
        cleaned = super().clean()
        # 얼굴/전신사진은 심사의 핵심 자료라 필수로 강제한다.
        if not cleaned.get("face_photo"):
            self.add_error("face_photo", "얼굴 사진은 필수입니다.")
        if not cleaned.get("body_photo"):
            self.add_error("body_photo", "전신 사진은 필수입니다.")
        if not cleaned.get("birth_year"):
            self.add_error("birth_year", "출생연도는 필수입니다.")
        if not cleaned.get("gender"):
            self.add_error("gender", "성별은 필수입니다.")
        return cleaned