import streamlit as st
import pandas as pd
from database import get_db_connection
from datetime import datetime, timedelta, date
import plotly.express as px
from email_service import send_email
import json

def show_alerts():
    st.header("🚨 Inventory Alerts")
    
    st.info("""
    **Alert System monitors:**
    - Items nearing expiration dates
    - Low stock situations (configurable thresholds)
    - Automatic email notifications to relevant users
    - Alert history and acknowledgment tracking
    """)
    
    tab1, tab2, tab3, tab4 = st.tabs(["🚨 Active Alerts", "📊 Alert Dashboard", "⚙️ Settings", "📧 Notifications"])
    
    with tab1:
        show_active_alerts()
    
    with tab2:
        show_alert_dashboard()
    
    with tab3:
        show_alert_settings()
    
    with tab4:
        show_notification_settings()

def show_active_alerts():
    """Display current active alerts"""
    st.subheader("🚨 Active Alerts")
    
    # Check for alerts button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🔄 Refresh Alerts", type="secondary"):
            st.rerun()
    
    with col2:
        auto_refresh = st.checkbox("Auto-refresh alerts", value=False)
    
    if auto_refresh:
        # Auto refresh every 30 seconds when enabled
        import time
        time.sleep(1)
        st.rerun()
    
    # Get current alerts
    alerts = get_current_alerts()
    
    if not alerts:
        st.success("✅ No active alerts! All inventory is within normal parameters.")
        return
    
    # Filter and display alerts
    alert_types = st.multiselect(
        "Filter by Alert Type:",
        options=["Expiring Soon", "Expired", "Low Stock", "Out of Stock"],
        default=["Expiring Soon", "Expired", "Low Stock", "Out of Stock"],
        key="alert_type_filter"
    )
    
    filtered_alerts = [alert for alert in alerts if alert['alert_type'] in alert_types]
    
    if not filtered_alerts:
        st.info("No alerts match the selected filters.")
        return
    
    # Display alerts by severity
    critical_alerts = [a for a in filtered_alerts if a['severity'] == 'Critical']
    warning_alerts = [a for a in filtered_alerts if a['severity'] == 'Warning']
    info_alerts = [a for a in filtered_alerts if a['severity'] == 'Info']
    
    # Critical alerts
    if critical_alerts:
        st.error(f"🔥 **{len(critical_alerts)} Critical Alerts**")
        display_alert_table(critical_alerts, "critical")
    
    # Warning alerts
    if warning_alerts:
        st.warning(f"⚠️ **{len(warning_alerts)} Warning Alerts**")
        display_alert_table(warning_alerts, "warning")
    
    # Info alerts
    if info_alerts:
        st.info(f"ℹ️ **{len(info_alerts)} Info Alerts**")
        display_alert_table(info_alerts, "info")
    
    # Bulk actions
    st.subheader("📋 Bulk Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📧 Send Alert Summary", type="secondary"):
            send_alert_summary_email(filtered_alerts)
            st.success("Alert summary email sent!")
    
    with col2:
        if st.button("✅ Acknowledge All", type="secondary"):
            acknowledge_alerts([alert['id'] for alert in filtered_alerts])
            st.success("All alerts acknowledged!")
            st.rerun()
    
    with col3:
        selected_alerts = st.multiselect(
            "Select alerts to acknowledge:",
            options=[(alert['id'], f"{alert['alert_type']}: {alert['item_name']}") for alert in filtered_alerts],
            format_func=lambda x: x[1]
        )
        
        if selected_alerts and st.button("✅ Acknowledge Selected"):
            acknowledge_alerts([alert[0] for alert in selected_alerts])
            st.success(f"Acknowledged {len(selected_alerts)} alerts!")
            st.rerun()

def get_current_alerts():
    """Get current active alerts from database"""
    conn = get_db_connection()
    if not conn:
        return []
    
    alerts = []
    
    try:
        cur = conn.cursor()
        
        # Get alert settings
        settings = get_alert_settings()
        
        # Check for expiring items
        expiry_alerts = check_expiry_alerts(cur, settings)
        alerts.extend(expiry_alerts)
        
        # Check for stock alerts
        stock_alerts = check_stock_alerts(cur, settings)
        alerts.extend(stock_alerts)
        
        cur.close()
        conn.close()
        
        return alerts
        
    except Exception as e:
        st.error(f"Error checking alerts: {str(e)}")
        if conn:
            conn.close()
        return []

