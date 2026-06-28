import logging
import datetime
from productivity.models import Habit, HabitEntry
from productivity.constants import DEFAULT_HABIT_HISTORY

logger = logging.getLogger(__name__)

def create_habit(user, name) -> Habit:
    habit = Habit.objects.create(
        user=user,
        name=name,
        streak_days=0,
        history=DEFAULT_HABIT_HISTORY.copy()
    )
    logger.info("User %s created habit %s", user.id, habit.id)
    return habit

def toggle_habit_day(user, habit_id, day_index) -> Habit:
    habit = Habit.objects.get(id=habit_id, user=user)
    if not (0 <= day_index < 7):
        raise IndexError("Day index out of range")

    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    target_date = monday + datetime.timedelta(days=day_index)

    entry, created = HabitEntry.objects.get_or_create(
        habit=habit,
        date=target_date,
        defaults={'completed': True}
    )
    if not created:
        entry.completed = not entry.completed
        entry.save()

    # Also keep legacy history JSON field updated for backward compatibility
    # Ensure habit.history has 7 items
    if not habit.history or len(habit.history) < 7:
        habit.history = DEFAULT_HABIT_HISTORY.copy()
    habit.history[day_index]['completed'] = entry.completed

    # Recalculate streak counting consecutive completed entries backwards from today
    streak = 0
    check_date = today
    today_entry = HabitEntry.objects.filter(habit=habit, date=today).first()
    if not (today_entry and today_entry.completed):
        check_date = today - datetime.timedelta(days=1)

    while True:
        e = HabitEntry.objects.filter(habit=habit, date=check_date).first()
        if e and e.completed:
            streak += 1
            check_date -= datetime.timedelta(days=1)
        else:
            break

    habit.streak_days = streak
    habit.save()
    logger.info("User %s toggled day_index %s (date: %s) on habit %s. Streak: %s", user.id, day_index, target_date, habit.id, habit.streak_days)
    return habit

def delete_habit(user, habit_id) -> bool:
    try:
        habit = Habit.objects.get(id=habit_id, user=user)
        habit.delete()
        logger.info("User %s deleted habit %s", user.id, habit_id)
        return True
    except Habit.DoesNotExist:
        return False
