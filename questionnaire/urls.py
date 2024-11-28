from django.urls import path
from . import views

from django.urls import path
from . import views

urlpatterns = [
    path('questionnaire/', views.questionnaire_form, name='questionnaire_form'),
    path('oauth2callback/', views.oauth2callback, name='oauth2callback'),
]
