import streamlit as st
import pandas as pd
import re
from datetime import datetime, date
import os
import hashlib
import io

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate phone number format"""
    pattern = r'^\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}$'
    return re.match(pattern, phone) is not None

def format_currency(amount):
    """Format amount as currency"""
    if amount is None:
        return "N/A"
    return f"${amount:,.2f}"

def format_date(date_obj):
    """Format date object as string"""
    if date_obj is None:
        return "N/A"
    if isinstance(date_obj, str):
        return date_obj
    return date_obj.strftime('%Y-%m-%d')

def generate_inventory_number(prefix="INV"):
    """Generate unique inventory number"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    hash_obj = hashlib.md5(timestamp.encode())
    hash_hex = hash_obj.hexdigest()[:6].upper()
    return f"{prefix}-{timestamp[-6:]}-{hash_hex}"

def validate_inventory_data(data):
    """Validate inventory data before database insertion"""
    errors = []
    
    # Required fields
    required_fields = ['patient_name', 'patient_id', 'drug_item_name']
    
    for field in required_fields:
        if not data.get(field):
            errors.append(f"{field.replace('_', ' ').title()} is required")
    
    # Validate patient_id is numeric
    if data.get('patient_id'):
        try:
            int(data['patient_id'])
        except (ValueError, TypeError):
            errors.append("Patient ID must be a valid number")
    
    # Validate dates
    date_fields = ['date_of_service', 'date_of_dispense', 'date_ordered', 'date_received', 'expiration_date']
    
    for field in date_fields:
        if data.get(field):
            if isinstance(data[field], str):
                try:
                    datetime.strptime(data[field], '%Y-%m-%d')
                except ValueError:
                    errors.append(f"{field.replace('_', ' ').title()} must be in YYYY-MM-DD format")
    
    # Validate purchase price
    if data.get('purchase_price'):
        try:
            float(data['purchase_price'])
        except (ValueError, TypeError):
            errors.append("Purchase price must be a valid number")
    
    # Validate numeric fields
    numeric_fields = ['order_number', 'invoice_number', 'po_number', 'lot_number']
    
    for field in numeric_fields:
        if data.get(field) and data[field] != '':
            try:
                int(data[field])
            except (ValueError, TypeError):
                errors.append(f"{field.replace('_', ' ').title()} must be a valid number")
    
    return errors

def sanitize_filename(filename):
    """Sanitize filename for safe storage"""
    # Remove or replace unsafe characters
    safe_chars = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limit length
    if len(safe_chars) > 255:
        name, ext = os.path.splitext(safe_chars)
        safe_chars = name[:255-len(ext)] + ext
    
    return safe_chars

def get_file_hash(file_content):
    """Generate hash for file content"""
    return hashlib.md5(file_content).hexdigest()

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def check_expiration_status(expiration_date):
    """Check expiration status of an item"""
    if not expiration_date:
        return "Unknown", "secondary"
    
    if isinstance(expiration_date, str):
        exp_date = datetime.strptime(expiration_date, '%Y-%m-%d').date()
    else:
        exp_date = expiration_date
    
    today = date.today()
    days_until_expiration = (exp_date - today).days
    
    if days_until_expiration < 0:
        return "Expired", "error"
    elif days_until_expiration <= 7:
        return "Expires Soon", "warning"
    elif days_until_expiration <= 30:
        return "Expiring", "info"
    else:
        return "Valid", "success"

def create_audit_log_entry(table_name, record_id, action, old_values=None, new_values=None, user=None):
    """Create audit log entry"""
    from database import get_db_connection
    
    conn = get_db_connection()
    if not conn:
        return False
    
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO audit_log (table_name, record_id, action, old_values, new_values, changed_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            table_name,
            record_id,
            action,
            old_values,
            new_values,
            user or 'system'
        ))
        
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"Failed to create audit log: {str(e)}")
        return False
        
    finally:
        cur.close()
        conn.close()

def export_to_excel(data, filename=None):
    """Export data to Excel format"""
    if filename is None:
        filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    # Convert data to DataFrame if it's not already
    if not isinstance(data, pd.DataFrame):
        df = pd.DataFrame(data)
    else:
        df = data
    
    # Create Excel file in memory
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Data', index=False)
        
        # Get workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Data']
        
        # Add some formatting
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        
        # Write headers with formatting
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Auto-adjust column widths
        for i, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).str.len().max(),
                len(str(col))
            )
            worksheet.set_column(i, i, min(max_length + 2, 50))
    
    return output.getvalue()

def parse_scanned_data(scanned_text, code_type):
    """Parse scanned barcode/QR code data"""
    parsed_data = {}
    
    if code_type == "Inventory Number":
        parsed_data['inventory_number'] = scanned_text.strip()
    
    elif code_type == "Patient ID":
        # Extract numeric ID
        patient_id = re.search(r'\d+', scanned_text)
        if patient_id:
            parsed_data['patient_id'] = int(patient_id.group())
    
    elif code_type == "QR Code":
        # Assume QR code contains structured data
        # Format: field1=value1;field2=value2;...
        pairs = scanned_text.split(';')
        for pair in pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                parsed_data[key.strip().lower()] = value.strip()
    
    else:
        # Generic parsing
        parsed_data['scanned_data'] = scanned_text.strip()
    
    return parsed_data

def get_system_health():
    """Get basic system health metrics"""
    health = {
        'database_connection': False,
        'file_system': False,
        'email_service': False
    }
    
    # Test database connection
    try:
        from database import get_db_connection
        conn = get_db_connection()
        if conn:
            conn.close()
            health['database_connection'] = True
    except Exception:
        pass
    
    # Test file system
    try:
        test_dir = "uploads"
        if not os.path.exists(test_dir):
            os.makedirs(test_dir)
        
        test_file = os.path.join(test_dir, "health_check.txt")
        with open(test_file, 'w') as f:
            f.write("health check")
        
        if os.path.exists(test_file):
            os.remove(test_file)
            health['file_system'] = True
    except Exception:
        pass
    
    # Test email service
    try:
        from email_service import get_sendgrid_client
        sg = get_sendgrid_client()
        if sg:
            health['email_service'] = True
    except Exception:
        pass
    
    return health

def log_user_activity(user, action, details=None):
    """Log user activity for audit purposes"""
    try:
        from database import get_db_connection
        
        conn = get_db_connection()
        if not conn:
            return
        
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO user_activity (username, action, details, timestamp)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (user, action, details, datetime.now()))
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception:
        # Don't fail the main operation if logging fails
        pass
