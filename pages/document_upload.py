import streamlit as st
import os
from PIL import Image
import io
import base64
from database import get_db_connection, get_inventory_records
import pandas as pd
from datetime import datetime

def show_document_upload():
    st.header("📄 Document Upload & Scanning")
    
    tab1, tab2, tab3 = st.tabs(["📎 Upload Documents", "🖼️ View Documents", "🔍 Scan to Inventory"])
    
    with tab1:
        show_upload_form()
    
    with tab2:
        show_document_list()
    
    with tab3:
        show_scan_integration()

def show_upload_form():
    """Document upload form with validation"""
    st.subheader("Upload Scanned Documents")
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Choose files to upload",
        type=['pdf', 'jpg', 'jpeg', 'png', 'tiff', 'docx', 'doc'],
        accept_multiple_files=True,
        help="Supported formats: PDF, JPG, PNG, TIFF, DOCX, DOC"
    )
    
    if uploaded_files:
        for uploaded_file in uploaded_files:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**File:** {uploaded_file.name}")
                st.write(f"**Size:** {uploaded_file.size:,} bytes")
                st.write(f"**Type:** {uploaded_file.type}")
            
            with col2:
                # Link to inventory record (optional)
                inventory_records = get_inventory_records(limit=100)
                if inventory_records:
                    record_options = ["None"] + [
                        f"{record['id']} - {record['patient_name']} ({record['drug_item_name']})"
                        for record in inventory_records
                    ]
                    selected_record = st.selectbox(
                        "Link to Inventory Record",
                        record_options,
                        key=f"record_{uploaded_file.name}"
                    )
                else:
                    selected_record = "None"
            
            # Description
            description = st.text_area(
                "Description (optional)",
                placeholder="Brief description of the document",
                key=f"desc_{uploaded_file.name}"
            )
            
            # Preview for images
            if uploaded_file.type.startswith('image/'):
                try:
                    image = Image.open(uploaded_file)
                    
                    # Resize image for preview
                    max_size = (400, 300)
                    image.thumbnail(max_size, Image.Resampling.LANCZOS)
                    
                    st.image(image, caption="Preview", use_column_width=True)
                except Exception as e:
                    st.warning(f"Could not preview image: {str(e)}")
            
            st.divider()
        
        # Upload button
        if st.button("Upload All Documents", type="primary", use_container_width=True):
            success_count = 0
            error_count = 0
            
            for uploaded_file in uploaded_files:
                try:
                    # Get inventory record ID if linked
                    inventory_id = None
                    record_key = f"record_{uploaded_file.name}"
                    if record_key in st.session_state and st.session_state[record_key] != "None":
                        inventory_id = int(st.session_state[record_key].split(" - ")[0])
                    
                    # Get description
                    desc_key = f"desc_{uploaded_file.name}"
                    file_description = st.session_state.get(desc_key, "")
                    
                    # Save file
                    if save_document(uploaded_file, inventory_id, file_description):
                        success_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    st.error(f"Error uploading {uploaded_file.name}: {str(e)}")
                    error_count += 1
            
            if success_count > 0:
                st.success(f"Successfully uploaded {success_count} document(s)")
            if error_count > 0:
                st.error(f"Failed to upload {error_count} document(s)")
            
            if success_count > 0:
                st.rerun()

