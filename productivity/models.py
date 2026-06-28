from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('developer', 'Developer'),
        ('designer', 'Designer'),
        ('manager', 'Manager'),
        ('student', 'Student'),
        ('freelancer', 'Freelancer'),
        ('other', 'Other'),
    ]
    GOAL_CHOICES = [
        ('task_management', 'Task Management'),
        ('focus_time', 'Deep Focus & Flow'),
        ('habit_tracking', 'Habit Tracking'),
        ('scheduling', 'Smart Scheduling'),
        ('all', 'All of the Above'),
    ]
    SCHEDULE_CHOICES = [
        ('morning', 'Morning (6 AM – 12 PM)'),
        ('afternoon', 'Afternoon (12 PM – 6 PM)'),
        ('evening', 'Evening (6 PM – 12 AM)'),
        ('flexible', 'Flexible / No Preference'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar_url = models.URLField(
        max_length=1000,
        default="https://lh3.googleusercontent.com/aida-public/AB6AXuDKyikOCROszoGheai5pxSAQclGd5Nc6zIw99cYkQNxykhjDgA8HACtE-0eeMduP-HQOR134PHfbHHHyJZvBlrgPF4EBH16uqSu2W7E9VpKgBAEG2yHCOQZs2-xL_bIuQMNWkXSeaX6D0tNdKoNE5BYS03TFjnlRhR4VF_rYoDOh5_Dr5_GRkN0EEBk-4nwvpzrslQelQVAjplh8KMwJGpFN-RI1eB6q-mtvkXCuJHm6hzQrhc6l5Zq1kEBMFHLcljnLm5tzR8wgh8"
    )
    flow_score = models.IntegerField(default=0)
    daily_saved_hours = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    flow_state_active = models.BooleanField(default=False)

    # Onboarding fields
    onboarding_completed = models.BooleanField(default=False)
    work_role = models.CharField(max_length=50, choices=ROLE_CHOICES, blank=True, default='')
    primary_goal = models.CharField(max_length=50, choices=GOAL_CHOICES, blank=True, default='')
    preferred_work_hours = models.CharField(max_length=50, choices=SCHEDULE_CHOICES, blank=True, default='')

    def __str__(self):
        return f"{self.user.username}'s Profile"

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    instance.profile.save()

class Category(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='categories',
        null=True,     # null for system/default categories
        blank=True
    )
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=50, default="primary")

    class Meta:
        verbose_name_plural = "Categories"
        # A user can't have two categories with the same name
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'],
                condition=models.Q(user__isnull=False),
                name='unique_category_per_user'
            )
        ]

    def __str__(self):
        return self.name

class Task(models.Model):
    PRIORITY_CHOICES = [
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    due_date = models.DateTimeField(null=True, blank=True)
    ai_score = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'completed'], name='task_user_completed_idx'),
            models.Index(fields=['user', 'due_date'],  name='task_user_due_date_idx'),
            models.Index(fields=['user', 'priority'],  name='task_user_priority_idx'),
            models.Index(fields=['completed_at'],       name='task_completed_at_idx'),
        ]
        ordering = ['completed', '-ai_score']

    def __str__(self):
        return self.title

class HabitEntry(models.Model):
    habit = models.ForeignKey(
        'Habit',
        on_delete=models.CASCADE,
        related_name='entries'
    )
    date = models.DateField()
    completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('habit', 'date')
        ordering = ['date']
        indexes = [
            models.Index(fields=['habit', 'date']),
        ]

    def __str__(self):
        return f"{self.habit.name} — {self.date}: {'✓' if self.completed else '✗'}"

class Habit(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='habits')
    name = models.CharField(max_length=255)
    streak_days = models.IntegerField(default=0)
    # Storing history, e.g. [{"day": "Mon", "completed": true}, ...] (DEPRECATED: Use HabitEntry instead)
    history = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class CalendarIntegration(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendar_integrations')
    provider = models.CharField(max_length=100) # e.g. Google Calendar, Microsoft Outlook
    connected_email = models.EmailField()
    sync_active = models.BooleanField(default=True)
    last_synced = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'provider', 'connected_email'],
                name='unique_calendar_integration'
            )
        ]

    def __str__(self):
        return f"{self.provider} ({self.connected_email})"

class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ('USER', 'User'),
        ('AI', 'AI'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    # To support tables or custom rich UI logs generated by assistant
    structured_data = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'timestamp'], name='chat_user_timestamp_idx'),
        ]
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.role}: {self.content[:30]}..."