def check_expiry_alerts(cur, settings):
    """Check for expiration alerts"""
    alerts = []
    
    try:
        # Get expiry thresholds from settings
        warning_days = settings.get('expiry_warning_days', 30)
        critical_days = settings.get('expiry_critical_days', 7)
        
        warning_date = datetime.now().date() + timedelta(days=warning_days)
        critical_date = datetime.now().date() + timedelta(days=critical_days)
        
        # Find expired items
        cur.execute("""
            SELECT id, patient_name, drug_item_name, expiration_date, inventory_number, location
            FROM inventory 
            WHERE expiration_date < CURRENT_DATE 
            AND (acknowledged_alerts IS NULL OR NOT (acknowledged_alerts ? 'expired'))
        """)
        
        expired_items = cur.fetchall()
        
        for item in expired_items:
            days_expired = (datetime.now().date() - item[2]).days
            alerts.append({
                'id': f"expired_{item[0]}",
                'record_id': item[0],
                'alert_type': 'Expired',
                'severity': 'Critical',
                'patient_name': item[1],
                'item_name': item[2],
                'expiry_date': item[2],
                'inventory_number': item[3],
                'location': item[4],
                'message': f"Item expired {days_expired} days ago",
                'days_until_expiry': -days_expired,
                'created_at': datetime.now()
            })
        
        # Find items expiring soon (critical)
        cur.execute("""
            SELECT id, patient_name, drug_item_name, expiration_date, inventory_number, location
            FROM inventory 
            WHERE expiration_date <= %s AND expiration_date >= CURRENT_DATE
            AND (acknowledged_alerts IS NULL OR NOT (acknowledged_alerts ? 'expiring_critical'))
        """, (critical_date,))
        
        critical_expiry = cur.fetchall()
        
        for item in critical_expiry:
            days_until_expiry = (item[3] - datetime.now().date()).days
            alerts.append({
                'id': f"expiring_critical_{item[0]}",
                'record_id': item[0],
                'alert_type': 'Expiring Soon',
                'severity': 'Critical',
                'patient_name': item[1],
                'item_name': item[2],
                'expiry_date': item[3],
                'inventory_number': item[4],
                'location': item[5],
                'message': f"Expires in {days_until_expiry} days",
                'days_until_expiry': days_until_expiry,
                'created_at': datetime.now()
            })
        
        # Find items expiring soon (warning)
        cur.execute("""
            SELECT id, patient_name, drug_item_name, expiration_date, inventory_number, location
            FROM inventory 
            WHERE expiration_date <= %s AND expiration_date > %s
            AND (acknowledged_alerts IS NULL OR NOT (acknowledged_alerts ? 'expiring_warning'))
        """, (warning_date, critical_date))
        
        warning_expiry = cur.fetchall()
        
        for item in warning_expiry:
            days_until_expiry = (item[3] - datetime.now().date()).days
            alerts.append({
                'id': f"expiring_warning_{item[0]}",
                'record_id': item[0],
                'alert_type': 'Expiring Soon',
                'severity': 'Warning',
                'patient_name': item[1],
                'item_name': item[2],
                'expiry_date': item[3],
                'inventory_number': item[4],
                'location': item[5],
                'message': f"Expires in {days_until_expiry} days",
                'days_until_expiry': days_until_expiry,
                'created_at': datetime.now()
            })
        
        return alerts
        
    except Exception as e:
        st.error(f"Error checking expiry alerts: {str(e)}")
        return []

def check_stock_alerts(cur, settings):
    """Check for stock level alerts"""
    alerts = []
    
    try:
        # For now, we'll implement basic stock alerts based on inventory count
        # In a full system, this would track actual inventory quantities
        
        # Get low stock threshold from settings
        low_stock_threshold = settings.get('low_stock_threshold', 5)
        
        # Count items by drug name and location
        cur.execute("""
            SELECT drug_item_name, location, COUNT(*) as stock_count
            FROM inventory 
            WHERE expiration_date >= CURRENT_DATE  -- Only count non-expired items
            GROUP BY drug_item_name, location
            HAVING COUNT(*) <= %s
        """, (low_stock_threshold,))
        
        low_stock_items = cur.fetchall()
        
        for item in low_stock_items:
            drug_name, location, stock_count = item
            
            severity = 'Critical' if stock_count == 0 else 'Warning' if stock_count <= 2 else 'Info'
            alert_type = 'Out of Stock' if stock_count == 0 else 'Low Stock'
            
            alerts.append({
                'id': f"stock_{drug_name}_{location}".replace(' ', '_'),
                'record_id': None,
                'alert_type': alert_type,
                'severity': severity,
                'patient_name': 'Multiple Patients',
                'item_name': drug_name,
                'expiry_date': None,
                'inventory_number': 'Multiple',
                'location': location,
                'message': f"Only {stock_count} items remaining" if stock_count > 0 else "Out of stock",
                'stock_count': stock_count,
                'created_at': datetime.now()
            })
        
        return alerts
        
    except Exception as e:
        st.error(f"Error checking stock alerts: {str(e)}")
        return []

