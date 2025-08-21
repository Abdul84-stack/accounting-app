import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import numpy as np
import io

# --- Configuration and Initialization ---
st.set_page_config(layout="wide", page_title="Simple Accounting Package")

# Initialize session state for data storage
if 'receivables' not in st.session_state:
    st.session_state.receivables = pd.DataFrame(columns=['Date', 'Customer', 'Type', 'Amount', 'Description']).astype({
        'Date': 'datetime64[ns]',
        'Customer': str,
        'Type': str,
        'Amount': float,
        'Description': str
    })
if 'payables' not in st.session_state:
    st.session_state.payables = pd.DataFrame(columns=['Date', 'Vendor/Category', 'Amount', 'Description']).astype({
        'Date': 'datetime64[ns]',
        'Vendor/Category': str,
        'Amount': float,
        'Description': str
    })
if 'inventory' not in st.session_state:
    st.session_state.inventory = pd.DataFrame(columns=['Item', 'Quantity', 'Unit Cost', 'Selling Price', 'Last Updated']).astype({
        'Item': str,
        'Quantity': int,
        'Unit Cost': float,
        'Selling Price': float,
        'Last Updated': str
    })
if 'fixed_assets' not in st.session_state:
    st.session_state.fixed_assets = pd.DataFrame(columns=['Asset Tag', 'Asset Name', 'Category', 'Location', 'Acquisition Date', 'Cost', 'Salvage Value', 'Useful Life (Years)', 'Accumulated Depreciation']).astype({
        'Asset Tag': str,
        'Asset Name': str,
        'Category': str,
        'Location': str,
        'Acquisition Date': 'datetime64[ns]',
        'Cost': float,
        'Salvage Value': float,
        'Useful Life (Years)': int,
        'Accumulated Depreciation': float
    })

# Initialize a simplified General Ledger (GL)
if 'general_ledger' not in st.session_state:
    st.session_state.general_ledger = pd.DataFrame(columns=['Date', 'Account', 'Debit', 'Credit', 'Description']).astype({
        'Date': 'datetime64[ns]',
        'Account': str,
        'Debit': float,
        'Credit': float,
        'Description': str
    })

# Initialize for uploaded financial statements
if 'uploaded_is' not in st.session_state:
    st.session_state.uploaded_is = None
if 'uploaded_bs' not in st.session_state:
    st.session_state.uploaded_bs = None

# --- Sidebar Navigation ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Daily Records (Receivables & Payables)", "Inventory Management", "Fixed Asset Register", "Point of Sale (POS)", "Financial Statements", "Analytics"])

# --- Helper Functions ---
def post_to_gl(date, account, debit, credit, description):
    """Posts a transaction to the simplified General Ledger."""
    new_gl_entry = pd.DataFrame([{
        'Date': date,
        'Account': account,
        'Debit': debit,
        'Credit': credit,
        'Description': description
    }])
    new_gl_entry = new_gl_entry.astype(st.session_state.general_ledger.dtypes)
    st.session_state.general_ledger = pd.concat([st.session_state.general_ledger, new_gl_entry], ignore_index=True)

def add_receivable_record(date, customer, record_type, amount, description):
    """Adds a new receivable record and posts to GL."""
    new_record = pd.DataFrame([{
        'Date': date,
        'Customer': customer,
        'Type': record_type, # 'Cash' or 'Credit'
        'Amount': amount,
        'Description': description
    }])
    new_record = new_record.astype(st.session_state.receivables.dtypes)
    st.session_state.receivables = pd.concat([st.session_state.receivables, new_record], ignore_index=True)

    # Post to GL
    if record_type == 'Cash':
        post_to_gl(date, 'Cash', amount, 0, f"Cash Sale to {customer}: {description}")
        post_to_gl(date, 'Sales Revenue', 0, amount, f"Cash Sale to {customer}: {description}")
    else: # Credit
        post_to_gl(date, 'Accounts Receivable', amount, 0, f"Credit Sale to {customer}: {description}")
        post_to_gl(date, 'Sales Revenue', 0, amount, f"Credit Sale to {customer}: {description}")
    st.success("Receivable record added successfully and posted to GL!")

def add_payable_record(date, vendor_category, amount, description):
    """Adds a new payable record and posts to GL."""
    new_record = pd.DataFrame([{
        'Date': date,
        'Vendor/Category': vendor_category,
        'Amount': amount,
        'Description': description
    }])
    new_record = new_record.astype(st.session_state.payables.dtypes)
    st.session_state.payables = pd.concat([st.session_state.payables, new_record], ignore_index=True)

    # Post to GL (assuming cash payment for simplicity, could be Accounts Payable)
    post_to_gl(date, 'Expenses', amount, 0, f"Expense: {vendor_category} - {description}")
    post_to_gl(date, 'Cash', 0, amount, f"Cash Payment for {vendor_category}: {description}")
    st.success("Payable record added successfully and posted to GL!")

