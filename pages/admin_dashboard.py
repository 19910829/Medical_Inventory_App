import streamlit as st
from database import get_inventory_stats, get_db_connection
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

def show_admin_dashboard():
    st.header("🔧 Admin Dashboard")
    
    # Get statistics
    stats = get_inventory_stats()
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Records",
            value=stats.get('total_records', 0),
            delta=f"+{stats.get('recent_additions', 0)} this week"
        )
    
    with col2:
        st.metric(
            label="Expiring Soon",
            value=stats.get('expiring_soon', 0),
            delta="Next 30 days"
        )
    
    with col3:
        st.metric(
            label="Recent Additions",
            value=stats.get('recent_additions', 0),
            delta="Last 7 days"
        )
    
    with col4:
        st.metric(
            label="Item Types",
            value=len(stats.get('by_type', [])),
            delta="Categories"
        )
    
    st.divider()
    
    # Charts section
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Inventory by Type")
        if stats.get('by_type'):
            df_types = pd.DataFrame(stats['by_type'])
            fig = px.pie(df_types, values='count', names='inventory_type', 
                        title="Distribution by Inventory Type")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for inventory types")
    
    with col2:
        st.subheader("📈 Recent Activity")
        show_recent_activity_chart()
    
    st.divider()
    
    # System health and alerts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🚨 System Alerts")
        show_system_alerts()
    
    with col2:
        st.subheader("📋 Recent Records")
        show_recent_records()

def show_recent_activity_chart():
    """Show recent activity chart"""
    conn = get_db_connection()
    if not conn:
        st.error("Database connection failed")
        return
    
    cur = conn.cursor()
    
    # Get daily activity for last 30 days
    cur.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM inventory
        WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(created_at)
        ORDER BY date
    """)
    
    activity_data = cur.fetchall()
    cur.close()
    conn.close()
    
    if activity_data:
        df = pd.DataFrame(activity_data, columns=['Date', 'Count'])
        fig = px.line(df, x='Date', y='Count', title="Daily Inventory Additions")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No recent activity data available")

def show_system_alerts():
    """Show system alerts and warnings"""
    alerts = []
    
    conn = get_db_connection()
    if not conn:
        st.error("Database connection failed")
        return
    
    cur = conn.cursor()
    
    # Check for expiring items
    cur.execute("""
        SELECT COUNT(*) as count
        FROM inventory
        WHERE expiration_date <= CURRENT_DATE + INTERVAL '30 days'
        AND expiration_date > CURRENT_DATE
    """)
    expiring_count = cur.fetchone()[0]
    
    if expiring_count > 0:
        alerts.append({
            'type': 'warning',
            'message': f"{expiring_count} items expiring in next 30 days"
        })
    
    # Check for expired items
    cur.execute("""
        SELECT COUNT(*) as count
        FROM inventory
        WHERE expiration_date < CURRENT_DATE
    """)
    expired_count = cur.fetchone()[0]
    
    if expired_count > 0:
        alerts.append({
            'type': 'error',
            'message': f"{expired_count} items have expired"
        })
    
    # Check for missing inventory numbers
    cur.execute("""
        SELECT COUNT(*) as count
        FROM inventory
        WHERE inventory_number IS NULL OR inventory_number = ''
    """)
    missing_inv_count = cur.fetchone()[0]
    
    if missing_inv_count > 0:
        alerts.append({
            'type': 'info',
            'message': f"{missing_inv_count} items missing inventory numbers"
        })
    
    cur.close()
    conn.close()
    
    if alerts:
        for alert in alerts:
            if alert['type'] == 'error':
                st.error(alert['message'])
            elif alert['type'] == 'warning':
                st.warning(alert['message'])
            else:
                st.info(alert['message'])
    else:
        st.success("No system alerts")

def show_recent_records():
    """Show recent inventory records"""
    conn = get_db_connection()
    if not conn:
        st.error("Database connection failed")
        return
    
    cur = conn.cursor()
    
    cur.execute("""
        SELECT patient_name, drug_item_name, inventory_number, created_at
        FROM inventory
        ORDER BY created_at DESC
        LIMIT 10
    """)
    
    recent_records = cur.fetchall()
    cur.close()
    conn.close()
    
    if recent_records:
        df = pd.DataFrame(recent_records, columns=[
            'Patient Name', 'Drug/Item', 'Inventory #', 'Created'
        ])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No recent records found")
