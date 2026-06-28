from rest_framework import serializers
from .models import ChatMessage, Category, Task, Habit, UserProfile

class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'structured_data', 'timestamp']
        read_only_fields = ['id', 'role', 'timestamp']

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'color']

class TaskSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='category',
        write_only=True,
        required=False,
        allow_null=True
    )
    ai_score = serializers.IntegerField(read_only=True)

    class Meta:
        model = Task
        fields = ['id', 'title', 'category', 'category_id', 'priority',
                  'due_date', 'completed', 'completed_at', 'ai_score', 'created_at']
        read_only_fields = ['id', 'ai_score', 'created_at', 'completed_at']

class HabitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Habit
        fields = ['id', 'name', 'streak_days', 'history', 'created_at']
        read_only_fields = ['id', 'streak_days', 'created_at']

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['work_role', 'primary_goal', 'preferred_work_hours',
                  'avatar_url', 'flow_score', 'daily_saved_hours', 'onboarding_completed']
        read_only_fields = ['flow_score', 'onboarding_completed']
