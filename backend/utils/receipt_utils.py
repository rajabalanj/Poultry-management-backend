import os
from datetime import date
from typing import List, Optional
from decimal import Decimal
from fpdf import FPDF
from sqlalchemy.orm import Session, selectinload


class PDF(FPDF):
    def header(self):
        pass  # suppress default FPDF header

from models.sales_orders import SalesOrder as SalesOrderModel
from models.business_partners import BusinessPartner as BusinessPartnerModel
from models.sales_order_items import SalesOrderItem as SalesOrderItemModel
from models.app_config import AppConfig
from models.journal_entry import JournalEntry
from models.journal_item import JournalItem
from crud.financial_settings import get_financial_settings
from sqlalchemy import func

def generate_sales_order_receipt(db: Session, so_id: int) -> str:
    """
    Generates a PDF receipt for a single sales order.
    """
    # 1. Fetch the sales order with all related data
    so = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items).selectinload(SalesOrderItemModel.inventory_item),
        selectinload(SalesOrderModel.customer),
        selectinload(SalesOrderModel.payments)
    ).filter(SalesOrderModel.id == so_id).first()

    if not so:
        raise FileNotFoundError(f"Sales Order {so_id} not found")

    # 2. Setup PDF
    pdf = PDF()
    pdf.add_page()

    # Fetch Seller Address from AppConfig for the current tenant
    seller_address_config = db.query(AppConfig).filter(
        AppConfig.name == 'seller_address', 
        AppConfig.tenant_id == so.tenant_id
    ).first()
    seller_address = seller_address_config.value if seller_address_config else ""

    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt=f"Sales Order Receipt", ln=True, align="C")
    if seller_address:
        pdf.set_font("Arial", size=9)
        pdf.multi_cell(0, 5, txt=seller_address, align="C")
    pdf.ln(5)

    # 3. Order & Customer Info
    pdf.set_font("Arial", size=10)
    pdf.cell(100, 6, txt=f"Order Number: SO-{so.so_number}", ln=0)
    pdf.cell(0, 6, txt=f"Date: {so.order_date.isoformat()}", ln=1)
    pdf.cell(100, 6, txt=f"Bill No: {so.bill_no or 'N/A'}", ln=0)
    pdf.cell(0, 6, txt=f"Status: {so.status.value}", ln=1)
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, txt="Customer Details:", ln=1)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, txt=f"Name: {so.customer.name}", ln=1)
    pdf.cell(0, 6, txt=f"Contact: {so.customer.phone or 'N/A'}", ln=1)
    pdf.ln(5)

    # 4. Items Table
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(80, 8, "Item", 1)
    pdf.cell(30, 8, "Qty", 1, 0, 'C')
    pdf.cell(40, 8, "Price", 1, 0, 'R')
    pdf.cell(40, 8, "Total", 1, 1, 'R')

    pdf.set_font("Arial", size=10)
    for item in so.items:
        item_name = item.inventory_item.name if item.inventory_item else "Unknown Item"
        if item.variant_name:
            item_name += f" ({item.variant_name})"
            
        pdf.cell(80, 8, item_name, 1)
        pdf.cell(30, 8, str(item.quantity), 1, 0, 'C')
        pdf.cell(40, 8, f"{item.price_per_unit:,.2f}", 1, 0, 'R')
        pdf.cell(40, 8, f"{item.line_total:,.2f}", 1, 1, 'R')

    # 5. Financial Summary
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(150, 8, "GRAND TOTAL SALES:", 0, 0, 'R')
    pdf.cell(40, 8, f"{so.total_amount:,.2f}", 1, 1, 'R')
    
    total_paid = sum(p.amount_paid for p in so.payments if p.deleted_at is None)
    pdf.cell(150, 8, "TOTAL AMOUNT PAID:", 0, 0, 'R')
    pdf.cell(40, 8, f"{total_paid:,.2f}", 1, 1, 'R')
    
    pdf.set_text_color(255, 0, 0)
    pdf.cell(150, 8, "TOTAL OUTSTANDING:", 0, 0, 'R')
    pdf.cell(40, 8, f"{(so.total_amount - total_paid):,.2f}", 1, 1, 'R')
    pdf.set_text_color(0, 0, 0) # Reset color

    # Add payment status note
    pdf.ln(5)
    pdf.set_font("Arial", 'I', 9)
    if total_paid == 0:
        pdf.cell(0, 6, txt="* No payments have been made for this order yet.", ln=True, align='C')
    elif total_paid < so.total_amount:
        pdf.cell(0, 6, txt=f"* Partial payment: {(total_paid/so.total_amount*100):.1f}% of total amount paid.", ln=True, align='C')
    else:
        pdf.cell(0, 6, txt="* This order has been fully paid.", ln=True, align='C')

    # 6. Save and Return Path
    output_dir = "temp_receipts"
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"SO_Receipt_{so.so_number}.pdf")
    pdf.output(filepath)
    return filepath