def save_document(uploaded_file, inventory_id=None, description=""):
    """Save uploaded document to database and file system"""
    try:
        # Create uploads directory if it doesn't exist
        upload_dir = "uploads"
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{uploaded_file.name}"
        file_path = os.path.join(upload_dir, filename)
        
        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Save to database
        conn = get_db_connection()
        if not conn:
            return False
        
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO documents (
                filename, file_path, file_size, file_type,
                inventory_id, uploaded_by, description
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            uploaded_file.name,
            file_path,
            uploaded_file.size,
            uploaded_file.type,
            inventory_id,
            st.session_state.username,
            description
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        st.error(f"Error saving document: {str(e)}")
        return False

def show_document_list():
    """Display uploaded documents"""
    st.subheader("Uploaded Documents")
    
    conn = get_db_connection()
    if not conn:
        st.error("Database connection failed")
        return
    
    cur = conn.cursor()
    
    cur.execute("""
        SELECT d.id, d.filename, d.file_size, d.file_type, d.uploaded_at, d.uploaded_by,
               d.description, i.patient_name, i.drug_item_name
        FROM documents d
        LEFT JOIN inventory i ON d.inventory_id = i.id
        ORDER BY d.uploaded_at DESC
    """)
    
    documents = cur.fetchall()
    cur.close()
    conn.close()
    
    if documents:
        for doc in documents:
            with st.expander(f"📄 {doc[1]} (uploaded by {doc[5]})"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**File Type:** {doc[3]}")
                    st.write(f"**Size:** {doc[2]:,} bytes")
                    st.write(f"**Uploaded:** {doc[4].strftime('%Y-%m-%d %H:%M:%S')}")
                
                with col2:
                    if doc[7]:  # patient_name
                        st.write(f"**Linked to:** {doc[7]} ({doc[8]})")
                    else:
                        st.write("**Linked to:** No inventory record")
                
                if doc[6]:  # description
                    st.write(f"**Description:** {doc[6]}")
                
                # Download button
                file_path = f"uploads/{doc[4].strftime('%Y%m%d_%H%M%S')}_{doc[1]}"
                if os.path.exists(file_path):
                    with open(file_path, "rb") as file:
                        st.download_button(
                            label="📥 Download",
                            data=file.read(),
                            file_name=doc[1],
                            mime=doc[3]
                        )
    else:
        st.info("No documents uploaded yet")

def show_scan_integration():
    """Simulated scanning integration - placeholder for barcode/QR code scanning"""
    st.subheader("🔍 Scan Integration")
    
    st.info("""
    **Scanning Features:**
    - Barcode scanning for inventory numbers
    - QR code scanning for quick data entry
    - Document text recognition (OCR)
    
    This is where barcode/QR code scanning integration would be implemented.
    """)
    
    # Simulated barcode input
    st.subheader("Manual Barcode/QR Entry")
    
    with st.form("scan_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            scanned_code = st.text_input(
                "Scanned Code",
                placeholder="Enter barcode or QR code manually",
                help="In production, this would be automatically filled from scanner"
            )
            
            code_type = st.selectbox("Code Type", [
                "Inventory Number",
                "Patient ID", 
                "Order Number",
                "Lot Number",
                "Custom"
            ])
        
        with col2:
            auto_fill = st.checkbox("Auto-fill form with scanned data", value=True)
            
            scan_to_search = st.checkbox("Use scan to search existing records", value=False)
        
        submitted = st.form_submit_button("Process Scanned Code")
        
        if submitted and scanned_code:
            if scan_to_search:
                # Search for existing records
                search_scanned_data(scanned_code, code_type)
            else:
                # Show form with pre-filled data
                st.success(f"Scanned: {scanned_code} (Type: {code_type})")
                if auto_fill:
                    show_prefilled_form(scanned_code, code_type)

def search_scanned_data(scanned_code, code_type):
    """Search inventory records based on scanned data"""
    conn = get_db_connection()
    if not conn:
        st.error("Database connection failed")
        return
    
    cur = conn.cursor()
    
    # Build search query based on code type
    if code_type == "Inventory Number":
        cur.execute("SELECT * FROM inventory WHERE inventory_number = %s", (scanned_code,))
    elif code_type == "Patient ID":
        cur.execute("SELECT * FROM inventory WHERE patient_id = %s", (scanned_code,))
    elif code_type == "Order Number":
        cur.execute("SELECT * FROM inventory WHERE order_number = %s", (scanned_code,))
    elif code_type == "Lot Number":
        cur.execute("SELECT * FROM inventory WHERE lot_number = %s", (scanned_code,))
    else:
        # Search across multiple fields
        cur.execute("""
            SELECT * FROM inventory 
            WHERE inventory_number = %s 
               OR CAST(patient_id AS TEXT) = %s 
               OR CAST(order_number AS TEXT) = %s
               OR CAST(lot_number AS TEXT) = %s
        """, (scanned_code, scanned_code, scanned_code, scanned_code))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    if results:
        st.success(f"Found {len(results)} matching record(s)")
        
        # Convert to DataFrame for display
        columns = [
            'id', 'patient_name', 'patient_id', 'drug_item_name', 
            'inventory_number', 'date_of_service', 'provider'
        ]
        
        df = pd.DataFrame(results, columns=[desc[0] for desc in cur.description])
        display_df = df[columns].copy()
        
        st.dataframe(display_df, use_container_width=True)
    else:
        st.warning(f"No records found for {code_type}: {scanned_code}")

def show_prefilled_form(scanned_code, code_type):
    """Show inventory form with pre-filled data from scan"""
    st.subheader("📝 New Record from Scan")
    
    # Pre-fill appropriate field based on code type
    default_values = {}
    
    if code_type == "Inventory Number":
        default_values['inventory_number'] = scanned_code
    elif code_type == "Patient ID":
        try:
            default_values['patient_id'] = int(scanned_code)
        except:
            default_values['patient_id'] = None
    elif code_type == "Order Number":
        try:
            default_values['order_number'] = int(scanned_code)
        except:
            default_values['order_number'] = None
    elif code_type == "Lot Number":
        try:
            default_values['lot_number'] = int(scanned_code)
        except:
            default_values['lot_number'] = None
    
    st.info(f"Form pre-filled with scanned {code_type}: {scanned_code}")
    st.write("Complete the remaining fields to create the inventory record.")
    
    # Note: In a full implementation, this would redirect to the add inventory form
    # with the pre-filled values
