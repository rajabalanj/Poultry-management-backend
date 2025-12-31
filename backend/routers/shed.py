from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.shed import Shed as ShedModel
from schemas.shed import Shed, ShedCreate, ShedUpdate
from crud import shed as crud_shed
from utils.tenancy import get_tenant_id
from utils.auth_utils import get_current_user

router = APIRouter(prefix="/sheds", tags=["Sheds"])

@router.post("/", response_model=Shed, status_code=status.HTTP_201_CREATED)
def create_shed(
    shed: ShedCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Create a new shed."""
    db_shed = crud_shed.get_shed_by_shed_no(db, shed_no=shed.shed_no, tenant_id=tenant_id)
    if db_shed:
        raise HTTPException(status_code=400, detail="Shed with this number already exists")
    
    new_shed = crud_shed.create_shed(db=db, shed=shed, tenant_id=tenant_id, user=user)
    return new_shed

@router.get("/", response_model=List[Shed])
def read_sheds(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """Retrieve a list of sheds."""
    sheds = crud_shed.get_sheds(db=db, tenant_id=tenant_id, skip=skip, limit=limit)
    return sheds

@router.get("/{shed_id}", response_model=Shed)
def read_shed(shed_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    """Retrieve a single shed by ID."""
    db_shed = crud_shed.get_shed(db=db, shed_id=shed_id, tenant_id=tenant_id)
    if db_shed is None:
        raise HTTPException(status_code=404, detail="Shed not found")
    return db_shed

@router.patch("/{shed_id}", response_model=Shed)
def update_shed(
    shed_id: int,
    shed: ShedUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Update an existing shed."""
    db_shed = crud_shed.get_shed(db=db, shed_id=shed_id, tenant_id=tenant_id)
    if db_shed is None:
        raise HTTPException(status_code=404, detail="Shed not found")
    
    if shed.shed_no != db_shed.shed_no:
        existing_shed = crud_shed.get_shed_by_shed_no(db, shed_no=shed.shed_no, tenant_id=tenant_id)
        if existing_shed:
            raise HTTPException(status_code=400, detail="Shed with this number already exists")

    updated_shed = crud_shed.update_shed(db=db, shed_id=shed_id, shed=shed, tenant_id=tenant_id, user=user)
    return updated_shed

@router.delete("/{shed_id}", status_code=status.HTTP_200_OK)
def delete_shed(
    shed_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Soft delete a shed."""
    success, message = crud_shed.delete_shed(db=db, shed_id=shed_id, tenant_id=tenant_id, user=user)
    if not success:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
    
    return {"message": message}
