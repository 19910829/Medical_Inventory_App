import streamlit as st
from database import get_inventory_stats, get_db_connection
import pandas as pd
import plotly.express as px

def show_employee_dashboard():
    st.header("📊 Employee Dashboard")
    
    # Get statistics
    stats = get_inventory_stats()
    
    # Key metrics for employees
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Total Inventory Items",
            value=stats.get('total_records', 0)
        )
    
    with col2:
        st.metric(
            label="Items Added This Week",
            value=stats.get('recent_additions', 0)
        )
    
    with col3:
        st.metric(
            label="Items Expiring Soon",
            value=stats.get('expiring_soon', 0),
            delta="Next 30 days"
        )
    
    st.divider()
    
    # My recent activity
    st.subheader("📝 My Recent Activity")
    show_user_activity()
    
    st.divider()
    
    # Quick actions
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔍 Quick Search")
        show_quick_search()
    
    with col2:
        st.subheader("📈 Inventory Overview")
        show_inventory_overview()

def show_user_activity():
    """Show current user's recent activity"""
    username = st.session_state.username
    
    conn = get_db_connection()
    if not conn:
        st.error("Database connection failed")
        return
    
    cur = conn.cursor()
    
    cur.execute("""
        SELECT patient_name, drug_item_name, inventory_number, created_at
        FROM inventory
        WHERE created_by = %s
        ORDER BY created_at DESC
        LIMIT 10
    """, (username,))
    
    user_records = cur.fetchall()
    cur.close()
    conn.close()
    
    if user_records:
        df = pd.DataFrame(user_records, columns=[
            'Patient Name', 'Drug/Item', 'Inventory #', 'Created'
        ])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No records created by you yet")

def show_quick_search():
    """Quick search functionality"""
    search_term = st.text_input("Search inventory...", placeholder="Patient name, drug name, or inventory number")
    
    if search_term:
        conn = get_db_connection()
        if not conn:
            st.error("Database connection failed")
            return
        
        cur = conn.cursor()
        
        cur.execute("""
            SELECT patient_name, drug_item_name, inventory_number, date_of_service
            FROM inventory
            WHERE patient_name ILIKE %s 
               OR drug_item_name ILIKE %s 
               OR inventory_number ILIKE %s
            ORDER BY created_at DESC
            LIMIT 5
        """, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
        
        search_results = cur.fetchall()
        cur.close()
        conn.close()
        
        if search_results:
            df = pd.DataFrame(search_results, columns=[
                'Patient Name', 'Drug/Item', 'Inventory #', 'Service Date'
            ])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No matching records found")

def show_inventory_overview():
    """Show inventory overview chart"""
    conn = get_db_connection()
    if not conn:
        st.error("Database connection failed")
        return
    
    cur = conn.cursor()
    
    # Get inventory by type
    cur.execute("""
        SELECT inventory_type, COUNT(*) as count
        FROM inventory
        WHERE inventory_type IS NOT NULL
        GROUP BY inventory_type
        ORDER BY count DESC
        LIMIT 10
    """)
    
    type_data = cur.fetchall()
    cur.close()
    conn.close()
    
    if type_data:
        df = pd.DataFrame(type_data, columns=['Type', 'Count'])
        fig = px.bar(df, x='Type', y='Count', title="Items by Type")
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No inventory type data available")
