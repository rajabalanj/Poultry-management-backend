from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import date

from database import get_db
from schemas.subscription import Subscription, SubscriptionCreate, SubscriptionUpdate
from crud import subscription as crud_subscription
from utils.tenancy import get_tenant_id
from utils.auth_utils import get_current_user, require_super_admin

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

@router.get("/status", response_model=Subscription)
def read_subscription_status(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: dict = Depends(get_current_user)
):
    """Retrieve the subscription status for the current tenant."""
    db_subscription = crud_subscription.get_subscription(db=db, tenant_id=tenant_id)
    if db_subscription is None:
        raise HTTPException(status_code=404, detail="No subscription found for this tenant.")
    return db_subscription

@router.get("/", response_model=List[Subscription])
def read_all_subscriptions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_super_admin)
):
    """Retrieve all subscriptions. Super admin only."""
    return crud_subscription.get_all_subscriptions(db=db, skip=skip, limit=limit)

@router.post("/", response_model=Subscription, status_code=status.HTTP_201_CREATED)
def create_subscription(
    subscription: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_super_admin)
):
    """Create a new subscription for a tenant. Super admin only."""
    # Check if tenant already has a subscription
    existing = crud_subscription.get_subscription(db=db, tenant_id=subscription.tenant_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Tenant already has a subscription"
        )
    return crud_subscription.create_subscription(db=db, subscription=subscription)

@router.patch("/{tenant_id}", response_model=Subscription)
def update_subscription(
    tenant_id: str,
    subscription: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_super_admin)
):
    """Update subscription payment status. Super admin only."""
    db_subscription = crud_subscription.update_subscription(
        db=db, tenant_id=tenant_id, subscription=subscription
    )
    if not db_subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return db_subscription
