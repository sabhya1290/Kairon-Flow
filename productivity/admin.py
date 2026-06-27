from django.contrib import admin
from .models import UserProfile, Category, Task, Habit, CalendarIntegration, ChatMessage

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'flow_score', 'daily_saved_hours', 'flow_state_active')
    search_fields = ('user__username',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'color')
    search_fields = ('name',)

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'priority', 'due_date', 'ai_score', 'completed')
    list_filter = ('priority', 'completed', 'category')
    search_fields = ('title', 'user__username')

@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'streak_days')
    search_fields = ('name', 'user__username')

@admin.register(CalendarIntegration)
class CalendarIntegrationAdmin(admin.ModelAdmin):
    list_display = ('provider', 'user', 'connected_email', 'sync_active', 'last_synced')
    list_filter = ('provider', 'sync_active')
    search_fields = ('connected_email', 'user__username')

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('role', 'user', 'content_preview', 'timestamp')
    list_filter = ('role', 'timestamp')
    search_fields = ('content', 'user__username')

    def content_preview(self, obj):
        return obj.content[:50]
    content_preview.short_description = "Content"
