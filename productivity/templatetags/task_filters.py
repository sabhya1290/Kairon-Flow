from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def time_remaining(due_date):
    """Returns a human-readable string like '2h 30m left' or 'Overdue by 1h'."""
    if not due_date:
        return "No deadline"

    now = timezone.now()
    diff = due_date - now

    total_seconds = int(diff.total_seconds())

    if total_seconds < 0:
        # Overdue
        total_seconds = abs(total_seconds)
        if total_seconds < 60:
            return "Just overdue"
        elif total_seconds < 3600:
            mins = total_seconds // 60
            return f"Overdue by {mins}m"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            mins = (total_seconds % 3600) // 60
            if mins > 0:
                return f"Overdue by {hours}h {mins}m"
            return f"Overdue by {hours}h"
        else:
            days = total_seconds // 86400
            return f"Overdue by {days}d"
    else:
        if total_seconds < 60:
            return "Less than 1m left"
        elif total_seconds < 3600:
            mins = total_seconds // 60
            return f"{mins}m left"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            mins = (total_seconds % 3600) // 60
            if mins > 0:
                return f"{hours}h {mins}m left"
            return f"{hours}h left"
        elif total_seconds < 604800:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            if hours > 0:
                return f"{days}d {hours}h left"
            return f"{days}d left"
        else:
            days = total_seconds // 86400
            return f"{days}d left"


@register.filter
def is_overdue(due_date):
    """Returns True if the due date is in the past."""
    if not due_date:
        return False
    return due_date < timezone.now()


@register.filter
def format_due(due_date):
    """Returns a short formatted due date like 'Today 5:00 PM' or 'Jun 28, 3:00 PM'."""
    if not due_date:
        return "No deadline"

    now = timezone.now()
    local_due = timezone.localtime(due_date)
    local_now = timezone.localtime(now)
    # Format time and remove leading zero from hour
    time_str = local_due.strftime("%I:%M %p").lstrip("0")

    if local_due.date() == local_now.date():
        return f"Today {time_str}"
    elif local_due.date() == (local_now + timezone.timedelta(days=1)).date():
        return f"Tomorrow {time_str}"
    elif local_due.date() == (local_now - timezone.timedelta(days=1)).date():
        return f"Yesterday {time_str}"
    else:
        return local_due.strftime("%b %d") + f" {time_str}"
