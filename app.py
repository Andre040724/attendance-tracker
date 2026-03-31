import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="Attendance Monitor", page_icon="⏱️", layout="wide")

# --- Database Setup ---
# This creates a local file to save your employees permanently
ROSTER_FILE = "master_roster.csv"

def load_roster():
    if os.path.exists(ROSTER_FILE):
        return pd.read_csv(ROSTER_FILE)
    else:
        # Create an empty template if the file doesn't exist yet
        return pd.DataFrame(columns=["Email Address", "Employee ID", "Scheduled Time In", "Scheduled Time Out"])

# Load the saved employees
df_roster = load_roster()

st.title("⏱️ Automated Attendance Tracker")

# --- Create Tabs for Navigation ---
tab1, tab2 = st.tabs(["📊 Analyze Attendance", "👥 Manage Master Roster"])


# ==========================================
# TAB 2: MANAGE MASTER ROSTER 
# ==========================================
with tab2:
    st.header("Add New Employee")
    st.write("Fill out the details below. The data will save automatically.")
    
    # Create an input form
    with st.form("add_employee_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            new_email = st.text_input("Email Address*")
            new_id = st.text_input("Employee ID*")
        with col2:
            new_time_in = st.text_input("Scheduled Time In (e.g., 08:00:00)*")
            new_time_out = st.text_input("Scheduled Time Out (e.g., 17:00:00)*")
        
        # The Add Employee Button
        submitted = st.form_submit_button("➕ Add Employee")
        
        if submitted:
            if new_email and new_id and new_time_in and new_time_out:
                # Group the new data
                new_employee = pd.DataFrame([{
                    "Email Address": new_email,
                    "Employee ID": new_id,
                    "Scheduled Time In": new_time_in,
                    "Scheduled Time Out": new_time_out
                }])
                
                # Add it to the existing roster and save the file
                df_roster = pd.concat([df_roster, new_employee], ignore_index=True)
                df_roster.to_csv(ROSTER_FILE, index=False)
                
                st.success(f"Successfully added {new_email} to the database!")
                st.rerun() # Refreshes the app instantly to show the new employee
            else:
                st.error("Please fill in all the input boxes.")

    st.divider()
    
    # Bonus Feature: An interactive table to edit/delete existing employees
    st.subheader("Current Employee Database")
    st.write("You can also double-click cells below to edit them, or select rows to delete them.")
    edited_roster = st.data_editor(df_roster, num_rows="dynamic", use_container_width=True)
    
    if st.button("💾 Save Database Changes"):
        edited_roster.to_csv(ROSTER_FILE, index=False)
        st.success("Database updated successfully!")


# ==========================================
# TAB 1: ANALYZE ATTENDANCE
# ==========================================
with tab1:
    st.write("Upload your daily Google Forms CSV. The app will automatically check it against your saved Master Roster.")
    
    # Notice we only need ONE file uploader now!
    attendance_file = st.file_uploader("Upload Daily Log (Google Forms CSV)", type=["csv"])
    
    if attendance_file:
        try:
            df_log = pd.read_csv(attendance_file)
            df_log['Timestamp'] = pd.to_datetime(df_log['Timestamp'])
            df_log['DateOnly'] = df_log['Timestamp'].dt.date
        except Exception as e:
            st.error(f"Error reading file. Error: {e}")
            st.stop()

        st.markdown("### 📅 Select a Date to Analyze")
        unique_dates = sorted(df_log['DateOnly'].dropna().unique())
        selected_date = st.selectbox("Choose a date from the dataset:", unique_dates)

        if st.button("Run Analysis"):
            if df_roster.empty:
                st.warning("Your Master Roster is empty! Please go to the 'Manage Master Roster' tab and add employees first.")
            else:
                with st.spinner('Analyzing...'):
                    daily_data = df_log[df_log['DateOnly'] == selected_date].copy()
                    
                    # Compare the daily log to the saved roster
                    merged_data = pd.merge(daily_data, df_roster, on='Email Address', how='left')

                    statuses = []

                    for index, row in merged_data.iterrows():
                        # If the email from the form isn't in your roster
                        if pd.isna(row['Scheduled Time In']):
                            statuses.append("Not in Roster")
                            continue

                        actual_time = row['Timestamp'].time()
                        try:
                            scheduled_in = datetime.strptime(str(row['Scheduled Time In']).strip(), "%H:%M:%S").time()
                            scheduled_out = datetime.strptime(str(row['Scheduled Time Out']).strip(), "%H:%M:%S").time()
                        except ValueError:
                            statuses.append("Time Format Error")
                            continue
                        
                        # Math setup for early/late calculations
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

                    # Apply calculations
                    merged_data['Calculated Status'] = statuses
                    
                    # Clean up the output table
                    final_report = merged_data[['Timestamp', 'Email Address', 'Employee ID_x', 'Action', 'Scheduled Time In', 'Scheduled Time Out', 'Calculated Status']]
                    final_report = final_report.rename(columns={'Employee ID_x': 'Employee ID'})
                    
                    st.success("Analysis Complete!")
                    st.dataframe(final_report, use_container_width=True)

                    # Create download link
                    csv_output = final_report.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Daily Report (CSV)",
                        data=csv_output,
                        file_name=f"Attendance_Report_{selected_date}.csv",
                        mime='text/csv',
                    )
                    
