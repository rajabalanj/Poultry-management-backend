from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from database import SessionLocal, engine, Base
import models  # This will import models in the correct order
from schemas.batch import Batch, BatchCreate
# from schemas.batch_history import BatchHistory
import crud.batch as crud
# import crud.batch_history as crud_history
from datetime import date

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def read_root():
    return {"message": "Poultry Management API"}

@app.post("/batches/", response_model=Batch)
def create_batch(
    batch: BatchCreate, 
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    return crud.create_batch(db=db, batch=batch, changed_by=x_user_id)

@app.get("/batches/", response_model=List[Batch])
def read_batches(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_all_batches(db, skip=skip, limit=limit)

@app.get("/batches/{batch_id}", response_model=Batch)
def read_batch(batch_id: int, db: Session = Depends(get_db)):
    db_batch = crud.get_batch(db, batch_id=batch_id)
    if db_batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return db_batch

@app.patch("/batches/{batch_id}", response_model=Batch)
def update_batch(
    batch_id: int, 
    batch_data: dict, 
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    db_batch = crud.update_batch(db, batch_id=batch_id, batch_data=batch_data, changed_by=x_user_id)
    if db_batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return db_batch

@app.delete("/batches/{batch_id}")
def delete_batch(
    batch_id: int, 
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    success = crud.delete_batch(db, batch_id=batch_id, changed_by=x_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"message": "Batch deleted successfully"}

# @app.get("/batch-history/{batch_id}", response_model=List[BatchHistory])
# def get_batch_history(batch_id: int, db: Session = Depends(get_db)):
#     """Get the history of changes for a specific batch"""
#     history = crud_history.get_batch_history(db, batch_id)
#     if not history:
#         raise HTTPException(status_code=404, detail="No history found for this batch")
#     return history

# @app.get("/batch-history", response_model=List[BatchHistory])
# def get_all_history(
#     skip: int = 0, 
#     limit: int = 100,
#     action: Optional[str] = None,
#     db: Session = Depends(get_db)
# ):
#     """Get all batch history records with optional filtering"""
#     return crud_history.get_all_history(db, skip=skip, limit=limit, action=action) 