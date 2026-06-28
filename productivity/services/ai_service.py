import logging
import datetime
import re
from django.utils import timezone
from productivity.models import Task, Habit, Category
from productivity.services.task_service import create_task, compute_ai_score

logger = logging.getLogger(__name__)

def _parse_time_str(time_str):
    """Parse a time string like '5pm', '5:30pm', '17:00' into (hour, minute)."""
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

def parse_command(user, content) -> tuple[str, dict | None]:
    """
    Smart AI that parses user messages and takes real actions.
    Replace regex logic with LLM API call in Phase 3, Step 5.
    """
    text = content.lower().strip()
    ai_content = ""
    structured_data = None
    username = user.first_name or user.username

    # ── ADD TASK ──────────────────────────────────────────────
    add_task_match = re.match(
        r'(?:add|create|new)\s+(?:a\s+)?task\s*[:\-]?\s*(.+)',
        text, re.IGNORECASE
    )
    if add_task_match:
        raw = add_task_match.group(1).strip()

        # Extract priority
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
                hour, minute = _parse_time_str(time_part)
                due_date = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
                time_str = due_date.strftime("%I:%M %p").lstrip("0")
                due_label = f"{day_word.capitalize()} at {time_str}"
                raw = raw[:day_match.start()] + raw[day_match.end():]
                raw = raw.strip()

        # Pattern: standalone time like "5pm", "5:30pm", "17:00"
        if not due_date:
            time_match = re.search(r'\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b', raw, re.IGNORECASE)
            if time_match:
                hour, minute = _parse_time_str(time_match.group(1))
                due_date = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if due_date <= now:
                    due_date += datetime.timedelta(days=1)
                    due_label = f"Tomorrow at {due_date.strftime('%I:%M %p').lstrip('0')}"
                else:
                    due_label = f"Today at {due_date.strftime('%I:%M %p').lstrip('0')}"
                raw = raw[:time_match.start()] + raw[time_match.end():]
                raw = raw.strip()

        # Fallback
        if not due_date:
            due_date = now + datetime.timedelta(days=1)
            due_label = "Tomorrow"

        title = re.sub(r'\s+', ' ', raw).strip(' ,-:')
        if not title:
            title = "Untitled Task"
        title = title[0].upper() + title[1:] if title else "Untitled Task"

        cat = Category.objects.first()
        task = create_task(user, title, cat.id if cat else None, priority, due_date)

        # Calculate time remaining
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
            "due_date": task.due_date.isoformat() if task.due_date else None
        }
        ai_content = f"Okay, I've created the task: **\"{task.title}\"** ({priority_label} Priority, due {due_label}, which is in about {time_left})."
        logger.info("AI Service parsed and created task %s for user %s", task.id, user.id)
        return ai_content, structured_data

    # ── COMPLETE TASK ─────────────────────────────────────────
    complete_task_match = re.match(
        r'(?:complete|done|finish)\s+(?:task\s+)?(.+)',
        text, re.IGNORECASE
    )
    if complete_task_match:
        query = complete_task_match.group(1).strip()
        task = Task.objects.filter(
            user=user, completed=False, title__icontains=query
        ).first()
        if task:
            task.completed = True
            task.completed_at = timezone.now()
            task.save()
            ai_content = f"Nicely done! I've marked your task **\"{task.title}\"** as completed. Keep up the momentum! 🎉"
            logger.info("AI Service marked task %s as complete for user %s", task.id, user.id)
        else:
            ai_content = f"I couldn't find any pending task matching \"{query}\"."
        return ai_content, structured_data

    # ── DELETE TASK ───────────────────────────────────────────
    delete_task_match = re.match(
        r'(?:delete|remove)\s+task\s+(.+)',
        text, re.IGNORECASE
    )
    if delete_task_match:
        query = delete_task_match.group(1).strip()
        task = Task.objects.filter(
            user=user, title__icontains=query
        ).first()
        if task:
            title = task.title
            task.delete()
            ai_content = f"Deleted the task **\"{title}\"** from your list."
            logger.info("AI Service deleted task for user %s", user.id)
        else:
            ai_content = f"I couldn't find any task matching \"{query}\" to delete."
        return ai_content, structured_data

    # ── ADD HABIT ─────────────────────────────────────────────
    add_habit_match = re.match(
        r'(?:add|create|new)\s+habit\s+(.+)',
        text, re.IGNORECASE
    )
    if add_habit_match:
        from productivity.services.habit_service import create_habit
        habit_name = add_habit_match.group(1).strip()
        habit = create_habit(user, habit_name)
        ai_content = f"Awesome! I've started tracking your new habit: **\"{habit.name}\"**. Build that streak! 📈"
        logger.info("AI Service created habit %s for user %s", habit.id, user.id)
        return ai_content, structured_data

    # ── LISTING ───────────────────────────────────────────────
    if any(w in text for w in ['list tasks', 'show tasks', 'view tasks', 'my tasks']):
        pending = Task.objects.filter(user=user, completed=False).order_by('-priority')
        if pending.exists():
            tasks_str = "\n".join([f"• **{t.title}** ({t.priority.capitalize()})" for t in pending])
            ai_content = f"Here are your pending tasks:\n{tasks_str}"
        else:
            ai_content = "You don't have any pending tasks right now! Time to add some? 📋"
        return ai_content, structured_data

    if any(w in text for w in ['list habits', 'show habits', 'view habits', 'my habits']):
        habits = Habit.objects.filter(user=user)
        if habits.exists():
            habits_str = "\n".join([f"• **{h.name}** (Streak: {h.streak_days} days)" for h in habits])
            ai_content = f"Here are the habits you are tracking:\n{habits_str}"
        else:
            ai_content = "You aren't tracking any habits yet. Type **\"add habit [name]\"** to start one! 🚀"
        return ai_content, structured_data

    # ── STATUS / ANALYTICS SUMMARY ────────────────────────────
    if 'status' in text or 'summary' in text or 'dashboard' in text:
        pending = Task.objects.filter(user=user, completed=False).count()
        completed = Task.objects.filter(user=user, completed=True).count()
        habits_count = Habit.objects.filter(user=user).count()

        ai_content = (
            f"Here is your current workspace status summary:\n\n"
            f"📋 **Tasks**: {pending} pending, {completed} completed.\n"
            f"🔥 **Habits**: Tracking {habits_count} active habit{'s' if habits_count != 1 else ''}.\n"
            f"⏳ **Saved Time**: {user.profile.daily_saved_hours} hours saved today."
        )
        return ai_content, structured_data

    # ── SMART SCHEDULING ──────────────────────────────────────
    if 'schedule' in text or 'plan' in text or 'focus' in text or 'optimize' in text:
        schedule_pref = user.profile.preferred_work_hours
        schedule_label = "Morning (6 AM - 12 PM)" if schedule_pref == 'morning' else ("Afternoon (12 PM - 6 PM)" if schedule_pref == 'afternoon' else ("Evening (6 PM - 12 AM)" if schedule_pref == 'evening' else "Flexible"))

        task_count = Task.objects.filter(user=user, completed=False).count()

        structured_data = {"type": "schedule_opt"}
        ai_content = (
            f"Workspace scheduling optimized! ⚡\n\n"
            f"Based on your onboarding preferences, I've prioritized your focus block:\n"
            f"• **Preferred Block**: {schedule_label}\n\n"
            f"You have **{task_count} pending tasks** in your backlog. I recommend tackling your highest priority items during this window."
        )
        return ai_content, structured_data

    # ── HELP GUIDE ────────────────────────────────────────────
    if 'help' in text or 'commands' in text:
        ai_content = (
            "Here is the command guide for Kairon Flow:\n\n"
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
