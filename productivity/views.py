from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.utils import timezone
from django.http import JsonResponse
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action

from .models import UserProfile, Category, Task, Habit, CalendarIntegration, ChatMessage
from .serializers import ChatMessageSerializer

import datetime
import functools
import re

def compute_ai_score(priority: str, due_date) -> int:
    """
    Simple deterministic score based on priority and deadline proximity.
    HIGH = base 80, MEDIUM = base 50, LOW = base 20.
    Add up to 20 urgency points if due within 24 hours,
    10 if due within 72 hours, 5 if due within 7 days.
    Cap at 100.
    """
    base = {'HIGH': 80, 'MEDIUM': 50, 'LOW': 20}.get(priority, 50)
    if due_date:
        now = timezone.now()
        delta = (due_date - now).total_seconds()
        if delta < 86400:
            base += 20
        elif delta < 259200:
            base += 10
        elif delta < 604800:
            base += 5
    return min(base, 100)


def create_personalized_data(user):
    """One-time creation of personalized initial data based on user's onboarding preferences."""
    profile = user.profile
    role = profile.work_role
    goal = profile.primary_goal
    schedule = profile.preferred_work_hours
    username = user.first_name or user.username

    # Determine focus time based on schedule preference
    if schedule == 'morning':
        focus_start_hour = 9
        focus_label = "Morning Focus Block"
    elif schedule == 'afternoon':
        focus_start_hour = 13
        focus_label = "Afternoon Focus Block"
    elif schedule == 'evening':
        focus_start_hour = 18
        focus_label = "Evening Focus Block"
    else:
        focus_start_hour = 10
        focus_label = "Flexible Focus Block"

    # Create categories based on role
    if role == 'developer':
        cats = [
            ("Development", "secondary"),
            ("Code Review", "outline"),
            ("DevOps", "error"),
        ]
    elif role == 'designer':
        cats = [
            ("Design", "secondary"),
            ("Prototyping", "outline"),
            ("User Research", "error"),
        ]
    elif role == 'manager':
        cats = [
            ("Planning", "secondary"),
            ("Meetings", "outline"),
            ("Reports", "error"),
        ]
    elif role == 'student':
        cats = [
            ("Study", "secondary"),
            ("Assignments", "outline"),
            ("Research", "error"),
        ]
    elif role == 'freelancer':
        cats = [
            ("Client Work", "secondary"),
            ("Admin", "outline"),
            ("Outreach", "error"),
        ]
    else:
        cats = [
            ("Work", "secondary"),
            ("Personal", "outline"),
            ("Admin", "error"),
        ]

    created_cats = []
    for name, color in cats:
        cat, _ = Category.objects.get_or_create(name=name, defaults={"color": color})
        created_cats.append(cat)

    # Create starter tasks based on goal
    now = timezone.localtime(timezone.now())
    if goal == 'task_management' or goal == 'all':
        due1 = now.replace(hour=focus_start_hour, minute=0, second=0, microsecond=0)
        Task.objects.create(
            user=user,
            title=f"Set up your first project workspace",
            category=created_cats[0],
            priority="HIGH",
            due_date=due1,
            ai_score=compute_ai_score("HIGH", due1),
            completed=False
        )
        due2 = now + datetime.timedelta(days=1)
        Task.objects.create(
            user=user,
            title=f"Organize tasks by priority",
            category=created_cats[1],
            priority="MEDIUM",
            due_date=due2,
            ai_score=compute_ai_score("MEDIUM", due2),
            completed=False
        )
    if goal == 'focus_time' or goal == 'all':
        due3 = now.replace(hour=focus_start_hour, minute=0, second=0, microsecond=0)
        Task.objects.create(
            user=user,
            title=f"Complete your first {focus_label}",
            category=created_cats[0],
            priority="HIGH",
            due_date=due3,
            ai_score=compute_ai_score("HIGH", due3),
            completed=False
        )
    if goal == 'habit_tracking' or goal == 'all':
        due4 = now + datetime.timedelta(days=1)
        Task.objects.create(
            user=user,
            title="Set up your daily habits",
            category=created_cats[1],
            priority="MEDIUM",
            due_date=due4,
            ai_score=compute_ai_score("MEDIUM", due4),
            completed=False
        )
    if goal == 'scheduling' or goal == 'all':
        due5 = now + datetime.timedelta(days=2)
        Task.objects.create(
            user=user,
            title="Connect your calendar for smart scheduling",
            category=created_cats[2] if len(created_cats) > 2 else created_cats[0],
            priority="MEDIUM",
            due_date=due5,
            ai_score=compute_ai_score("MEDIUM", due5),
            completed=False
        )

    # If no specific goal matched, create generic starter tasks
    if not Task.objects.filter(user=user).exists():
        due6 = now + datetime.timedelta(days=1)
        Task.objects.create(
            user=user,
            title="Explore your Kairon Flow dashboard",
            category=created_cats[0],
            priority="MEDIUM",
            due_date=due6,
            ai_score=compute_ai_score("MEDIUM", due6),
            completed=False
        )

    # Create starter habits based on goal
    if goal in ('habit_tracking', 'all'):
        Habit.objects.create(
            user=user,
            name="Daily Planning Session",
            streak_days=0,
            history=[
                {"day": "Mon", "completed": False},
                {"day": "Tue", "completed": False},
                {"day": "Wed", "completed": False},
                {"day": "Thu", "completed": False},
                {"day": "Fri", "completed": False},
                {"day": "Sat", "completed": False},
                {"day": "Sun", "completed": False}
            ]
        )
        Habit.objects.create(
            user=user,
            name="Mindful Break",
            streak_days=0,
            history=[
                {"day": "Mon", "completed": False},
                {"day": "Tue", "completed": False},
                {"day": "Wed", "completed": False},
                {"day": "Thu", "completed": False},
                {"day": "Fri", "completed": False},
                {"day": "Sat", "completed": False},
                {"day": "Sun", "completed": False}
            ]
        )
    elif goal in ('focus_time', 'all'):
        Habit.objects.create(
            user=user,
            name="Deep Work Session",
            streak_days=0,
            history=[
                {"day": "Mon", "completed": False},
                {"day": "Tue", "completed": False},
                {"day": "Wed", "completed": False},
                {"day": "Thu", "completed": False},
                {"day": "Fri", "completed": False},
                {"day": "Sat", "completed": False},
                {"day": "Sun", "completed": False}
            ]
        )

    # Create personalized welcome chat message
    role_label = dict(UserProfile.ROLE_CHOICES).get(role, 'professional')
    goal_label = dict(UserProfile.GOAL_CHOICES).get(goal, 'productivity')
    schedule_label = dict(UserProfile.SCHEDULE_CHOICES).get(schedule, 'flexible')

    task_count = Task.objects.filter(user=user, completed=False).count()

    ChatMessage.objects.create(
        user=user,
        role="AI",
        content=(
            f"Welcome, {username}! 🎉 Your workspace is ready.\n\n"
            f"I've set things up based on your preferences:\n"
            f"• **Role**: {role_label}\n"
            f"• **Focus**: {goal_label}\n"
            f"• **Schedule**: {schedule_label}\n\n"
            f"You have **{task_count} starter tasks** to get you going. "
            f"Try typing a command like \"help\" to see what I can do, or just tell me what you'd like to work on!"
        )
    )


