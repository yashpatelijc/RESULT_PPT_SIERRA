import streamlit as st
import pandas as pd
import re
import io

# --- 1. Robust Parser Function ---
def parse_strategy_text(text):
    """
    Parses the raw text pasted from the trading platform to extract metrics.
    Handles 'glued' text (e.g. '$1848Avg') and removes currency symbols.
    """
    data = {}
    
    # Helper: Finds a label, skips non-digit chars (like $ : space), captures the number
    def extract_val(label_pattern, text_block):
        # Pattern: Label -> skip any non-digit/minus -> capture number (digits, commas, dots, minus)
        # We use [^0-9-]* to skip '$', ':', ' ', etc.
        full_pattern = label_pattern + r"[^0-9-]*([\d,.-]+)"
        match = re.search(full_pattern, text_block, re.IGNORECASE)
        if match:
            clean_str = match.group(1).replace(',', '').strip()
            try:
                # Remove trailing '.' if it exists (e.g. end of sentence)
                if clean_str.endswith('.'):
                    clean_str = clean_str[:-1]
                return float(clean_str)
            except ValueError:
                return 0.0
        return 0.0

    # Helper: Extracts 3 values (All, Long, Short) following a label
    def extract_triple(label, text_block):
        # Pattern: Label -> skip junk -> num1 -> space -> num2 -> space -> num3
        # We allow for messy spacing
        pattern = f"{label}" + r".*?([\d\.-]+)\s+([\d\.-]+)\s+([\d\.-]+)"
        match = re.search(pattern, text_block, re.IGNORECASE | re.DOTALL)
        if match:
            try:
                return float(match.group(1)), float(match.group(2)), float(match.group(3))
            except ValueError:
                return 0.0, 0.0, 0.0
        return 0.0, 0.0, 0.0

    # --- Extraction Logic ---
    
    # 1. Total PnL 
    # Logic: Look for "Total Profit" first. If 0, look for "Overall" at the start.
    total_pnl = extract_val(r"Total Profit", text)
    if total_pnl == 0:
        total_pnl = extract_val(r"Overall", text)
    data['Total PnL'] = total_pnl

    # 2. General Metrics (Updated for glued text)
    data['Avg Win Trade PnL'] = extract_val(r"Avg Win Trade PnL", text)
    data['Avg Losing Trade PnL'] = extract_val(r"Avg Losing Trade PnL", text)
    data['Realized RRR'] = extract_val(r"Realized RRR", text)
    data['PnL per Trade'] = extract_val(r"PnL per Trade", text)
    
    # 3. Account Size
    data['Account Size'] = extract_val(r"Account Size", text)

    # 4. Triple Metrics (All, Long, Short)
    pf_all, pf_long, pf_short = extract_triple("Profit Factor", text)
    data['Profit Factor (All)'] = pf_all
    data['Profit Factor (Long)'] = pf_long
    data['Profit Factor (Short)'] = pf_short

    tt_all, tt_long, tt_short = extract_triple("Total Trades", text)
    data['Total Trades (All)'] = tt_all
    data['Total Trades (Long)'] = tt_long
    data['Total Trades (Short)'] = tt_short

    p_all, p_long, p_short = extract_triple("% Profitable", text)
    data['% Profitable (All)'] = p_all
    data['% Profitable (Long)'] = p_long
    data['% Profitable (Short)'] = p_short

    return data

# --- 2. Processing Logic ---
def process_entry(product, timeframe, start_year, end_year, raw_text, test_type):
    if not raw_text.strip():
        return None

    parsed_data = parse_strategy_text(raw_text)
    
    # --- Calculation Updates ---
    try:
        # User request: Difference + 1
        no_of_years = (int(end_year) - int(start_year)) + 1
    except ValueError:
        no_of_years = 1
        
    # Safety: ensure at least 1 year to avoid division by zero
    calc_years = no_of_years if no_of_years > 0 else 1
    
    account_size = parsed_data.get('Account Size', 0)
    # Safety: ensure account size is not zero for division
    safe_account_size = account_size if account_size > 0 else 1

    # ROI Calculation: (Total PnL / Years) / Account Size
    avg_pnl_per_year = parsed_data.get('Total PnL', 0) / calc_years
    metric_roi = avg_pnl_per_year / safe_account_size

    # New Calculation: Avg Trades per Year
    avg_trades_all = parsed_data.get('Total Trades (All)', 0) / calc_years
    avg_trades_long = parsed_data.get('Total Trades (Long)', 0) / calc_years
    avg_trades_short = parsed_data.get('Total Trades (Short)', 0) / calc_years

    # Construct Row
    row = {
        "Product": product,
        "Timeframe": timeframe,
        "Test Type": test_type, # Helper col for sorting
        "Start Year": start_year,
        "End Year": end_year,
        "No of Years": no_of_years,
        "Account Size": account_size,
        "Total PnL": parsed_data.get('Total PnL', 0),
        "Avg PnL per Year / Account Size": metric_roi,
        
        # Trades
        "Total Trades (All)": parsed_data.get('Total Trades (All)', 0),
        "Total Trades (Long)": parsed_data.get('Total Trades (Long)', 0),
        "Total Trades (Short)": parsed_data.get('Total Trades (Short)', 0),
        
        # Avg Trades (Calculated)
        "Avg Trades/Year (All)": avg_trades_all,
        "Avg Trades/Year (Long)": avg_trades_long,
        "Avg Trades/Year (Short)": avg_trades_short,

        # Performance Metrics
        "Avg Win Trade PnL": parsed_data.get('Avg Win Trade PnL', 0),
        "Avg Losing Trade PnL": parsed_data.get('Avg Losing Trade PnL', 0),
        "Realized RRR": parsed_data.get('Realized RRR', 0),
        "PnL per Trade": parsed_data.get('PnL per Trade', 0),
        
        "Profit Factor (All)": parsed_data.get('Profit Factor (All)', 0),
        "Profit Factor (Long)": parsed_data.get('Profit Factor (Long)', 0),
        "Profit Factor (Short)": parsed_data.get('Profit Factor (Short)', 0),
        
        "% Profitable (All)": parsed_data.get('% Profitable (All)', 0),
        "% Profitable (Long)": parsed_data.get('% Profitable (Long)', 0),
        "% Profitable (Short)": parsed_data.get('% Profitable (Short)', 0),
    }
    return row

