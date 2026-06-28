from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
import datetime
from productivity.models import Task, Category, CalendarIntegration
from productivity.views import compute_ai_score, KaironSignupForm

class TaskScoreAndCompletionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.category = Category.objects.create(name="Development", color="secondary")

    def test_compute_ai_score(self):
        # High priority, no due date -> base 80
        self.assertEqual(compute_ai_score("HIGH", None), 80)
        
        # High priority, due in 12 hours -> 80 + 20 = 100
        due_now = timezone.now() + datetime.timedelta(hours=12)
        self.assertEqual(compute_ai_score("HIGH", due_now), 100)

        # Low priority, due in 5 days -> 20 + 5 = 25
        due_week = timezone.now() + datetime.timedelta(days=5)
        self.assertEqual(compute_ai_score("LOW", due_week), 25)

    def test_task_completion_timestamp(self):
        client = Client()
        client.login(username="testuser", password="password")
        self.user.profile.onboarding_completed = True
        self.user.profile.save()

        task = Task.objects.create(
            user=self.user,
            title="Fix backend bug",
            priority="HIGH",
            completed=False
        )
        self.assertIsNone(task.completed_at)

        # Toggle completion
        response = client.post(reverse('tasks'), {'action': 'update', 'task_id': task.id, 'completed': 'true'})
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertTrue(task.completed)
        self.assertIsNotNone(task.completed_at)


class SettingsAndSignupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.user.profile.onboarding_completed = True
        self.user.profile.save()

    def test_calendar_integration_limit(self):
        client = Client()
        client.login(username="testuser", password="password")

        # Create 10 integrations
        for i in range(10):
            CalendarIntegration.objects.create(
                user=self.user,
                provider="Google Calendar",
                connected_email=f"user{i}@example.com"
            )

        # Attempt to create 11th integration
        response = client.post(reverse('settings'), {
            'action': 'connect_integration',
            'provider': 'Google Calendar',
            'connected_email': 'user11@example.com'
        })
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(
            response.content.decode('utf-8'),
            {"status": "error", "message": "Maximum of 10 integrations allowed."}
        )

    def test_kairon_signup_form(self):
        form_data = {
            'username': 'newuser',
            'password1': 'KaironPass123_456',
            'password2': 'KaironPass123_456',
            'email': 'newuser@example.com',
            'first_name': 'New'
        }
        form = KaironSignupForm(data=form_data)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertEqual(user.first_name, 'New')
