import streamlit as st
from database import get_inventory_records, insert_inventory_record, update_inventory_record, get_db_connection
from email_service import send_inventory_update_notification
import pandas as pd
from datetime import datetime, date
import os

def show_inventory_management():
    st.header("📦 Inventory Management")
    
    # Action tabs
    tab1, tab2, tab3 = st.tabs(["📋 View Records", "➕ Add New", "🔍 Search & Filter"])
    
    with tab1:
        show_inventory_list()
    
    with tab2:
        show_add_inventory_form()
    
    with tab3:
        show_search_filter()

def show_inventory_list():
    """Display inventory records in a table"""
    st.subheader("Current Inventory Records")
    
    # Get all records
    records = get_inventory_records(limit=100)
    
    if records:
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Select key columns for display
        display_columns = [
            'id', 'patient_name', 'patient_id', 'drug_item_name', 
            'inventory_number', 'date_of_service', 'expiration_date',
            'purchase_price', 'provider', 'created_at'
        ]
        
        display_df = df[display_columns].copy()
        
        # Format dates
        date_columns = ['date_of_service', 'expiration_date', 'created_at']
        for col in date_columns:
            if col in display_df.columns:
                display_df[col] = pd.to_datetime(display_df[col]).dt.strftime('%Y-%m-%d')
        
        # Show dataframe with selection
        selected_indices = st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # Edit selected record
        if selected_indices.selection and selected_indices.selection.get('rows'):
            selected_row = selected_indices.selection['rows'][0]
            selected_record = records[selected_row]
            
            st.divider()
            st.subheader("📝 Edit Selected Record")
            show_edit_form(selected_record)
    else:
        st.info("No inventory records found")

def show_add_inventory_form():
    """Form to add new inventory record"""
    st.subheader("Add New Inventory Record")
    
    with st.form("add_inventory_form"):
        # Basic patient information
        col1, col2 = st.columns(2)
        
        with col1:
            patient_name = st.text_input("Patient Name*", placeholder="Enter patient name")
            patient_id = st.number_input("Patient ID*", min_value=1, value=None, format="%d")
            administration_location = st.text_input("Administration Location", placeholder="Where treatment was administered")
        
        with col2:
            drug_item_name = st.text_input("Drug/Item Name*", placeholder="Name of drug or item")
            inventory_type = st.selectbox("Inventory Type", [
                "", "Medication", "Medical Device", "Supply", "Equipment", "Other"
            ])
            provider = st.text_input("Provider", placeholder="Healthcare provider")
        
        # Dates
        st.subheader("📅 Important Dates")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            date_of_service = st.date_input("Date of Service")
        with col2:
            date_of_dispense = st.date_input("Date of Dispense", value=None)
        with col3:
            date_ordered = st.date_input("Date Ordered", value=None)
        with col4:
            date_received = st.date_input("Date Received", value=None)
        
        # Numbers and identifiers
        st.subheader("🔢 Numbers & Identifiers")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            order_number = st.number_input("Order Number", min_value=0, value=None, format="%d")
            invoice_number = st.number_input("Invoice Number", min_value=0, value=None, format="%d")
        
        with col2:
            po_number = st.number_input("PO Number", min_value=0, value=None, format="%d")
            lot_number = st.number_input("Lot Number", min_value=0, value=None, format="%d")
        
        with col3:
            inventory_number = st.text_input("Inventory Number", placeholder="e.g., PPF-0000108")
            expiration_date = st.date_input("Expiration Date", value=None)
        
        # Financial and location info
        st.subheader("💰 Financial & Location")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Admin-only price editing
            if st.session_state.user_role == "admin":
                purchase_price = st.number_input("Purchase Price ($)", min_value=0.0, value=50.0, format="%.2f")
            else:
                purchase_price = st.number_input("Purchase Price ($)", value=50.0, disabled=True, format="%.2f")
                st.caption("Price editing requires admin access")
        
        with col2:
            location = st.text_input("Location", placeholder="Storage location")
            inventory_site = st.text_input("Inventory Site", placeholder="Site where inventory is kept")
        
        with col3:
            username = st.text_input("Username", value=st.session_state.username, disabled=True)
            dose_swap_status = st.checkbox("Dose Swap Status")
        
        # Email notification
        notify_email = st.text_input("Email for Notifications (optional)", placeholder="admin@company.com")
        
        # Submit button
        submitted = st.form_submit_button("Add Inventory Record", use_container_width=True)
        
        if submitted:
            # Validate required fields
            if not patient_name or not patient_id or not drug_item_name:
                st.error("Please fill in all required fields marked with *")
                return
            
            # Prepare data
            inventory_data = {
                'patient_name': patient_name,
                'patient_id': patient_id,
                'administration_location': administration_location,
                'drug_item_name': drug_item_name,
                'date_of_service': date_of_service,
                'date_of_dispense': date_of_dispense,
                'date_ordered': date_ordered,
                'date_received': date_received,
                'order_number': order_number,
                'invoice_number': invoice_number,
                'po_number': po_number,
                'lot_number': lot_number,
                'expiration_date': expiration_date,
                'inventory_number': inventory_number,
                'inventory_type': inventory_type if inventory_type else None,
                'purchase_price': purchase_price,
                'provider': provider,
                'location': location,
                'inventory_site': inventory_site,
                'username': username,
                'dose_swap_status': dose_swap_status,
                'created_by': st.session_state.username,
                'updated_by': st.session_state.username
            }
            
            try:
                # Insert record
                record_id = insert_inventory_record(inventory_data)
                st.success(f"Inventory record added successfully! (ID: {record_id})")
                
                # Send email notification if provided
                if notify_email:
                    inventory_data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    if send_inventory_update_notification(notify_email, inventory_data, "created"):
                        st.success("Email notification sent successfully!")
                    else:
                        st.warning("Record added but email notification failed")
                
                # Refresh the page
                st.rerun()
                
            except Exception as e:
                st.error(f"Failed to add inventory record: {str(e)}")

