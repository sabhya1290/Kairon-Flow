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
from .serializers import ChatMessageSerializer, TaskSerializer, HabitSerializer, CategorySerializer, UserProfileSerializer
from django.db.models import Q, Sum

import logging
logger = logging.getLogger(__name__)

import datetime
import functools
import re
from django_ratelimit.decorators import ratelimit

from .services.task_service import (
    compute_ai_score,
    setup_onboarding_data,
    create_task,
    update_task,
    delete_task,
    toggle_task_complete,
)
from .services.habit_service import create_habit, toggle_habit_day, delete_habit
from .constants import INTEGRATION_MAX_PER_USER


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
    chat_messages = ChatMessage.objects.filter(user=request.user).order_by('timestamp').defer('structured_data')
    priority_tasks = Task.objects.filter(user=request.user, completed=False).select_related('category').order_by('-ai_score', '-priority')[:4]
    profile = request.user.profile
    categories = Category.objects.filter(Q(user=request.user) | Q(user__isnull=True))

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
            
            task = create_task(request.user, title, category_id, priority, due_date)
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
            try:
                # Resolve fields to update
                fields = {}
                title = request.POST.get("title")
                category_id = request.POST.get("category_id")
                priority = request.POST.get("priority")
                due_date_str = request.POST.get("due_date")
                duration_value = request.POST.get("duration_value")
                duration_unit = request.POST.get("duration_unit")
                completed_str = request.POST.get("completed")

                if title is not None:
                    fields['title'] = title.strip()
                if category_id is not None:
                    fields['category_id'] = category_id
                if priority is not None:
                    fields['priority'] = priority

                # Due Date
                now = timezone.now()
                if duration_value and duration_value.strip():
                    try:
                        amount = int(duration_value)
                        unit = duration_unit.lower()
                        if unit == 'minutes':
                            fields['due_date'] = now + datetime.timedelta(minutes=amount)
                        elif unit == 'hours':
                            fields['due_date'] = now + datetime.timedelta(hours=amount)
                        elif unit == 'days':
                            fields['due_date'] = now + datetime.timedelta(days=amount)
                    except ValueError:
                        pass
                elif due_date_str is not None:
                    if due_date_str == "":
                        fields['due_date'] = None
                    else:
                        from django.utils.dateparse import parse_datetime
                        due_date = parse_datetime(due_date_str)
                        if due_date:
                            if timezone.is_naive(due_date):
                                due_date = timezone.make_aware(due_date, timezone.get_current_timezone())
                            fields['due_date'] = due_date

                if completed_str is not None:
                    fields['completed'] = completed_str.lower() == "true"

                update_task(request.user, task_id, **fields)
                from django.core.cache import cache
                cache.delete(f'analytics_stats_{request.user.id}')
                return JsonResponse({"status": "success"})
            except Task.DoesNotExist:
                return JsonResponse({"status": "error", "message": "Task not found"}, status=404)
            
        # 3. DELETE TASK
        elif action == "delete":
            task_id = request.POST.get("task_id")
            if delete_task(request.user, task_id):
                return JsonResponse({"status": "success"})
            return JsonResponse({"status": "error", "message": "Task not found"}, status=404)
            
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
            try:
                task = toggle_task_complete(request.user, task_id)
                from django.core.cache import cache
                cache.delete(f'analytics_stats_{request.user.id}')
                return JsonResponse({"status": "success", "completed": task.completed})
            except Task.DoesNotExist:
                return JsonResponse({"status": "error", "message": "Task not found"}, status=404)

    tasks = Task.objects.filter(user=request.user).select_related('category').order_by('completed', '-ai_score')
    profile = request.user.profile
    categories = Category.objects.filter(Q(user=request.user) | Q(user__isnull=True))

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
                habit = toggle_habit_day(request.user, habit_id, day_index)
                return JsonResponse({
                    'status': 'success',
                    'completed': habit.history[day_index]['completed'],
                    'streak_days': habit.streak_days,
                })
            except Habit.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Habit not found'}, status=404)
            except IndexError:
                return JsonResponse({'status': 'error', 'message': 'Day index out of range'}, status=400)
            except Exception as e:
                logger.error("Habit toggle failed: %s", str(e), exc_info=True)
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

        elif action == 'create_habit':
            name = request.POST.get('name', '').strip()
            if name:
                try:
                    habit = create_habit(request.user, name)
                    return JsonResponse({'status': 'success', 'habit_id': habit.id, 'name': habit.name})
                except Exception as e:
                    return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            return JsonResponse({'status': 'error', 'message': 'Name is required'}, status=400)

        elif action == 'delete_habit':
            habit_id = request.POST.get('habit_id')
            if delete_habit(request.user, habit_id):
                return JsonResponse({'status': 'success'})
            return JsonResponse({'status': 'error', 'message': 'Habit not found'}, status=404)

        return JsonResponse({'status': 'error', 'message': 'Unknown action'}, status=400)

    # GET — compute real analytics
    from django.core.cache import cache

    # GET — check cache first
    cache_key = f'analytics_stats_{request.user.id}'
    cached = cache.get(cache_key)

    if cached:
        context = cached
        context['habits'] = Habit.objects.filter(user=request.user).prefetch_related('entries')
        context['current_tab'] = 'analytics'
        context['profile'] = profile
    else:
        habits = Habit.objects.filter(user=request.user).prefetch_related('entries')
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

        cached_stats = {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'completion_rate': completion_rate,
            'trend_up': trend_up,
            'high_count': high_count,
            'medium_count': medium_count,
            'low_count': low_count,
            'weekly_data': weekly_data,
        }
        cache.set(cache_key, cached_stats, timeout=60)  # 60-second TTL

        context = cached_stats
        context['habits'] = habits
        context['current_tab'] = 'analytics'
        context['profile'] = profile

    # Perform Habit history decoration for template render using HabitEntry database rows
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    sunday = monday + datetime.timedelta(days=6)

    # N+1 queries fix: replace Python-level aggregation with SQL aggregate Sum
    total_streak = context['habits'].aggregate(total=Sum('streak_days'))['total'] or 0
    context['total_streak'] = total_streak

    for habit in context['habits']:
        entries = {e.date: e.completed for e in habit.entries.filter(date__gte=monday, date__lte=sunday)}
        week_history = []
        DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for i, name in enumerate(DAY_NAMES):
            d = monday + datetime.timedelta(days=i)
            completed = entries.get(d, False)
            week_history.append({'day': name, 'completed': completed})
        habit.history = week_history

    return render(request, 'productivity/analytics.html', context)