def generate_customer_bill_pdf(
    db: Session,
    customer: BusinessPartnerModel,
    sales_orders: List[SalesOrderModel],
    start_date: date,
    end_date: date
) -> str:
    """
    Generates a customer statement PDF in ledger format with opening balance, transactions, and closing balance.
    """
    # Get financial settings
    settings = get_financial_settings(db, customer.tenant_id)
    if not settings or not settings.default_accounts_receivable_account_id:
        raise ValueError("Accounts Receivable account not configured")

    ar_account_id = settings.default_accounts_receivable_account_id

    # Get all reference documents for this customer to accurately calculate balances and find all transactions
    all_customer_sos = db.query(SalesOrderModel).filter(
        SalesOrderModel.customer_id == customer.id,
        SalesOrderModel.tenant_id == customer.tenant_id
    ).all()
    all_ref_docs = [f"SO-{so.so_number}" for so in all_customer_sos]

    if not all_ref_docs:
        opening_balance = Decimal('0.0')
        transactions = []
    else:
        # Calculate opening balance: sum(debit - credit) for AR account, all_ref_docs, date < start_date
        opening_balance_query = db.query(func.sum(JournalItem.debit - JournalItem.credit)).join(JournalEntry).filter(
            JournalEntry.tenant_id == customer.tenant_id,
            JournalEntry.reference_document.in_(all_ref_docs),
            JournalEntry.date < start_date,
            JournalItem.account_id == ar_account_id
        )
        opening_balance = opening_balance_query.scalar() or Decimal('0.0')

        # Get transactions: journal entries for all_ref_docs in date range
        transactions = db.query(JournalEntry).options(
            selectinload(JournalEntry.items).selectinload(JournalItem.account)
        ).filter(
            JournalEntry.tenant_id == customer.tenant_id,
            JournalEntry.reference_document.in_(all_ref_docs),
            JournalEntry.date >= start_date,
            JournalEntry.date <= end_date
        ).order_by(JournalEntry.date, JournalEntry.id).all()

    # Setup PDF
    pdf = PDF()
    pdf.add_page()

    # Fetch Seller Address from AppConfig
    seller_address_config = db.query(AppConfig).filter(
        AppConfig.name == 'seller_address',
        AppConfig.tenant_id == customer.tenant_id
    ).first()
    seller_address = seller_address_config.value if seller_address_config else ""

    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt="Customer Statement", ln=True, align="C")
    if seller_address:
        pdf.set_font("Arial", size=9)
        pdf.multi_cell(0, 5, txt=seller_address, align="C")
    pdf.ln(5)

    # Customer Information
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, txt=f"Customer: {customer.name}", ln=True)
    pdf.cell(0, 6, txt=f"Contact: {customer.phone or 'N/A'}", ln=True)
    pdf.cell(0, 6, txt=f"Address: {customer.address or 'N/A'}", ln=True)
    pdf.ln(5)

    # Date Range
    date_range_str = ""
    if start_date and end_date:
        date_range_str = f"Period: {start_date.isoformat()} to {end_date.isoformat()}"
    elif start_date:
        date_range_str = f"Period from: {start_date.isoformat()}"
    elif end_date:
        date_range_str = f"Period up to: {end_date.isoformat()}"
    
    if date_range_str:
        pdf.cell(0, 5, txt=date_range_str, ln=True)
        pdf.ln(5)

    # Opening Balance
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, txt=f"Opening Balance: {opening_balance:,.2f}", ln=True)
    pdf.ln(5)

    # Transactions Table
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(25, 8, "Date", 1)
    pdf.cell(80, 8, "Description", 1)
    pdf.cell(30, 8, "Debit", 1, 0, 'R')
    pdf.cell(30, 8, "Credit", 1, 0, 'R')
    pdf.cell(30, 8, "Balance", 1, 1, 'R')

    pdf.set_font("Arial", size=9)
    balance = opening_balance
    for entry in transactions:
        # Find the AR journal item
        ar_item = next((item for item in entry.items if item.account_id == ar_account_id), None)
        if ar_item:
            debit = ar_item.debit
            credit = ar_item.credit
            balance += debit - credit

            pdf.cell(25, 8, str(entry.date), 1)
            pdf.cell(80, 8, entry.description, 1)
            pdf.cell(30, 8, f"{debit:,.2f}" if debit else "", 1, 0, 'R')
            pdf.cell(30, 8, f"{credit:,.2f}" if credit else "", 1, 0, 'R')
            pdf.cell(30, 8, f"{balance:,.2f}", 1, 1, 'R')

    # Closing Balance
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, txt=f"Closing Balance: {balance:,.2f}", ln=True)

    # Save and Return Path
    output_dir = "temp_bills"
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"customer_statement_{customer.id}_{start_date}_{end_date}.pdf")
    pdf.output(filepath)
    return filepath