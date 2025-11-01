from fpdf import FPDF
import datetime
from sqlalchemy.orm import Session
from models.sales_payments import SalesPayment
from models.sales_orders import SalesOrder
from models.business_partners import BusinessPartner
from models.sales_order_items import SalesOrderItem
import os
import uuid
import logging

logger = logging.getLogger(__name__)

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Receipt', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_sales_receipt(db: Session, payment_id: int) -> str:
    """
    Generates a PDF receipt for a given sales payment.

    Args:
        db: The database session.
        payment_id: The ID of the sales payment.

    Returns:
        The path to the generated PDF file.
    """
    db_payment = db.query(SalesPayment).filter(SalesPayment.id == payment_id).first()
    if not db_payment:
        raise FileNotFoundError("Payment not found")

    db_sales_order = db_payment.sales_order
    db_customer = db_sales_order.customer

    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)

    # Company Info
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Poultry Management System', 0, 1, 'L')
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, '123 Poultry Lane, Farmville, FS 54321', 0, 1, 'L')
    pdf.ln(10)

    # Receipt Info
    pdf.cell(0, 10, f'Receipt #: {db_payment.id}', 0, 1, 'L')
    pdf.cell(0, 10, f'Payment Date: {db_payment.payment_date.strftime("%Y-%m-%d")}', 0, 1, 'L')
    pdf.ln(5)

    # Customer Info
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Bill To:', 0, 1, 'L')
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, db_customer.name, 0, 1, 'L')
    if db_customer.address:
        pdf.cell(0, 10, db_customer.address, 0, 1, 'L')
    if db_customer.email:
        pdf.cell(0, 10, db_customer.email, 0, 1, 'L')
    if db_customer.phone:
        pdf.cell(0, 10, db_customer.phone, 0, 1, 'L')
    pdf.ln(10)

    # Items Table Header
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(100, 10, 'Item', 1, 0, 'C')
    pdf.cell(30, 10, 'Quantity', 1, 0, 'C')
    pdf.cell(30, 10, 'Unit Price', 1, 0, 'C')
    pdf.cell(30, 10, 'Total', 1, 1, 'C')

    # Items Table Rows
    pdf.set_font('Arial', '', 12)
    for item in db_sales_order.items:
        pdf.cell(100, 10, item.inventory_item.name, 1, 0, 'L')
        pdf.cell(30, 10, str(item.quantity), 1, 0, 'R')
        pdf.cell(30, 10, f'{item.price_per_unit:.2f}', 1, 0, 'R')
        pdf.cell(30, 10, f'{item.line_total:.2f}', 1, 1, 'R')

    pdf.ln(10)

    # Totals
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(130, 10, '', 0, 0)
    pdf.cell(30, 10, 'Subtotal:', 1, 0, 'R')
    pdf.cell(30, 10, f'{db_sales_order.total_amount:.2f}', 1, 1, 'R')

    pdf.cell(130, 10, '', 0, 0)
    pdf.cell(30, 10, 'Amount Paid:', 1, 0, 'R')
    pdf.cell(30, 10, f'{db_sales_order.total_amount_paid:.2f}', 1, 1, 'R')

    balance_due = db_sales_order.total_amount - db_sales_order.total_amount_paid
    pdf.cell(130, 10, '', 0, 0)
    pdf.cell(30, 10, 'Balance Due:', 1, 0, 'R')
    pdf.cell(30, 10, f'{balance_due:.2f}', 1, 1, 'R')


    # Save the PDF
    # Create a unique filename
    temp_dir = r'd:\poultry project git\Poultry-Management\backend\temp'
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    logger.debug(f"Defining filename for payment ID: {db_payment.id}")
    filename = f'receipt_{db_payment.id}_{uuid.uuid4().hex}.pdf'
    logger.debug(f"Filename defined as: {filename}")
    filepath = os.path.join(temp_dir, filename)
    
    pdf.output(filepath)
    
    return filepath

def generate_sales_order_receipt(db: Session, order_id: int) -> str:
    """
    Generates a PDF receipt for a given sales order.

    Args:
        db: The database session.
        order_id: The ID of the sales order.

    Returns:
        The path to the generated PDF file.
    """
    db_sales_order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not db_sales_order:
        raise FileNotFoundError("Sales Order not found")

    db_customer = db_sales_order.customer

    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)

    # Company Info
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Poultry Management System', 0, 1, 'L')
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, '123 Poultry Lane, Farmville, FS 54321', 0, 1, 'L')
    pdf.ln(10)

    # Receipt Info
    pdf.cell(0, 10, f'Order #: {db_sales_order.id}', 0, 1, 'L')
    pdf.cell(0, 10, f'Order Date: {db_sales_order.order_date.strftime("%Y-%m-%d")}', 0, 1, 'L')
    pdf.ln(5)

    # Customer Info
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Bill To:', 0, 1, 'L')
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, db_customer.name, 0, 1, 'L')
    if db_customer.address:
        pdf.cell(0, 10, db_customer.address, 0, 1, 'L')
    if db_customer.email:
        pdf.cell(0, 10, db_customer.email, 0, 1, 'L')
    if db_customer.phone:
        pdf.cell(0, 10, db_customer.phone, 0, 1, 'L')
    pdf.ln(10)

    # Items Table Header
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(100, 10, 'Item', 1, 0, 'C')
    pdf.cell(30, 10, 'Quantity', 1, 0, 'C')
    pdf.cell(30, 10, 'Unit Price', 1, 0, 'C')
    pdf.cell(30, 10, 'Total', 1, 1, 'C')

    # Items Table Rows
    pdf.set_font('Arial', '', 12)
    for item in db_sales_order.items:
        pdf.cell(100, 10, item.inventory_item.name, 1, 0, 'L')
        pdf.cell(30, 10, str(item.quantity), 1, 0, 'R')
        pdf.cell(30, 10, f'{item.price_per_unit:.2f}', 1, 0, 'R')
        pdf.cell(30, 10, f'{item.line_total:.2f}', 1, 1, 'R')

    pdf.ln(10)

    # Totals
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(130, 10, '', 0, 0)
    pdf.cell(30, 10, 'Subtotal:', 1, 0, 'R')
    pdf.cell(30, 10, f'{db_sales_order.total_amount:.2f}', 1, 1, 'R')

    pdf.cell(130, 10, '', 0, 0)
    pdf.cell(30, 10, 'Amount Paid:', 1, 0, 'R')
    pdf.cell(30, 10, f'{db_sales_order.total_amount_paid:.2f}', 1, 1, 'R')

    balance_due = db_sales_order.total_amount - db_sales_order.total_amount_paid
    pdf.cell(130, 10, '', 0, 0)
    pdf.cell(30, 10, 'Balance Due:', 1, 0, 'R')
    pdf.cell(30, 10, f'{balance_due:.2f}', 1, 1, 'R')


    # Save the PDF
    # Create a unique filename
    temp_dir = r'd:\poultry project git\Poultry-Management\backend\temp'
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    filename = f'sales_order_receipt_{db_sales_order.id}_{uuid.uuid4().hex}.pdf'
    filepath = os.path.join(temp_dir, filename)
    
    pdf.output(filepath)
    
    return filepath
