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
    db, # Session object might be needed for additional lookups, though ideally data is pre-fetched
    customer: BusinessPartnerModel,
    sales_orders: List[SalesOrderModel],
    start_date: Optional[date],
    end_date: Optional[date]
) -> str:
    """
    Generates a consolidated PDF bill for a customer based on a list of sales orders.
    """
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Header
    pdf.cell(200, 10, txt="Customer Bill", ln=True, align="C")
    pdf.ln(10)

    # Customer Information
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 5, txt=f"Customer Name: {customer.name}", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, txt=f"Address: {customer.address or 'N/A'}", ln=True)
    pdf.cell(0, 5, txt=f"Contact: {customer.phone or 'N/A'}", ln=True)
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

    # Sales Orders Details
    total_billed_amount = Decimal('0.0')
    total_paid_amount = Decimal('0.0')

    for so in sales_orders:
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 7, txt=f"Sales Order #{so.so_number} (Date: {so.order_date.isoformat()}) - Status: {so.status.value}", ln=True)
        pdf.set_font("Arial", '', 9)
        pdf.cell(0, 5, txt=f"  Bill No: {so.bill_no or 'N/A'}", ln=True)
        
        # Items table header
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(70, 6, "Item", 1)
        pdf.cell(30, 6, "Quantity", 1)
        pdf.cell(30, 6, "Price/Unit", 1)
        pdf.cell(30, 6, "Line Total", 1, ln=True)
        
        # Items
        pdf.set_font("Arial", '', 9)
        for item in so.items:
            pdf.cell(70, 6, item.inventory_item.name if item.inventory_item else "N/A", 1)
            pdf.cell(30, 6, str(item.quantity), 1)
            pdf.cell(30, 6, str(item.price_per_unit), 1)
            pdf.cell(30, 6, str(item.line_total), 1, ln=True)
        
        # Sales Order Totals
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(130, 7, "Sales Order Total:", 1, 0, 'R')
        pdf.cell(30, 7, str(so.total_amount), 1, ln=True)
        
        current_so_paid = sum(p.amount_paid for p in so.payments if p.deleted_at is None)
        pdf.cell(130, 7, "Amount Paid for SO:", 1, 0, 'R')
        pdf.cell(30, 7, str(current_so_paid), 1, ln=True)
        
        outstanding_so = so.total_amount - current_so_paid
        pdf.cell(130, 7, "Outstanding for SO:", 1, 0, 'R')
        pdf.cell(30, 7, str(outstanding_so), 1, ln=True)
        pdf.ln(5)

        total_billed_amount += so.total_amount
        total_paid_amount += current_so_paid

    # Grand Summary
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "--- Grand Summary ---", ln=True, align="C")
    pdf.cell(130, 8, "Total Billed Amount:", 1, 0, 'R')
    pdf.cell(30, 8, str(total_billed_amount), 1, ln=True)
    pdf.cell(130, 8, "Total Amount Paid:", 1, 0, 'R')
    pdf.cell(30, 8, str(total_paid_amount), 1, ln=True)
    pdf.cell(130, 8, "Total Outstanding Balance:", 1, 0, 'R')
    pdf.cell(30, 8, str(total_billed_amount - total_paid_amount), 1, ln=True)

    # Save the PDF
    output_dir = "temp_bills"
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"customer_bill_{customer.id}_{date.today().isoformat()}.pdf")
    pdf.output(filepath)
    return filepath