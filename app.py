import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="Attendance Monitor", page_icon="⏱️", layout="wide")

# --- Database Setup ---
EMPLOYEES_FILE = "employees.csv"

def load_employees():
    if os.path.exists(EMPLOYEES_FILE):
        return pd.read_csv(EMPLOYEES_FILE)
    else:
        return pd.DataFrame(columns=["Employee ID", "Scheduled Time In", "Scheduled Time Out"])

df_employees = load_employees()

st.title("⏱️ Automated Attendance Tracker")

# --- Helper Functions for Time Parsing ---
def parse_time_string(time_str):
    time_str = time_str.strip()
    if time_str == '24:00' or time_str == '24:00:00':
        return datetime.strptime("23:59:59", "%H:%M:%S").time()
    
    if time_str.count(':') == 1:
        return datetime.strptime(time_str, "%H:%M").time()
    else:
        return datetime.strptime(time_str, "%H:%M:%S").time()

def get_closest_scheduled_time(actual_time, sched_times_list):
    dummy_date = datetime(2000, 1, 1)
    # If the actual time is past midnight (e.g. 00:05), push it forward 24 hours for math
    # so it correctly calculates distance from a 23:59:59 schedule
    is_late_night = actual_time.hour < 5
    dt_actual = datetime.combine(dummy_date, actual_time)
    if is_late_night:
        dt_actual += timedelta(days=1)
    
    closest_dt = None
    min_diff = None
    
    for st_time in sched_times_list:
        dt_st = datetime.combine(dummy_date, st_time)
        # If the scheduled time is 23:59:59, we also push it forward so the math matches
        if st_time.hour >= 23:
            dt_st += timedelta(days=1)
            
        diff = abs((dt_actual - dt_st).total_seconds())
        if min_diff is None or diff < min_diff:
            min_diff = diff
            closest_dt = dt_st
            
    # Revert the dummy date push before returning
    if closest_dt.day > 1:
        closest_dt -= timedelta(days=1)
        
    return closest_dt.time()

# --- Create Tabs for Navigation ---
tab1, tab2 = st.tabs(["📊 Analyze Attendance", "👥 Manage Employees"])

