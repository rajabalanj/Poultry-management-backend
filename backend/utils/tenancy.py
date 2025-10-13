from fastapi import Header, HTTPException

def get_tenant_id(x_tenant_id: str = Header(...)) -> str:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header is missing")
    return x_tenant_id
