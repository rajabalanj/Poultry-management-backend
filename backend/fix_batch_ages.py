#!/usr/bin/env python3
"""
One-off script to recalculate `age` and `opening_count` for a batch's DailyBatch rows.

Usage examples:
  python fix_batch_ages.py --batch-id 16 --from-date 2025-06-26 --dry-run
  python fix_batch_ages.py --batch-id 16 --tenant-id tenant_1

This script walks DailyBatch rows in ascending date order and recomputes `age`
using `calculate_age_progression`, propagating from the batch's base age and
ensuring subsequent rows increment from the previously computed age. It also
recomputes `opening_count` from previous row's `closing_count`.
"""

import argparse
from datetime import datetime, date
from typing import Optional
import logging

from database import SessionLocal
from models.batch import Batch as BatchModel
from models.daily_batch import DailyBatch as DailyBatchModel
from utils.age_utils import calculate_age_progression

logger = logging.getLogger("fix_batch_ages")
logging.basicConfig(level=logging.INFO)


def parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    # Accept both YYYY-MM-DD and DD-MM-YYYY
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    raise ValueError(f"Unable to parse date: {s}")


def fix_batch_ages(batch_id: int, tenant_id: Optional[str] = None, from_date: Optional[date] = None, dry_run: bool = True):
    db = SessionLocal()
    try:
        qry = db.query(BatchModel).filter(BatchModel.id == batch_id)
        if tenant_id:
            qry = qry.filter(BatchModel.tenant_id == tenant_id)
        batch = qry.first()
        if not batch:
            logger.error("Batch %s not found (tenant: %s)", batch_id, tenant_id)
            return

        initial_age = 0.0
        try:
            initial_age = float(batch.age)
        except Exception:
            initial_age = 0.0

        batch_start_date = batch.date if isinstance(batch.date, date) else batch.date.date()

        rows_q = db.query(DailyBatchModel).filter(DailyBatchModel.batch_id == batch_id)
        if tenant_id:
            rows_q = rows_q.filter(DailyBatchModel.tenant_id == tenant_id)
        rows = rows_q.order_by(DailyBatchModel.batch_date.asc()).all()

        if not rows:
            logger.info("No DailyBatch rows found for batch %s", batch_id)
            return

        changed = 0
        prev_age = None
        prev_date = None
        prev_closing = None

        for idx, row in enumerate(rows):
            row_date = row.batch_date if isinstance(row.batch_date, date) else row.batch_date.date()

            # If from_date is specified, skip rows before it (user asked to fix from 26-06-2025 onwards)
            if from_date and row_date < from_date:
                # Still need to set prev values so subsequent rows compute correctly
                prev_date = row_date
                try:
                    prev_age = float(row.age)
                except Exception:
                    # fallback compute from batch start
                    prev_age = calculate_age_progression(initial_age, (row_date - batch_start_date).days)
                prev_closing = row.closing_count
                continue

            if prev_date is None:
                # First effective row: compute relative to batch start
                days_diff = (row_date - batch_start_date).days
                new_age = calculate_age_progression(initial_age, days_diff)
                opening_count = batch.opening_count
            else:
                days_diff = (row_date - prev_date).days
                new_age = calculate_age_progression(prev_age, days_diff)
                opening_count = prev_closing

            age_str = str(round(new_age, 1))

            updated = False
            if row.age != age_str:
                row.age = age_str
                updated = True

            if row.opening_count != opening_count:
                row.opening_count = opening_count
                updated = True

            if updated:
                changed += 1
                db.add(row)

            # advance prev values
            prev_age = new_age
            prev_date = row_date
            prev_closing = row.closing_count

        if dry_run:
            db.rollback()
            logger.info("Dry-run complete. Rows that would be changed: %d", changed)
        else:
            db.commit()
            logger.info("Completed update. Rows changed: %d", changed)

    except Exception as e:
        db.rollback()
        logger.exception("Error while fixing batch ages: %s", e)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Fix ages/opening_count for a batch's daily rows")
    parser.add_argument("--batch-id", type=int, required=True)
    parser.add_argument("--tenant-id", type=str, default=None)
    parser.add_argument("--from-date", type=str, default=None, help="Start fixing from this date (YYYY-MM-DD or DD-MM-YYYY)")
    parser.add_argument("--dry-run", action="store_true", help="Do not commit changes")

    args = parser.parse_args()
    from_date = parse_date(args.from_date) if args.from_date else None

    logger.info("Running fix for batch_id=%s tenant=%s from_date=%s dry_run=%s", args.batch_id, args.tenant_id, from_date, args.dry_run)
    fix_batch_ages(batch_id=args.batch_id, tenant_id=args.tenant_id, from_date=from_date, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
