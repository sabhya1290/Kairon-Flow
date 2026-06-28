from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
import datetime

from .models import UserProfile, Task, Habit, HabitEntry, Category, ChatMessage, CalendarIntegration
from .services.task_service import compute_ai_score
from .constants import DEFAULT_HABIT_HISTORY, INTEGRATION_MAX_PER_USER


# ──────────────────────────────────────────
# MODEL TESTS
# ──────────────────────────────────────────

class UserProfileSignalTest(TestCase):
    """UserProfile is auto-created via post_save signal when a User is created."""
    def test_profile_created_on_user_save(self):
        user = User.objects.create_user(username='alice', password='pass1234')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsInstance(user.profile, UserProfile)

    def test_profile_not_duplicated_on_user_update(self):
        user = User.objects.create_user(username='bob', password='pass1234')
        user.first_name = 'Bob'
        user.save()
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)


class TaskModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass1234')
        self.cat = Category.objects.create(user=self.user, name='Work', color='primary')

    def test_task_str(self):
        task = Task.objects.create(user=self.user, title='Fix bug', priority='HIGH')
        self.assertEqual(str(task), 'Fix bug')

    def test_task_defaults(self):
        task = Task.objects.create(user=self.user, title='A task')
        self.assertFalse(task.completed)
        self.assertEqual(task.priority, 'MEDIUM')
        self.assertIsNone(task.completed_at)

    def test_task_completed_at_set_on_completion(self):
        task = Task.objects.create(user=self.user, title='A task')
        task.completed = True
        task.completed_at = timezone.now()
        task.save()
        task.refresh_from_db()
        self.assertIsNotNone(task.completed_at)


class HabitEntryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='habiter', password='pass1234')
        self.habit = Habit.objects.create(user=self.user, name='Morning run')

    def test_entry_unique_per_day(self):
        from django.db import IntegrityError
        today = datetime.date.today()
        HabitEntry.objects.create(habit=self.habit, date=today, completed=True)
        with self.assertRaises(IntegrityError):
            HabitEntry.objects.create(habit=self.habit, date=today, completed=False)


# ──────────────────────────────────────────
# SERVICE TESTS
# ──────────────────────────────────────────

class ComputeAiScoreTest(TestCase):
    """compute_ai_score returns expected scores based on priority + deadline proximity."""

    def test_high_priority_no_due_date(self):
        score = compute_ai_score('HIGH', None)
        self.assertEqual(score, 80)

    def test_medium_priority_no_due_date(self):
        score = compute_ai_score('MEDIUM', None)
        self.assertEqual(score, 50)

    def test_low_priority_no_due_date(self):
        score = compute_ai_score('LOW', None)
        self.assertEqual(score, 20)

    def test_high_priority_due_in_1_hour(self):
        due = timezone.now() + datetime.timedelta(hours=1)
        score = compute_ai_score('HIGH', due)
        self.assertEqual(score, 100)  # 80 + 20 urgency, capped at 100

    def test_medium_priority_due_in_2_days(self):
        due = timezone.now() + datetime.timedelta(days=2)
        score = compute_ai_score('MEDIUM', due)
        self.assertEqual(score, 60)  # 50 + 10 urgency

    def test_score_capped_at_100(self):
        due = timezone.now() + datetime.timedelta(minutes=30)
        score = compute_ai_score('HIGH', due)
        self.assertLessEqual(score, 100)


# ──────────────────────────────────────────
# VIEW / AUTH TESTS
# ──────────────────────────────────────────

class AuthViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='authuser', password='pass1234')
        self.user.profile.onboarding_completed = True
        self.user.profile.save()

    def test_login_redirects_authenticated_user(self):
        self.client.login(username='authuser', password='pass1234')
        response = self.client.get('/login/')
        self.assertRedirects(response, '/')

    def test_dashboard_requires_login(self):
        response = self.client.get('/')
        self.assertRedirects(response, '/login/?next=/')

    def test_signup_creates_user_and_profile(self):
        response = self.client.post('/signup/', {
            'username': 'newuser',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
            'email': 'new@example.com',
            'first_name': 'New',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.filter(username='newuser').count(), 1)
        new_user = User.objects.get(username='newuser')
        self.assertEqual(new_user.email, 'new@example.com')
        self.assertTrue(hasattr(new_user, 'profile'))


# ──────────────────────────────────────────
# TASK API TESTS
# ──────────────────────────────────────────

class TaskAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='taskuser', password='pass1234')
        self.user.profile.onboarding_completed = True
        self.user.profile.save()
        self.client.force_authenticate(user=self.user)
        self.other_user = User.objects.create_user(username='other', password='pass1234')

    def test_list_tasks_only_returns_own_tasks(self):
        Task.objects.create(user=self.user, title='My task')
        Task.objects.create(user=self.other_user, title='Other task')
        response = self.client.get('/api/tasks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [t['title'] for t in response.data]
        self.assertIn('My task', titles)
        self.assertNotIn('Other task', titles)

    def test_create_task_returns_201(self):
        response = self.client.post('/api/tasks/', {'title': 'New task', 'priority': 'HIGH'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'New task')

    def test_create_task_sets_ai_score(self):
        response = self.client.post('/api/tasks/', {'title': 'Scored task', 'priority': 'HIGH'})
        self.assertGreater(response.data['ai_score'], 0)

    def test_cannot_access_other_users_task(self):
        other_task = Task.objects.create(user=self.other_user, title='Private task')
        response = self.client.get(f'/api/tasks/{other_task.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_task(self):
        task = Task.objects.create(user=self.user, title='To delete')
        response = self.client.delete(f'/api/tasks/{task.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Task.objects.filter(id=task.id).exists())

    def test_complete_task_sets_completed_at(self):
        task = Task.objects.create(user=self.user, title='To complete')
        response = self.client.patch(f'/api/tasks/{task.id}/', {'completed': True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertTrue(task.completed)
        self.assertIsNotNone(task.completed_at)

    def test_error_response_has_correct_status_code(self):
        response = self.client.get('/api/tasks/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ──────────────────────────────────────────
# INTEGRATION LIMIT TEST
# ──────────────────────────────────────────

class IntegrationLimitTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='intuser', password='pass1234')
        self.user.profile.onboarding_completed = True
        self.user.profile.save()
        self.client.login(username='intuser', password='pass1234')

    def test_cannot_exceed_integration_limit(self):
        for i in range(INTEGRATION_MAX_PER_USER):
            CalendarIntegration.objects.create(
                user=self.user,
                provider='Google Calendar',
                connected_email=f'test{i}@example.com',
                sync_active=True,
            )
        response = self.client.post('/settings/', {
            'action': 'connect_integration',
            'provider': 'Google Calendar',
            'connected_email': 'overflow@example.com',
        }, content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 400)
