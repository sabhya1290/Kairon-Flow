import datetime
import logging
from django.utils import timezone
from productivity.models import Task, Category, Habit
from productivity.constants import DEFAULT_HABIT_HISTORY

logger = logging.getLogger(__name__)

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

def setup_onboarding_data(user):
    """One-time creation of personalized initial data based on user's onboarding preferences."""
    profile = user.profile
    role = profile.work_role
    goal = profile.primary_goal
    schedule = profile.preferred_work_hours

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
        cat, _ = Category.objects.get_or_create(user=user, name=name, defaults={"color": color})
        created_cats.append(cat)

    # Create starter tasks based on goal
    now = timezone.localtime(timezone.now())
    if goal == 'task_management' or goal == 'all':
        due1 = now.replace(hour=focus_start_hour, minute=0, second=0, microsecond=0)
        create_task(user, f"Set up your first project workspace", created_cats[0].id, "HIGH", due1)
        due2 = now + datetime.timedelta(days=1)
        create_task(user, f"Organize tasks by priority", created_cats[1].id, "MEDIUM", due2)
    if goal == 'focus_time' or goal == 'all':
        due3 = now.replace(hour=focus_start_hour, minute=0, second=0, microsecond=0)
        create_task(user, f"Complete your first {focus_label}", created_cats[0].id, "HIGH", due3)
    if goal == 'habit_tracking' or goal == 'all':
        due4 = now + datetime.timedelta(days=1)
        create_task(user, "Set up your daily habits", created_cats[1].id, "MEDIUM", due4)
    if goal == 'scheduling' or goal == 'all':
        due5 = now + datetime.timedelta(days=2)
        cat_id = created_cats[2].id if len(created_cats) > 2 else created_cats[0].id
        create_task(user, "Connect your calendar for smart scheduling", cat_id, "MEDIUM", due5)

    # If no specific goal matched, create generic starter tasks
    if not Task.objects.filter(user=user).exists():
        due6 = now + datetime.timedelta(days=1)
        create_task(user, "Explore your Kairon Flow dashboard", created_cats[0].id, "MEDIUM", due6)

    # Create starter habits based on goal
    if goal in ('habit_tracking', 'all'):
        Habit.objects.create(
            user=user,
            name="Daily Planning Session",
            streak_days=0,
            history=DEFAULT_HABIT_HISTORY.copy()
        )
        Habit.objects.create(
            user=user,
            name="Deep Work Focus",
            streak_days=0,
            history=DEFAULT_HABIT_HISTORY.copy()
        )
        logger.info("Created starter habits for user %s during onboarding setup", user.id)

def create_task(user, title, category_id, priority, due_date) -> Task:
    category = None
    if category_id:
        category = Category.objects.filter(id=category_id).first()
    task = Task.objects.create(
        user=user,
        title=title,
        category=category,
        priority=priority,
        due_date=due_date,
        ai_score=compute_ai_score(priority, due_date),
        completed=False
    )
    logger.info("User %s created task %s", user.id, task.id)
    return task

def update_task(user, task_id, **fields) -> Task:
    task = Task.objects.get(user=user, id=task_id)
    for field, value in fields.items():
        if field == 'category_id':
            if value == "" or value is None:
                task.category = None
            else:
                task.category = Category.objects.filter(id=value).first()
        elif field == 'completed':
            new_completed = value
            if new_completed and not task.completed:
                task.completed_at = timezone.now()
            elif not new_completed and task.completed:
                task.completed_at = None
            task.completed = new_completed
        else:
            setattr(task, field, value)
    
    # Recalculate AI score on priority or due_date changes
    task.ai_score = compute_ai_score(task.priority, task.due_date)
    task.save()
    logger.info("User %s updated task %s", user.id, task.id)
    return task

def delete_task(user, task_id) -> bool:
    try:
        task = Task.objects.get(user=user, id=task_id)
        task.delete()
        logger.info("User %s deleted task %s", user.id, task_id)
        return True
    except Task.DoesNotExist:
        return False

def toggle_task_complete(user, task_id) -> Task:
    task = Task.objects.get(user=user, id=task_id)
    task.completed = not task.completed
    if task.completed:
        task.completed_at = timezone.now()
    else:
        task.completed_at = None
    task.ai_score = compute_ai_score(task.priority, task.due_date)
    task.save()
    logger.info("User %s toggled task %s to completed=%s", user.id, task.id, task.completed)
    return task