def show_edit_form(record):
    """Form to edit existing inventory record"""
    with st.form("edit_inventory_form"):
        # Basic patient information
        col1, col2 = st.columns(2)
        
        with col1:
            patient_name = st.text_input("Patient Name*", value=record['patient_name'] or "")
            patient_id = st.number_input("Patient ID*", value=record['patient_id'] or 0)
            administration_location = st.text_input("Administration Location", value=record['administration_location'] or "")
        
        with col2:
            drug_item_name = st.text_input("Drug/Item Name*", value=record['drug_item_name'] or "")
            inventory_type = st.selectbox("Inventory Type", [
                "", "Medication", "Medical Device", "Supply", "Equipment", "Other"
            ], index=0 if not record['inventory_type'] else ["", "Medication", "Medical Device", "Supply", "Equipment", "Other"].index(record['inventory_type']))
            provider = st.text_input("Provider", value=record['provider'] or "")
        
        # Dates
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            date_of_service = st.date_input("Date of Service", value=record['date_of_service'])
        with col2:
            date_of_dispense = st.date_input("Date of Dispense", value=record['date_of_dispense'])
        with col3:
            date_ordered = st.date_input("Date Ordered", value=record['date_ordered'])
        with col4:
            date_received = st.date_input("Date Received", value=record['date_received'])
        
        # Numbers
        col1, col2, col3 = st.columns(3)
        
        with col1:
            order_number = st.number_input("Order Number", value=record['order_number'] or 0)
            invoice_number = st.number_input("Invoice Number", value=record['invoice_number'] or 0)
        
        with col2:
            po_number = st.number_input("PO Number", value=record['po_number'] or 0)
            lot_number = st.number_input("Lot Number", value=record['lot_number'] or 0)
        
        with col3:
            inventory_number = st.text_input("Inventory Number", value=record['inventory_number'] or "")
            expiration_date = st.date_input("Expiration Date", value=record['expiration_date'])
        
        # Financial and location
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.session_state.user_role == "admin":
                purchase_price = st.number_input("Purchase Price ($)", value=float(record['purchase_price'] or 50.0), format="%.2f")
            else:
                purchase_price = st.number_input("Purchase Price ($)", value=float(record['purchase_price'] or 50.0), disabled=True, format="%.2f")
        
        with col2:
            location = st.text_input("Location", value=record['location'] or "")
            inventory_site = st.text_input("Inventory Site", value=record['inventory_site'] or "")
        
        with col3:
            username = st.text_input("Username", value=record['username'] or "")
            dose_swap_status = st.checkbox("Dose Swap Status", value=record['dose_swap_status'] or False)
        
        # Email notification
        notify_email = st.text_input("Email for Notifications (optional)", placeholder="admin@company.com")
        
        # Submit button
        submitted = st.form_submit_button("Update Record", use_container_width=True)
        
        if submitted:
            # Prepare data
            inventory_data = {
                'patient_name': patient_name,
                'patient_id': patient_id,
                'administration_location': administration_location,
                'drug_item_name': drug_item_name,
                'date_of_service': date_of_service,
                'date_of_dispense': date_of_dispense,
                'date_ordered': date_ordered,
                'date_received': date_received,
                'order_number': order_number if order_number > 0 else None,
                'invoice_number': invoice_number if invoice_number > 0 else None,
                'po_number': po_number if po_number > 0 else None,
                'lot_number': lot_number if lot_number > 0 else None,
                'expiration_date': expiration_date,
                'inventory_number': inventory_number,
                'inventory_type': inventory_type if inventory_type else None,
                'purchase_price': purchase_price,
                'provider': provider,
                'location': location,
                'inventory_site': inventory_site,
                'username': username,
                'dose_swap_status': dose_swap_status,
                'updated_by': st.session_state.username
            }
            
            try:
                # Update record
                update_inventory_record(record['id'], inventory_data)
                st.success("Inventory record updated successfully!")
                
                # Send email notification if provided
                if notify_email:
                    inventory_data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    if send_inventory_update_notification(notify_email, inventory_data, "updated"):
                        st.success("Email notification sent successfully!")
                    else:
                        st.warning("Record updated but email notification failed")
                
                # Refresh the page
                st.rerun()
                
            except Exception as e:
                st.error(f"Failed to update inventory record: {str(e)}")

