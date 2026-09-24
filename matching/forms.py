from django import forms

from accounts.models import User
from .models import (
    HEIGHT_CHOICES_FOR_FEMALE,
    HEIGHT_CHOICES_FOR_MALE,
    MatchingPreference,
    SmokingPreference,
)


class MatchingPreferenceForm(forms.Form):
    """
    ModelForm 대신 일반 Form으로 만들었다 - preferred_regions 등이 모델에선
    콤마구분 문자열 하나지만, 화면에서는 체크박스 여러 개로 받아야 해서
    화면 쪽 표현(리스트)과 저장 쪽 표현(문자열)을 이 폼이 직접 변환해준다.
    """

    preferred_regions = forms.MultipleChoiceField(
        choices=User.Region.choices, widget=forms.CheckboxSelectMultiple, label="거주지역"
    )
    preferred_height_code = forms.ChoiceField(widget=forms.RadioSelect, label="상대방 키")
    preferred_religions = forms.MultipleChoiceField(
        choices=User.Religion.choices, widget=forms.CheckboxSelectMultiple, label="종교"
    )
    preferred_smoking = forms.MultipleChoiceField(
        choices=SmokingPreference.choices, widget=forms.CheckboxSelectMultiple, label="흡연"
    )
    favorite_artists = forms.CharField(
        required=False, max_length=200, label="좋아하는 가수 (선택, 최대 3명)"
    )

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        # 키 선택지는 내 성별에 따라 달라진다 (여성 -> 원하는 남성 키, 남성 -> 원하는 여성 키).
        if viewer and viewer.gender == User.Gender.MALE:
            self.fields["preferred_height_code"].choices = HEIGHT_CHOICES_FOR_MALE
        else:
            self.fields["preferred_height_code"].choices = HEIGHT_CHOICES_FOR_FEMALE

    @classmethod
    def initial_from_instance(cls, preference: MatchingPreference | None):
        if preference is None:
            return {}
        return {
            "preferred_regions": preference.preferred_regions_list,
            "preferred_height_code": preference.preferred_height_code,
            "preferred_religions": preference.preferred_religions_list,
            "preferred_smoking": preference.preferred_smoking_list,
            "favorite_artists": preference.favorite_artists,
        }

    def save(self, user):
        preference, _ = MatchingPreference.objects.get_or_create(user=user)
        preference.preferred_regions = ",".join(self.cleaned_data["preferred_regions"])
        preference.preferred_height_code = self.cleaned_data["preferred_height_code"]
        preference.preferred_religions = ",".join(self.cleaned_data["preferred_religions"])
        preference.preferred_smoking = ",".join(self.cleaned_data["preferred_smoking"])
        preference.favorite_artists = self.cleaned_data["favorite_artists"]
        preference.save()
        return preference
