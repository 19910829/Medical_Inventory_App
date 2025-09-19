import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from database import get_db_connection, update_inventory_record
import json
import time
from datetime import datetime, timedelta
import base64
import cv2
import numpy as np
from io import BytesIO
from PIL import Image

def show_barcode_scanner():
    st.header("📱 Barcode/QR Scanner")
    
    st.info("""
    **Barcode Scanner Features:**
    - Real-time camera scanning for barcodes and QR codes
    - Quick lookup of inventory items by scanning
    - Instant inventory updates via scan
    - Support for common barcode formats (Code128, EAN, UPC, QR codes)
    - Mobile-friendly interface for handheld scanning
    """)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📱 Live Scanner", "📋 Scan History", "🔍 Manual Lookup", "⚙️ Settings"])
    
    with tab1:
        show_live_scanner()
    
    with tab2:
        show_scan_history()
    
    with tab3:
        show_manual_lookup()
    
    with tab4:
        show_scanner_settings()

def show_live_scanner():
    """Show live barcode scanner interface"""
    st.subheader("📱 Live Barcode Scanner")
    
    # Scanner mode selection
    col1, col2 = st.columns(2)
    
    with col1:
        scanner_mode = st.selectbox(
            "Scanner Mode",
            ["Lookup Only", "Quick Update", "Full Edit"],
            help="Choose what happens when a barcode is scanned"
        )
    
    with col2:
        enable_sound = st.checkbox("Enable scan sound", value=True)
    
    # Camera scanner component
    st.write("**📷 Camera Scanner:**")
    
    # Check if we have camera access
    if 'camera_available' not in st.session_state:
        st.session_state.camera_available = True
    
    if st.session_state.camera_available:
        # Render the camera scanner
        scanned_data = render_camera_scanner(enable_sound)
        
        if scanned_data and scanned_data.strip():
            handle_scanned_data(scanned_data, scanner_mode)
    else:
        st.warning("Camera access not available. Please use manual lookup or file upload.")
    
    # Alternative input methods
    st.write("---")
    st.subheader("🔤 Alternative Input Methods")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Manual barcode entry
        manual_barcode = st.text_input(
            "Enter barcode manually:",
            placeholder="Type or paste barcode here",
            key="manual_barcode_input"
        )
        
        if manual_barcode and st.button("🔍 Lookup Manual Entry"):
            handle_scanned_data(manual_barcode, scanner_mode)
    
    with col2:
        # Image upload for scanning
        uploaded_image = st.file_uploader(
            "Upload barcode image:",
            type=['jpg', 'jpeg', 'png', 'bmp'],
            help="Upload an image containing a barcode to scan"
        )
        
        if uploaded_image:
            try:
                # Process uploaded image
                barcode_data = process_uploaded_image(uploaded_image)
                if barcode_data:
                    st.success(f"Found barcode: {barcode_data}")
                    handle_scanned_data(barcode_data, scanner_mode)
                else:
                    st.error("No barcode found in the uploaded image")
            except Exception as e:
                st.error(f"Error processing image: {str(e)}")

