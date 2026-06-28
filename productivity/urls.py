from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    dashboard_view,
    task_list_view,
    analytics_view,
    login_view,
    logout_view,
    signup_view,
    onboarding_view,
    settings_view,
    help_view,
    ChatMessageViewSet,
    TaskViewSet,
    HabitViewSet
)

router = DefaultRouter()
router.register(r'chat', ChatMessageViewSet, basename='chat-api')
router.register(r'tasks', TaskViewSet, basename='task-api')
router.register(r'habits', HabitViewSet, basename='habit-api')

urlpatterns = [
    # Page views
    path('', dashboard_view, name='dashboard'),
    path('tasks/', task_list_view, name='tasks'),
    path('analytics/', analytics_view, name='analytics'),
    path('onboarding/', onboarding_view, name='onboarding'),
    path('settings/', settings_view, name='settings'),
    path('help/', help_view, name='help'),
    
    # Auth views
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('signup/', signup_view, name='signup'),

    # REST API views
    path('api/', include(router.urls)),
]

