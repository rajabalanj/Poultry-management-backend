from sqlalchemy.orm import Session
from models import journal_entry as journal_entry_model
from models import journal_item as journal_item_model
from schemas.journal_entry import JournalEntryCreate
from typing import Optional
from datetime import date

def create_journal_entry(db: Session, entry: JournalEntryCreate, tenant_id: str):
    """
    Creates a new journal entry and its corresponding items.
    """
    # Create the parent JournalEntry object
    db_entry = journal_entry_model.JournalEntry(
        date=entry.date,
        description=entry.description,
        reference_document=entry.reference_document,
        tenant_id=tenant_id
    )
    db.add(db_entry)
    db.flush()  # Flush to get the ID for the parent entry before creating children

    # Create the child JournalItem objects
    for item_data in entry.items:
        db_item = journal_item_model.JournalItem(
            **item_data.dict(),
            journal_entry_id=db_entry.id,
            tenant_id=tenant_id
        )
        db.add(db_item)

    db.commit()
    db.refresh(db_entry)
    return db_entry

def get_journal_entry(db: Session, entry_id: int, tenant_id: str):
    """
    Retrieves a single journal entry by its ID.
    """
    return db.query(journal_entry_model.JournalEntry).filter(
        journal_entry_model.JournalEntry.id == entry_id,
        journal_entry_model.JournalEntry.tenant_id == tenant_id
    ).first()

def get_journal_entries(
    db: Session,
    tenant_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieves a list of journal entries with optional date filtering.
    """
    query = db.query(journal_entry_model.JournalEntry).filter(
        journal_entry_model.JournalEntry.tenant_id == tenant_id
    )

    if start_date:
        query = query.filter(journal_entry_model.JournalEntry.date >= start_date)
    if end_date:
        query = query.filter(journal_entry_model.JournalEntry.date <= end_date)

    return query.order_by(journal_entry_model.JournalEntry.date.desc(), journal_entry_model.JournalEntry.id.desc()).offset(skip).limit(limit).all()
