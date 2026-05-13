from fastapi import Request, HTTPException, Depends, status
from sqlalchemy.orm import Session
from database import get_db
from crud.subscription import get_subscription

def require_active_subscription_for_writes(
    request: Request, 
    db: Session = Depends(get_db)
):
    # 1. Whitelist endpoints that should bypass the read-only check.
    # This allows Super Admins to use the /subscriptions endpoints to re-enable access.
    excluded_paths = ["/", "/docs", "/redoc", "/openapi.json", "/favicon.ico"]
    if request.url.path in excluded_paths or request.url.path.startswith("/subscriptions"):
        return

    # We only want to block requests that alter data
    write_methods = {"POST", "PUT", "PATCH", "DELETE"}
    
    if request.method in write_methods:
        # 2. Extract tenant_id from headers manually so public routes (like /docs) don't crash
        tenant_id = request.headers.get("x-tenant-id")
        if not tenant_id:
            return  # Let the actual route's Depends(get_tenant_id) handle the missing header error
            
        subscription = get_subscription(db=db, tenant_id=tenant_id)
        
        # If no subscription exists, or if it exists but is not paid
        if not subscription or not subscription.is_paid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is in read-only mode. Please upgrade your subscription to modify data."
            )
