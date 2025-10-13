from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from crud import composition as crud_composition
from schemas.composition import Composition, CompositionCreate
from utils.auth_utils import get_current_user, get_user_identifier, require_group
from utils.tenancy import get_tenant_id

router = APIRouter()


@router.post("/compositions/", response_model=Composition)
def create_composition(composition: CompositionCreate, db: Session = Depends(get_db), user: dict = Depends(require_group(["admin"])), tenant_id: str = Depends(get_tenant_id)):
    # Pass the user identifier to the CRUD function so it can populate audit fields
    return crud_composition.create_composition(db, composition, tenant_id, user_id=get_user_identifier(user))


@router.get("/compositions/", response_model=List[Composition])
def read_compositions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    return crud_composition.get_compositions(db, skip=skip, limit=limit, tenant_id=tenant_id)

@router.put("/compositions/{composition_id}", response_model=Composition)
def update_composition(composition_id: int, composition: CompositionCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user), tenant_id: str = Depends(get_tenant_id)):
    db_composition = crud_composition.update_composition(db, composition_id, composition, tenant_id, user_id=get_user_identifier(user))
    if db_composition is None:
        raise HTTPException(status_code=404, detail="Composition not found")
    return db_composition

@router.delete("/compositions/{composition_id}")
def delete_composition(composition_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user), tenant_id: str = Depends(get_tenant_id)):
    success = crud_composition.delete_composition(db, composition_id, tenant_id, user_id=get_user_identifier(user))
    if not success:
        raise HTTPException(status_code=404, detail="Composition not found")
    return {"message": "Composition deleted"}

@router.patch("/compositions/{composition_id}", response_model=Composition)
def patch_composition(composition_id: int, composition: CompositionCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user), tenant_id: str = Depends(get_tenant_id)):
    db_composition = crud_composition.update_composition(db, composition_id, composition, tenant_id, user_id=get_user_identifier(user))
    if db_composition is None:
        raise HTTPException(status_code=404, detail="Composition not found")
    return db_composition

@router.get("/compositions/{composition_id}", response_model=Composition)
def read_composition(composition_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    db_composition = crud_composition.get_composition(db, composition_id, tenant_id)
    if db_composition is None:
        raise HTTPException(status_code=404, detail="Composition not found")
    return db_composition
