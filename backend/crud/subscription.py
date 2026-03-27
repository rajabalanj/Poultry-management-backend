from sqlalchemy.orm import Session
from models.subscription import Subscription
from schemas.subscription import SubscriptionCreate, SubscriptionUpdate
from datetime import date

# Subscription CRUD
def get_subscription(db: Session, tenant_id: str):
    """Get subscription by tenant ID (each tenant has one subscription)"""
    return db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()

def get_all_subscriptions(db: Session, skip: int = 0, limit: int = 100):
    """Get all subscriptions (for super admin)"""
    return db.query(Subscription).offset(skip).limit(limit).all()

def create_subscription(db: Session, subscription: SubscriptionCreate):
    """Create a new subscription for a tenant"""
    db_subscription = Subscription(**subscription.model_dump())
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

def update_subscription(db: Session, tenant_id: str, subscription: SubscriptionUpdate):
    """Update subscription payment status"""
    db_subscription = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
    if db_subscription:
        update_data = subscription.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_subscription, key, value)
        db.commit()
        db.refresh(db_subscription)
    return db_subscription

def check_subscription_status(db: Session, tenant_id: str) -> bool:
    """Check if tenant has paid subscription"""
    subscription = get_subscription(db, tenant_id)
    return subscription and subscription.is_paid