def render_camera_scanner(enable_sound):
    """Render the camera scanner component using HTML/JS"""
    
    # HTML template for barcode scanner
    scanner_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://unpkg.com/@zxing/library@latest"></script>
        <style>
            #scanner-container {{
                width: 100%;
                max-width: 600px;
                margin: 0 auto;
                text-align: center;
            }}
            #video {{
                width: 100%;
                max-width: 500px;
                height: 300px;
                border: 2px solid #ddd;
                border-radius: 8px;
                background-color: #000;
            }}
            #result {{
                margin-top: 10px;
                padding: 10px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                min-height: 50px;
            }}
            .status {{
                color: #6c757d;
                font-style: italic;
            }}
            .success {{
                color: #28a745;
                font-weight: bold;
            }}
            .error {{
                color: #dc3545;
                font-weight: bold;
            }}
            .controls {{
                margin: 10px 0;
            }}
            button {{
                margin: 5px;
                padding: 8px 16px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f8f9fa;
                cursor: pointer;
            }}
            button:hover {{
                background-color: #e2e6ea;
            }}
            button:disabled {{
                opacity: 0.6;
                cursor: not-allowed;
            }}
        </style>
    </head>
    <body>
        <div id="scanner-container">
            <video id="video"></video>
            <div class="controls">
                <button id="start-btn" onclick="startScanning()">▶️ Start Scanner</button>
                <button id="stop-btn" onclick="stopScanning()" disabled>⏹️ Stop Scanner</button>
                <button id="switch-camera" onclick="switchCamera()">🔄 Switch Camera</button>
            </div>
            <div id="result">
                <div class="status">Click "Start Scanner" to begin scanning barcodes</div>
            </div>
        </div>

        <script>
            let codeReader = new ZXing.BrowserMultiFormatReader();
            let selectedDeviceId;
            let isScanning = false;
            let currentStream = null;
            let lastScannedCode = '';
            let lastScannedTime = 0;
            let cameraDevices = [];
            let currentCameraIndex = 0;

            // Initialize camera devices
            async function initializeCameras() {{
                try {{
                    const devices = await codeReader.getVideoInputDevices();
                    cameraDevices = devices;
                    if (devices.length > 0) {{
                        selectedDeviceId = devices[0].deviceId;
                    }}
                    
                    if (cameraDevices.length <= 1) {{
                        document.getElementById('switch-camera').style.display = 'none';
                    }}
                }} catch (err) {{
                    console.error('Error initializing cameras:', err);
                    document.getElementById('result').innerHTML = '<div class="error">Camera access denied or unavailable</div>';
                }}
            }}

            function startScanning() {{
                if (isScanning) return;
                
                const video = document.getElementById('video');
                const result = document.getElementById('result');
                const startBtn = document.getElementById('start-btn');
                const stopBtn = document.getElementById('stop-btn');
                
                result.innerHTML = '<div class="status">Starting camera...</div>';
                
                codeReader.decodeFromVideoDevice(selectedDeviceId, 'video', (result, err) => {{
                    if (result) {{
                        const currentTime = Date.now();
                        const scannedCode = result.text;
                        
                        // Prevent duplicate scans within 2 seconds
                        if (scannedCode !== lastScannedCode || (currentTime - lastScannedTime) > 2000) {{
                            lastScannedCode = scannedCode;
                            lastScannedTime = currentTime;
                            
                            // Play sound if enabled
                            {f'playBeep();' if enable_sound else ''}
                            
                            // Display result
                            document.getElementById('result').innerHTML = 
                                '<div class="success">✅ Scanned: ' + scannedCode + '</div>';
                            
                            // Send data to Streamlit
                            sendToStreamlit(scannedCode);
                        }}
                    }}
                    if (err && !(err instanceof ZXing.NotFoundException)) {{
                        console.error(err);
                    }}
                }}).then((controls) => {{
                    currentStream = controls;
                    isScanning = true;
                    startBtn.disabled = true;
                    stopBtn.disabled = false;
                    result.innerHTML = '<div class="status">📱 Ready to scan - Point camera at barcode</div>';
                }}).catch((err) => {{
                    console.error(err);
                    result.innerHTML = '<div class="error">❌ Failed to start camera: ' + err.message + '</div>';
                }});
            }}

            function stopScanning() {{
                if (!isScanning) return;
                
                if (currentStream) {{
                    currentStream.stop();
                    currentStream = null;
                }}
                
                isScanning = false;
                document.getElementById('start-btn').disabled = false;
                document.getElementById('stop-btn').disabled = true;
                document.getElementById('result').innerHTML = '<div class="status">Scanner stopped</div>';
            }}

            function switchCamera() {{
                if (cameraDevices.length <= 1) return;
                
                currentCameraIndex = (currentCameraIndex + 1) % cameraDevices.length;
                selectedDeviceId = cameraDevices[currentCameraIndex].deviceId;
                
                if (isScanning) {{
                    stopScanning();
                    setTimeout(startScanning, 500);
                }}
            }}

            function playBeep() {{
                // Create a short beep sound
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioContext.createOscillator();
                const gainNode = audioContext.createGain();
                
                oscillator.connect(gainNode);
                gainNode.connect(audioContext.destination);
                
                oscillator.frequency.value = 800;
                gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.1);
                
                oscillator.start(audioContext.currentTime);
                oscillator.stop(audioContext.currentTime + 0.1);
            }}

            function sendToStreamlit(data) {{
                // Send scanned data to Streamlit
                window.parent.postMessage({{
                    type: 'barcode_scanned',
                    data: data
                }}, '*');
            }}

            // Initialize when page loads
            window.addEventListener('load', initializeCameras);
            
            // Clean up when page unloads
            window.addEventListener('beforeunload', () => {{
                if (currentStream) {{
                    currentStream.stop();
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    # Render the HTML component
    scanner_component = components.html(scanner_html, height=500, scrolling=False)
    
    # Handle incoming data from the scanner
    if 'scanned_barcode_data' not in st.session_state:
        st.session_state.scanned_barcode_data = None
    
    # JavaScript to listen for messages from the scanner
    components.html("""
    <script>
        window.addEventListener('message', function(event) {
            if (event.data.type === 'barcode_scanned') {
                // Send the scanned data to Streamlit
                window.parent.postMessage({
                    type: 'streamlit:componentValue',
                    value: event.data.data
                }, '*');
            }
        });
    </script>
    """, height=0)
    
    return scanner_component

def handle_scanned_data(barcode_data, scanner_mode):
    """Handle scanned barcode data based on mode"""
    if not barcode_data or not barcode_data.strip():
        return
    
    st.success(f"📱 Scanned: `{barcode_data}`")
    
    # Record the scan
    record_scan(barcode_data)
    
    # Look up inventory item
    inventory_item = get_inventory_by_barcode(barcode_data)
    
    if inventory_item:
        st.success("✅ Item found in inventory!")
        display_inventory_item(inventory_item, scanner_mode)
    else:
        st.warning("⚠️ Item not found in inventory")
        show_create_new_item_option(barcode_data)

def get_inventory_by_barcode(barcode_data):
    """Look up inventory item by barcode"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor()
        
        # Search in multiple potential barcode fields
        cur.execute("""
            SELECT * FROM inventory 
            WHERE inventory_number = %s 
               OR lot_number::text = %s 
               OR order_number::text = %s
               OR po_number::text = %s
               OR invoice_number::text = %s
            ORDER BY created_at DESC 
            LIMIT 1
        """, (barcode_data, barcode_data, barcode_data, barcode_data, barcode_data))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result:
            columns = [desc[0] for desc in cur.description]
            return dict(zip(columns, result))
        
        return None
        
    except Exception as e:
        st.error(f"Error looking up barcode: {str(e)}")
        if conn:
            conn.close()
        return None

def display_inventory_item(item, scanner_mode):
    """Display inventory item details and actions"""
    # Display item information
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**📋 Item Details:**")
        st.write(f"• **Patient:** {item['patient_name']}")
        st.write(f"• **Drug/Item:** {item['drug_item_name']}")
        st.write(f"• **Inventory #:** {item['inventory_number']}")
        st.write(f"• **Lot Number:** {item['lot_number']}")
        st.write(f"• **Location:** {item['location']}")
    
    with col2:
        st.write("**📅 Important Dates:**")
        st.write(f"• **Expiry:** {item['expiration_date']}")
        st.write(f"• **Service Date:** {item['date_of_service']}")
        st.write(f"• **Price:** ${item['purchase_price']:.2f}")
        
        # Show expiry status
        if item['expiration_date']:
            days_until_expiry = (item['expiration_date'] - datetime.now().date()).days
            if days_until_expiry < 0:
                st.error(f"⚠️ EXPIRED {abs(days_until_expiry)} days ago")
            elif days_until_expiry <= 7:
                st.warning(f"⚠️ Expires in {days_until_expiry} days")
            elif days_until_expiry <= 30:
                st.info(f"ℹ️ Expires in {days_until_expiry} days")
    
    # Actions based on scanner mode
    st.write("**🎯 Actions:**")
    
    if scanner_mode == "Lookup Only":
        st.info("Lookup mode - no actions available")
    
    elif scanner_mode == "Quick Update":
        show_quick_update_form(item)
    
    elif scanner_mode == "Full Edit":
        show_full_edit_form(item)

def show_quick_update_form(item):
    """Show quick update form for scanned item"""
    st.write("**⚡ Quick Update:**")
    
    with st.form(f"quick_update_{item['id']}"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            new_location = st.text_input("New Location", value=item['location'])
        
        with col2:
            dose_swapped = st.checkbox("Mark as Dose Swapped", value=bool(item['dose_swap_status']))
        
        with col3:
            notes = st.text_area("Notes", height=60)
        
        if st.form_submit_button("💾 Update Item"):
            try:
                update_data = {
                    'location': new_location,
                    'dose_swap_status': dose_swapped,
                    'updated_by': st.session_state.username,
                    'updated_at': datetime.now()
                }
                
                if notes:
                    update_data['notes'] = notes
                
                if update_inventory_record(item['id'], update_data):
                    st.success("✅ Item updated successfully!")
                    record_scan_action(item['id'], 'quick_update', update_data)
                else:
                    st.error("❌ Failed to update item")
            
            except Exception as e:
                st.error(f"Error updating item: {str(e)}")

def show_full_edit_form(item):
    """Show full edit form for scanned item"""
    st.write("**📝 Full Edit Mode:**")
    
    if st.button("🔓 Open Full Edit"):
        st.session_state.edit_item_id = item['id']
        st.switch_page("pages/inventory_management.py")

def show_create_new_item_option(barcode_data):
    """Show option to create new inventory item with scanned barcode"""
    st.write("**➕ Create New Item:**")
    
    if st.button("📝 Create New Inventory Item"):
        # Pre-populate form with barcode data
        st.session_state.new_item_barcode = barcode_data
        st.switch_page("pages/inventory_management.py")

def process_uploaded_image(uploaded_file):
    """Process uploaded image to extract barcode"""
    try:
        # Read image
        image = Image.open(uploaded_file)
        
        # Convert to OpenCV format
        opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Try using pyzbar for barcode detection
        try:
            from pyzbar import pyzbar
            
            # Convert to grayscale for better detection
            gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)
            
            # Detect and decode barcodes
            barcodes = pyzbar.decode(gray)
            
            if barcodes:
                return barcodes[0].data.decode('utf-8')
                
        except ImportError:
            # Fallback to OpenCV if pyzbar not available
            try:
                # Convert to grayscale
                gray = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2GRAY)
                
                # Use QRCodeDetector for QR codes
                detector = cv2.QRCodeDetector()
                retval, decoded_info, corners = detector.detectAndDecode(gray)
                
                if retval and decoded_info:
                    return decoded_info
            except:
                pass
        
        return None
        
    except Exception as e:
        st.error(f"Error processing image: {str(e)}")
        return None

def record_scan(barcode_data):
    """Record barcode scan in database"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # Create scan_history table if it doesn't exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id SERIAL PRIMARY KEY,
                barcode_data VARCHAR(255) NOT NULL,
                scanned_by VARCHAR(100),
                scan_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                found_in_inventory BOOLEAN,
                inventory_id INTEGER,
                action_taken VARCHAR(100)
            )
        """)
        
        # Check if barcode exists in inventory
        inventory_item = get_inventory_by_barcode(barcode_data)
        
        # Record scan
        cur.execute("""
            INSERT INTO scan_history (barcode_data, scanned_by, found_in_inventory, inventory_id)
            VALUES (%s, %s, %s, %s)
        """, (
            barcode_data,
            st.session_state.username,
            inventory_item is not None,
            inventory_item['id'] if inventory_item else None
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error recording scan: {str(e)}")
        if conn:
            conn.rollback()
            conn.close()

def record_scan_action(inventory_id, action, data):
    """Record action taken after scan"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # Update the most recent scan record
        cur.execute("""
            UPDATE scan_history 
            SET action_taken = %s
            WHERE inventory_id = %s 
            AND scanned_by = %s
            AND scan_timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
            ORDER BY scan_timestamp DESC
            LIMIT 1
        """, (action, inventory_id, st.session_state.username))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error recording scan action: {str(e)}")
        if conn:
            conn.close()

def show_scan_history():
    """Show scan history"""
    st.subheader("📋 Scan History")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        date_filter = st.date_input("From Date", value=datetime.now().date())
    
    with col2:
        user_filter = st.selectbox("Scanned By", ["All", st.session_state.username], key="scan_history_user")
    
    with col3:
        status_filter = st.selectbox("Status", ["All", "Found", "Not Found"], key="scan_history_status")
    
    # Get scan history
    scan_history = get_scan_history(date_filter, user_filter, status_filter)
    
    if scan_history:
        # Display history
        display_data = []
        for scan in scan_history:
            display_data.append({
                'Timestamp': scan['scan_timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'Barcode': scan['barcode_data'],
                'Scanned By': scan['scanned_by'],
                'Found': '✅' if scan['found_in_inventory'] else '❌',
                'Action': scan['action_taken'] or 'None',
                'Inventory ID': scan['inventory_id'] or 'N/A'
            })
        
        df = pd.DataFrame(display_data)
        st.dataframe(df, use_container_width=True)
        
        # Download option
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="📥 Download History CSV",
            data=csv_data,
            file_name=f"scan_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
        
    else:
        st.info("No scan history found for the selected criteria.")

def get_scan_history(date_filter, user_filter, status_filter):
    """Get scan history from database"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'scan_history'
            );
        """)
        
        if not cur.fetchone()[0]:
            cur.close()
            conn.close()
            return []
        
        # Build query
        query = "SELECT * FROM scan_history WHERE scan_timestamp >= %s"
        params = [date_filter]
        
        if user_filter != "All":
            query += " AND scanned_by = %s"
            params.append(user_filter)
        
        if status_filter == "Found":
            query += " AND found_in_inventory = true"
        elif status_filter == "Not Found":
            query += " AND found_in_inventory = false"
        
        query += " ORDER BY scan_timestamp DESC LIMIT 100"
        
        cur.execute(query, params)
        records = cur.fetchall()
        
        columns = [desc[0] for desc in cur.description]
        history = [dict(zip(columns, record)) for record in records]
        
        cur.close()
        conn.close()
        
        return history
        
    except Exception as e:
        st.error(f"Error fetching scan history: {str(e)}")
        if conn:
            conn.close()
        return []

def show_manual_lookup():
    """Show manual barcode lookup interface"""
    st.subheader("🔍 Manual Barcode Lookup")
    
    st.info("Enter barcode data manually to search inventory records")
    
    # Manual lookup form
    with st.form("manual_lookup"):
        lookup_value = st.text_input("Barcode/ID to lookup:", placeholder="Enter barcode, inventory number, lot number, etc.")
        lookup_field = st.selectbox(
            "Search in field:",
            ["All Fields", "Inventory Number", "Lot Number", "Order Number", "PO Number", "Invoice Number"]
        )
        
        if st.form_submit_button("🔍 Search"):
            if lookup_value:
                results = search_inventory_by_value(lookup_value, lookup_field)
                if results:
                    st.success(f"Found {len(results)} matching records:")
                    for item in results:
                        with st.expander(f"📦 {item['drug_item_name']} - {item['patient_name']}"):
                            display_inventory_item(item, "Lookup Only")
                else:
                    st.warning("No matching records found")

def search_inventory_by_value(value, field):
    """Search inventory by specific field value"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        
        if field == "All Fields":
            query = """
                SELECT * FROM inventory 
                WHERE inventory_number ILIKE %s 
                   OR lot_number::text ILIKE %s 
                   OR order_number::text ILIKE %s
                   OR po_number::text ILIKE %s
                   OR invoice_number::text ILIKE %s
                   OR drug_item_name ILIKE %s
                   OR patient_name ILIKE %s
                ORDER BY created_at DESC 
                LIMIT 10
            """
            search_pattern = f"%{value}%"
            params = [search_pattern] * 7
        else:
            field_mapping = {
                "Inventory Number": "inventory_number",
                "Lot Number": "lot_number::text",
                "Order Number": "order_number::text",
                "PO Number": "po_number::text",
                "Invoice Number": "invoice_number::text"
            }
            
            db_field = field_mapping[field]
            query = f"SELECT * FROM inventory WHERE {db_field} ILIKE %s ORDER BY created_at DESC LIMIT 10"
            params = [f"%{value}%"]
        
        cur.execute(query, params)
        results = cur.fetchall()
        
        columns = [desc[0] for desc in cur.description]
        items = [dict(zip(columns, result)) for result in results]
        
        cur.close()
        conn.close()
        
        return items
        
    except Exception as e:
        st.error(f"Error searching inventory: {str(e)}")
        if conn:
            conn.close()
        return []

def show_scanner_settings():
    """Show scanner settings and configuration"""
    st.subheader("⚙️ Scanner Settings")
    
    # Scanner preferences
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**📱 Scanner Preferences:**")
        
        default_mode = st.selectbox(
            "Default Scanner Mode",
            ["Lookup Only", "Quick Update", "Full Edit"],
            key="default_scanner_mode"
        )
        
        sound_enabled = st.checkbox("Enable scan sound by default", value=True, key="default_sound")
        
        auto_record = st.checkbox("Auto-record all scans", value=True, key="auto_record_scans")
        
    with col2:
        st.write("**🔍 Barcode Field Mapping:**")
        
        st.info("""
        The scanner searches for barcodes in these fields:
        • Inventory Number (primary)
        • Lot Number
        • Order Number
        • PO Number  
        • Invoice Number
        """)
    
    # Scan statistics
    st.subheader("📊 Scan Statistics")
    
    # Get scan stats
    scan_stats = get_scan_statistics()
    
    if scan_stats:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Scans", scan_stats.get('total_scans', 0))
        
        with col2:
            st.metric("Successful Finds", scan_stats.get('found_scans', 0))
        
        with col3:
            success_rate = (scan_stats.get('found_scans', 0) / scan_stats.get('total_scans', 1)) * 100
            st.metric("Success Rate", f"{success_rate:.1f}%")
        
        with col4:
            st.metric("Today's Scans", scan_stats.get('today_scans', 0))
    
    # Maintenance options
    st.subheader("🧹 Maintenance")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ Clear Scan History"):
            if clear_scan_history():
                st.success("Scan history cleared!")
    
    with col2:
        if st.button("📊 Export All Scans"):
            export_scan_data()

def get_scan_statistics():
    """Get scan statistics"""
    conn = get_db_connection()
    if not conn:
        return {}
    
    try:
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'scan_history'
            );
        """)
        
        if not cur.fetchone()[0]:
            cur.close()
            conn.close()
            return {}
        
        # Get statistics
        stats = {}
        
        # Total scans
        cur.execute("SELECT COUNT(*) FROM scan_history")
        stats['total_scans'] = cur.fetchone()[0]
        
        # Found scans
        cur.execute("SELECT COUNT(*) FROM scan_history WHERE found_in_inventory = true")
        stats['found_scans'] = cur.fetchone()[0]
        
        # Today's scans
        cur.execute("SELECT COUNT(*) FROM scan_history WHERE scan_timestamp >= CURRENT_DATE")
        stats['today_scans'] = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return stats
        
    except Exception as e:
        if conn:
            conn.close()
        return {}

def clear_scan_history():
    """Clear scan history"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM scan_history")
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return False

def export_scan_data():
    """Export scan data"""
    scan_history = get_scan_history(datetime.now().date() - timedelta(days=30), "All", "All")
    
    if scan_history:
        df = pd.DataFrame(scan_history)
        csv_data = df.to_csv(index=False)
        
        st.download_button(
            label="📥 Download Complete Scan Data",
            data=csv_data,
            file_name=f"complete_scan_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No scan data available to export")