def display_alert_table(alerts, severity_class):
    """Display alerts in a table format"""
    if not alerts:
        return
    
    # Create DataFrame
    display_data = []
    for alert in alerts:
        display_data.append({
            'Type': alert['alert_type'],
            'Item': alert['item_name'],
            'Patient': alert['patient_name'],
            'Location': alert['location'],
            'Inventory #': alert['inventory_number'],
            'Message': alert['message'],
            'Expiry Date': alert['expiry_date'].strftime('%Y-%m-%d') if alert['expiry_date'] else 'N/A',
            'Action': '⚠️ Needs Attention'
        })
    
    df = pd.DataFrame(display_data)
    
    # Color coding based on severity
    if severity_class == "critical":
        styled_df = df.style.apply(lambda x: ['background-color: #f8d7da'] * len(x), axis=1)
    elif severity_class == "warning":
        styled_df = df.style.apply(lambda x: ['background-color: #fff3cd'] * len(x), axis=1)
    else:
        styled_df = df.style.apply(lambda x: ['background-color: #d1ecf1'] * len(x), axis=1)
    
    st.dataframe(styled_df, use_container_width=True)

def show_alert_dashboard():
    """Show alert analytics and trends"""
    st.subheader("📊 Alert Analytics")
    
    # Date range for analytics
    col1, col2 = st.columns(2)
    with col1:
        analytics_from = st.date_input("Analytics From", value=date.today() - timedelta(days=30), key="alerts_analytics_from")
    with col2:
        analytics_to = st.date_input("Analytics To", value=date.today(), key="alerts_analytics_to")
    
    # Get current alerts for summary
    current_alerts = get_current_alerts()
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    critical_count = len([a for a in current_alerts if a['severity'] == 'Critical'])
    warning_count = len([a for a in current_alerts if a['severity'] == 'Warning'])
    expiry_count = len([a for a in current_alerts if 'Expir' in a['alert_type']])
    stock_count = len([a for a in current_alerts if 'Stock' in a['alert_type']])
    
    with col1:
        st.metric("🔥 Critical Alerts", critical_count)
    with col2:
        st.metric("⚠️ Warning Alerts", warning_count)
    with col3:
        st.metric("📅 Expiry Alerts", expiry_count)
    with col4:
        st.metric("📦 Stock Alerts", stock_count)
    
    if current_alerts:
        # Alert distribution
        col1, col2 = st.columns(2)
        
        with col1:
            # By alert type
            alert_types = [alert['alert_type'] for alert in current_alerts]
            alert_type_counts = pd.Series(alert_types).value_counts()
            
            fig = px.pie(
                values=alert_type_counts.values,
                names=alert_type_counts.index,
                title="Alerts by Type"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # By severity
            severity_counts = [alert['severity'] for alert in current_alerts]
            severity_counts = pd.Series(severity_counts).value_counts()
            
            fig = px.bar(
                x=severity_counts.index,
                y=severity_counts.values,
                title="Alerts by Severity",
                color=severity_counts.index,
                color_discrete_map={
                    'Critical': '#dc3545',
                    'Warning': '#ffc107',
                    'Info': '#17a2b8'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Expiry timeline
        expiry_alerts = [a for a in current_alerts if 'days_until_expiry' in a]
        if expiry_alerts:
            st.subheader("📅 Expiry Timeline")
            
            expiry_df = pd.DataFrame([{
                'Item': alert['item_name'],
                'Patient': alert['patient_name'],
                'Days Until Expiry': alert['days_until_expiry'],
                'Severity': alert['severity']
            } for alert in expiry_alerts])
            
            fig = px.scatter(
                expiry_df,
                x='Days Until Expiry',
                y='Item',
                color='Severity',
                title="Items by Days Until Expiry",
                color_discrete_map={
                    'Critical': '#dc3545',
                    'Warning': '#ffc107',
                    'Info': '#17a2b8'
                }
            )
            st.plotly_chart(fig, use_container_width=True)

def show_alert_settings():
    """Show and manage alert settings"""
    st.subheader("⚙️ Alert Configuration")
    
    # Load current settings
    settings = get_alert_settings()
    
    # Expiry alert settings
    st.write("**📅 Expiry Alert Settings**")
    col1, col2 = st.columns(2)
    
    with col1:
        expiry_warning_days = st.number_input(
            "Warning days before expiry",
            min_value=1,
            max_value=365,
            value=settings.get('expiry_warning_days', 30),
            help="Send warning alerts this many days before expiration"
        )
    
    with col2:
        expiry_critical_days = st.number_input(
            "Critical days before expiry",
            min_value=1,
            max_value=30,
            value=settings.get('expiry_critical_days', 7),
            help="Send critical alerts this many days before expiration"
        )
    
    # Stock alert settings
    st.write("**📦 Stock Alert Settings**")
    col1, col2 = st.columns(2)
    
    with col1:
        low_stock_threshold = st.number_input(
            "Low stock threshold",
            min_value=1,
            max_value=100,
            value=settings.get('low_stock_threshold', 5),
            help="Alert when stock count falls to or below this number"
        )
    
    with col2:
        enable_stock_alerts = st.checkbox(
            "Enable stock alerts",
            value=settings.get('enable_stock_alerts', True),
            help="Enable/disable stock level monitoring"
        )
    
    # Notification settings
    st.write("**📧 Notification Settings**")
    
    enable_email_notifications = st.checkbox(
        "Enable email notifications",
        value=settings.get('enable_email_notifications', False),
        help="Send email notifications for new alerts"
    )
    
    # Initialize default values
    notification_recipients = settings.get('notification_recipients', '')
    notification_frequency = settings.get('notification_frequency', 'Daily')
    
    if enable_email_notifications:
        notification_recipients = st.text_area(
            "Notification recipients",
            value=notification_recipients,
            help="Email addresses separated by commas"
        )
        
        notification_frequency = st.selectbox(
            "Notification frequency",
            options=['Immediate', 'Daily', 'Weekly'],
            index=['Immediate', 'Daily', 'Weekly'].index(notification_frequency)
        )
    
    # Save settings
    if st.button("💾 Save Settings", type="primary"):
        new_settings = {
            'expiry_warning_days': expiry_warning_days,
            'expiry_critical_days': expiry_critical_days,
            'low_stock_threshold': low_stock_threshold,
            'enable_stock_alerts': enable_stock_alerts,
            'enable_email_notifications': enable_email_notifications,
        }
        
        if enable_email_notifications:
            new_settings.update({
                'notification_recipients': notification_recipients,
                'notification_frequency': notification_frequency
            })
        
        if save_alert_settings(new_settings):
            st.success("Settings saved successfully!")
            st.rerun()

def show_notification_settings():
    """Show notification history and settings"""
    st.subheader("📧 Notification Management")
    
    # Manual notification controls
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📧 Send Test Email", type="secondary"):
            send_test_notification()
            st.success("Test email sent!")
    
    with col2:
        if st.button("📊 Send Alert Summary", type="secondary"):
            alerts = get_current_alerts()
            send_alert_summary_email(alerts)
            st.success("Alert summary sent!")
    
    # Notification history (if implemented)
    st.subheader("📋 Recent Notifications")
    st.info("Notification history feature coming soon...")

def get_alert_settings():
    """Get alert settings from database or return defaults"""
    conn = get_db_connection()
    if not conn:
        return get_default_alert_settings()
    
    try:
        cur = conn.cursor()
        
        # Create alert_settings table if it doesn't exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alert_settings (
                id SERIAL PRIMARY KEY,
                settings JSONB NOT NULL,
                updated_by VARCHAR(100),
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Get latest settings
        cur.execute("""
            SELECT settings FROM alert_settings 
            ORDER BY updated_at DESC 
            LIMIT 1
        """)
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result:
            return result[0]
        else:
            return get_default_alert_settings()
            
    except Exception as e:
        st.error(f"Error loading alert settings: {str(e)}")
        if conn:
            conn.close()
        return get_default_alert_settings()

def get_default_alert_settings():
    """Return default alert settings"""
    return {
        'expiry_warning_days': 30,
        'expiry_critical_days': 7,
        'low_stock_threshold': 5,
        'enable_stock_alerts': True,
        'enable_email_notifications': False,
        'notification_recipients': '',
        'notification_frequency': 'Daily'
    }

def save_alert_settings(settings):
    """Save alert settings to database"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        # Insert new settings
        cur.execute("""
            INSERT INTO alert_settings (settings, updated_by)
            VALUES (%s, %s)
        """, (json.dumps(settings), st.session_state.username))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        st.error(f"Error saving alert settings: {str(e)}")
        if conn:
            conn.rollback()
            conn.close()
        return False

def acknowledge_alerts(alert_ids):
    """Acknowledge alerts by marking them in the database"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        # Update acknowledged alerts in inventory records
        for alert_id in alert_ids:
            if '_' in alert_id:
                alert_type, record_id = alert_id.split('_', 1)
                if record_id.isdigit():
                    # Update inventory record with acknowledged alert
                    acknowledge_key = f"{alert_type}_acknowledged"
                    cur.execute("""
                        UPDATE inventory 
                        SET acknowledged_alerts = 
                            COALESCE(acknowledged_alerts, '{}'::jsonb) || %s::jsonb
                        WHERE id = %s
                    """, (json.dumps({acknowledge_key: datetime.now().isoformat()}), int(record_id)))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        st.error(f"Error acknowledging alerts: {str(e)}")
        if conn:
            conn.rollback()
            conn.close()
        return False

def send_alert_summary_email(alerts):
    """Send alert summary via email"""
    try:
        settings = get_alert_settings()
        if not settings.get('enable_email_notifications') or not settings.get('notification_recipients'):
            st.warning("Email notifications not configured. Please check alert settings.")
            return
        
        recipients = [email.strip() for email in settings['notification_recipients'].split(',')]
        
        # Create email content
        subject = f"Inventory Alert Summary - {len(alerts)} Active Alerts"
        
        if not alerts:
            content = "Good news! There are currently no active inventory alerts."
        else:
            critical_alerts = [a for a in alerts if a['severity'] == 'Critical']
            warning_alerts = [a for a in alerts if a['severity'] == 'Warning']
            
            content = f"""
            Inventory Alert Summary - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            Total Active Alerts: {len(alerts)}
            - Critical: {len(critical_alerts)}
            - Warnings: {len(warning_alerts)}
            
            Critical Alerts:
            """
            
            for alert in critical_alerts[:10]:  # Limit to first 10
                content += f"- {alert['alert_type']}: {alert['item_name']} ({alert['patient_name']}) - {alert['message']}\n"
            
            if len(critical_alerts) > 10:
                content += f"... and {len(critical_alerts) - 10} more critical alerts\n"
            
            content += "\nWarning Alerts:\n"
            
            for alert in warning_alerts[:10]:  # Limit to first 10
                content += f"- {alert['alert_type']}: {alert['item_name']} ({alert['patient_name']}) - {alert['message']}\n"
            
            if len(warning_alerts) > 10:
                content += f"... and {len(warning_alerts) - 10} more warnings\n"
            
            content += "\nPlease review the inventory system for detailed information."
        
        # Send to each recipient
        for recipient in recipients:
            send_email(recipient, "inventory-alerts@system.com", subject, content)
            
    except Exception as e:
        st.error(f"Error sending alert summary: {str(e)}")

def send_test_notification():
    """Send a test notification email"""
    try:
        settings = get_alert_settings()
        if not settings.get('enable_email_notifications') or not settings.get('notification_recipients'):
            st.warning("Email notifications not configured. Please check alert settings.")
            return
        
        recipients = [email.strip() for email in settings['notification_recipients'].split(',')]
        
        subject = "Inventory Alert System - Test Notification"
        content = f"""
        This is a test notification from the Inventory Alert System.
        
        Test sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        Sent by: {st.session_state.username}
        
        If you receive this email, the alert notification system is working correctly.
        """
        
        for recipient in recipients:
            send_email(recipient, "inventory-alerts@system.com", subject, content)
            
    except Exception as e:
        st.error(f"Error sending test notification: {str(e)}")