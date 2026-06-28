import logging
from productivity.models import Habit
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
        logger.info("User %s toggled day_index %s on habit %s. Streak: %s", user.id, day_index, habit.id, habit.streak_days)
        return habit
    else:
        raise IndexError("Day index out of range")

def delete_habit(user, habit_id) -> bool:
    try:
        habit = Habit.objects.get(id=habit_id, user=user)
        habit.delete()
        logger.info("User %s deleted habit %s", user.id, habit_id)
        return True
    except Habit.DoesNotExist:
        return False
