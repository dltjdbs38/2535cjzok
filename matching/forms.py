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
    preferred_height_codes = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple, label="상대방 키"
    )
    preferred_religions = forms.MultipleChoiceField(
        choices=User.Religion.choices, widget=forms.CheckboxSelectMultiple, label="종교"
    )
    preferred_smoking = forms.MultipleChoiceField(
        choices=SmokingPreference.choices, widget=forms.CheckboxSelectMultiple, label="흡연"
    )

    # 원하는 상대방의 취미. (내 취미가 아니라 상대에게 바라는 취미를 직접 고르는 필드)
    preferred_hobby_first = forms.ChoiceField(choices=User.Hobby.choices, label="좋아하는 것 1순위")
    preferred_hobby_second = forms.ChoiceField(choices=User.Hobby.choices, label="좋아하는 것 2순위")
    preferred_hobby_dislike = forms.ChoiceField(choices=User.Hobby.choices, label="관심없는 것 1순위")

    favorite_artist_1 = forms.CharField(
        required=False, max_length=50, label="가수 1",
        widget=forms.TextInput(attrs={"placeholder": "예: ハシタイロ"}),
    )
    favorite_artist_2 = forms.CharField(
        required=False, max_length=50, label="가수 2",
        widget=forms.TextInput(attrs={"placeholder": "예: Novocaine"}),
    )
    favorite_artist_3 = forms.CharField(
        required=False, max_length=50, label="가수 3",
        widget=forms.TextInput(attrs={"placeholder": "예: 아이유"}),
    )

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewer = viewer
        # 키 선택지는 내 성별에 따라 달라진다 (여성 -> 원하는 남성 키, 남성 -> 원하는 여성 키).
        if viewer and viewer.gender == User.Gender.MALE:
            self.fields["preferred_height_codes"].choices = HEIGHT_CHOICES_FOR_MALE
        else:
            self.fields["preferred_height_codes"].choices = HEIGHT_CHOICES_FOR_FEMALE

    @classmethod
    def initial_from_instance(cls, preference: MatchingPreference | None):
        if preference is None:
            return {}
        return {
            "preferred_regions": preference.preferred_regions_list,
            "preferred_height_codes": preference.preferred_height_codes_list,
            "preferred_religions": preference.preferred_religions_list,
            "preferred_smoking": preference.preferred_smoking_list,
            "preferred_hobby_first": preference.preferred_hobby_first,
            "preferred_hobby_second": preference.preferred_hobby_second,
            "preferred_hobby_dislike": preference.preferred_hobby_dislike,
            "favorite_artist_1": preference.favorite_artist_1,
            "favorite_artist_2": preference.favorite_artist_2,
            "favorite_artist_3": preference.favorite_artist_3,
        }

    def save(self, user):
        preference, _ = MatchingPreference.objects.get_or_create(user=user)
        preference.preferred_regions = ",".join(self.cleaned_data["preferred_regions"])
        preference.preferred_height_codes = ",".join(self.cleaned_data["preferred_height_codes"])
        preference.preferred_religions = ",".join(self.cleaned_data["preferred_religions"])
        preference.preferred_smoking = ",".join(self.cleaned_data["preferred_smoking"])
        preference.preferred_hobby_first = self.cleaned_data["preferred_hobby_first"]
        preference.preferred_hobby_second = self.cleaned_data["preferred_hobby_second"]
        preference.preferred_hobby_dislike = self.cleaned_data["preferred_hobby_dislike"]
        preference.favorite_artist_1 = self.cleaned_data["favorite_artist_1"]
        preference.favorite_artist_2 = self.cleaned_data["favorite_artist_2"]
        preference.favorite_artist_3 = self.cleaned_data["favorite_artist_3"]
        preference.save()
        return preference