# --- 3. Streamlit UI ---
st.set_page_config(page_title="Strategy Analyzer", layout="wide")

st.title("📊 Strategy Performance Parser")
st.markdown("Enter strategy details below. Paste text directly from your report (glued text is handled automatically).")

# Initialize Session State
if 'strategy_data' not in st.session_state:
    st.session_state.strategy_data = []

# --- Input Section ---
with st.form("entry_form", clear_on_submit=True):
    col_main1, col_main2 = st.columns(2)
    
    with col_main1:
        product_name = st.text_input("Product Name", placeholder="e.g. Nifty Futures")
    with col_main2:
        timeframe_input = st.selectbox("Timeframe", ["Daily", "240M", "Weekly"])

    st.markdown("---")
    
    c1, c2 = st.columns(2)

    # === Backtesting Column ===
    with c1:
        st.subheader("Backtesting Data")
        bt_start = st.number_input("BT Start Year", min_value=1990, max_value=2030, value=2015, step=1, key="bt_start")
        bt_end = st.number_input("BT End Year", min_value=1990, max_value=2030, value=2020, step=1, key="bt_end")
        bt_text = st.text_area("Paste Backtest Results", height=200, key="bt_text")

    # === Forward Testing Column ===
    with c2:
        st.subheader("Forward Testing Data")
        ft_start = st.number_input("FT Start Year", min_value=1990, max_value=2030, value=2021, step=1, key="ft_start")
        ft_end = st.number_input("FT End Year", min_value=1990, max_value=2030, value=2023, step=1, key="ft_end")
        ft_text = st.text_area("Paste Forward Test Results", height=200, key="ft_text")

    submitted = st.form_submit_button("Add Entry to List")

    if submitted:
        if not product_name:
            st.error("Please enter a Product Name.")
        else:
            added_count = 0
            if bt_text:
                bt_row = process_entry(product_name, timeframe_input, bt_start, bt_end, bt_text, "Backtesting")
                if bt_row: 
                    st.session_state.strategy_data.append(bt_row)
                    added_count += 1
            if ft_text:
                ft_row = process_entry(product_name, timeframe_input, ft_start, ft_end, ft_text, "Forward Testing")
                if ft_row: 
                    st.session_state.strategy_data.append(ft_row)
                    added_count += 1
            
            if added_count > 0:
                st.success(f"Added {added_count} entries for {product_name}.")
            else:
                st.warning("No text pasted.")

# --- 4. Display & Export Section ---
if st.session_state.strategy_data:
    df = pd.DataFrame(st.session_state.strategy_data)
    
    st.markdown("### 📋 Current Entries")
    st.dataframe(df)
    
    # --- Excel Export Logic ---
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Get unique combos of Timeframe + Test Type
        combos = df[['Timeframe', 'Test Type']].drop_duplicates()
        
        for _, row in combos.iterrows():
            tf = row['Timeframe']
            tt = row['Test Type']
            
            sheet_df = df[(df['Timeframe'] == tf) & (df['Test Type'] == tt)]
            sheet_df = sheet_df.drop(columns=['Test Type']) # Clean up
            
            # Sheet Name: e.g. "Daily Backtesting"
            sheet_name = f"{tf} {tt}"[:31]
            sheet_df.to_excel(writer, index=False, sheet_name=sheet_name)
            
    output.seek(0)
    
    st.download_button(
        label="📥 Download Excel Report",
        data=output,
        file_name="Strategy_Performance_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    if st.button("Clear All Data"):
        st.session_state.strategy_data = []
        st.rerun()
