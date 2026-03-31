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
        # Template only uses Employee ID and times now
        return pd.DataFrame(columns=["Employee ID", "Scheduled Time In", "Scheduled Time Out"])

df_employees = load_employees()

st.title("⏱️ Automated Attendance Tracker")

# --- Create Tabs for Navigation ---
tab1, tab2 = st.tabs(["📊 Analyze Attendance", "👥 Manage Employees"])


# ==========================================
# TAB 2: MANAGE EMPLOYEES 
# ==========================================
with tab2:
    st.header("Add New Employee")
    st.write("Fill out the details below to add an employee to the system.")
    
    with st.form("add_employee_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            new_id = st.text_input("Employee ID*")
        with col2:
            new_time_in = st.text_input("Scheduled Time In (e.g., 08:00:00)*")
        with col3:
            new_time_out = st.text_input("Scheduled Time Out (e.g., 17:00:00)*")
        
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
    st.write("Double-click cells to edit them, or select rows to delete them.")
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
            df_log['DateOnly'] = df_log['Timestamp'].dt.date
            # Clean Employee ID in the daily log to ensure a perfect match
            df_log['Employee ID'] = df_log['Employee ID'].astype(str).str.strip()
        except Exception as e:
            st.error(f"Error reading file. Error: {e}")
            st.stop()

        st.markdown("### 📅 Select a Date to Analyze")
        unique_dates = sorted(df_log['DateOnly'].dropna().unique())
        
        # Calculate the index of the latest date (the last item in the sorted list)
        latest_date_index = len(unique_dates) - 1
        
        # Set the default selected option to the latest date
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
                    # Refresh employee list and clean IDs for merging
                    df_employees = load_employees()
                    df_employees['Employee ID'] = df_employees['Employee ID'].astype(str).str.strip()

                    daily_data = df_log[df_log['DateOnly'] == selected_date].copy()
                    
                    # Merge on Employee ID instead of Email
                    merged_data = pd.merge(daily_data, df_employees, on='Employee ID', how='left')

                    statuses = []

                    for index, row in merged_data.iterrows():
                        if pd.isna(row['Scheduled Time In']):
                            statuses.append("Not in Employee List")
                            continue

                        actual_time = row['Timestamp'].time()
                        try:
                            scheduled_in = datetime.strptime(str(row['Scheduled Time In']).strip(), "%H:%M:%S").time()
                            scheduled_out = datetime.strptime(str(row['Scheduled Time Out']).strip(), "%H:%M:%S").time()
                        except ValueError:
                            statuses.append("Time Format Error")
                            continue
                        
                        dummy_date = datetime(2000, 1, 1)
                        dt_actual = datetime.combine(dummy_date, actual_time)
                        dt_sched_in = datetime.combine(dummy_date, scheduled_in)
                        dt_sched_out = datetime.combine(dummy_date, scheduled_out)
                        
                        grace_period_in = dt_sched_in + timedelta(minutes=10)
                        grace_period_out = dt_sched_out + timedelta(minutes=30)

                        action = str(row['Action']).strip().lower()

                        if "clock in" in action:
                            if dt_actual < dt_sched_in:
                                statuses.append("Early In")
                            elif dt_sched_in <= dt_actual <= grace_period_in:
                                statuses.append("On Time In")
                            else:
                                statuses.append("Late In")
                        
                        elif "clock out" in action:
                            if dt_actual < dt_sched_out:
                                statuses.append("Early Out")
                            elif dt_sched_out <= dt_actual <= grace_period_out:
                                statuses.append("On Time Out")
                            else:
                                statuses.append("Late Out")
                        else:
                            statuses.append("Unknown Action")

                    merged_data['Calculated Status'] = statuses
                    
                    # The Email Address is still pulled from the daily log for the final report
                    final_report = merged_data[['Timestamp', 'Email Address', 'Employee ID', 'Action', 'Scheduled Time In', 'Scheduled Time Out', 'Calculated Status']]
                    
                    st.success("Analysis Complete!")
                    st.dataframe(final_report, use_container_width=True)

                    csv_output = final_report.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Daily Report (CSV)",
                        data=csv_output,
                        file_name=f"Attendance_Report_{selected_date}.csv",
                        mime='text/csv',
                    )
                    
