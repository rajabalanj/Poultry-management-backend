# Poultry Management System - Domain Formulas

This document outlines the key mathematical formulas and logical classifications used across the system for batches, production, inventory, and financial reporting.

## 1. Batch Classifications

The system automatically classifies flock types based on their age in weeks:
| Classification | Age Range |
| :--- | :--- |
| **Chick** | Age < 8.0 weeks |
| **Grower** | 8.0 weeks ≤ Age ≤ 17.0 weeks |
| **Layer** | Age > 17.0 weeks |

**Active Status**: A batch is considered **Active** if it has no `closing_date` set or if the `closing_date` is in the future.

## 2. Daily Batch Metrics

These metrics are calculated daily for every individual batch.

*   **Total Eggs**: Sum of all egg types collected.
    *   `Total Eggs = Table Eggs + Jumbo Eggs + CR (Cracked/Rejects)`
*   **Closing Count**: The number of birds remaining at the end of the day.
    *   `Closing Count = Opening Count + Birds Added - (Mortality + Culls)`
*   **Hen Day (HD)**: A measure of production efficiency.
    *   `HD = Total Eggs / Closing Count` (only calculated if Closing Count > 0)
*   **Feed Consumption (Actual)**: Aggregated weight of all feed used for the batch on a specific date.
    *   `Actual Feed (kg) = Σ (Item Weight * Number of Times Prepared)` where item category is 'Feed'.

## 3. Performance Standards (Bovans White / BV300)

The system compares actual performance against breed standards.

*   **Standard Hen Day %**: The expected production percentage derived from the standard table based on the flock's current week.
*   **Standard Feed Intake**: The recommended daily feed per bird (in grams) based on age.
*   **Feed Efficiency (Standard vs Actual)**:
    *   `Feed Per Egg (Actual) = Total Feed Grams / Total Eggs`

## 4. Egg Room Inventory (Grading & Transfers)

The system tracks the flow of eggs from sheds through grading.

*   **Table Egg Closing**:
    *   `Opening + Received from Sheds - Transferred Out - Damaged - Sent to Jumbo Grading + Returned from Jumbo Grading`
*   **Jumbo Egg Closing**:
    *   `Opening + Received from Sheds - Transferred Out - Wasted + Sent from Table Grading - Returned to Table Grading`
*   **Grade C Egg Closing**:
    *   `Opening + Received from Sheds + Damaged (from Table Eggs) - Transferred Out - Given to Labour - Wasted`

## 5. Report-Specific Metrics

### Weekly Layer Report
*   **Hen Housing**: The number of birds that entered the layer phase (Closing Count at week 16.7).
*   **Livability %**: `(Current Closing Count / Hen Housing) * 100`
*   **Feed Per Bird Per Day**: `(Total Actual Feed Consumed * 1000) / (Hen Housing * 7)`

### Monthly Financial Analytics
*   **Total Cost**: `Feed/Composition Costs + Operational Expenses`
*   **Cost Per Egg**: `Total Cost / Total Eggs Produced`
*   **Revenue Per Egg**: `Total Sales Revenue / Total Eggs Sold`
*   **Net Margin Per Egg**: `Revenue Per Egg - Cost Per Egg`

## 6. Financial Ledger Logic

*   **Cash Balance**:
    *   `Starting Balance + Total Sales Payments Received - Total Purchase Payments Made - Total Operating Expenses Paid`
*   **Accounts Receivable (Receivables)**:
    *   `Total Value of Sales Orders - Total Payments Received from Customers`
*   **Accounts Payable (Payables)**:
    *   `Total Value of Purchase Orders - Total Payments Made to Vendors`

---
*Last Updated: April 2026*