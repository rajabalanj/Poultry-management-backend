"""
Scheduled tasks for subscription lifecycle management.
These tasks should be run periodically to maintain subscription status.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from crud.subscription import check_and_update_expired_subscriptions


def check_expired_subscriptions():
    """
    Check all active subscriptions and update their status if they have expired.
    This should be called daily (e.g., via cron job or scheduled task).
    """
    db = SessionLocal()
    try:
        count = check_and_update_expired_subscriptions(db)
        print(f"[{datetime.now()}] Checked subscriptions. Updated {count} expired subscriptions.")
        return count
    except Exception as e:
        print(f"[{datetime.now()}] Error checking expired subscriptions: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # Run the task
    check_expired_subscriptions()
