# Task 2: Hidden Logic Extraction (Excel -> Python-Ready)

Date: 2026-03-18
Source file reviewed: `docs/امر البيع (1).xlsx`

## 0) Scope Alignment (Line-Level)

Based on client clarification, the sold job is represented on `sale.order.line`.

- The formulas in this document should be implemented primarily as line-level computes.
- Optional order-level fields on `sale.order` can aggregate sums from lines for reporting.

## 1) GOSI Rule

### What is found in Excel notes

- Cell `F6` states (Arabic): company contribution for **foreign employee** is **2%** of `(Basic Salary + Housing Allowance)`.
- Cell `F7` states (Arabic): company contribution for **Saudi employee** is **11.75%** of `(Basic Salary + Housing Allowance)`.

### Python-ready rule

```python
def compute_gosi(basic_salary: float, housing_allowance: float, nationality: str) -> float:
    base = basic_salary + housing_allowance
    n = (nationality or "").strip().lower()

    # Saudi gets 11.75%, non-Saudi gets 2% based on workbook notes.
    if n in {"saudi", "sa", "ksa", "سعودي", "السعودية"}:
        return base * 0.1175
    return base * 0.02
```

### Nationality confirmation from workbook

- Workbook has nationality column (`S4`, `S23` = "الجنسية").
- Example nationality values exist (e.g., `S5=مصري`, `S6=اهندي`, `S24=مصري`, `S25=اهندي`).
- Rule text explicitly distinguishes **Saudi** vs **foreign**.

Conclusion:

- `Total_GOSI = (Basic + Housing) * 0.02` applies to **non-Saudi** employees.
- Saudi employees should use **11.75%** based on the workbook text.

## 2) Accrual Rule (Vacation + EOS)

Requested normalized formula:

- `Accrual = (Total_Salary / 30) * (Contract_Days / 12)`

Python-ready:

```python
def compute_vacation_eos_accrual(total_salary: float, contract_days: float) -> float:
    return (total_salary / 30.0) * (contract_days / 12.0)
```

### Workbook alignment notes

- Vacation note (`H6`) uses monthly vacation accrual logic tied to annual leave days (21 or 30) divided by 12.
- EOS note (`H7`) indicates annual EOS equivalent to half-month salary for one year (`total_salary / 12 / 2` wording in sheet context).

Implementation note:

- If business wants one combined accrual field, use the requested normalized formula above.
- If business wants separate components, keep vacation and EOS as two formulas and sum them.

## 3) Total Service Cost Rule

Requested definition:

- `Total_Service_Cost = sum(all monthly costs) + Service_Fee`

Python-ready generic expression:

```python
def compute_total_service_cost(
    monthly_salary_components_total: float,
    monthly_gosi: float,
    monthly_medical_insurance: float,
    monthly_medical_exam: float,
    monthly_gov_fees_accrual: float,
    monthly_vacation_eos_accrual: float,
    service_fee: float,
    other_monthly_costs: float = 0.0,
) -> float:
    monthly_costs_sum = (
        monthly_salary_components_total
        + monthly_gosi
        + monthly_medical_insurance
        + monthly_medical_exam
        + monthly_gov_fees_accrual
        + monthly_vacation_eos_accrual
        + other_monthly_costs
    )
    return monthly_costs_sum + service_fee
```

## 4) Suggested Odoo Compute Field Hooks

- On `sale.order.line`:
    - `x_gosi_amount` computed from: `x_basic_salary`, `x_housing_allowance`, `x_nationality`
    - `x_vacation_eos_accrual` computed from: `x_total_salary`, `x_contract_days`
    - `x_total_service_cost` computed from all monthly cost components + `x_service_fee`

- Optional on `sale.order`:
    - `x_total_service_cost_all_lines = sum(order_line.x_total_service_cost)`
    - `x_total_gosi_all_lines = sum(order_line.x_gosi_amount)`

## 5) Assumptions to Validate

- Nationality source field in Odoo should be normalized (`Saudi` vs Arabic variants) before GOSI rate selection.
- Confirm whether Saudi 11.75% applies universally or by contract/job category.
- Confirm whether "medical exam" is one-time cost prorated monthly or billed once as cost invoice.
- Confirm which government fees are monthly accruals vs one-time pass-through invoices.

---

Status: Hidden formula extraction completed, converted into Python-ready logic, and aligned to line-level implementation.
