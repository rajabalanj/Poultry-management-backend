from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from database import get_db
from schemas.journal_entry import JournalEntry, JournalEntryCreate
from crud import journal_entry as journal_entry_crud
from utils.tenancy import get_tenant_id
from utils.auth_utils import require_group

router = APIRouter(
    prefix="/journal-entries",
    tags=["Journal Entries"],
)

@router.post("/", response_model=JournalEntry, status_code=status.HTTP_201_CREATED)
def create_journal_entry(
    entry: JournalEntryCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    user: dict = Depends(require_group(["admin"]))
):
    """
    Create a new journal entry.
    The validation that debits must equal credits is handled in the JournalEntryCreate schema.
    """
    try:
        return journal_entry_crud.create_journal_entry(db=db, entry=entry, tenant_id=tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Generic error for other potential issues
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")


@router.get("/", response_model=List[JournalEntry])
def get_journal_entries(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    user: dict = Depends(require_group(["admin"]))
):
    """
    Retrieve a list of journal entries.
    """
    return journal_entry_crud.get_journal_entries(
        db=db,
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit
    )

@router.get("/{entry_id}", response_model=JournalEntry)
def get_journal_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    user: dict = Depends(require_group(["admin"]))
):
    """
    Retrieve a single journal entry by its ID.
    """
    db_entry = journal_entry_crud.get_journal_entry(db=db, entry_id=entry_id, tenant_id=tenant_id)
    if db_entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    return db_entry
