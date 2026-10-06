"""Build and queue post activity notifications."""

import logging
from datetime import datetime, timezone

from fastapi import BackgroundTasks

from models import Post, User
from services.email_service import send_email

logger = logging.getLogger(__name__)


def notify_post_activity(
    background_tasks: BackgroundTasks,
    post: Post,
    actor: User,
    activity: str,
    occurred_at: datetime,
) -> None:
    """Queue a post owner email after a successful comment or like."""
    if post.author_id == actor.id:
        return
    recipient = post.author
    if recipient is None or not recipient.email:
        logger.warning("Cannot notify owner of post %s: owner or email is missing", post.id)
        return

    timestamp = occurred_at
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d %I:%M %p UTC")
    activity_line = "Commented on your post" if activity == "comment" else "Liked your post"
    subject = f"{actor.username} {activity_line.lower()}"
    body = (
        f"Post: {post.title}\n"
        f"User: {actor.username}\n"
        f"Activity: {activity_line}\n"
        f"Time: {timestamp}\n"
    )
    # send_email is synchronous by design: Starlette runs sync BackgroundTasks
    # in its thread pool, so SMTP never blocks the endpoint's response.
    background_tasks.add_task(send_email, recipient.email, subject, body)