def add_sale_record(date, item, quantity, customer, sale_type):
    """Handles a POS sale, updates inventory, and posts to GL."""
    if item not in st.session_state.inventory['Item'].values:
        return 'error', 'Item not found in inventory.'

    item_row = st.session_state.inventory[st.session_state.inventory['Item'] == item].iloc[0]
    if quantity > item_row['Quantity']:
        return 'error', f"Not enough stock. Only {item_row['Quantity']} units available."

    # Calculate sale amounts
    total_sales_revenue = quantity * item_row['Selling Price']
    cost_of_goods_sold = quantity * item_row['Unit Cost']

    # Update inventory
    st.session_state.inventory.loc[item_row.name, 'Quantity'] -= quantity
    st.session_state.inventory.loc[item_row.name, 'Last Updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Post to GL - Sales Revenue
    if sale_type == 'Cash':
        post_to_gl(date, 'Cash', total_sales_revenue, 0, f"Cash Sale of {quantity} units of {item} to {customer}")
    else: # Credit
        post_to_gl(date, 'Accounts Receivable', total_sales_revenue, 0, f"Credit Sale of {quantity} units of {item} to {customer}")
    post_to_gl(date, 'Sales Revenue', 0, total_sales_revenue, f"Sale of {quantity} units of {item} to {customer}")

    # Post to GL - Cost of Goods Sold
    post_to_gl(date, 'Cost of Goods Sold', cost_of_goods_sold, 0, f"COGS for {quantity} units of {item} sold to {customer}")
    post_to_gl(date, 'Inventory', 0, cost_of_goods_sold, f"Inventory reduction for {quantity} units of {item} sold to {customer}")

    return 'success', "Sale recorded successfully and inventory updated!"

def generate_asset_tag(company, category, year, location):
    """Generates a unique asset tag."""
    tag = f"{company.upper()}-{category.upper()}-{year}-{location.upper()}"
    return tag

def calculate_and_post_depreciation(date):
    """Calculates and posts annual straight-line depreciation for all fixed assets."""
    if st.session_state.fixed_assets.empty:
        return 'warning', "No fixed assets to depreciate."

    gl = st.session_state.general_ledger
    # Check if depreciation has already been posted for the current year
    current_year = date.year
    if not gl[(gl['Account'] == 'Depreciation Expense') & (gl['Date'].dt.year == current_year)].empty:
        return 'warning', f"Depreciation for {current_year} has already been posted."

    for index, row in st.session_state.fixed_assets.iterrows():
        if row['Useful Life (Years)'] > 0:
            # Calculate annual depreciation using the straight-line method
            annual_depreciation = (row['Cost'] - row['Salvage Value']) / row['Useful Life (Years)']
            
            # Post to GL
            post_to_gl(date, 'Depreciation Expense', annual_depreciation, 0, f"Annual depreciation for {row['Asset Name']}")
            post_to_gl(date, 'Accumulated Depreciation', 0, annual_depreciation, f"Annual depreciation for {row['Asset Name']}")
            
            # Update the accumulated depreciation in the fixed assets register
            st.session_state.fixed_assets.loc[index, 'Accumulated Depreciation'] += annual_depreciation
    
    return 'success', f"Depreciation for {current_year} calculated and posted for all assets."

# --- Financial Statement Generation Functions ---

def generate_trial_balance():
    """Generates a simplified Trial Balance from the GL."""
    gl = st.session_state.general_ledger
    if gl.empty:
        return pd.DataFrame(columns=['Account', 'Debit', 'Credit'])

    trial_balance = gl.groupby('Account').agg(
        Debit=('Debit', 'sum'),
        Credit=('Credit', 'sum')
    ).reset_index()

    trial_balance['Balance'] = trial_balance['Debit'] - trial_balance['Credit']

    tb_display = []
    for index, row in trial_balance.iterrows():
        if abs(row['Balance']) > 0.01: # Only include accounts with a balance
            if row['Balance'] > 0: # Debit balance
                tb_display.append({'Account': row['Account'], 'Debit': row['Balance'], 'Credit': 0.0})
            else: # Credit balance
                tb_display.append({'Account': row['Account'], 'Debit': 0.0, 'Credit': abs(row['Balance'])})

    tb_df = pd.DataFrame(tb_display)
    if not tb_df.empty:
        tb_df.loc['Total'] = tb_df.sum(numeric_only=True)
        tb_df.loc['Total', 'Account'] = 'Total'
    return tb_df.fillna('')

def generate_income_statement():
    """Generates a simplified Income Statement, including COGS."""
    gl = st.session_state.general_ledger
    if gl.empty:
        return pd.DataFrame(columns=['Item', 'Amount'])

    revenue = gl[gl['Account'] == 'Sales Revenue']['Credit'].sum()
    cogs = gl[gl['Account'] == 'Cost of Goods Sold']['Debit'].sum()
    gross_profit = revenue - cogs
    
    # Sum up other expenses from GL
    expenses = gl[gl['Account'] == 'Expenses']['Debit'].sum()
    depreciation_expense = gl[gl['Account'] == 'Depreciation Expense']['Debit'].sum()
    
    total_operating_expenses = expenses + depreciation_expense
    net_income = gross_profit - total_operating_expenses

    data = {
        'Item': ['Sales Revenue', 'Less: Cost of Goods Sold', 'Gross Profit', 'Less: Operating Expenses', 'Less: Depreciation Expense', 'Net Income (Loss)'],
        'Amount': [revenue, -cogs, gross_profit, -expenses, -depreciation_expense, net_income]
    }
    return pd.DataFrame(data)

def generate_balance_sheet():
    """Generates a simplified Balance Sheet."""
    gl = st.session_state.general_ledger
    if gl.empty:
        return pd.DataFrame(columns=['Category', 'Account', 'Amount'])

    # Assets
    cash = gl[gl['Account'] == 'Cash']['Debit'].sum() - gl[gl['Account'] == 'Cash']['Credit'].sum()
    accounts_receivable = gl[gl['Account'] == 'Accounts Receivable']['Debit'].sum() - gl[gl['Account'] == 'Accounts Receivable']['Credit'].sum()
    inventory = gl[gl['Account'] == 'Inventory']['Debit'].sum() - gl[gl['Account'] == 'Inventory']['Credit'].sum()
    fixed_assets_cost = gl[gl['Account'] == 'Fixed Assets']['Debit'].sum()
    accumulated_depreciation = gl[gl['Account'] == 'Accumulated Depreciation']['Credit'].sum()
    net_fixed_assets = fixed_assets_cost - accumulated_depreciation

    total_current_assets = cash + accounts_receivable + inventory
    total_non_current_assets = net_fixed_assets
    total_assets = total_current_assets + total_non_current_assets

    # Liabilities & Equity
    accounts_payable = gl[gl['Account'] == 'Accounts Payable']['Credit'].sum() - gl[gl['Account'] == 'Accounts Payable']['Debit'].sum()
    # Assume 0 long-term debt for simplicity
    
    # Equity is derived from initial investment + retained earnings (net income)
    net_income = generate_income_statement()['Amount'].iloc[-1] if not generate_income_statement().empty else 0.0
    initial_equity = 0.0 # Placeholder
    retained_earnings = net_income
    total_equity = initial_equity + retained_earnings

    total_liabilities = accounts_payable
    total_liabilities_equity = total_liabilities + total_equity

    # Combine for display
    assets_data = [
        {'Category': 'Current Assets', 'Account': 'Cash', 'Amount': cash},
        {'Category': 'Current Assets', 'Account': 'Accounts Receivable', 'Amount': accounts_receivable},
        {'Category': 'Current Assets', 'Account': 'Inventory', 'Amount': inventory},
        {'Category': 'Total Current Assets', 'Account': '', 'Amount': total_current_assets},
        {'Category': 'Non-Current Assets', 'Account': 'Fixed Assets (Net)', 'Amount': net_fixed_assets},
        {'Category': 'Total Assets', 'Account': '', 'Amount': total_assets}
    ]
    liabilities_equity_data = [
        {'Category': 'Current Liabilities', 'Account': 'Accounts Payable', 'Amount': accounts_payable},
        {'Category': 'Total Liabilities', 'Account': '', 'Amount': total_liabilities},
        {'Category': 'Equity', 'Account': 'Owner\'s Equity (Simplified)', 'Amount': total_equity},
        {'Category': 'Total Liabilities & Equity', 'Account': '', 'Amount': total_liabilities_equity}
    ]
    
    combined_df = pd.DataFrame(assets_data + liabilities_equity_data)
    return combined_df

def generate_cash_flow_statement():
    """Generates a simplified Cash Flow Statement."""
    gl = st.session_state.general_ledger
    if gl.empty:
        return pd.DataFrame(columns=['Activity', 'Amount'])

    cash_in_from_sales = gl[(gl['Account'] == 'Cash') & (gl['Debit'] > 0) & (gl['Description'].str.contains('Sale'))]['Debit'].sum()
    cash_out_for_expenses = gl[(gl['Account'] == 'Cash') & (gl['Credit'] > 0) & (gl['Description'].str.contains('Payment'))]['Credit'].sum()
    net_cash_operating = cash_in_from_sales - cash_out_for_expenses

    cash_out_fixed_assets = gl[(gl['Account'] == 'Cash') & (gl['Credit'] > 0) & (gl['Description'].str.contains('Acquisition'))]['Credit'].sum()
    net_cash_investing = -cash_out_fixed_assets

    net_cash_financing = 0.0
    net_increase_decrease_in_cash = net_cash_operating + net_cash_investing + net_cash_financing
    beginning_cash_balance = 0.0
    ending_cash_balance = beginning_cash_balance + net_increase_decrease_in_cash

    data = {
        'Activity': [
            'Net Cash from Operating Activities',
            'Net Cash from Investing Activities',
            'Net Cash from Financing Activities',
            'Net Increase (Decrease) in Cash',
            'Beginning Cash Balance',
            'Ending Cash Balance'
        ],
        'Amount': [
            net_cash_operating,
            net_cash_investing,
            net_cash_financing,
            net_increase_decrease_in_cash,
            beginning_cash_balance,
            ending_cash_balance
        ]
    }
    return pd.DataFrame(data)

def generate_statement_of_change_in_equity():
    """Generates a simplified Statement of Change in Equity."""
    income_statement = generate_income_statement()
    net_income = income_statement['Amount'].iloc[-1] if not income_statement.empty else 0.0

    beginning_equity = 0.0
    ending_equity = beginning_equity + net_income

    data = {
        'Item': [
            'Beginning Equity Balance',
            'Add: Net Income (Loss)',
            'Less: Dividends/Withdrawals (N/A in demo)',
            'Ending Equity Balance'
        ],
        'Amount': [
            beginning_equity,
            net_income,
            0.0,
            ending_equity
        ]
    }
    return pd.DataFrame(data)

# --- Financial Analytics Functions (using uploaded data) ---
# (Unchanged from original script as they rely on uploaded data, not the app's internal state)

def calculate_ratios(is_df, bs_df):
    """Calculates key financial ratios from uploaded Income Statement and Balance Sheet."""
    ratios = {}
    try:
        # Income Statement items
        revenue = is_df[is_df['Item'] == 'Sales Revenue']['Amount'].sum()
        cogs = is_df[is_df['Item'] == 'Cost of Goods Sold']['Amount'].sum()
        gross_profit = revenue - cogs
        operating_expenses = is_df[is_df['Item'] == 'Operating Expenses']['Amount'].sum()
        interest_expense = is_df[is_df['Item'] == 'Interest Expense']['Amount'].sum()
        taxes = is_df[is_df['Item'] == 'Taxes']['Amount'].sum()
        net_income = revenue - cogs - operating_expenses - interest_expense - taxes

        # Balance Sheet items
        cash = bs_df[bs_df['Item'] == 'Cash']['Amount'].sum()
        accounts_receivable = bs_df[bs_df['Item'] == 'Accounts Receivable']['Amount'].sum()
        inventory = bs_df[bs_df['Item'] == 'Inventory']['Amount'].sum()
        current_assets = cash + accounts_receivable + inventory
        fixed_assets_net = bs_df[bs_df['Item'] == 'Fixed Assets (Net)']['Amount'].sum()
        total_assets = current_assets + fixed_assets_net
        
        accounts_payable = bs_df[bs_df['Item'] == 'Accounts Payable']['Amount'].sum()
        current_liabilities = accounts_payable
        long_term_debt = bs_df[bs_df['Item'] == 'Long-term Debt']['Amount'].sum() if 'Long-term Debt' in bs_df['Item'].values else 0
        total_liabilities = current_liabilities + long_term_debt

        owner_equity = bs_df[bs_df['Item'] == 'Owner\'s Equity (Simplified)']['Amount'].sum()
        total_liabilities_equity = total_liabilities + owner_equity

        # Profitability Ratios
        ratios['Gross Profit Margin'] = (gross_profit / revenue) if revenue else 0
        ratios['Net Profit Margin'] = net_income / revenue if revenue else 0

        # Liquidity Ratios
        ratios['Current Ratio'] = current_assets / current_liabilities if current_liabilities else float('inf')
        ratios['Quick Ratio'] = (current_assets - inventory) / current_liabilities if current_liabilities else float('inf')

        # Solvency Ratios
        ratios['Debt-to-Equity Ratio'] = total_liabilities / owner_equity if owner_equity else float('inf')

        # Efficiency Ratios
        ratios['Accounts Receivable Turnover (Days)'] = 365 / (revenue / accounts_receivable) if accounts_receivable and revenue else 0

        # Return Ratios
        ratios['Return on Assets (ROA)'] = net_income / total_assets if total_assets else 0
        ratios['Return on Equity (ROE)'] = net_income / owner_equity if owner_equity else 0

    except Exception as e:
        st.error(f"Error calculating ratios: {e}. Please ensure your uploaded data has the expected 'Item' names.")
        return {}
    return ratios

def forecast_financials(is_df, bs_df, years, revenue_growth, cogs_pct_revenue, op_exp_pct_revenue):
    """Performs a simple financial forecast for N years."""
    if is_df.empty or bs_df.empty:
        return None, None

    forecast_is = pd.DataFrame(columns=['Year', 'Sales Revenue', 'Cost of Goods Sold', 'Gross Profit', 'Operating Expenses', 'Net Income'])
    forecast_bs = pd.DataFrame(columns=['Year', 'Cash', 'Accounts Receivable', 'Inventory', 'Current Assets', 'Fixed Assets (Net)', 'Total Assets', 'Accounts Payable', 'Long-term Debt', 'Total Liabilities', 'Owner\'s Equity', 'Total Liabilities & Equity'])

    current_revenue = is_df[is_df['Item'] == 'Sales Revenue']['Amount'].sum() if 'Amount' in is_df.columns else 0
    current_cogs = is_df[is_df['Item'] == 'Cost of Goods Sold']['Amount'].sum() if 'Amount' in is_df.columns else 0
    current_operating_expenses = is_df[is_df['Item'] == 'Operating Expenses']['Amount'].sum() if 'Amount' in is_df.columns else 0
    current_net_income = is_df[is_df['Item'] == 'Net Income (Loss)']['Amount'].sum() if 'Amount' in is_df.columns else 0

    current_cash = bs_df[bs_df['Item'] == 'Cash']['Amount'].sum() if 'Amount' in bs_df.columns else 0
    current_ar = bs_df[bs_df['Item'] == 'Accounts Receivable']['Amount'].sum() if 'Amount' in bs_df.columns else 0
    current_inv = bs_df[bs_df['Item'] == 'Inventory']['Amount'].sum() if 'Amount' in bs_df.columns else 0
    current_fixed_assets_net = bs_df[bs_df['Item'] == 'Fixed Assets (Net)']['Amount'].sum() if 'Amount' in bs_df.columns else 0
    current_ap = bs_df[bs_df['Item'] == 'Accounts Payable']['Amount'].sum() if 'Amount' in bs_df.columns else 0
    current_lt_debt = bs_df[bs_df['Item'] == 'Long-term Debt']['Amount'].sum() if 'Long-term Debt' in bs_df['Item'].values else 0
    current_owner_equity = bs_df[bs_df['Item'] == 'Owner\'s Equity (Simplified)']['Amount'].sum() if 'Amount' in bs_df.columns else 0

    prev_revenue = current_revenue
    prev_cogs = current_cogs
    prev_op_exp = current_operating_expenses
    prev_net_income = current_net_income
    prev_cash = current_cash
    prev_ar = current_ar
    prev_inv = current_inv
    prev_fixed_assets_net = current_fixed_assets_net
    prev_ap = current_ap
    prev_lt_debt = current_lt_debt
    prev_owner_equity = current_owner_equity

    for i in range(1, years + 1):
        # Income Statement Projection
        proj_revenue = prev_revenue * (1 + revenue_growth / 100)
        proj_cogs = proj_revenue * (cogs_pct_revenue / 100)
        proj_gross_profit = proj_revenue - proj_cogs
        proj_op_exp = proj_revenue * (op_exp_pct_revenue / 100)
        proj_net_income = proj_gross_profit - proj_op_exp

        forecast_is.loc[i-1] = [
            datetime.now().year + i,
            proj_revenue,
            proj_cogs,
            proj_gross_profit,
            proj_op_exp,
            proj_net_income
        ]

        # Balance Sheet Projection
        proj_ar = proj_revenue * 0.1
        proj_inv = proj_cogs * 0.05
        proj_ap = proj_cogs * 0.05
        proj_cash = prev_cash + proj_net_income - (proj_ar - prev_ar) - (proj_inv - prev_inv) + (proj_ap - prev_ap)

        proj_current_assets = proj_cash + proj_ar + proj_inv
        proj_fixed_assets_net = prev_fixed_assets_net
        proj_total_assets = proj_current_assets + proj_fixed_assets_net

        proj_current_liabilities = proj_ap
        proj_lt_debt = prev_lt_debt
        proj_total_liabilities = proj_current_liabilities + proj_lt_debt
        proj_owner_equity = prev_owner_equity + proj_net_income
        proj_total_liabilities_equity = proj_total_liabilities + proj_owner_equity

        forecast_bs.loc[i-1] = [
            datetime.now().year + i,
            proj_cash,
            proj_ar,
            proj_inv,
            proj_current_assets,
            proj_fixed_assets_net,
            proj_total_assets,
            proj_ap,
            proj_lt_debt,
            proj_total_liabilities,
            proj_owner_equity,
            proj_total_liabilities_equity
        ]

        # Update previous values for next iteration
        prev_revenue = proj_revenue
        prev_cogs = proj_cogs
        prev_op_exp = proj_op_exp
        prev_net_income = proj_net_income
        prev_cash = proj_cash
        prev_ar = proj_ar
        prev_inv = proj_inv
        prev_fixed_assets_net = proj_fixed_assets_net
        prev_ap = proj_ap
        prev_lt_debt = proj_lt_debt
        prev_owner_equity = proj_owner_equity

    return forecast_is, forecast_bs

# --- Page Content based on Navigation ---

if page == "Daily Records (Receivables & Payables)":
    st.title("Daily Records - Receivables & Payables")
    st.header("Daily Records of Receivables")
    with st.expander("Add New Receivable Record"):
        with st.form("receivable_form", clear_on_submit=True):
            r_date = st.date_input("Date", datetime.now())
            r_customer = st.text_input("Customer Name")
            r_type = st.radio("Record Type", ("Cash", "Credit"))
            r_amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            r_description = st.text_area("Description (Optional)")
            submit_receivable = st.form_submit_button("Add Receivable")
            if submit_receivable:
                if r_customer and r_amount > 0:
                    add_receivable_record(r_date, r_customer, r_type, r_amount, r_description)
                else:
                    st.error("Please fill in Customer Name and Amount.")
    st.subheader("All Receivable Records")
    if not st.session_state.receivables.empty:
        st.dataframe(st.session_state.receivables.sort_values(by='Date', ascending=False).reset_index(drop=True))
    else:
        st.info("No receivable records added yet.")
    st.markdown("---")
    st.header("Daily Records of Payables (Expenses)")
    with st.expander("Add New Payable Record"):
        with st.form("payable_form", clear_on_submit=True):
            p_date = st.date_input("Date ", datetime.now())
            p_vendor_category = st.text_input("Vendor/Expense Category")
            p_amount = st.number_input("Amount ", min_value=0.0, format="%.2f")
            p_description = st.text_area("Description (Optional) ")
            submit_payable = st.form_submit_button("Add Payable")
            if submit_payable:
                if p_vendor_category and p_amount > 0:
                    add_payable_record(p_date, p_vendor_category, p_amount, p_description)
                else:
                    st.error("Please fill in Vendor/Expense Category and Amount.")
    st.subheader("All Payable Records")
    if not st.session_state.payables.empty:
        st.dataframe(st.session_state.payables.sort_values(by='Date', ascending=False).reset_index(drop=True))
    else:
        st.info("No payable records added yet.")

elif page == "Inventory Management":
    st.title("Inventory Management")
    with st.expander("Add/Update Inventory Item"):
        with st.form("inventory_form", clear_on_submit=True):
            item_name = st.text_input("Item Name")
            quantity = st.number_input("Quantity", min_value=0, step=1)
            unit_cost = st.number_input("Unit Cost", min_value=0.0, format="%.2f")
            selling_price = st.number_input("Selling Price", min_value=0.0, format="%.2f")
            submit_inventory = st.form_submit_button("Add/Update Item")
            if submit_inventory:
                if item_name and quantity >= 0 and unit_cost >= 0 and selling_price >= 0:
                    if item_name in st.session_state.inventory['Item'].values:
                        idx = st.session_state.inventory[st.session_state.inventory['Item'] == item_name].index[0]
                        st.session_state.inventory.loc[idx, 'Quantity'] = quantity
                        st.session_state.inventory.loc[idx, 'Unit Cost'] = unit_cost
                        st.session_state.inventory.loc[idx, 'Selling Price'] = selling_price
                        st.session_state.inventory.loc[idx, 'Last Updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        st.success(f"Inventory for '{item_name}' updated.")
                    else:
                        new_item = pd.DataFrame([{
                            'Item': item_name,
                            'Quantity': quantity,
                            'Unit Cost': unit_cost,
                            'Selling Price': selling_price,
                            'Last Updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }])
                        new_item = new_item.astype(st.session_state.inventory.dtypes)
                        st.session_state.inventory = pd.concat([st.session_state.inventory, new_item], ignore_index=True)
                        st.success(f"New inventory item '{item_name}' added.")
                else:
                    st.error("Please fill in all inventory details correctly.")
    st.subheader("Current Inventory Stock")
    if not st.session_state.inventory.empty:
        st.dataframe(st.session_state.inventory)
    else:
        st.info("No inventory items added yet.")

elif page == "Fixed Asset Register":
    st.title("Fixed Asset Register")
    with st.expander("Add New Fixed Asset"):
        with st.form("fixed_asset_form", clear_on_submit=True):
            asset_name = st.text_input("Asset Name")
            asset_category = st.text_input("Asset Category (e.g., Vehicle, Equipment)")
            asset_location = st.text_input("Asset Location (e.g., HQ, Warehouse)")
            acquisition_date = st.date_input("Acquisition Date", datetime.now())
            cost = st.number_input("Cost", min_value=0.0, format="%.2f")
            salvage_value = st.number_input("Salvage Value", min_value=0.0, format="%.2f")
            useful_life = st.number_input("Useful Life (Years)", min_value=1, step=1)
            submit_asset = st.form_submit_button("Add Asset")
            if submit_asset:
                if asset_name and cost > 0 and useful_life > 0 and asset_category and asset_location:
                    asset_tag = generate_asset_tag("YOUR_COMPANY", asset_category, acquisition_date.year, asset_location)
                    new_asset = pd.DataFrame([{
                        'Asset Tag': asset_tag,
                        'Asset Name': asset_name,
                        'Category': asset_category,
                        'Location': asset_location,
                        'Acquisition Date': acquisition_date,
                        'Cost': cost,
                        'Salvage Value': salvage_value,
                        'Useful Life (Years)': useful_life,
                        'Accumulated Depreciation': 0.0
                    }])
                    new_asset = new_asset.astype(st.session_state.fixed_assets.dtypes)
                    st.session_state.fixed_assets = pd.concat([st.session_state.fixed_assets, new_asset], ignore_index=True)
                    post_to_gl(acquisition_date, 'Fixed Assets', cost, 0, f"Acquisition of {asset_name} ({asset_tag})")
                    post_to_gl(acquisition_date, 'Cash', 0, cost, f"Cash payment for {asset_name}")
                    st.success(f"Fixed asset '{asset_name}' added with tag '{asset_tag}' and posted to GL.")
                else:
                    st.error("Please fill in all asset details correctly.")
    
    st.subheader("Registered Fixed Assets")
    if not st.session_state.fixed_assets.empty:
        st.dataframe(st.session_state.fixed_assets)
    else:
        st.info("No fixed assets registered yet.")
    
    st.markdown("---")
    st.subheader("Depreciation Management")
    if st.button("Calculate and Post Annual Depreciation"):
        status, message = calculate_and_post_depreciation(datetime.now())
        if status == 'success':
            st.success(message)
        elif status == 'warning':
            st.warning(message)

elif page == "Point of Sale (POS)":
    st.title("Point of Sale (POS)")
    st.write("Record sales transactions and automatically update your inventory.")

    if st.session_state.inventory.empty:
        st.warning("Please add items to the Inventory Management page before making a sale.")
    else:
        with st.form("pos_form", clear_on_submit=True):
            sale_date = st.date_input("Date of Sale", datetime.now())
            available_items = st.session_state.inventory['Item'].tolist()
            selected_item = st.selectbox("Select Item", available_items)
            
            # Display item details for user
            if selected_item:
                item_details = st.session_state.inventory[st.session_state.inventory['Item'] == selected_item].iloc[0]
                st.write(f"**Available Quantity:** {item_details['Quantity']}")
                st.write(f"**Selling Price:** ${item_details['Selling Price']:.2f}")

            sale_quantity = st.number_input("Quantity Sold", min_value=1, step=1)
            customer_name = st.text_input("Customer Name (Optional)")
            sale_type = st.radio("Payment Type", ("Cash", "Credit"))

            submit_sale = st.form_submit_button("Record Sale")

            if submit_sale:
                status, message = add_sale_record(sale_date, selected_item, sale_quantity, customer_name, sale_type)
                if status == 'success':
                    st.success(message)
                else:
                    st.error(message)

elif page == "Financial Statements":
    st.title("Financial Statements")
    st.write("Generate essential financial reports based on your recorded transactions.")
    st.warning("These statements are illustrative and based on a simplified General Ledger. For accurate, auditable reports, a comprehensive accounting system is required.")

    with st.expander("View General Ledger (for debugging)", expanded=False):
        st.subheader("Simplified General Ledger Transactions")
        if not st.session_state.general_ledger.empty:
            st.dataframe(st.session_state.general_ledger.sort_values(by='Date', ascending=False).reset_index(drop=True))
        else:
            st.info("No GL entries yet. Add some transactions first.")
    
    st.markdown("---")
    
    col_tb, col_is, col_bs = st.columns(3)
    col_cf, col_sce, _ = st.columns(3)

    with col_tb:
        with st.expander("⚖️ Trial Balance", expanded=True):
            st.write("A summary of all debit and credit balances to ensure equality.")
            if st.button("Generate Trial Balance"):
                tb_df = generate_trial_balance()
                if not tb_df.empty:
                    st.dataframe(tb_df.style.format({'Debit': '{:,.2f}', 'Credit': '{:,.2f}'}), use_container_width=True)
                    if 'Total' in tb_df.index and abs(tb_df.loc['Total', 'Debit'] - tb_df.loc['Total', 'Credit']) > 0.01:
                        st.error("🚨 Debits and Credits do NOT balance! (This indicates an issue in GL posting)")
                    else:
                        st.success("✅ Debits and Credits balance!")
                else:
                    st.info("No data to generate Trial Balance.")

    with col_is:
        with st.expander("📈 Comprehensive Income Statement", expanded=True):
            st.write("Summarizes revenues and expenses over a period to show profitability.")
            if st.button("Generate Income Statement"):
                is_df = generate_income_statement()
                if not is_df.empty:
                    st.dataframe(is_df.style.format({'Amount': '{:,.2f}'}), use_container_width=True)
                else:
                    st.info("No data to generate Income Statement.")

    with col_bs:
        with st.expander("📊 Balance Sheet", expanded=True):
            st.write("A snapshot of assets, liabilities, and equity at a specific point in time.")
            if st.button("Generate Balance Sheet"):
                bs_df = generate_balance_sheet()
                if not bs_df.empty:
                    st.dataframe(bs_df.style.format({'Amount': '{:,.2f}'}), use_container_width=True)
                    total_assets = bs_df[bs_df['Category'] == 'Total Assets']['Amount'].iloc[0] if 'Total Assets' in bs_df['Category'].values else 0
                    total_liabilities_equity = bs_df[bs_df['Category'] == 'Total Liabilities & Equity']['Amount'].iloc[0] if 'Total Liabilities & Equity' in bs_df['Category'].values else 0
                    if abs(total_assets - total_liabilities_equity) > 0.01:
                        st.error("🚨 Assets do NOT equal Liabilities + Equity! (This indicates an issue)")
                    else:
                        st.success("✅ Assets = Liabilities + Equity!")
                else:
                    st.info("No data to generate Balance Sheet.")

    with col_cf:
        with st.expander("💸 Cash Flow Statement", expanded=True):
            st.write("Reports cash inflows and outflows from operating, investing, and financing activities.")
            if st.button("Generate Cash Flow Statement"):
                cfs_df = generate_cash_flow_statement()
                if not cfs_df.empty:
                    st.dataframe(cfs_df.style.format({'Amount': '{:,.2f}'}), use_container_width=True)
                else:
                    st.info("No data to generate Cash Flow Statement.")

    with col_sce:
        with st.expander("💰 Statement of Change in Equity", expanded=True):
            st.write("Details the changes in owner's equity over a period.")
            if st.button("Generate Statement of Change in Equity"):
                sce_df = generate_statement_of_change_in_equity()
                if not sce_df.empty:
                    st.dataframe(sce_df.style.format({'Amount': '{:,.2f}'}), use_container_width=True)
                else:
                    st.info("No data to generate Statement of Change in Equity.")

elif page == "Analytics":
    st.title("Financial Analytics & Insights")
    st.write("Explore key financial metrics, visualize trends, and perform basic modeling.")
    st.header("Upload Financial Statements for Analysis")
    st.info("Please upload your Income Statement and Balance Sheet as CSV files. "
            "Each file **must** have two columns: 'Item' and 'Amount'. "
            "**Ensure there are no extra spaces in column headers.**")
    uploaded_is_file = st.file_uploader("Upload Income Statement (CSV)", type=["csv"], key="is_uploader")
    uploaded_bs_file = st.file_uploader("Upload Balance Sheet (CSV)", type=["csv"], key="bs_uploader")

    if uploaded_is_file is not None:
        try:
            temp_df = pd.read_csv(uploaded_is_file)
            temp_df.columns = temp_df.columns.str.strip()
            if 'Item' in temp_df.columns and 'Amount' in temp_df.columns:
                st.session_state.uploaded_is = temp_df
                st.success("Income Statement uploaded successfully!")
                st.subheader("Uploaded Income Statement Preview:")
                st.dataframe(st.session_state.uploaded_is)
            else:
                st.error("Error: Income Statement CSV must contain 'Item' and 'Amount' columns.")
                st.session_state.uploaded_is = None
        except Exception as e:
            st.error(f"Error reading Income Statement file: {e}")
            st.session_state.uploaded_is = None
    if uploaded_bs_file is not None:
        try:
            temp_df = pd.read_csv(uploaded_bs_file)
            temp_df.columns = temp_df.columns.str.strip()
            if 'Item' in temp_df.columns and 'Amount' in temp_df.columns:
                st.session_state.uploaded_bs = temp_df
                st.success("Balance Sheet uploaded successfully!")
                st.subheader("Uploaded Balance Sheet Preview:")
                st.dataframe(st.session_state.uploaded_bs)
            else:
                st.error("Error: Balance Sheet CSV must contain 'Item' and 'Amount' columns.")
                st.session_state.uploaded_bs = None
        except Exception as e:
            st.error(f"Error reading Balance Sheet file: {e}")
            st.session_state.uploaded_bs = None

    st.markdown("---")
    if st.session_state.uploaded_is is not None and st.session_state.uploaded_bs is not None:
        is_df = st.session_state.uploaded_is
        bs_df = st.session_state.uploaded_bs
        col1, col2 = st.columns(2)
        with col1:
            with st.expander("📊 Financial Ratios", expanded=True):
                st.write("Analyze key financial performance indicators from your uploaded statements.")
                if st.button("Calculate Ratios"):
                    ratios = calculate_ratios(is_df, bs_df)
                    if ratios:
                        for ratio_name, value in ratios.items():
                            if isinstance(value, (int, float)):
                                st.write(f"**{ratio_name}:** {value:,.2f}")
                            else:
                                st.write(f"**{ratio_name}:** {value}")
                        st.info("Interpretation: These ratios provide insights into the company's profitability, liquidity, solvency, and efficiency.")
                    else:
                        st.warning("Could not calculate ratios. Please check your uploaded file format and 'Item' names.")
            with st.expander("📈 Forecasting for Years", expanded=True):
                st.write("Project future financial performance based on assumed growth rates.")
                st.subheader("Forecasting Assumptions")
                forecast_years = st.slider("Number of Years to Forecast", 1, 10, 3)
                revenue_growth_rate = st.slider("Annual Revenue Growth Rate (%)", 0, 30, 5)
                
                current_revenue = is_df[is_df['Item'] == 'Sales Revenue']['Amount'].sum() if 'Sales Revenue' in is_df['Item'].values else 0
                current_cogs = is_df[is_df['Item'] == 'Cost of Goods Sold']['Amount'].sum() if 'Cost of Goods Sold' in is_df['Item'].values else 0
                current_op_exp = is_df[is_df['Item'] == 'Operating Expenses']['Amount'].sum() if 'Operating Expenses' in is_df['Item'].values else 0
                cogs_pct_revenue = (current_cogs / current_revenue * 100) if current_revenue else 40
                op_exp_pct_revenue = (current_op_exp / current_revenue * 100) if current_revenue else 30
                
                st.write(f"Assumed COGS as % of Revenue: {cogs_pct_revenue:.2f}%")
                st.write(f"Assumed Operating Expenses as % of Revenue: {op_exp_pct_revenue:.2f}%")
                
                if st.button("Run Forecast"):
                    forecasted_is, forecasted_bs = forecast_financials(is_df, bs_df, forecast_years, revenue_growth_rate, cogs_pct_revenue, op_exp_pct_revenue)
                    if forecasted_is is not None and not forecasted_is.empty:
                        st.subheader("Forecasted Income Statement")
                        st.dataframe(forecasted_is.style.format('{:,.2f}'), use_container_width=True)
                        st.subheader("Forecasted Balance Sheet")
                        st.dataframe(forecasted_bs.style.format('{:,.2f}'), use_container_width=True)
                        st.info("Interpretation: This forecast helps in long-term planning and setting strategic goals.")
                    else:
                        st.warning("Could not generate forecast.")
        with col2:
            with st.expander("💰 Scenario & Sensitivity Analysis", expanded=True):
                st.write("Understand the impact of changing key variables on your financial outcomes.")
                st.subheader("Scenario Parameters")
                scenario_revenue_growth_impact = st.slider("Change in Revenue Growth (%)", -10, 10, 0)
                scenario_cogs_impact = st.slider("Change in COGS as % of Revenue (%)", -5, 5, 0)
                if st.button("Run Scenario Analysis"):
                    base_revenue = is_df[is_df['Item'] == 'Sales Revenue']['Amount'].sum() if 'Sales Revenue' in is_df['Item'].values else 0
                    base_cogs = is_df[is_df['Item'] == 'Cost of Goods Sold']['Amount'].sum() if 'Cost of Goods Sold' in is_df['Item'].values else 0
                    base_op_exp = is_df[is_df['Item'] == 'Operating Expenses']['Amount'].sum() if 'Operating Expenses' in is_df['Item'].values else 0
                    base_net_income = base_revenue - base_cogs - base_op_exp

                    base_cogs_pct = (base_cogs / base_revenue * 100) if base_revenue else 0
                    scenario_revenue = base_revenue * (1 + scenario_revenue_growth_impact / 100)
                    scenario_cogs_pct = base_cogs_pct + scenario_cogs_impact
                    scenario_cogs = scenario_revenue * (scenario_cogs_pct / 100)
                    scenario_op_exp = base_op_exp
                    scenario_net_income = scenario_revenue - scenario_cogs - scenario_op_exp

                    st.subheader("Scenario Results (Impact on Net Income)")
                    st.write(f"**Base Net Income:** ${base_net_income:,.2f}")
                    st.write(f"**Scenario Net Income:** ${scenario_net_income:,.2f}")
                    if base_net_income != 0:
                        st.metric(label="Change in Net Income", value=f"${scenario_net_income - base_net_income:,.2f}", delta=f"{((scenario_net_income - base_net_income) / base_net_income * 100):.2f}%")
                    else:
                        st.write(f"Change in Net Income: ${scenario_net_income - base_net_income:,.2f}")
                        st.info("Cannot calculate percentage change as Base Net Income is zero.")
            with st.expander("💼 Management Accounting (Conceptual)"):
                st.write("This section focuses on internal decision-making.")
                st.subheader("Basic Expense Overview (from GL data)")
                total_payables = st.session_state.payables['Amount'].sum() if not st.session_state.payables.empty else 0.0
                st.write(f"Total Recorded Expenses: ${total_payables:,.2f}")
                if not st.session_state.payables.empty:
                    st.dataframe(st.session_state.payables.groupby('Vendor/Category')['Amount'].sum().sort_values(ascending=False))
                else:
                    st.info("No payables data for expense overview.")
            with st.expander("📊 Relevant Charts (from GL data)", expanded=True):
                st.write("Visualizations of your daily records.")
                if not st.session_state.receivables.empty:
                    st.subheader("Receivables by Type")
                    receivables_by_type = st.session_state.receivables.groupby('Type')['Amount'].sum().reset_index()
                    fig_receivables = px.bar(receivables_by_type, x='Type', y='Amount', title='Total Receivables by Type (Cash vs. Credit)', labels={'Amount': 'Total Amount ($)', 'Type': 'Record Type'})
                    st.plotly_chart(fig_receivables, use_container_width=True)
                else:
                    st.info("No receivables data to chart yet.")
                st.markdown("---")
                if not st.session_state.payables.empty:
                    st.subheader("Payables by Category")
                    payables_by_category = st.session_state.payables.groupby('Vendor/Category')['Amount'].sum().reset_index()
                    fig_payables = px.pie(payables_by_category, values='Amount', names='Vendor/Category', title='Payables Distribution by Category')
                    st.plotly_chart(fig_payables, use_container_width=True)
                else:
                    st.info("No payables data to chart yet.")
    else:
        st.warning("Please upload both Income Statement and Balance Sheet CSV files to enable advanced analytics.")

st.sidebar.markdown("---")
st.sidebar.info("This is a basic framework. Data persistence would require integration with a database.")
