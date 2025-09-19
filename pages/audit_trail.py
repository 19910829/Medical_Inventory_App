import streamlit as st
import pandas as pd
from database import get_db_connection
import json
from datetime import datetime, timedelta, date
import plotly.express as px
import plotly.graph_objects as go

def show_audit_trail():
    st.header("📋 Audit Trail")
    
    st.info("""
    **Audit Trail tracks:**
    - All inventory record changes (create, update, delete)
    - Who made each change and when
    - Before and after values for updates
    - Complete history for compliance and tracking
    """)
    
    tab1, tab2, tab3 = st.tabs(["🔍 View Changes", "📊 Analytics", "⚙️ Settings"])
    
    with tab1:
        show_audit_log()
    
    with tab2:
        show_audit_analytics()
    
    with tab3:
        show_audit_settings()

def show_audit_log():
    """Display audit log with filtering and search"""
    st.subheader("🔍 Inventory Changes")
    
    # Filters
    with st.expander("🎛️ Filters", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Date range filter
            date_from = st.date_input(
                "From Date", 
                value=date.today() - timedelta(days=30),
                key="audit_date_from"
            )
            date_to = st.date_input(
                "To Date", 
                value=date.today(),
                key="audit_date_to"
            )
        
        with col2:
            # Action filter
            action_filter = st.selectbox(
                "Action Type",
                ["All", "INSERT", "UPDATE", "DELETE"],
                key="audit_action_filter"
            )
            
            # User filter
            user_filter = st.text_input(
                "Changed By (User)",
                placeholder="Enter username",
                key="audit_user_filter"
            )
        
        with col3:
            # Record ID filter
            record_id_filter = st.number_input(
                "Record ID",
                min_value=0,
                value=0,
                key="audit_record_filter",
                help="Filter by specific inventory record ID (0 = all records)"
            )
            
            # Table filter
            table_filter = st.selectbox(
                "Table",
                ["All", "inventory", "documents"],
                key="audit_table_filter"
            )
        
        with col4:
            # Search in changes
            search_text = st.text_input(
                "Search in Changes",
                placeholder="Search patient name, drug name, etc.",
                key="audit_search_text"
            )
            
            # Show details
            show_details = st.checkbox(
                "Show Change Details", 
                value=False,
                key="audit_show_details"
            )
    
    # Get audit data
    audit_data = get_audit_data(
        date_from=date_from,
        date_to=date_to,
        action_filter=action_filter,
        user_filter=user_filter,
        record_id_filter=record_id_filter if record_id_filter > 0 else None,
        table_filter=table_filter,
        search_text=search_text
    )
    
    if not audit_data:
        st.info("No audit records found matching the selected criteria.")
        return
    
    # Display results
    st.subheader(f"📊 Found {len(audit_data)} Changes")
    
    # Create display DataFrame
    display_data = []
    for record in audit_data:
        display_record = {
            'ID': record['id'],
            'Date/Time': record['changed_at'].strftime('%Y-%m-%d %H:%M:%S'),
            'Action': record['action'],
            'Table': record['table_name'],
            'Record ID': record['record_id'],
            'Changed By': record['changed_by'] or 'System',
            'Summary': generate_change_summary(record)
        }
        
        if show_details:
            display_record['Old Values'] = format_json_values(record['old_values'])
            display_record['New Values'] = format_json_values(record['new_values'])
        
        display_data.append(display_record)
    
    df = pd.DataFrame(display_data)
    
    # Color code by action type
    def highlight_actions(row):
        if row['Action'] == 'INSERT':
            return ['background-color: #d4edda'] * len(row)  # Green
        elif row['Action'] == 'UPDATE':
            return ['background-color: #fff3cd'] * len(row)  # Yellow
        elif row['Action'] == 'DELETE':
            return ['background-color: #f8d7da'] * len(row)  # Red
        else:
            return [''] * len(row)
    
    # Display the dataframe
    if len(df) > 0:
        # Add download button
        col1, col2 = st.columns([1, 3])
        with col1:
            csv_data = df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name=f"audit_trail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        # Display table
        styled_df = df.style.apply(highlight_actions, axis=1)
        st.dataframe(styled_df, use_container_width=True, height=600)
        
        # Show detailed view for selected records
        if show_details and len(audit_data) > 0:
            st.subheader("🔍 Detailed Change View")
            
            selected_id = st.selectbox(
                "Select record to view details:",
                options=[f"ID {record['id']} - {record['action']} on {record['changed_at'].strftime('%Y-%m-%d %H:%M')}" for record in audit_data],
                key="audit_detail_select"
            )
            
            if selected_id:
                record_id = int(selected_id.split(' ')[1])
                selected_record = next(r for r in audit_data if r['id'] == record_id)
                show_detailed_change(selected_record)

def get_audit_data(date_from, date_to, action_filter, user_filter, record_id_filter, table_filter, search_text):
    """Get audit data from database with filters"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        
        # Build query with filters
        query = """
            SELECT id, table_name, record_id, action, old_values, new_values, 
                   changed_by, changed_at
            FROM audit_log 
            WHERE changed_at >= %s AND changed_at <= %s
        """
        params = [date_from, date_to + timedelta(days=1)]  # Include full day
        
        if action_filter != "All":
            query += " AND action = %s"
            params.append(action_filter)
        
        if user_filter:
            query += " AND changed_by ILIKE %s"
            params.append(f"%{user_filter}%")
        
        if record_id_filter:
            query += " AND record_id = %s"
            params.append(record_id_filter)
        
        if table_filter != "All":
            query += " AND table_name = %s"
            params.append(table_filter)
        
        # Add search in JSON values
        if search_text:
            query += " AND (old_values::text ILIKE %s OR new_values::text ILIKE %s)"
            params.extend([f"%{search_text}%", f"%{search_text}%"])
        
        query += " ORDER BY changed_at DESC LIMIT 1000"
        
        cur.execute(query, params)
        records = cur.fetchall()
        
        # Convert to list of dicts
        columns = ['id', 'table_name', 'record_id', 'action', 'old_values', 'new_values', 'changed_by', 'changed_at']
        audit_data = [dict(zip(columns, record)) for record in records]
        
        cur.close()
        conn.close()
        
        return audit_data
        
    except Exception as e:
        st.error(f"Error fetching audit data: {str(e)}")
        if conn:
            conn.close()
        return []

def generate_change_summary(record):
    """Generate a human-readable summary of the change"""
    action = record['action']
    table_name = record['table_name']
    
    if action == 'INSERT':
        if record['new_values']:
            new_data = record['new_values']
            if isinstance(new_data, str):
                try:
                    new_data = json.loads(new_data)
                except:
                    pass
            
            if isinstance(new_data, dict):
                patient_name = new_data.get('patient_name', 'Unknown')
                drug_name = new_data.get('drug_item_name', 'Unknown item')
                return f"Created record for {patient_name} - {drug_name}"
        
        return f"Created new {table_name} record"
    
    elif action == 'UPDATE':
        changes = []
        if record['old_values'] and record['new_values']:
            try:
                old_data = record['old_values'] if isinstance(record['old_values'], dict) else json.loads(record['old_values'])
                new_data = record['new_values'] if isinstance(record['new_values'], dict) else json.loads(record['new_values'])
                
                # Find changed fields
                for key in new_data:
                    if key in old_data and old_data[key] != new_data[key]:
                        if key in ['patient_name', 'drug_item_name', 'purchase_price', 'expiration_date']:
                            changes.append(f"{key}: {old_data[key]} → {new_data[key]}")
                
                if changes:
                    patient_name = new_data.get('patient_name', 'Record')
                    return f"Updated {patient_name}: {', '.join(changes[:3])}"
                    
            except Exception:
                pass
        
        return f"Updated {table_name} record"
    
    elif action == 'DELETE':
        if record['old_values']:
            try:
                old_data = record['old_values'] if isinstance(record['old_values'], dict) else json.loads(record['old_values'])
                patient_name = old_data.get('patient_name', 'Unknown')
                drug_name = old_data.get('drug_item_name', 'Unknown item')
                return f"Deleted record for {patient_name} - {drug_name}"
            except:
                pass
        
        return f"Deleted {table_name} record"
    
    return f"{action} on {table_name}"

def format_json_values(json_data):
    """Format JSON data for display"""
    if not json_data:
        return "N/A"
    
    try:
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data
        
        # Format key fields for readability
        formatted_lines = []
        key_fields = ['patient_name', 'drug_item_name', 'purchase_price', 'expiration_date', 'inventory_number']
        
        for field in key_fields:
            if field in data and data[field] is not None:
                formatted_lines.append(f"{field}: {data[field]}")
        
        # Add other fields if not too many
        other_fields = [k for k in data.keys() if k not in key_fields and data[k] is not None]
        if len(other_fields) <= 5:
            for field in other_fields[:5]:
                formatted_lines.append(f"{field}: {data[field]}")
        elif len(other_fields) > 5:
            formatted_lines.append(f"... and {len(other_fields)} more fields")
        
        return "\n".join(formatted_lines)
        
    except Exception:
        return str(json_data)[:200] + "..." if len(str(json_data)) > 200 else str(json_data)

def show_detailed_change(record):
    """Show detailed view of a specific change"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Change Information:**")
        st.write(f"• **Action:** {record['action']}")
        st.write(f"• **Table:** {record['table_name']}")
        st.write(f"• **Record ID:** {record['record_id']}")
        st.write(f"• **Changed By:** {record['changed_by'] or 'System'}")
        st.write(f"• **Date/Time:** {record['changed_at'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    with col2:
        st.write("**Summary:**")
        st.write(generate_change_summary(record))
    
    if record['action'] in ['UPDATE', 'DELETE'] and record['old_values']:
        st.subheader("📋 Before (Old Values)")
        try:
            old_data = record['old_values'] if isinstance(record['old_values'], dict) else json.loads(record['old_values'])
            old_df = pd.DataFrame([(k, v) for k, v in old_data.items()], columns=['Field', 'Value'])
            st.dataframe(old_df, use_container_width=True, hide_index=True)
        except Exception:
            st.text(str(record['old_values']))
    
    if record['action'] in ['INSERT', 'UPDATE'] and record['new_values']:
        st.subheader("📋 After (New Values)")
        try:
            new_data = record['new_values'] if isinstance(record['new_values'], dict) else json.loads(record['new_values'])
            new_df = pd.DataFrame([(k, v) for k, v in new_data.items()], columns=['Field', 'Value'])
            st.dataframe(new_df, use_container_width=True, hide_index=True)
        except Exception:
            st.text(str(record['new_values']))

def show_audit_analytics():
    """Show audit analytics and statistics"""
    st.subheader("📊 Audit Analytics")
    
    # Date range for analytics
    col1, col2 = st.columns(2)
    with col1:
        analytics_from = st.date_input("Analytics From", value=date.today() - timedelta(days=30), key="analytics_from")
    with col2:
        analytics_to = st.date_input("Analytics To", value=date.today(), key="analytics_to")
    
    # Get analytics data
    analytics_data = get_audit_analytics_data(analytics_from, analytics_to)
    
    if not analytics_data:
        st.info("No audit data available for the selected period.")
        return
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_changes = len(analytics_data)
    inserts = len([r for r in analytics_data if r['action'] == 'INSERT'])
    updates = len([r for r in analytics_data if r['action'] == 'UPDATE'])
    deletes = len([r for r in analytics_data if r['action'] == 'DELETE'])
    
    with col1:
        st.metric("Total Changes", total_changes)
    with col2:
        st.metric("Records Created", inserts, delta=f"{inserts/total_changes*100:.1f}%" if total_changes > 0 else "0%")
    with col3:
        st.metric("Records Updated", updates, delta=f"{updates/total_changes*100:.1f}%" if total_changes > 0 else "0%")
    with col4:
        st.metric("Records Deleted", deletes, delta=f"{deletes/total_changes*100:.1f}%" if total_changes > 0 else "0%")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Activity by action type
        action_counts = {'INSERT': inserts, 'UPDATE': updates, 'DELETE': deletes}
        if any(action_counts.values()):
            fig = px.pie(
                values=list(action_counts.values()),
                names=list(action_counts.keys()),
                title="Changes by Action Type"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Activity by user
        user_activity = {}
        for record in analytics_data:
            user = record['changed_by'] or 'System'
            user_activity[user] = user_activity.get(user, 0) + 1
        
        if user_activity:
            users = list(user_activity.keys())
            counts = list(user_activity.values())
            
            fig = px.bar(
                x=counts,
                y=users,
                orientation='h',
                title="Activity by User",
                labels={'x': 'Number of Changes', 'y': 'User'}
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Daily activity timeline
    st.subheader("📈 Daily Activity")
    df = pd.DataFrame(analytics_data)
    if not df.empty:
        df['date'] = pd.to_datetime(df['changed_at']).dt.date
        daily_counts = df.groupby(['date', 'action']).size().unstack(fill_value=0)
        
        fig = px.line(
            daily_counts,
            title="Daily Changes Over Time",
            labels={'index': 'Date', 'value': 'Number of Changes'}
        )
        st.plotly_chart(fig, use_container_width=True)

def get_audit_analytics_data(date_from, date_to):
    """Get audit data for analytics"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        
        query = """
            SELECT action, changed_by, changed_at
            FROM audit_log 
            WHERE changed_at >= %s AND changed_at <= %s
            ORDER BY changed_at DESC
        """
        
        cur.execute(query, [date_from, date_to + timedelta(days=1)])
        records = cur.fetchall()
        
        columns = ['action', 'changed_by', 'changed_at']
        data = [dict(zip(columns, record)) for record in records]
        
        cur.close()
        conn.close()
        
        return data
        
    except Exception as e:
        st.error(f"Error fetching analytics data: {str(e)}")
        if conn:
            conn.close()
        return []

def show_audit_settings():
    """Show audit trail settings and management"""
    st.subheader("⚙️ Audit Trail Settings")
    
    # Audit status
    st.write("**Current Audit Status:**")
    
    conn = get_db_connection()
    if not conn:
        st.error("Cannot connect to database")
        return
    
    try:
        cur = conn.cursor()
        
        # Check if audit log table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'audit_log'
            );
        """)
        audit_table_exists = cur.fetchone()[0]
        
        if audit_table_exists:
            st.success("✅ Audit logging is active")
            
            # Get audit statistics
            cur.execute("SELECT COUNT(*) FROM audit_log")
            total_records = cur.fetchone()[0]
            
            cur.execute("SELECT MIN(changed_at), MAX(changed_at) FROM audit_log")
            date_range = cur.fetchone()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Audit Records", total_records)
            with col2:
                if date_range[0] and date_range[1]:
                    days_tracked = (date_range[1] - date_range[0]).days
                    st.metric("Days Tracked", days_tracked)
            
            # Maintenance options
            st.subheader("🧹 Maintenance")
            
            # Archive old records
            st.write("**Archive Old Records:**")
            archive_days = st.number_input("Archive records older than (days):", min_value=30, value=365)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗄️ Archive Old Records"):
                    archive_count = archive_old_records(archive_days)
                    if archive_count >= 0:
                        st.success(f"Archived {archive_count} old records")
            
            with col2:
                if st.button("🧮 Vacuum Audit Table"):
                    if vacuum_audit_table():
                        st.success("Audit table maintenance completed")
        
        else:
            st.warning("⚠️ Audit table not found - audit logging may not be active")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        st.error(f"Error checking audit status: {str(e)}")
        if conn:
            conn.close()

def archive_old_records(days):
    """Archive old audit records"""
    conn = get_db_connection()
    if not conn:
        return -1
    
    try:
        cur = conn.cursor()
        
        # Create archive table if it doesn't exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log_archive (
                LIKE audit_log INCLUDING ALL
            )
        """)
        
        # Move old records to archive
        cutoff_date = datetime.now() - timedelta(days=days)
        
        cur.execute("""
            INSERT INTO audit_log_archive 
            SELECT * FROM audit_log 
            WHERE changed_at < %s
        """, (cutoff_date,))
        
        archive_count = cur.rowcount
        
        # Delete archived records from main table
        cur.execute("DELETE FROM audit_log WHERE changed_at < %s", (cutoff_date,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return archive_count
        
    except Exception as e:
        st.error(f"Error archiving records: {str(e)}")
        if conn:
            conn.rollback()
            conn.close()
        return -1

def vacuum_audit_table():
    """Perform maintenance on audit table"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        # Vacuum the audit log table
        cur.execute("VACUUM ANALYZE audit_log")
        
        conn.commit()
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        st.error(f"Error performing maintenance: {str(e)}")
        if conn:
            conn.close()
        return False