@ratelimit(key='ip', rate='10/m', method='POST', block=True)
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
                logger.info("User %s logged in successfully", user.username)
                if not user.profile.onboarding_completed:
                    return redirect('onboarding')
                return redirect('dashboard')
            else:
                logger.warning("Failed login attempt for username %s", username)
        else:
            logger.warning("Invalid login form submission")
    else:
        form = AuthenticationForm()
    return render(request, 'productivity/login.html', {'form': form})

def logout_view(request):
    if request.user.is_authenticated:
        logger.info("User %s logged out", request.user.username)
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
        setup_onboarding_data(request.user)

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
        if not self.request or not self.request.user or self.request.user.is_anonymous:
            return ChatMessage.objects.none()
        qs = ChatMessage.objects.filter(user=self.request.user).order_by('timestamp')
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                qs = qs[max(0, qs.count() - int(limit)):]
            except (ValueError, TypeError):
                pass
        return qs

    def perform_create(self, serializer):
        from .services.ai_service import parse_command
        user_msg = serializer.save(user=self.request.user, role='USER')
        ai_content, structured_data = parse_command(
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


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not self.request or not self.request.user or self.request.user.is_anonymous:
            return Task.objects.none()
        qs = Task.objects.filter(user=self.request.user)
        completed = self.request.query_params.get('completed')
        priority = self.request.query_params.get('priority')
        limit = self.request.query_params.get('limit')
        if completed is not None:
            qs = qs.filter(completed=completed.lower() == 'true')
        if priority:
            qs = qs.filter(priority=priority.upper())
        qs = qs.order_by('completed', '-ai_score', '-priority')
        if limit:
            try:
                qs = qs[:int(limit)]
            except ValueError:
                pass
        return qs

    def perform_create(self, serializer):
        from .services.task_service import compute_ai_score
        priority = serializer.validated_data.get('priority', 'MEDIUM')
        due_date = serializer.validated_data.get('due_date')
        serializer.save(user=self.request.user, ai_score=compute_ai_score(priority, due_date))

    def perform_update(self, serializer):
        from .services.task_service import compute_ai_score
        instance = self.get_object()
        priority = serializer.validated_data.get('priority', instance.priority)
        due_date = serializer.validated_data.get('due_date', instance.due_date)
        if serializer.validated_data.get('completed') and not instance.completed:
            serializer.save(completed_at=timezone.now(), ai_score=compute_ai_score(priority, due_date))
        else:
            serializer.save(ai_score=compute_ai_score(priority, due_date))

class HabitViewSet(viewsets.ModelViewSet):
    serializer_class = HabitSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not self.request or not self.request.user or self.request.user.is_anonymous:
            return Habit.objects.none()
        return Habit.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        from .constants import DEFAULT_HABIT_HISTORY
        serializer.save(user=self.request.user, history=DEFAULT_HABIT_HISTORY.copy())

    @action(detail=True, methods=['post'], url_path='toggle-day')
    def toggle_day(self, request, pk=None):
        from .services.habit_service import toggle_habit_day
        day_index = request.data.get('day_index')
        if day_index is None:
            return Response({'error': 'day_index required'}, status=400)
        try:
            habit = toggle_habit_day(request.user, pk, int(day_index))
            return Response(HabitSerializer(habit).data)
        except Habit.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)



@login_required
@require_onboarding
def settings_view(request):
    profile = request.user.profile
    categories = Category.objects.filter(Q(user=request.user) | Q(user__isnull=True))
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

            if CalendarIntegration.objects.filter(user=request.user).count() >= INTEGRATION_MAX_PER_USER:
                return JsonResponse(
                    {"status": "error", "message": f"Maximum of {INTEGRATION_MAX_PER_USER} integrations allowed."},
                    status=400
                )

            integration, created = CalendarIntegration.objects.get_or_create(
                user=request.user,
                provider=provider,
                connected_email=connected_email,
                defaults={'sync_active': True, 'last_synced': timezone.now()}
            )
            if not created:
                return JsonResponse({"status": "error",
                                     "message": f"{provider} is already connected for this email."}, status=409)

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