def require_onboarding(view_func):
    """Decorator that redirects users to onboarding if they haven't completed it."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.profile.onboarding_completed:
            return redirect('onboarding')
        return view_func(request, *args, **kwargs)
    return wrapper


# View routing handlers
@login_required
@require_onboarding
def dashboard_view(request):
    # Fetch user's data
    chat_messages = ChatMessage.objects.filter(user=request.user).order_by('timestamp')
    priority_tasks = Task.objects.filter(user=request.user, completed=False).order_by('-priority', '-ai_score')[:4]
    profile = request.user.profile
    categories = Category.objects.all()

    # Simple mock timeline representation
    schedule = profile.preferred_work_hours
    if schedule == 'morning':
        timeline = [
            {"time": "06:00 AM", "title": "Morning Routine", "completed": True, "active": False},
            {"time": "07:00 AM - 11:00 AM", "title": "Deep Work Focus Block", "completed": False, "active": True},
            {"time": "11:30 AM", "title": "Review & Planning", "completed": False, "active": False},
        ]
    elif schedule == 'afternoon':
        timeline = [
            {"time": "12:00 PM", "title": "Lunch & Prep", "completed": True, "active": False},
            {"time": "01:00 PM - 05:00 PM", "title": "Deep Work Focus Block", "completed": False, "active": True},
            {"time": "05:30 PM", "title": "End-of-Day Review", "completed": False, "active": False},
        ]
    elif schedule == 'evening':
        timeline = [
            {"time": "06:00 PM", "title": "Session Start", "completed": True, "active": False},
            {"time": "07:00 PM - 10:00 PM", "title": "Deep Work Focus Block", "completed": False, "active": True},
            {"time": "10:30 PM", "title": "Wind Down & Review", "completed": False, "active": False},
        ]
    else:
        timeline = [
            {"time": "09:00 AM", "title": "Morning Sync", "completed": True, "active": False},
            {"time": "10:00 AM - 12:00 PM", "title": "Deep Work Focus Block", "completed": False, "active": True},
            {"time": "01:00 PM", "title": "Afternoon Planning", "completed": False, "active": False},
        ]

    context = {
        'profile': profile,
        'chat_messages': chat_messages,
        'priority_tasks': priority_tasks,
        'timeline': timeline,
        'categories': categories,
        'current_tab': 'chat',
    }
    return render(request, 'productivity/dashboard.html', context)

@login_required
@require_onboarding
def task_list_view(request):
    if request.method == "POST":
        action = request.POST.get("action")
        
        # 1. CREATE TASK
        if action == "create":
            title = request.POST.get("title", "").strip()
            category_id = request.POST.get("category_id")
            priority = request.POST.get("priority", "MEDIUM")
            due_date_str = request.POST.get("due_date")
            duration_value = request.POST.get("duration_value")
            duration_unit = request.POST.get("duration_unit")
            
            if not title:
                return JsonResponse({"status": "error", "message": "Title is required"}, status=400)
                
            # Category
            category = None
            if category_id:
                category = Category.objects.filter(id=category_id).first()
                
            # Due Date
            due_date = None
            now = timezone.now()
            if duration_value and duration_value.strip():
                try:
                    amount = int(duration_value)
                    unit = duration_unit.lower()
                    if unit == 'minutes':
                        due_date = now + datetime.timedelta(minutes=amount)
                    elif unit == 'hours':
                        due_date = now + datetime.timedelta(hours=amount)
                    elif unit == 'days':
                        due_date = now + datetime.timedelta(days=amount)
                except ValueError:
                    pass
            elif due_date_str:
                from django.utils.dateparse import parse_datetime
                due_date = parse_datetime(due_date_str)
                if due_date and timezone.is_naive(due_date):
                    due_date = timezone.make_aware(due_date, timezone.get_current_timezone())
            
            task = Task.objects.create(
                user=request.user,
                title=title,
                category=category,
                priority=priority,
                due_date=due_date,
                ai_score=compute_ai_score(priority, due_date),
                completed=False
            )
            return JsonResponse({
                "status": "success", 
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "priority": task.priority,
                    "completed": task.completed
                }
            })
            
        # 2. UPDATE TASK
        elif action == "update":
            task_id = request.POST.get("task_id")
            task = Task.objects.filter(user=request.user, id=task_id).first()
            if not task:
                return JsonResponse({"status": "error", "message": "Task not found"}, status=404)
                
            title = request.POST.get("title")
            category_id = request.POST.get("category_id")
            priority = request.POST.get("priority")
            due_date_str = request.POST.get("due_date")
            duration_value = request.POST.get("duration_value")
            duration_unit = request.POST.get("duration_unit")
            completed_str = request.POST.get("completed")
            
            if title is not None:
                task.title = title.strip()
            if category_id is not None:
                if category_id == "":
                    task.category = None
                else:
                    task.category = Category.objects.filter(id=category_id).first()
            if priority is not None:
                task.priority = priority
            
            # Due Date
            now = timezone.now()
            if duration_value and duration_value.strip():
                try:
                    amount = int(duration_value)
                    unit = duration_unit.lower()
                    if unit == 'minutes':
                        task.due_date = now + datetime.timedelta(minutes=amount)
                    elif unit == 'hours':
                        task.due_date = now + datetime.timedelta(hours=amount)
                    elif unit == 'days':
                        task.due_date = now + datetime.timedelta(days=amount)
                except ValueError:
                    pass
            elif due_date_str is not None:
                if due_date_str == "":
                    task.due_date = None
                else:
                    from django.utils.dateparse import parse_datetime
                    due_date = parse_datetime(due_date_str)
                    if due_date:
                        if timezone.is_naive(due_date):
                            due_date = timezone.make_aware(due_date, timezone.get_current_timezone())
                        task.due_date = due_date
            
            if completed_str is not None:
                new_completed = completed_str.lower() == "true"
                if new_completed and not task.completed:
                    task.completed_at = timezone.now()
                elif not new_completed and task.completed:
                    task.completed_at = None
                task.completed = new_completed
                
            task.save()
            return JsonResponse({"status": "success"})
            
        # 3. DELETE TASK
        elif action == "delete":
            task_id = request.POST.get("task_id")
            task = Task.objects.filter(user=request.user, id=task_id).first()
            if not task:
                return JsonResponse({"status": "error", "message": "Task not found"}, status=404)
            task.delete()
            return JsonResponse({"status": "success"})
            
        # 4. GET STATUS
        elif action == "get_status":
            task_id = request.POST.get("task_id")
            task = Task.objects.filter(user=request.user, id=task_id).first()
            if not task:
                return JsonResponse({"status": "error", "message": "Task not found"}, status=404)
            return JsonResponse({
                "status": "success",
                "priority": task.priority,
                "completed": task.completed,
                "due_date": task.due_date.isoformat() if task.due_date else None
            })
            
        # 5. DEFAULT TOGGLE COMPLETION (backward compatibility)
        else:
            task_id = request.POST.get("task_id")
            task = Task.objects.filter(user=request.user, id=task_id).first()
            if task:
                task.completed = not task.completed
                if task.completed:
                    task.completed_at = timezone.now()
                else:
                    task.completed_at = None
                task.save()
                return JsonResponse({"status": "success", "completed": task.completed})
            return JsonResponse({"status": "error", "message": "Task not found"}, status=404)

    tasks = Task.objects.filter(user=request.user).order_by('completed', '-priority', '-ai_score')
    profile = request.user.profile
    categories = Category.objects.all()

    context = {
        'profile': profile,
        'tasks': tasks,
        'categories': categories,
        'current_tab': 'tasks',
    }
    return render(request, 'productivity/tasks.html', context)

@login_required
@require_onboarding
def analytics_view(request):
    profile = request.user.profile

    # Handle POST requests for habit interactions
    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'toggle_habit_day':
            habit_id = request.POST.get('habit_id')
            day_index_str = request.POST.get('day_index')
            if not habit_id or day_index_str is None:
                return JsonResponse({'status': 'error', 'message': 'Habit ID and Day Index are required'}, status=400)
            try:
                day_index = int(day_index_str)
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'Invalid day index'}, status=400)

            try:
                habit = Habit.objects.get(id=habit_id, user=request.user)
                if 0 <= day_index < len(habit.history):
                    habit.history[day_index]['completed'] = not habit.history[day_index]['completed']
                    # Recalculate streak
                    streak = 0
                    for day in reversed(habit.history):
                         if day['completed']:
                             streak += 1
                         else:
                             break
                    habit.streak_days = streak
                    habit.save()
                    return JsonResponse({
                        'status': 'success',
                        'completed': habit.history[day_index]['completed'],
                        'streak_days': habit.streak_days,
                    })
                else:
                    return JsonResponse({'status': 'error', 'message': 'Day index out of range'}, status=400)
            except Habit.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Habit not found'}, status=404)
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

        elif action == 'create_habit':
            name = request.POST.get('name', '').strip()
            if name:
                try:
                    habit = Habit.objects.create(
                        user=request.user,
                        name=name,
                        streak_days=0,
                        history=[
                            {"day": "Mon", "completed": False},
                            {"day": "Tue", "completed": False},
                            {"day": "Wed", "completed": False},
                            {"day": "Thu", "completed": False},
                            {"day": "Fri", "completed": False},
                            {"day": "Sat", "completed": False},
                            {"day": "Sun", "completed": False},
                        ]
                    )
                    return JsonResponse({'status': 'success', 'habit_id': habit.id, 'name': habit.name})
                except Exception as e:
                    return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            return JsonResponse({'status': 'error', 'message': 'Name is required'}, status=400)

        elif action == 'delete_habit':
            habit_id = request.POST.get('habit_id')
            try:
                habit = Habit.objects.get(id=habit_id, user=request.user)
                habit.delete()
                return JsonResponse({'status': 'success'})
            except Habit.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Habit not found'}, status=404)
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

        return JsonResponse({'status': 'error', 'message': 'Unknown action'}, status=400)

    # GET — compute real analytics
    habits = Habit.objects.filter(user=request.user)
    all_tasks = Task.objects.filter(user=request.user)
    total_tasks = all_tasks.count()
    completed_tasks = all_tasks.filter(completed=True).count()
    completion_rate = round((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0

    # Task priority breakdown
    high_count = all_tasks.filter(priority='HIGH').count()
    medium_count = all_tasks.filter(priority='MEDIUM').count()
    low_count = all_tasks.filter(priority='LOW').count()

    # Weekly completion trend (last 7 days)
    today = timezone.localtime(timezone.now()).date()
    weekly_data = []
    max_completed_day = 0
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_completed = all_tasks.filter(
            completed=True,
            completed_at__date=day
        ).count()
        if day_completed > max_completed_day:
            max_completed_day = day_completed
        weekly_data.append({
            'label': day.strftime('%a'),
            'date': day.strftime('%b %d'),
            'count': day_completed,
        })
    # Compute bar height percentages
    for d in weekly_data:
        d['pct'] = round((d['count'] / max_completed_day * 100)) if max_completed_day > 0 else 0

    # Completion rate trend (simple: compare this week vs hypothetical baseline)
    trend_up = completion_rate >= 50

    context = {
        'profile': profile,
        'habits': habits,
        'current_tab': 'analytics',
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'completion_rate': completion_rate,
        'trend_up': trend_up,
        'high_count': high_count,
        'medium_count': medium_count,
        'low_count': low_count,
        'weekly_data': weekly_data,
    }
    return render(request, 'productivity/analytics.html', context)

def login_view(request):
    if request.user.is_authenticated:
        if not request.user.profile.onboarding_completed:
            return redirect('onboarding')
        return redirect('dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                if not user.profile.onboarding_completed:
                    return redirect('onboarding')
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'productivity/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

from django import forms
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm

class KaironSignupForm(BaseUserCreationForm):
    email = forms.EmailField(required=False, max_length=254)
    first_name = forms.CharField(required=False, max_length=150, strip=True)

    class Meta(BaseUserCreationForm.Meta):
        fields = BaseUserCreationForm.Meta.fields + ('email', 'first_name')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get('email', '')
        user.first_name = self.cleaned_data.get('first_name', '')
        if commit:
            user.save()
        return user

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('onboarding')
    if request.method == 'POST':
        form = KaironSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('onboarding')
    else:
        form = KaironSignupForm()
    return render(request, 'productivity/login.html', {'signup_form': form, 'signup_mode': True})


@login_required
def onboarding_view(request):
    profile = request.user.profile

    # If already onboarded, go to dashboard
    if profile.onboarding_completed:
        return redirect('dashboard')

    if request.method == 'POST':
        # Collect form data
        first_name = request.POST.get('first_name', '').strip()
        work_role = request.POST.get('work_role', '')
        primary_goal = request.POST.get('primary_goal', '')
        preferred_work_hours = request.POST.get('preferred_work_hours', '')

        # Save user's first name
        if first_name:
            request.user.first_name = first_name
            request.user.save()

        # Save preferences to profile
        profile.work_role = work_role
        profile.primary_goal = primary_goal
        profile.preferred_work_hours = preferred_work_hours
        profile.onboarding_completed = True
        profile.save()

        # Create personalized initial data
        create_personalized_data(request.user)

        return redirect('dashboard')

    return render(request, 'productivity/onboarding.html', {
        'role_choices': UserProfile.ROLE_CHOICES,
        'goal_choices': UserProfile.GOAL_CHOICES,
        'schedule_choices': UserProfile.SCHEDULE_CHOICES,
    })


# REST API Endpoint for Chatbot Panel
class ChatMessageViewSet(viewsets.ModelViewSet):
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatMessage.objects.filter(user=self.request.user).order_by('timestamp')

    @staticmethod
    def _parse_time_str(time_str):
        """Parse a time string like '5pm', '5:30pm', '17:00' into (hour, minute)."""
        import re
        if not time_str:
            return (17, 0)  # default to 5 PM

        time_str = time_str.strip().lower()

        # Match "5pm", "5:30pm", "5:30 pm", "5 pm"
        match = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', time_str)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            period = match.group(3)
            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0
            return (hour, minute)

        # Match 24-hour format "17:00"
        match = re.match(r'(\d{1,2}):(\d{2})', time_str)
        if match:
            return (int(match.group(1)), int(match.group(2)))

        return (17, 0)  # fallback

    def _parse_and_execute(self, user, content):
        """Smart AI that parses user messages and takes real actions."""
        text = content.lower().strip()
        ai_content = ""
        structured_data = None
        username = user.first_name or user.username

        # ── ADD TASK ──────────────────────────────────────────────
        # Matches: "add task ...", "create task ...", "new task ..."
        # Supports: "add task Buy groceries high 5pm"
        #           "add task Fix bug medium tomorrow 3pm"
        #           "add task Read docs low in 2 hours"
        add_task_match = re.match(
            r'(?:add|create|new)\s+(?:a\s+)?task\s*[:\-]?\s*(.+)',
            text, re.IGNORECASE
        )
        if add_task_match:
            raw = add_task_match.group(1).strip()

            # Extract priority (high/medium/low)
            priority = 'MEDIUM'
            priority_label = 'Medium'
            priority_pattern = r'\b(high|medium|med|low)\b'
            pri_match = re.search(priority_pattern, raw, re.IGNORECASE)
            if pri_match:
                p = pri_match.group(1).lower()
                if p == 'high':
                    priority, priority_label = 'HIGH', 'High'
                elif p in ('medium', 'med'):
                    priority, priority_label = 'MEDIUM', 'Medium'
                elif p == 'low':
                    priority, priority_label = 'LOW', 'Low'
                raw = re.sub(priority_pattern, '', raw, flags=re.IGNORECASE).strip()

            # Extract time/date
            now = timezone.localtime(timezone.now())
            due_date = None
            due_label = ''

            # Pattern: "in X hours/minutes"
            in_match = re.search(r'in\s+(\d+)\s*(hours?|hrs?|minutes?|mins?|days?)', raw, re.IGNORECASE)
            if in_match:
                amount = int(in_match.group(1))
                unit = in_match.group(2).lower()
                if unit.startswith('hour') or unit.startswith('hr'):
                    due_date = now + datetime.timedelta(hours=amount)
                    due_label = f"in {amount} hour{'s' if amount != 1 else ''}"
                elif unit.startswith('min'):
                    due_date = now + datetime.timedelta(minutes=amount)
                    due_label = f"in {amount} minute{'s' if amount != 1 else ''}"
                elif unit.startswith('day'):
                    due_date = now + datetime.timedelta(days=amount)
                    due_label = f"in {amount} day{'s' if amount != 1 else ''}"
                raw = raw[:in_match.start()] + raw[in_match.end():]
                raw = raw.strip()

            # Pattern: "tomorrow [time]" or "today [time]"
            if not due_date:
                day_match = re.search(r'(today|tomorrow)\s*(?:at\s*)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?', raw, re.IGNORECASE)
                if day_match:
                    day_word = day_match.group(1).lower()
                    time_part = day_match.group(2)
                    if day_word == 'tomorrow':
                        base = now + datetime.timedelta(days=1)
                    else:
                        base = now
                    hour, minute = self._parse_time_str(time_part)
                    due_date = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    time_str = due_date.strftime("%I:%M %p").lstrip("0")
                    due_label = f"{day_word.capitalize()} at {time_str}"
                    raw = raw[:day_match.start()] + raw[day_match.end():]
                    raw = raw.strip()

            # Pattern: standalone time like "5pm", "5:30pm", "17:00"
            if not due_date:
                time_match = re.search(r'\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b', raw, re.IGNORECASE)
                if time_match:
                    hour, minute = self._parse_time_str(time_match.group(1))
                    due_date = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    # If the time has already passed today, set it for tomorrow
                    if due_date <= now:
                        due_date += datetime.timedelta(days=1)
                        due_label = f"Tomorrow at {due_date.strftime('%I:%M %p').lstrip('0')}"
                    else:
                        due_label = f"Today at {due_date.strftime('%I:%M %p').lstrip('0')}"
                    raw = raw[:time_match.start()] + raw[time_match.end():]
                    raw = raw.strip()

            # Fallback: no time specified → due tomorrow at same time
            if not due_date:
                due_date = now + datetime.timedelta(days=1)
                due_label = "Tomorrow"

            # Clean up title (remove leftover punctuation/spaces)
            title = re.sub(r'\s+', ' ', raw).strip(' ,-:')
            if not title:
                title = "Untitled Task"
            title = title[0].upper() + title[1:] if title else "Untitled Task"

            cat = Category.objects.first()
            task = Task.objects.create(
                user=user,
                title=title,
                category=cat,
                priority=priority,
                due_date=due_date,
                ai_score=compute_ai_score(priority, due_date),
                completed=False
            )

            # Calculate time remaining for confirmation
            remaining_secs = int((due_date - now).total_seconds())
            if remaining_secs < 3600:
                time_left = f"{remaining_secs // 60}m"
            elif remaining_secs < 86400:
                h = remaining_secs // 3600
                m = (remaining_secs % 3600) // 60
                time_left = f"{h}h {m}m" if m else f"{h}h"
            else:
                d = remaining_secs // 86400
                h = (remaining_secs % 86400) // 3600
                time_left = f"{d}d {h}h" if h else f"{d}d"

            structured_data = {
                "type": "task_created",
                "task_id": task.id,
                "priority": task.priority,
                "time_left": time_left,
            }

            ai_content = (
                f"✅ Task created successfully!\n\n"
                f"• **Title**: {task.title}\n"
                f"• **Priority**: {priority_label}\n"
                f"• **Due**: {due_label}\n"
                f"• **Time left**: {time_left}\n\n"
                f"You can view it in the **Master Task List** or in the sidebar."
            )
            return ai_content, structured_data

        # ── COMPLETE / DONE TASK ──────────────────────────────────
        # Matches: "complete task ...", "done with ...", "finish ..."
        done_match = re.match(
            r'(?:complete|done\s+(?:with)?|finish|mark\s+(?:as\s+)?done)\s*[:\-]?\s*(.+)',
            text, re.IGNORECASE
        )
        if done_match:
            query = done_match.group(1).strip()
            task = Task.objects.filter(
                user=user, completed=False,
                title__icontains=query
            ).first()
            if task:
                task.completed = True
                task.save()
                remaining = Task.objects.filter(user=user, completed=False).count()
                ai_content = (
                    f"✅ Marked **\"{task.title}\"** as complete!\n\n"
                    f"Great work, {username}. You have **{remaining}** task{'s' if remaining != 1 else ''} remaining."
                )
            else:
                ai_content = f"I couldn't find an active task matching \"{query}\". Try checking the **Master Task List** to see your current tasks."
            return ai_content, structured_data

        # ── DELETE TASK ───────────────────────────────────────────
        delete_match = re.match(
            r'(?:delete|remove)\s+(?:a\s+)?task\s*[:\-]?\s*(.+)',
            text, re.IGNORECASE
        )
        if delete_match:
            query = delete_match.group(1).strip()
            task = Task.objects.filter(user=user, title__icontains=query).first()
            if task:
                title = task.title
                task.delete()
                ai_content = f"🗑️ Deleted task **\"{title}\"**."
            else:
                ai_content = f"I couldn't find a task matching \"{query}\"."
            return ai_content, structured_data

        # ── ADD HABIT ─────────────────────────────────────────────
        habit_match = re.match(
            r'(?:add|create|new|track)\s+(?:a\s+)?habit\s*[:\-]?\s*(.+)',
            text, re.IGNORECASE
        )
        if habit_match:
            name = habit_match.group(1).strip().capitalize()
            habit = Habit.objects.create(
                user=user,
                name=name,
                streak_days=0,
                history=[
                    {"day": "Mon", "completed": False},
                    {"day": "Tue", "completed": False},
                    {"day": "Wed", "completed": False},
                    {"day": "Thu", "completed": False},
                    {"day": "Fri", "completed": False},
                    {"day": "Sat", "completed": False},
                    {"day": "Sun", "completed": False}
                ]
            )
            ai_content = (
                f"🎯 New habit created: **\"{habit.name}\"**\n\n"
                f"I'll track this for you daily. Check the **Analytics & Habits** tab to see your streak progress!"
            )
            return ai_content, structured_data

        # ── STATUS / SUMMARY ──────────────────────────────────────
        if any(w in text for w in ['status', 'summary', 'overview', 'how am i', 'dashboard', 'what\'s up', 'whats up']):
            total_tasks = Task.objects.filter(user=user).count()
            pending = Task.objects.filter(user=user, completed=False).count()
            completed = Task.objects.filter(user=user, completed=True).count()
            high_priority = Task.objects.filter(user=user, completed=False, priority='HIGH').count()
            habits = Habit.objects.filter(user=user)
            habit_count = habits.count()
            total_streak = sum(h.streak_days for h in habits)

            ai_content = f"📊 Here's your workspace summary, {username}:\n"
            structured_data = {
                "type": "table",
                "headers": ["Metric", "Value"],
                "rows": [
                    {"section": "📋 Total Tasks", "owner": str(total_tasks), "status": "", "status_color": ""},
                    {"section": "⏳ Pending", "owner": str(pending), "status": "Active" if pending > 0 else "Clear", "status_color": "error" if pending > 3 else "outline"},
                    {"section": "✅ Completed", "owner": str(completed), "status": "", "status_color": ""},
                    {"section": "🔴 High Priority", "owner": str(high_priority), "status": "Urgent" if high_priority > 0 else "None", "status_color": "error" if high_priority > 0 else "outline"},
                    {"section": "🎯 Habits Tracked", "owner": str(habit_count), "status": "", "status_color": ""},
                    {"section": "🔥 Total Streak Days", "owner": str(total_streak), "status": "", "status_color": ""},
                ]
            }
            return ai_content, structured_data

        # ── LIST TASKS ────────────────────────────────────────────
        if any(w in text for w in ['list task', 'show task', 'my task', 'all task', 'pending task', 'what task']):
            tasks = Task.objects.filter(user=user, completed=False).order_by('-priority', '-ai_score')[:8]
            if tasks:
                ai_content = f"📋 Here are your active tasks, {username}:"
                rows = []
                for i, t in enumerate(tasks, 1):
                    priority_color = "error" if t.priority == 'HIGH' else ("outline" if t.priority == 'MEDIUM' else "highest")
                    rows.append({
                        "section": f"{i}. {t.title}",
                        "owner": t.category.name if t.category else "General",
                        "status": t.get_priority_display(),
                        "status_color": priority_color
                    })
                structured_data = {
                    "type": "table",
                    "headers": ["Task", "Category", "Priority"],
                    "rows": rows
                }
            else:
                ai_content = f"🎉 You have no pending tasks, {username}! Time to add some or enjoy your free time."
            return ai_content, structured_data

        # ── LIST HABITS ───────────────────────────────────────────
        if any(w in text for w in ['list habit', 'show habit', 'my habit', 'all habit']):
            habits = Habit.objects.filter(user=user)
            if habits:
                ai_content = f"🎯 Your tracked habits:"
                rows = []
                for h in habits:
                    rows.append({
                        "section": h.name,
                        "owner": f"{h.streak_days} days",
                        "status": "Active" if h.streak_days > 0 else "New",
                        "status_color": "outline" if h.streak_days > 0 else "highest"
                    })
                structured_data = {
                    "type": "table",
                    "headers": ["Habit", "Streak", "Status"],
                    "rows": rows
                }
            else:
                ai_content = f"You don't have any habits tracked yet. Try saying **\"add habit Morning exercise\"** to get started!"
            return ai_content, structured_data

        # ── SCHEDULE / FOCUS ──────────────────────────────────────
        if any(w in text for w in ['schedule', 'focus', 'block', 'plan my day', 'optimize']):
            profile = user.profile
            schedule = profile.preferred_work_hours
            pending = Task.objects.filter(user=user, completed=False).order_by('-priority', '-ai_score')[:3]

            if schedule == 'morning':
                block_time = "7:00 AM – 11:00 AM"
            elif schedule == 'afternoon':
                block_time = "1:00 PM – 5:00 PM"
            elif schedule == 'evening':
                block_time = "7:00 PM – 10:00 PM"
            else:
                block_time = "10:00 AM – 12:00 PM"

            task_list = ""
            for i, t in enumerate(pending, 1):
                task_list += f"  {i}. {t.title} ({t.get_priority_display()})\n"

            if not task_list:
                task_list = "  No pending tasks! Add some to get started.\n"

            ai_content = (
                f"📅 Optimized schedule for today, {username}:\n\n"
                f"**Focus Block**: {block_time}\n"
                f"**Suggested tasks for this session:**\n{task_list}\n"
                f"💡 *Tip: Close notifications and use the focus block to tackle high-priority items first.*"
            )
            return ai_content, structured_data

        # ── HELP ──────────────────────────────────────────────────
        if any(w in text for w in ['help', 'command', 'what can you', 'how to', 'guide']):
            ai_content = (
                f"👋 Here's what I can do for you, {username}:\n\n"
                "**Task Management:**\n"
                "• **\"add task Buy groceries\"** — Creates a new task\n"
                "• **\"add task Fix bug urgent\"** — Creates a high-priority task\n"
                "• **\"complete Buy groceries\"** — Marks a task as done\n"
                "• **\"delete task Buy groceries\"** — Removes a task\n"
                "• **\"list tasks\"** — Shows all pending tasks\n\n"
                "**Habit Tracking:**\n"
                "• **\"add habit Morning meditation\"** — Creates a new habit\n"
                "• **\"list habits\"** — Shows all tracked habits\n\n"
                "**Productivity:**\n"
                "• **\"status\"** — Shows your workspace summary\n"
                "• **\"schedule\"** — Optimizes your focus blocks\n"
                "• **\"help\"** — Shows this guide\n\n"
                "Just type naturally — I'll figure out what you need! 🚀"
            )
            return ai_content, structured_data

        # ── GREETINGS ─────────────────────────────────────────────
        if any(w in text for w in ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'sup']):
            pending = Task.objects.filter(user=user, completed=False).count()
            high = Task.objects.filter(user=user, completed=False, priority='HIGH').count()

            greeting = "Good morning" if datetime.datetime.now().hour < 12 else ("Good afternoon" if datetime.datetime.now().hour < 17 else "Good evening")

            ai_content = (
                f"{greeting}, {username}! 👋\n\n"
                f"Here's a quick glance at your day:\n"
                f"• **{pending}** pending task{'s' if pending != 1 else ''}"
            )
            if high > 0:
                ai_content += f" ({high} high-priority)"
            ai_content += (
                f"\n\nWhat would you like to work on? Type **\"help\"** to see all available commands."
            )
            return ai_content, structured_data

        # ── FALLBACK ──────────────────────────────────────────────
        pending = Task.objects.filter(user=user, completed=False).count()
        ai_content = (
            f"I'm not sure what you mean by \"{content}\". 🤔\n\n"
            f"Here are some things you can try:\n"
            f"• **\"add task [name]\"** — to create a task\n"
            f"• **\"status\"** — to see your summary\n"
            f"• **\"help\"** — to see all commands\n\n"
            f"You have **{pending}** pending task{'s' if pending != 1 else ''} right now."
        )
        return ai_content, structured_data

    def perform_create(self, serializer):
        user_msg = serializer.save(user=self.request.user, role='USER')
        ai_content, structured_data = self._parse_and_execute(
            self.request.user, user_msg.content
        )
        ChatMessage.objects.create(
            user=self.request.user,
            role="AI",
            content=ai_content,
            structured_data=structured_data
        )

    @action(detail=False, methods=['post'], url_path='clear')
    def clear_history(self, request):
        username = request.user.first_name or request.user.username
        ChatMessage.objects.filter(user=request.user).delete()
        ChatMessage.objects.create(
            user=request.user,
            role="AI",
            content=f"🧹 Workspace cleared, {username}. Fresh start! What would you like to work on?"
        )
        return Response({'status': 'history cleared'}, status=status.HTTP_200_OK)


@login_required
@require_onboarding
def settings_view(request):
    profile = request.user.profile
    categories = Category.objects.all()
    integrations = CalendarIntegration.objects.filter(user=request.user)

    if request.method == "POST":
        action = request.POST.get("action")

        # Update Profile Settings
        if action == "update_profile":
            avatar_url = request.POST.get("avatar_url")
            work_role = request.POST.get("work_role")
            primary_goal = request.POST.get("primary_goal")
            preferred_work_hours = request.POST.get("preferred_work_hours")
            daily_saved_hours = request.POST.get("daily_saved_hours", "0.0")

            if avatar_url:
                profile.avatar_url = avatar_url
            if work_role:
                profile.work_role = work_role
            if primary_goal:
                profile.primary_goal = primary_goal
            if preferred_work_hours:
                profile.preferred_work_hours = preferred_work_hours
            if daily_saved_hours:
                try:
                    profile.daily_saved_hours = float(daily_saved_hours)
                except ValueError:
                    pass
            profile.save()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get("ajax") == "true":
                return JsonResponse({"status": "success", "message": "Profile updated successfully"})
            
            return redirect('settings')

        # Add/Connect Integration
        elif action == "connect_integration":
            provider = request.POST.get("provider")
            connected_email = request.POST.get("connected_email")

            if not provider or not connected_email:
                return JsonResponse({"status": "error", "message": "Provider and Email are required"}, status=400)

            if CalendarIntegration.objects.filter(user=request.user).count() >= 10:
                return JsonResponse(
                    {"status": "error", "message": "Maximum of 10 integrations allowed."},
                    status=400
                )

            integration = CalendarIntegration.objects.create(
                user=request.user,
                provider=provider,
                connected_email=connected_email,
                sync_active=True,
                last_synced=timezone.now()
            )

            return JsonResponse({
                "status": "success",
                "message": f"Successfully connected {provider}!",
                "integration": {
                    "id": integration.id,
                    "provider": integration.provider,
                    "connected_email": integration.connected_email,
                    "sync_active": integration.sync_active,
                }
            })

        # Toggle Sync state of Integration
        elif action == "toggle_sync":
            integration_id = request.POST.get("integration_id")
            integration = CalendarIntegration.objects.filter(user=request.user, id=integration_id).first()
            if not integration:
                return JsonResponse({"status": "error", "message": "Integration not found"}, status=404)

            integration.sync_active = not integration.sync_active
            integration.save()

            return JsonResponse({
                "status": "success",
                "message": f"Sync is now {'enabled' if integration.sync_active else 'disabled'}.",
                "sync_active": integration.sync_active
            })

        # Disconnect/Delete Integration
        elif action == "disconnect_integration":
            integration_id = request.POST.get("integration_id")
            integration = CalendarIntegration.objects.filter(user=request.user, id=integration_id).first()
            if not integration:
                return JsonResponse({"status": "error", "message": "Integration not found"}, status=404)

            provider = integration.provider
            integration.delete()

            return JsonResponse({
                "status": "success",
                "message": f"Successfully disconnected {provider}."
            })

        return JsonResponse({"status": "error", "message": "Invalid action"}, status=400)

    context = {
        'profile': profile,
        'categories': categories,
        'integrations': integrations,
        'current_tab': 'settings',
    }
    return render(request, 'productivity/settings.html', context)


@login_required
@require_onboarding
def help_view(request):
    profile = request.user.profile
    context = {
        'profile': profile,
        'current_tab': 'help',
    }
    return render(request, 'productivity/help.html', context)


