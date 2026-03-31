import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="Attendance Monitor", page_icon="⏱️", layout="wide")
st.title("⏱️ Automated Attendance Tracker")
st.write("Upload your daily Google Forms CSV and your Master Roster to analyze attendance.")

# --- File Uploaders ---
col1, col2 = st.columns(2)
with col1:
    attendance_file = st.file_uploader("Upload Daily Log (Google Forms CSV)", type=["csv"])
with col2:
    roster_file = st.file_uploader("Upload Master Roster (CSV)", type=["csv"])

if attendance_file and roster_file:
    # 1. Load Data
    try:
        df_log = pd.read_csv(attendance_file)
        df_roster = pd.read_csv(roster_file)
        
        # Ensure Timestamps are correctly formatted
        df_log['Timestamp'] = pd.to_datetime(df_log['Timestamp'])
        # Extract the Date part for filtering
        df_log['DateOnly'] = df_log['Timestamp'].dt.date
    except Exception as e:
        st.error(f"Error reading files. Ensure they are valid CSVs. Error: {e}")
        st.stop()

    # 2. Date Filtering
    st.markdown("### 📅 Select a Date to Analyze")
    unique_dates = sorted(df_log['DateOnly'].dropna().unique())
    selected_date = st.selectbox("Choose a date from the dataset:", unique_dates)

    if st.button("Run Analysis"):
        with st.spinner('Analyzing...'):
            # Filter the attendance log based on selected date
            daily_data = df_log[df_log['DateOnly'] == selected_date].copy()
            
            # Merge with Master Roster based on Email
            merged_data = pd.merge(daily_data, df_roster, on='Email Address', how='left')

            # We'll build a list to hold the calculated statuses
            statuses = []

            for index, row in merged_data.iterrows():
                # If they aren't in the master roster, flag them
                if pd.isna(row['Scheduled Time In']):
                    statuses.append("Not in Roster")
                    continue

                # Get actual time (HH:MM:SS) and scheduled times
                actual_time = row['Timestamp'].time()
                scheduled_in = datetime.strptime(str(row['Scheduled Time In']), "%H:%M:%S").time()
                scheduled_out = datetime.strptime(str(row['Scheduled Time Out']), "%H:%M:%S").time()
                
                # Convert scheduled times to full datetime for easier math (add 10 min grace period)
                dummy_date = datetime(2000, 1, 1) # Just a placeholder date to do math
                dt_actual = datetime.combine(dummy_date, actual_time)
                dt_sched_in = datetime.combine(dummy_date, scheduled_in)
                dt_sched_out = datetime.combine(dummy_date, scheduled_out)
                
                # Grace period calculations
                grace_period_in = dt_sched_in + timedelta(minutes=10)
                grace_period_out = dt_sched_out + timedelta(minutes=30) # Giving 30 mins grace for late out

                # Logic Engine
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

            # 3. Output Final Data
            merged_data['Calculated Status'] = statuses
            
            # Keep only the important columns for the final report
            final_report = merged_data[['Timestamp', 'Email Address', 'Employee ID', 'Action', 'Scheduled Time In', 'Scheduled Time Out', 'Calculated Status']]
            
            st.success("Analysis Complete!")
            st.dataframe(final_report, use_container_width=True)

            # --- Download Button ---
            csv_output = final_report.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Daily Report (CSV)",
                data=csv_output,
                file_name=f"Attendance_Report_{selected_date}.csv",
                mime='text/csv',
            )