def show_search_filter():
    """Search and filter functionality"""
    st.subheader("🔍 Search & Filter Inventory")
    
    with st.form("search_form"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            patient_name_filter = st.text_input("Patient Name")
            drug_name_filter = st.text_input("Drug/Item Name")
        
        with col2:
            inventory_type_filter = st.selectbox("Inventory Type", [
                "", "Medication", "Medical Device", "Supply", "Equipment", "Other"
            ])
            provider_filter = st.text_input("Provider")
        
        with col3:
            date_from = st.date_input("Service Date From", value=None)
            date_to = st.date_input("Service Date To", value=None)
        
        search_submitted = st.form_submit_button("Search", use_container_width=True)
    
    if search_submitted:
        # Build filters
        filters = {}
        
        if patient_name_filter:
            filters['patient_name'] = patient_name_filter
        if drug_name_filter:
            filters['drug_item_name'] = drug_name_filter
        if inventory_type_filter:
            filters['inventory_type'] = inventory_type_filter
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
        
        # Get filtered records
        records = get_inventory_records(filters=filters)
        
        if records:
            df = pd.DataFrame(records)
            
            # Select display columns
            display_columns = [
                'patient_name', 'drug_item_name', 'inventory_number',
                'date_of_service', 'provider', 'inventory_type', 'purchase_price'
            ]
            
            display_df = df[display_columns].copy()
            
            # Format dates
            if 'date_of_service' in display_df.columns:
                display_df['date_of_service'] = pd.to_datetime(display_df['date_of_service']).dt.strftime('%Y-%m-%d')
            
            st.dataframe(display_df, use_container_width=True)
            
            # Download button
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Search Results as CSV",
                data=csv,
                file_name=f"inventory_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No records found matching the search criteria")