# ==========================================
# TAB 2: MANAGE EMPLOYEES 
# ==========================================
with tab2:
    st.header("Add New Employee")
    st.write("Fill out the details below. **For multiple shifts, separate times with a slash (/)**.")
    
    with st.form("add_employee_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            new_id = st.text_input("Employee ID*")
        with col2:
            new_time_in = st.text_input("Scheduled Time In (e.g., 10:00/18:00)*")
        with col3:
            new_time_out = st.text_input("Scheduled Time Out (e.g., 12:00/24:00)*")
        
        submitted = st.form_submit_button("➕ Add Employee")
        
        if submitted:
            if new_id and new_time_in and new_time_out:
                new_employee = pd.DataFrame([{
                    "Employee ID": str(new_id).strip(),
                    "Scheduled Time In": str(new_time_in).strip(),
                    "Scheduled Time Out": str(new_time_out).strip()
                }])
                
                df_employees = pd.concat([df_employees, new_employee], ignore_index=True)
                df_employees.to_csv(EMPLOYEES_FILE, index=False)
                
                st.success(f"Successfully added {new_id} to the database!")
                st.rerun()
            else:
                st.error("Please fill in all the input boxes.")

    st.divider()
    
    st.subheader("Current Employee Database")
    edited_employees = st.data_editor(df_employees, num_rows="dynamic", use_container_width=True)
    
    if st.button("💾 Save Database Changes"):
        edited_employees.to_csv(EMPLOYEES_FILE, index=False)
        st.success("Database updated successfully!")

# ==========================================
# TAB 1: ANALYZE ATTENDANCE
# ==========================================
with tab1:
    st.write("Upload your daily Google Forms CSV. The app will automatically check it against your saved Employees.")
    
    attendance_file = st.file_uploader("Upload Daily Log (Google Forms CSV)", type=["csv"])
    
    if attendance_file:
        try:
            df_log = pd.read_csv(attendance_file)
            df_log['Timestamp'] = pd.to_datetime(df_log['Timestamp'])
            
            # --- THE MIDNIGHT CROSSOVER FIX ---
            # Subtract 5 hours from the timestamp just to figure out what "Logical Date" it belongs to.
            # E.g., March 2nd at 01:00 AM is grouped with March 1st.
            df_log['LogicalDate'] = (df_log['Timestamp'] - pd.Timedelta(hours=5)).dt.date
            
            df_log['Employee ID'] = df_log['Employee ID'].astype(str).str.strip()
        except Exception as e:
            st.error(f"Error reading file. Error: {e}")
            st.stop()

        st.markdown("### 📅 Select a Date to Analyze")
        # We now sort by the Logical Date
        unique_dates = sorted(df_log['LogicalDate'].dropna().unique())
        
        latest_date_index = len(unique_dates) - 1
        selected_date = st.selectbox(
            "Choose a date from the dataset:", 
            unique_dates, 
            index=latest_date_index
        )

        if st.button("Run Analysis"):
            if df_employees.empty:
                st.warning("Your Employee list is empty! Please go to the 'Manage Employees' tab and add them first.")
            else:
                with st.spinner('Analyzing...'):
                    df_employees = load_employees()
                    df_employees['Employee ID'] = df_employees['Employee ID'].astype(str).str.strip()

                    # We filter the data based on the Logical Date, not the raw calendar date!
                    daily_data = df_log[df_log['LogicalDate'] == selected_date].copy()
                    
                    merged_data = pd.merge(daily_data, df_employees, on='Employee ID', how='inner')

                    statuses = []
                    matched_shifts = []

                    for index, row in merged_data.iterrows():
                        actual_time = row['Timestamp'].time()
                        action = str(row['Action']).strip().lower()
                        
                        raw_in_strs = [s.strip() for s in str(row['Scheduled Time In']).split('/') if s.strip()]
                        raw_out_strs = [s.strip() for s in str(row['Scheduled Time Out']).split('/') if s.strip()]
                        
                        try:
                            sched_ins = [parse_time_string(ts) for ts in raw_in_strs]
                            sched_outs = [parse_time_string(ts) for ts in raw_out_strs]
                        except ValueError:
                            statuses.append("Time Format Error")
                            matched_shifts.append("Error")
                            continue
                        
                        # --- MATH FOR LATE NIGHTS ---
                        dummy_date = datetime(2000, 1, 1)
                        dt_actual = datetime.combine(dummy_date, actual_time)
                        
                        # If actual time is early morning (past midnight), push it to "tomorrow" for the math
                        if actual_time.hour < 5:
                            dt_actual += timedelta(days=1)

                        if "clock in" in action:
                            if not sched_ins:
                                statuses.append("No Schedule")
                                matched_shifts.append("None")
                                continue
                                
                            closest_time_in = get_closest_scheduled_time(actual_time, sched_ins)
                            matched_shifts.append(closest_time_in.strftime("%H:%M:%S"))
                            
                            dt_sched_in = datetime.combine(dummy_date, closest_time_in)
                            if closest_time_in.hour >= 23:
                                dt_sched_in += timedelta(days=1)
                                
                            grace_period_in = dt_sched_in + timedelta(minutes=10)
                            
                            if dt_actual <= grace_period_in:
                                statuses.append("On Time In")
                            else:
                                statuses.append("Late In")
                        
                        elif "clock out" in action:
                            if not sched_outs:
                                statuses.append("No Schedule")
                                matched_shifts.append("None")
                                continue
                                
                            closest_time_out = get_closest_scheduled_time(actual_time, sched_outs)
                            matched_shifts.append(closest_time_out.strftime("%H:%M:%S"))
                            
                            dt_sched_out = datetime.combine(dummy_date, closest_time_out)
                            if closest_time_out.hour >= 23:
                                dt_sched_out += timedelta(days=1)
                                
                            grace_period_out = dt_sched_out + timedelta(minutes=30)
                            
                            if dt_actual < dt_sched_out:
                                statuses.append("Early Out")
                            elif dt_sched_out <= dt_actual <= grace_period_out:
                                statuses.append("On Time Out")
                            else:
                                statuses.append("Late Out")
                        else:
                            statuses.append("Unknown Action")
                            matched_shifts.append("N/A")

                    merged_data['Calculated Status'] = statuses
                    merged_data['Matched Shift'] = matched_shifts
                    
                    final_report = merged_data[['Timestamp', 'Email Address', 'Employee ID', 'Action', 'Matched Shift', 'Calculated Status']]
                    final_report = final_report.sort_values(by=['Employee ID', 'Timestamp'])
                    
                    st.success("Analysis Complete!")
                    
                    st.markdown("### 🧑‍💻 Individual Employee Breakdown")
                    st.write("Click on an employee to see their specific clock-in and clock-out logs.")
                    
                    grouped_data = final_report.groupby('Employee ID')
                    for emp_id, emp_data in grouped_data:
                        emp_email = emp_data['Email Address'].iloc[0]
                        with st.expander(f"Employee: {emp_id} ({emp_email})"):
                            clean_emp_data = emp_data[['Timestamp', 'Action', 'Matched Shift', 'Calculated Status']]
                            st.dataframe(clean_emp_data, use_container_width=True, hide_index=True)
                            
                    st.divider()
                    
                    st.markdown("### 📋 Full Sorted Report")
                    st.dataframe(final_report, use_container_width=True, hide_index=True)

                    csv_output = final_report.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Sorted Report (CSV)",
                        data=csv_output,
                        file_name=f"Attendance_Report_{selected_date}.csv",
                        mime='text/csv',
                    )
                    
