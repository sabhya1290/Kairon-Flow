from django.db import migrations
import datetime

def migrate_history_forward(apps, schema_editor):
    Habit = apps.get_model('productivity', 'Habit')
    HabitEntry = apps.get_model('productivity', 'HabitEntry')
    DAY_NAMES = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']

    for habit in Habit.objects.all():
        if not habit.history:
            continue
        today = datetime.date.today()
        # Find which weekday is Monday of this week
        monday = today - datetime.timedelta(days=today.weekday())
        for i, entry in enumerate(habit.history):
            if i >= 7:
                break
            entry_date = monday + datetime.timedelta(days=i)
            HabitEntry.objects.get_or_create(
                habit=habit,
                date=entry_date,
                defaults={'completed': bool(entry.get('completed', False))}
            )

def migrate_history_backward(apps, schema_editor):
    HabitEntry = apps.get_model('productivity', 'HabitEntry')
    HabitEntry.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('productivity', '0004_add_habit_entry_model'),
    ]
    operations = [
        migrations.RunPython(migrate_history_forward, migrate_history_backward),
    ]
