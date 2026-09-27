from django import forms
from django.forms.widgets import ClearableFileInput

from .models import User


class PhotoUploadWidget(ClearableFileInput):
    """
    Django 기본 ClearableFileInput은 "Currently: <파일경로 텍스트링크>" + "Clear" 체크박스 +
    "Change: [파일 선택]" 네이티브 버튼으로 렌더링되는데, 이게 아니라
    실제 사진 미리보기 + 앱 스타일 버튼으로 보이게 하려고 템플릿만 갈아끼운 위젯.
    "Clear"(사진만 지우고 새로 안 올리는 옵션)는 어차피 얼굴/전신사진이 필수 항목이라 의미가 없어서 뺐다.
    기존 파일이 있을 때(수정 화면)는 새로 선택 안 하면 원래 파일을 그대로 유지하는 동작은
    ClearableFileInput 자체 로직이라 템플릿만 바꿔도 그대로 유지된다.
    """

    template_name = "accounts/widgets/photo_upload_widget.html"


class ProfileSetupForm(forms.ModelForm):
    """
    카카오 로그인 직후(또는 승인된 회원이 정보를 고칠 때) 채우는 프로필 폼.
    txt 2번 요구사항: 얼굴사진/전신사진/신체조건을 여기서 받는다.
    항목이 하나라도 비면 제출이 안 되게 전부 필수로 강제한다.
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
            "showcase_photo",
        ]
        labels = {
            "face_photo": "얼굴이 잘 보이는 사진",
            "body_photo": "전신이 잘 나오는 사진",
            "showcase_photo": "내가 좋아하는 또는 나를 표현하는 사진",
        }
        widgets = {
            "intro": forms.TextInput(attrs={"maxlength": 20, "placeholder": "최대 20자, 비우면 '-'로 표시"}),
            "face_photo": PhotoUploadWidget(attrs={"accept": "image/*", "style": "display:none;"}),
            "body_photo": PhotoUploadWidget(attrs={"accept": "image/*", "style": "display:none;"}),
            "showcase_photo": PhotoUploadWidget(attrs={"accept": "image/*", "style": "display:none;"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Meta.fields 전부(사진 포함) 필수 처리하고, 에러 문구를 요청받은 문구로 통일한다.
        for field in self.fields.values():
            field.required = True
            field.error_messages["required"] = "모든 항목에 응답해주세요"

    def clean_is_smoker(self):
        # is_smoker는 null=True인 BooleanField라 ModelForm이 NullBooleanField로 만드는데,
        # 이 필드는 required=True를 줘도 "미응답(Unknown)"을 그냥 통과시켜버리는 특이한 동작이 있어서
        # 여기서 따로 한 번 더 막아준다.
        value = self.cleaned_data.get("is_smoker")
        if value is None:
            raise forms.ValidationError("모든 항목에 응답해주세요")
        return value
