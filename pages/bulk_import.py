import streamlit as st
import pandas as pd
import io
from database import insert_inventory_record, get_db_connection
from utils import validate_inventory_data
from datetime import datetime
import traceback

def show_bulk_import():
    st.header("📂 Bulk Import Inventory Data")
    
    st.info("""
    **Bulk Import allows you to:**
    - Upload CSV or Excel files with multiple inventory records
    - Preview data before importing
    - Validate all records for errors
    - Import valid records while reporting any issues
    """)
    
    tab1, tab2, tab3 = st.tabs(["📤 Upload & Import", "📋 Template", "📊 Import History"])
    
    with tab1:
        show_upload_import()
    
    with tab2:
        show_template_download()
    
    with tab3:
        show_import_history()

def show_upload_import():
    st.subheader("Upload Data File")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose CSV or Excel file",
        type=['csv', 'xlsx', 'xls'],
        help="Upload a CSV or Excel file containing inventory data"
    )
    
    if uploaded_file is not None:
        try:
            # Read file based on type
            if uploaded_file.type == 'text/csv':
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"File uploaded successfully! Found {len(df)} rows.")
            
            # Show file preview
            with st.expander("📋 File Preview", expanded=True):
                st.dataframe(df.head(10), use_container_width=True)
                
                if len(df) > 10:
                    st.info(f"Showing first 10 rows of {len(df)} total rows")
            
            # Column mapping
            st.subheader("📍 Column Mapping")
            st.write("Map your file columns to inventory fields:")
            
            expected_columns = {
                'patient_name': 'Patient Name*',
                'patient_id': 'Patient ID*',
                'administration_location': 'Administration Location',
                'drug_item_name': 'Drug/Item Name*',
                'date_of_service': 'Date of Service',
                'date_of_dispense': 'Date of Dispense',
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
                'dose_swap_status': 'Dose Swap Status'
            }
            
            file_columns = [""] + list(df.columns)
            column_mapping = {}
            
            # Create column mapping interface
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Required Fields:**")
                for field, display_name in list(expected_columns.items())[:len(expected_columns)//2]:
                    if '*' in display_name:
                        column_mapping[field] = st.selectbox(
                            display_name, 
                            file_columns,
                            key=f"map_{field}"
                        )
                    else:
                        column_mapping[field] = st.selectbox(
                            display_name, 
                            file_columns,
                            key=f"map_{field}"
                        )
            
            with col2:
                st.write("**Optional Fields:**")
                for field, display_name in list(expected_columns.items())[len(expected_columns)//2:]:
                    column_mapping[field] = st.selectbox(
                        display_name, 
                        file_columns,
                        key=f"map_{field}"
                    )
            
            # Import options
            st.subheader("⚙️ Import Options")
            
            col1, col2 = st.columns(2)
            with col1:
                skip_errors = st.checkbox("Skip rows with errors", value=True, help="Continue importing valid rows even if some rows have errors")
                send_notification = st.checkbox("Send email notification", value=False)
                
                if send_notification:
                    notification_email = st.text_input("Notification Email", placeholder="admin@company.com")
            
            with col2:
                default_values = st.checkbox("Use default values for empty fields", value=True)
                
                if default_values:
                    default_price = st.number_input("Default Purchase Price", value=50.0, format="%.2f")
                    default_created_by = st.text_input("Default Created By", value=st.session_state.username)
            
            # Validate and import
            if st.button("🔍 Validate Data", type="secondary", use_container_width=True):
                validation_results = validate_import_data(df, column_mapping, expected_columns)
                show_validation_results(validation_results)
                
                # Store validation results in session state for import
                st.session_state['validation_results'] = validation_results
                st.session_state['column_mapping'] = column_mapping
                st.session_state['import_df'] = df
                st.session_state['import_options'] = {
                    'skip_errors': skip_errors,
                    'send_notification': send_notification,
                    'notification_email': notification_email if send_notification else None,
                    'default_values': default_values,
                    'default_price': default_price if default_values else None,
                    'default_created_by': default_created_by if default_values else st.session_state.username
                }
            
            # Import button (only show if validation was successful)
            if 'validation_results' in st.session_state and st.session_state['validation_results']['valid_rows']:
                valid_count = len(st.session_state['validation_results']['valid_rows'])
                
                if st.button(f"✅ Import {valid_count} Valid Records", type="primary", use_container_width=True):
                    import_results = perform_import(
                        st.session_state['import_df'],
                        st.session_state['column_mapping'],
                        st.session_state['validation_results'],
                        st.session_state['import_options']
                    )
                    show_import_results(import_results)
                    
                    # Clear session state after import
                    for key in ['validation_results', 'column_mapping', 'import_df', 'import_options']:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    st.rerun()
                        
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")
            st.error("Please check that your file is properly formatted CSV or Excel file.")

def validate_import_data(df, column_mapping, expected_columns):
    """Validate import data and return results"""
    results = {
        'valid_rows': [],
        'invalid_rows': [],
        'errors': [],
        'warnings': []
    }
    
    # Check required fields are mapped
    required_fields = ['patient_name', 'patient_id', 'drug_item_name']
    missing_required = []
    
    for field in required_fields:
        if not column_mapping.get(field) or column_mapping[field] == "":
            missing_required.append(expected_columns[field])
    
    if missing_required:
        results['errors'].append(f"Missing required field mappings: {', '.join(missing_required)}")
        return results
    
    # Validate each row
    for idx, row in df.iterrows():
        try:
            # Map columns to expected format
            mapped_row = {}
            for field, file_column in column_mapping.items():
                if file_column and file_column != "":
                    mapped_row[field] = row.get(file_column, None)
                else:
                    mapped_row[field] = None
            
            # Validate mapped row
            validation_errors = validate_inventory_data(mapped_row)
            
            if validation_errors:
                results['invalid_rows'].append({
                    'row': idx + 1,
                    'data': mapped_row,
                    'errors': validation_errors
                })
            else:
                results['valid_rows'].append({
                    'row': idx + 1,
                    'data': mapped_row
                })
                
        except Exception as e:
            results['invalid_rows'].append({
                'row': idx + 1,
                'data': {},
                'errors': [f"Processing error: {str(e)}"]
            })
    
    return results

def show_validation_results(results):
    """Display validation results"""
    st.subheader("🔍 Validation Results")
    
    if results['errors']:
        for error in results['errors']:
            st.error(error)
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("✅ Valid Records", len(results['valid_rows']))
    
    with col2:
        st.metric("❌ Invalid Records", len(results['invalid_rows']))
    
    with col3:
        total = len(results['valid_rows']) + len(results['invalid_rows'])
        success_rate = (len(results['valid_rows']) / total * 100) if total > 0 else 0
        st.metric("Success Rate", f"{success_rate:.1f}%")
    
    # Show invalid rows if any
    if results['invalid_rows']:
        with st.expander("❌ Invalid Records Details"):
            for invalid_row in results['invalid_rows']:
                st.write(f"**Row {invalid_row['row']}:** {', '.join(invalid_row['errors'])}")

def perform_import(df, column_mapping, validation_results, options):
    """Perform the actual import"""
    results = {
        'successful': 0,
        'failed': 0,
        'errors': [],
        'summary': {}
    }
    
    try:
        for valid_row in validation_results['valid_rows']:
            try:
                data = valid_row['data'].copy()
                
                # Apply default values if enabled
                if options.get('default_values'):
                    if not data.get('purchase_price') and options.get('default_price'):
                        data['purchase_price'] = options['default_price']
                    
                    data['created_by'] = options.get('default_created_by', st.session_state.username)
                    data['updated_by'] = options.get('default_created_by', st.session_state.username)
                
                # Insert record
                record_id = insert_inventory_record(data)
                if record_id:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Row {valid_row['row']}: Failed to insert record")
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Row {valid_row['row']}: {str(e)}")
                
                if not options.get('skip_errors'):
                    break
    
        # Send notification if requested
        if options.get('send_notification') and options.get('notification_email'):
            try:
                from email_service import send_email
                subject = f"Bulk Import Completed - {results['successful']} records imported"
                content = f"""
                Bulk import completed:
                - Successful imports: {results['successful']}
                - Failed imports: {results['failed']}
                - Import performed by: {st.session_state.username}
                - Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
                send_email(options['notification_email'], "noreply@inventory.com", subject, content)
            except Exception as e:
                results['errors'].append(f"Failed to send notification: {str(e)}")
    
    except Exception as e:
        results['errors'].append(f"Import failed: {str(e)}")
    
    # Save import history
    save_import_history(results, options)
    
    return results

def show_import_results(results):
    """Display import results"""
    st.subheader("📊 Import Results")
    
    if results['successful'] > 0:
        st.success(f"Successfully imported {results['successful']} records!")
    
    if results['failed'] > 0:
        st.warning(f"Failed to import {results['failed']} records")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("✅ Successful", results['successful'])
    
    with col2:
        st.metric("❌ Failed", results['failed'])
    
    if results['errors']:
        with st.expander("❌ Error Details"):
            for error in results['errors']:
                st.write(f"• {error}")

def show_template_download():
    """Show template download options"""
    st.subheader("📋 Download Import Template")
    
    st.info("""
    Use these templates to format your data correctly for bulk import:
    - **CSV Template**: Simple comma-separated format
    - **Excel Template**: Formatted spreadsheet with validation
    """)
    
    # Create template data
    template_data = {
        'Patient Name': ['John Doe', 'Jane Smith'],
        'Patient ID': [189093, 189094],
        'Administration Location': ['Hospital A', 'Clinic B'],
        'Drug/Item Name': ['Medicine X', 'Device Y'],
        'Date Of Service': ['2024-01-15', '2024-01-16'],
        'Date Of Dispense': ['2024-01-15', '2024-01-16'],
        'Date Ordered': ['2024-01-10', '2024-01-11'],
        'Date Received': ['2024-01-12', '2024-01-13'],
        'Order Number': [3422575715, 3422575716],
        'Invoice Number': [12345, 12346],
        'PO Number': [67890, 67891],
        'Lot Number': [11111, 22222],
        'Expiration Date': ['2025-01-15', '2025-01-16'],
        'Inventory Number': ['PPF-0000108', 'PPF-0000109'],
        'Inventory Type': ['Medication', 'Medical Device'],
        'Purchase Price': [50.00, 75.00],
        'Provider': ['Provider A', 'Provider B'],
        'Location': ['Storage A', 'Storage B'],
        'Inventory Site': ['Site 1', 'Site 2'],
        'Username': ['admin', 'admin'],
        'Dose Swap Status': [False, True]
    }
    
    template_df = pd.DataFrame(template_data)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV download
        csv_data = template_df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV Template",
            data=csv_data,
            file_name="inventory_import_template.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # Excel download
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            template_df.to_excel(writer, sheet_name='Inventory Template', index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Inventory Template']
            
            # Add formatting
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D7E4BC',
                'border': 1
            })
            
            # Format headers
            for col_num, value in enumerate(template_df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 15)
        
        st.download_button(
            label="📥 Download Excel Template",
            data=excel_buffer.getvalue(),
            file_name="inventory_import_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    # Show template preview
    with st.expander("👀 Template Preview"):
        st.dataframe(template_df, use_container_width=True)

def save_import_history(results, options):
    """Save import history to database"""
    try:
        conn = get_db_connection()
        if not conn:
            return
        
        cur = conn.cursor()
        
        # Create import_history table if it doesn't exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS import_history (
                id SERIAL PRIMARY KEY,
                imported_by VARCHAR(100),
                import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_rows INTEGER,
                successful_rows INTEGER,
                failed_rows INTEGER,
                errors TEXT,
                options JSONB
            )
        """)
        
        # Insert import record
        cur.execute("""
            INSERT INTO import_history (imported_by, total_rows, successful_rows, failed_rows, errors, options)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            st.session_state.username,
            results['successful'] + results['failed'],
            results['successful'],
            results['failed'],
            '\n'.join(results['errors']) if results['errors'] else None,
            str(options)  # Convert to JSON string
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Failed to save import history: {e}")

def show_import_history():
    """Show import history"""
    st.subheader("📊 Import History")
    
    conn = get_db_connection()
    if not conn:
        st.error("Database connection failed")
        return
    
    cur = conn.cursor()
    
    try:
        # Check if import_history table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'import_history'
            );
        """)
        
        if not cur.fetchone()[0]:
            st.info("No import history available yet. Complete your first bulk import to see history here.")
            cur.close()
            conn.close()
            return
        
        # Get import history
        cur.execute("""
            SELECT imported_by, import_date, total_rows, successful_rows, failed_rows, errors
            FROM import_history
            ORDER BY import_date DESC
            LIMIT 50
        """)
        
        history = cur.fetchall()
        cur.close()
        conn.close()
        
        if history:
            history_df = pd.DataFrame(history, columns=[
                'Imported By', 'Import Date', 'Total Rows', 'Successful', 'Failed', 'Errors'
            ])
            
            # Format date
            history_df['Import Date'] = pd.to_datetime(history_df['Import Date']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            st.dataframe(history_df, use_container_width=True)
        else:
            st.info("No import history available yet.")
    
    except Exception as e:
        st.error(f"Failed to load import history: {str(e)}")
        cur.close()
        conn.close()