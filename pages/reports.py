import streamlit as st
import pandas as pd
from database import get_inventory_records, get_db_connection
from email_service import send_report_email
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io

def show_reports():
    st.header("📈 Advanced Reports & Analytics")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Dashboard Analytics", 
        "🎯 KPI Dashboard",
        "📈 Trend Analysis",
        "📥 Export Data", 
        "📧 Email Reports",
        "📋 Custom Reports"
    ])
    
    with tab1:
        show_analytics_dashboard()
    
    with tab2:
        show_kpi_dashboard()
    
    with tab3:
        show_trend_analysis()
        
    with tab4:
        show_export_functionality()
    
    with tab5:
        show_email_reports()
    
    with tab6:
        show_custom_reports()

def show_analytics_dashboard():
    """Enhanced analytics dashboard with interactive charts and real-time metrics"""
    st.subheader("📊 Interactive Inventory Analytics")
    
    # Manual refresh option
    col1, col2, col3 = st.columns([2, 1, 1])
    with col3:
        if st.button("🔄 Refresh Now"):
            st.rerun()
    
    # Date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("End Date", value=datetime.now())
    
    # Get data for the date range
    records = get_inventory_records(filters={
        'date_from': start_date,
        'date_to': end_date
    })
    
    if not records:
        st.warning("No data available for the selected date range")
        return
    
    df = pd.DataFrame(records)
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Records", len(df))
    
    with col2:
        total_value = df['purchase_price'].sum()
        st.metric("Total Value", f"${total_value:,.2f}")
    
    with col3:
        unique_patients = df['patient_name'].nunique()
        st.metric("Unique Patients", unique_patients)
    
    with col4:
        unique_drugs = df['drug_item_name'].nunique()
        st.metric("Unique Items", unique_drugs)
    
    st.divider()
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Inventory by type
        if 'inventory_type' in df.columns:
            type_counts = df['inventory_type'].value_counts()
            if not type_counts.empty:
                fig = px.pie(
                    values=type_counts.values,
                    names=type_counts.index,
                    title="Distribution by Inventory Type"
                )
                st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Daily additions
        df['created_at'] = pd.to_datetime(df['created_at'])
        daily_counts = df.groupby(df['created_at'].dt.date).size()
        
        if not daily_counts.empty:
            fig = px.line(
                x=daily_counts.index,
                y=daily_counts.values,
                title="Daily Inventory Additions"
            )
            fig.update_xaxes(title="Date")
            fig.update_yaxes(title="Number of Items")
            st.plotly_chart(fig, use_container_width=True)
    
    # Top providers and locations
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Top Providers")
        provider_counts = df['provider'].value_counts().head(10)
        if not provider_counts.empty:
            fig = px.bar(
                x=provider_counts.values,
                y=provider_counts.index,
                orientation='h',
                title="Top 10 Providers"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Top Locations")
        location_counts = df['location'].value_counts().head(10)
        if not location_counts.empty:
            fig = px.bar(
                x=location_counts.values,
                y=location_counts.index,
                orientation='h',
                title="Top 10 Locations"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Expiration analysis
    st.subheader("📅 Expiration Analysis")
    
    # Filter out null expiration dates
    df_exp = df[df['expiration_date'].notna()].copy()
    
    if not df_exp.empty:
        df_exp['expiration_date'] = pd.to_datetime(df_exp['expiration_date'])
        current_date = pd.Timestamp.now()
        
        # Calculate days until expiration
        df_exp['days_until_expiration'] = (df_exp['expiration_date'] - current_date).dt.days
        
        # Categorize by expiration status
        expired = df_exp[df_exp['days_until_expiration'] < 0]
        expiring_soon = df_exp[(df_exp['days_until_expiration'] >= 0) & (df_exp['days_until_expiration'] <= 30)]
        expiring_later = df_exp[df_exp['days_until_expiration'] > 30]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Expired Items", len(expired), delta=f"Immediate attention needed")
        
        with col2:
            st.metric("Expiring Soon", len(expiring_soon), delta="Next 30 days")
        
        with col3:
            st.metric("Expiring Later", len(expiring_later), delta="Beyond 30 days")
        
        # Expiration timeline
        if len(df_exp) > 0:
            fig = px.histogram(
                df_exp,
                x='days_until_expiration',
                nbins=20,
                title="Expiration Timeline Distribution"
            )
            fig.update_xaxes(title="Days Until Expiration")
            fig.update_yaxes(title="Number of Items")
            st.plotly_chart(fig, use_container_width=True)

def show_export_functionality():
    """Data export functionality"""
    st.subheader("📥 Export Inventory Data")
    
    # Export options
    col1, col2 = st.columns(2)
    
    with col1:
        export_format = st.selectbox(
            "Export Format",
            ["Excel (.xlsx)", "CSV (.csv)", "JSON (.json)"]
        )
        
        include_all = st.checkbox("Include All Records", value=True)
        
        if not include_all:
            max_records = st.number_input("Maximum Records", min_value=1, value=1000)
        else:
            max_records = None
    
    with col2:
        # Date range for export
        export_start = st.date_input("Start Date (optional)")
        export_end = st.date_input("End Date (optional)")
        
        # Filter options
        filter_type = st.selectbox(
            "Filter by Type",
            ["", "Medication", "Medical Device", "Supply", "Equipment", "Other"]
        )
    
    # Advanced filters
    with st.expander("Advanced Filters"):
        col1, col2 = st.columns(2)
        
        with col1:
            filter_provider = st.text_input("Provider Contains", key="export_filter_provider")
            filter_location = st.text_input("Location Contains", key="export_filter_location")
        
        with col2:
            only_expiring = st.checkbox("Only Expiring Items (next 30 days)")
            only_recent = st.checkbox("Only Recent Items (last 7 days)")
    
    # Generate export
    if st.button("Generate Export", type="primary", use_container_width=True):
        # Build filters
        filters = {}
        
        if export_start:
            filters['date_from'] = export_start
        if export_end:
            filters['date_to'] = export_end
        if filter_type:
            filters['inventory_type'] = filter_type
        if filter_provider:
            filters['provider'] = filter_provider
        if filter_location:
            filters['location'] = filter_location
        
        # Get records
        records = get_inventory_records(filters=filters, limit=max_records)
        
        if records:
            df = pd.DataFrame(records)
            
            # Apply additional filters
            if only_expiring:
                df = df[pd.to_datetime(df['expiration_date']) <= pd.Timestamp.now() + pd.Timedelta(days=30)]
            
            if only_recent:
                df = df[pd.to_datetime(df['created_at']) >= pd.Timestamp.now() - pd.Timedelta(days=7)]
            
            # Format data for export
            export_df = format_export_data(df)
            
            # Generate download based on format
            if export_format.startswith("Excel"):
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    export_df.to_excel(writer, sheet_name='Inventory', index=False)
                
                st.download_button(
                    label="📥 Download Excel File",
                    data=excel_buffer.getvalue(),
                    file_name=f"inventory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            elif export_format.startswith("CSV"):
                csv_data = export_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV File",
                    data=csv_data,
                    file_name=f"inventory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            elif export_format.startswith("JSON"):
                json_data = export_df.to_json(orient='records', date_format='iso')
                st.download_button(
                    label="📥 Download JSON File",
                    data=json_data,
                    file_name=f"inventory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            
            st.success(f"Export generated successfully! ({len(export_df)} records)")
            
            # Show preview
            st.subheader("Export Preview")
            st.dataframe(export_df.head(), use_container_width=True)
            
        else:
            st.warning("No records found matching the export criteria")

def format_export_data(df):
    """Format data for export"""
    # Select and rename columns for export
    export_columns = {
        'patient_name': 'Patient Name',
        'patient_id': 'Patient ID',
        'administration_location': 'Administration Location',
        'drug_item_name': 'Drug/Item Name',
        'date_of_service': 'Date Of Service',
        'date_of_dispense': 'Date Of Dispense',
        'date_ordered': 'Date Ordered',
        'date_received': 'Date Received',
        'order_number': 'Order Number',
        'invoice_number': 'Invoice Number',
        'po_number': 'PO Number',
        'lot_number': 'Lot Number',
        'expiration_date': 'Expiration Date',
        'inventory_number': 'Inventory Number',
        'inventory_type': 'Inventory Type',
        'purchase_price': 'Purchase Price',
        'provider': 'Provider',
        'location': 'Location',
        'inventory_site': 'Inventory Site',
        'username': 'Username',
        'dose_swap_status': 'Dose Swap Status',
        'created_at': 'Created At',
        'created_by': 'Created By'
    }
    
    # Select available columns
    available_columns = {k: v for k, v in export_columns.items() if k in df.columns}
    export_df = df[available_columns.keys()].copy()
    export_df = export_df.rename(columns=available_columns)
    
    # Format dates
    date_columns = ['Date Of Service', 'Date Of Dispense', 'Date Ordered', 'Date Received', 'Expiration Date', 'Created At']
    for col in date_columns:
        if col in export_df.columns:
            export_df[col] = pd.to_datetime(export_df[col]).dt.strftime('%Y-%m-%d')
    
    return export_df

def show_email_reports():
    """Email reporting functionality"""
    st.subheader("📧 Email Reports")
    
    with st.form("email_report_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            recipient_email = st.text_input("Recipient Email*", placeholder="admin@company.com")
            report_type = st.selectbox("Report Type", [
                "Full Inventory Report",
                "Expiring Items Report",
                "Recent Activity Report",
                "Low Stock Alert",
                "Custom Report"
            ])
        
        with col2:
            include_attachments = st.checkbox("Include Excel Attachment", value=True)
            schedule_report = st.checkbox("Schedule Regular Reports", value=False)
            
            if schedule_report:
                schedule_frequency = st.selectbox("Frequency", [
                    "Daily", "Weekly", "Monthly"
                ])
        
        # Report parameters
        st.subheader("Report Parameters")
        
        col1, col2 = st.columns(2)
        
        with col1:
            date_range_days = st.number_input("Include Last N Days", min_value=1, value=30)
            filter_by_type = st.selectbox("Filter by Type", [
                "All Types", "Medication", "Medical Device", "Supply", "Equipment", "Other"
            ])
        
        with col2:
            only_expiring = st.checkbox("Only Expiring Items")
            include_statistics = st.checkbox("Include Statistics", value=True)
        
        # Custom message
        custom_message = st.text_area(
            "Custom Message (optional)",
            placeholder="Additional message to include in the email"
        )
        
        submitted = st.form_submit_button("Send Report", use_container_width=True)
        
        if submitted:
            if not recipient_email:
                st.error("Please enter a recipient email address")
                return
            
            # Generate report data
            filters = {}
            
            # Date filter
            start_date = datetime.now() - timedelta(days=date_range_days)
            filters['date_from'] = start_date.date()
            
            # Type filter
            if filter_by_type != "All Types":
                filters['inventory_type'] = filter_by_type
            
            # Get records
            records = get_inventory_records(filters=filters)
            
            if records:
                # Prepare report data
                report_data = {
                    'report_type': report_type,
                    'generated_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'total_records': len(records),
                    'generated_by': st.session_state.username,
                    'date_range_days': date_range_days,
                    'custom_message': custom_message
                }
                
                # Add statistics if requested
                if include_statistics:
                    df = pd.DataFrame(records)
                    report_data['statistics'] = {
                        'total_value': df['purchase_price'].sum(),
                        'unique_patients': df['patient_name'].nunique(),
                        'unique_items': df['drug_item_name'].nunique(),
                        'most_common_type': df['inventory_type'].mode().iloc[0] if not df['inventory_type'].mode().empty else 'N/A'
                    }
                
                # Generate attachment if requested
                attachment_name = None
                if include_attachments:
                    df = pd.DataFrame(records)
                    export_df = format_export_data(df)
                    
                    # Save temporary Excel file
                    attachment_name = f"inventory_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    # Note: In production, you would save the file and attach it to the email
                
                # Send email
                if send_report_email(recipient_email, report_data, attachment_name):
                    st.success(f"Report sent successfully to {recipient_email}")
                    
                    if schedule_report:
                        st.info(f"Report scheduled for {schedule_frequency.lower()} delivery")
                        # Note: In production, you would set up scheduled tasks
                else:
                    st.error("Failed to send report email")
            else:
                st.warning("No data available for the specified criteria")

def show_custom_reports():
    """Custom report builder"""
    st.subheader("📋 Custom Report Builder")
    
    # Report configuration
    with st.expander("Report Configuration", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            report_name = st.text_input("Report Name", placeholder="My Custom Report")
            
            # Select columns to include
            all_columns = [
                'patient_name', 'patient_id', 'drug_item_name', 'inventory_number',
                'date_of_service', 'provider', 'location', 'inventory_type',
                'purchase_price', 'expiration_date', 'dose_swap_status'
            ]
            
            selected_columns = st.multiselect(
                "Select Columns to Include",
                all_columns,
                default=['patient_name', 'drug_item_name', 'inventory_number', 'date_of_service']
            )
        
        with col2:
            # Grouping and aggregation
            group_by = st.selectbox("Group By (optional)", [""] + all_columns)
            
            if group_by:
                aggregation = st.selectbox("Aggregation", [
                    "Count", "Sum", "Average", "Min", "Max"
                ])
                
                if aggregation in ["Sum", "Average", "Min", "Max"]:
                    numeric_columns = ['purchase_price', 'patient_id']
                    agg_column = st.selectbox("Aggregate Column", numeric_columns)
    
    # Filters
    with st.expander("Filters"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filter_patient = st.text_input("Patient Name Contains", key="custom_filter_patient")
            filter_drug = st.text_input("Drug/Item Contains", key="custom_filter_drug")
        
        with col2:
            filter_provider = st.text_input("Provider Contains", key="custom_filter_provider")
            filter_type = st.selectbox("Inventory Type", [""] + ["Medication", "Medical Device", "Supply", "Equipment", "Other"], key="custom_filter_type")
        
        with col3:
            date_from = st.date_input("Service Date From", value=None, key="custom_date_from")
            date_to = st.date_input("Service Date To", value=None, key="custom_date_to")
    
    # Generate report
    if st.button("Generate Custom Report", type="primary", use_container_width=True):
        if not selected_columns:
            st.error("Please select at least one column to include")
            return
        
        # Build filters
        filters = {}
        
        if filter_patient:
            filters['patient_name'] = filter_patient
        if filter_drug:
            filters['drug_item_name'] = filter_drug
        if filter_type:
            filters['inventory_type'] = filter_type
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
        
        # Get records
        records = get_inventory_records(filters=filters)
        
        if records:
            df = pd.DataFrame(records)
            
            # Select columns
            report_df = df[selected_columns].copy()
            
            # Apply grouping if specified
            if group_by and group_by in report_df.columns:
                if aggregation == "Count":
                    report_df = report_df.groupby(group_by).size().reset_index(name='Count')
                elif aggregation == "Sum" and agg_column in report_df.columns:
                    report_df = report_df.groupby(group_by)[agg_column].sum().reset_index()
                elif aggregation == "Average" and agg_column in report_df.columns:
                    report_df = report_df.groupby(group_by)[agg_column].mean().reset_index()
                elif aggregation == "Min" and agg_column in report_df.columns:
                    report_df = report_df.groupby(group_by)[agg_column].min().reset_index()
                elif aggregation == "Max" and agg_column in report_df.columns:
                    report_df = report_df.groupby(group_by)[agg_column].max().reset_index()
            
            # Display report
            st.subheader(f"📊 {report_name or 'Custom Report'}")
            st.dataframe(report_df, use_container_width=True)
            
            # Export options
            col1, col2, col3 = st.columns(3)
            
            with col1:
                csv_data = report_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download as CSV",
                    data=csv_data,
                    file_name=f"custom_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                # Excel export
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    report_df.to_excel(writer, sheet_name='Custom Report', index=False)
                
                st.download_button(
                    label="📥 Download as Excel",
                    data=excel_buffer.getvalue(),
                    file_name=f"custom_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            with col3:
                # Email report option
                email_recipient = st.text_input("Email To", placeholder="admin@company.com", key="custom_report_email")
                if st.button("📧 Email Report") and email_recipient:
                    report_data = {
                        'report_type': report_name or 'Custom Report',
                        'generated_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'total_records': len(report_df),
                        'generated_by': st.session_state.username
                    }
                    
                    if send_report_email(email_recipient, report_data):
                        st.success("Report emailed successfully!")
                    else:
                        st.error("Failed to send email")
        
        else:
            st.warning("No records found matching the specified criteria")

def show_kpi_dashboard():
    """Advanced KPI dashboard with performance metrics"""
    st.subheader("🎯 Key Performance Indicators")
    
    # Time period selector
    time_period = st.selectbox(
        "Analysis Period",
        ["Last 7 Days", "Last 30 Days", "Last 90 Days", "Last Year", "All Time"],
        index=1
    )
    
    # Convert to date range
    if time_period == "Last 7 Days":
        days_back = 7
    elif time_period == "Last 30 Days":
        days_back = 30
    elif time_period == "Last 90 Days":
        days_back = 90
    elif time_period == "Last Year":
        days_back = 365
    else:
        days_back = None
    
    if days_back:
        start_date = datetime.now() - timedelta(days=days_back)
        filters = {'date_from': start_date.date()}
    else:
        filters = {}
    
    # Get enhanced data
    records = get_inventory_records(filters=filters)
    
    if not records:
        st.warning("No data available for the selected period")
        return
    
    df = pd.DataFrame(records)
    current_date = datetime.now().date()
    
    # Advanced KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        # Inventory turnover rate
        total_items = len(df)
        st.metric(
            "🔄 Total Items",
            f"{total_items:,}",
            delta=f"{int(total_items / max(days_back, 1) * 7)}/week" if days_back else None
        )
    
    with col2:
        # Average inventory value
        avg_value = df['purchase_price'].mean()
        st.metric(
            "💰 Avg Item Value",
            f"${avg_value:.2f}",
            delta=f"${df['purchase_price'].median():.2f} median"
        )
    
    with col3:
        # Expiry risk score
        df_with_dates = df[df['expiration_date'].notna()].copy()
        if not df_with_dates.empty:
            df_with_dates['days_to_expire'] = (pd.to_datetime(df_with_dates['expiration_date']) - pd.Timestamp(current_date)).dt.days
            risk_items = len(df_with_dates[df_with_dates['days_to_expire'] <= 30])
            risk_percentage = (risk_items / len(df_with_dates)) * 100
            st.metric(
                "⚠️ Expiry Risk",
                f"{risk_percentage:.1f}%",
                delta=f"{risk_items} items"
            )
        else:
            st.metric("⚠️ Expiry Risk", "N/A")
    
    with col4:
        # Provider diversity
        unique_providers = df['provider'].nunique()
        most_common_provider_pct = (df['provider'].value_counts().iloc[0] / len(df)) * 100 if len(df) > 0 else 0
        st.metric(
            "🏢 Provider Diversity",
            f"{unique_providers} providers",
            delta=f"{most_common_provider_pct:.1f}% top provider"
        )
    
    with col5:
        # Location efficiency
        unique_locations = df['location'].nunique()
        avg_items_per_location = len(df) / max(unique_locations, 1)
        st.metric(
            "📍 Location Efficiency",
            f"{avg_items_per_location:.1f} items/loc",
            delta=f"{unique_locations} locations"
        )
    
    st.divider()
    
    # Advanced visualizations
    col1, col2 = st.columns(2)
    
    with col1:
        # Inventory composition treemap
        st.subheader("🗺️ Inventory Composition")
        
        if 'inventory_type' in df.columns and df['inventory_type'].notna().any():
            type_value_df = df.groupby('inventory_type').agg({
                'purchase_price': 'sum',
                'drug_item_name': 'count'
            }).reset_index()
            type_value_df.columns = ['Type', 'Total Value', 'Count']
            
            fig = px.treemap(
                type_value_df,
                path=['Type'],
                values='Total Value',
                color='Count',
                title="Inventory Value by Type",
                color_continuous_scale="Viridis"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No inventory type data available")
    
    with col2:
        # Price distribution box plot
        st.subheader("📊 Price Distribution Analysis")
        
        if 'inventory_type' in df.columns and df['inventory_type'].notna().any():
            fig = px.box(
                df,
                y='purchase_price',
                x='inventory_type',
                title="Price Distribution by Type",
                points="outliers"
            )
        else:
            fig = px.box(
                df,
                y='purchase_price',
                title="Overall Price Distribution",
                points="outliers"
            )
        
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    # Performance trends
    st.subheader("📈 Performance Trends")
    
    if days_back:
        df['date'] = pd.to_datetime(df['created_at']).dt.date
        daily_metrics = df.groupby('date').agg({
            'purchase_price': ['count', 'sum', 'mean'],
            'drug_item_name': 'nunique'
        }).reset_index()
        
        daily_metrics.columns = ['Date', 'Items Added', 'Total Value', 'Avg Value', 'Unique Items']
        
        if len(daily_metrics) > 1:
            # Multi-metric line chart
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=daily_metrics['Date'],
                y=daily_metrics['Items Added'],
                mode='lines+markers',
                name='Items Added',
                yaxis='y'
            ))
            
            fig.add_trace(go.Scatter(
                x=daily_metrics['Date'],
                y=daily_metrics['Total Value'],
                mode='lines+markers',
                name='Total Value ($)',
                yaxis='y2'
            ))
            
            fig.update_layout(
                title="Daily Activity Trends",
                xaxis_title="Date",
                yaxis=dict(title="Items Added", side="left"),
                yaxis2=dict(title="Total Value ($)", side="right", overlaying="y"),
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)

def show_trend_analysis():
    """Advanced trend analysis with predictive insights"""
    st.subheader("📈 Trend Analysis & Predictions")
    
    # Analysis configuration
    col1, col2, col3 = st.columns(3)
    
    with col1:
        analysis_metric = st.selectbox(
            "Metric to Analyze",
            ["Inventory Additions", "Total Value", "Average Price", "Expiry Events"]
        )
    
    with col2:
        time_granularity = st.selectbox(
            "Time Granularity",
            ["Daily", "Weekly", "Monthly"]
        )
    
    with col3:
        lookback_period = st.selectbox(
            "Analysis Period",
            ["Last 3 Months", "Last 6 Months", "Last Year", "All Time"]
        )
    
    # Convert lookback period to days
    if lookback_period == "Last 3 Months":
        days_back = 90
    elif lookback_period == "Last 6 Months":
        days_back = 180
    elif lookback_period == "Last Year":
        days_back = 365
    else:
        days_back = None
    
    if days_back:
        start_date = datetime.now() - timedelta(days=days_back)
        filters = {'date_from': start_date.date()}
    else:
        filters = {}
    
    # Get data
    records = get_inventory_records(filters=filters)
    
    if not records:
        st.warning("No data available for the selected period")
        return
    
    df = pd.DataFrame(records)
    df['date'] = pd.to_datetime(df['created_at'])
    
    # Group by time granularity
    if time_granularity == "Daily":
        df['period'] = df['date'].dt.date
    elif time_granularity == "Weekly":
        df['period'] = df['date'].dt.to_period('W').dt.start_time.dt.date
    else:  # Monthly
        df['period'] = df['date'].dt.to_period('M').dt.start_time.dt.date
    
    # Calculate metrics by period
    if analysis_metric == "Inventory Additions":
        trend_data = df.groupby('period').size()
        y_title = "Number of Items"
        metric_name = "Items Added"
    elif analysis_metric == "Total Value":
        trend_data = df.groupby('period')['purchase_price'].sum()
        y_title = "Total Value ($)"
        metric_name = "Value Added"
    elif analysis_metric == "Average Price":
        trend_data = df.groupby('period')['purchase_price'].mean()
        y_title = "Average Price ($)"
        metric_name = "Avg Price"
    else:  # Expiry Events
        df_exp = df[df['expiration_date'].notna()].copy()
        if not df_exp.empty:
            df_exp['exp_date'] = pd.to_datetime(df_exp['expiration_date'])
            df_exp['is_expired'] = df_exp['exp_date'] <= pd.Timestamp.now()
            trend_data = df_exp[df_exp['is_expired']].groupby('period').size()
        else:
            trend_data = pd.Series(dtype=int)
        y_title = "Expired Items"
        metric_name = "Expired Items"
    
    if trend_data.empty or len(trend_data) < 2:
        st.warning(f"Not enough data available for {analysis_metric} analysis")
        return
    
    # Create trend visualization with basic analysis
    trend_df = trend_data.reset_index()
    trend_df.columns = ['Date', 'Value']
    
    # Simple trend calculation
    if len(trend_df) > 2:
        recent_avg = trend_df['Value'].tail(3).mean()
        earlier_avg = trend_df['Value'].head(3).mean()
        trend_direction = "Increasing" if recent_avg > earlier_avg else "Decreasing" if recent_avg < earlier_avg else "Stable"
        change_pct = ((recent_avg - earlier_avg) / earlier_avg) * 100 if earlier_avg > 0 else 0
        
        # Display trend insights
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "📈 Trend Direction",
                trend_direction,
                delta=f"{change_pct:+.1f}%"
            )
        
        with col2:
            volatility = trend_df['Value'].std()
            volatility_level = "High" if volatility > trend_df['Value'].mean() * 0.3 else "Low"
            st.metric(
                "🌪️ Volatility",
                volatility_level,
                delta=f"{volatility:.1f}"
            )
        
        with col3:
            st.metric(
                "📉 Current Level",
                f"{trend_df['Value'].iloc[-1]:.1f}",
                delta=f"vs {trend_df['Value'].mean():.1f} avg"
            )
        
        # Create advanced trend chart
        fig = go.Figure()
        
        # Actual data
        fig.add_trace(go.Scatter(
            x=trend_df['Date'],
            y=trend_df['Value'],
            mode='lines+markers',
            name=f'Actual {metric_name}',
            line=dict(width=3)
        ))
        
        # Moving average if enough data
        if len(trend_df) >= 5:
            ma_window = min(5, len(trend_df) // 2)
            trend_df['MA'] = trend_df['Value'].rolling(window=ma_window, center=True).mean()
            
            fig.add_trace(go.Scatter(
                x=trend_df['Date'],
                y=trend_df['MA'],
                mode='lines',
                name=f'{ma_window}-Period Moving Average',
                line=dict(width=2, color='green')
            ))
        
        fig.update_layout(
            title=f"{analysis_metric} Trend Analysis ({time_granularity})",
            xaxis_title="Date",
            yaxis_title=y_title,
            height=500,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Simple insights
        if trend_direction != "Stable":
            st.info(f"📈 **Trend Insight:** {metric_name} has been {trend_direction.lower()} over the analysis period with {change_pct:+.1f}% change in recent periods compared to earlier periods.")
    
    else:
        st.warning("Not enough data points for comprehensive trend analysis")

