import psycopg2
import os
from psycopg2.extras import RealDictCursor
import streamlit as st

def get_db_connection():
    """Get database connection using environment variables"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('PGHOST', 'localhost'),
            database=os.getenv('PGDATABASE', 'inventory_db'),
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', 'password'),
            port=os.getenv('PGPORT', '5432')
        )
        return conn
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return None

def init_database():
    """Initialize database tables"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # Create inventory table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id SERIAL PRIMARY KEY,
                patient_name VARCHAR(255) NOT NULL,
                patient_id INTEGER NOT NULL,
                administration_location VARCHAR(255),
                drug_item_name VARCHAR(255) NOT NULL,
                date_of_service DATE,
                date_of_dispense DATE,
                date_ordered DATE,
                date_received DATE,
                order_number BIGINT,
                invoice_number BIGINT,
                po_number BIGINT,
                lot_number BIGINT,
                expiration_date DATE,
                inventory_number VARCHAR(50) UNIQUE,
                inventory_type VARCHAR(100),
                purchase_price DECIMAL(10,2) DEFAULT 50.00,
                provider VARCHAR(255),
                location VARCHAR(255),
                inventory_site VARCHAR(255),
                username VARCHAR(100),
                dose_swap_status BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by VARCHAR(100),
                updated_by VARCHAR(100)
            )
        """)
        
        # Create documents table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                file_path VARCHAR(500),
                file_size INTEGER,
                file_type VARCHAR(50),
                inventory_id INTEGER REFERENCES inventory(id),
                uploaded_by VARCHAR(100),
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        """)
        
        # Create audit log table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                table_name VARCHAR(50),
                record_id INTEGER,
                action VARCHAR(20),
                old_values JSONB,
                new_values JSONB,
                changed_by VARCHAR(100),
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create trigger function for audit logging with proper error handling
        try:
            cur.execute("""
                CREATE OR REPLACE FUNCTION audit_trigger_func()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF TG_OP = 'INSERT' THEN
                        INSERT INTO audit_log (table_name, record_id, action, new_values, changed_by)
                        VALUES (TG_TABLE_NAME, NEW.id, 'INSERT', row_to_json(NEW), COALESCE(NEW.created_by, 'system'));
                        RETURN NEW;
                    ELSIF TG_OP = 'UPDATE' THEN
                        INSERT INTO audit_log (table_name, record_id, action, old_values, new_values, changed_by)
                        VALUES (TG_TABLE_NAME, NEW.id, 'UPDATE', row_to_json(OLD), row_to_json(NEW), COALESCE(NEW.updated_by, 'system'));
                        RETURN NEW;
                    ELSIF TG_OP = 'DELETE' THEN
                        INSERT INTO audit_log (table_name, record_id, action, old_values, changed_by)
                        VALUES (TG_TABLE_NAME, OLD.id, 'DELETE', row_to_json(OLD), 'system');
                        RETURN OLD;
                    END IF;
                    RETURN NULL;
                END;
                $$ LANGUAGE plpgsql;
            """)
            
            # Create triggers with proper conflict handling
            cur.execute("""
                DO $$
                BEGIN
                    DROP TRIGGER IF EXISTS inventory_audit_trigger ON inventory;
                    CREATE TRIGGER inventory_audit_trigger
                    AFTER INSERT OR UPDATE OR DELETE ON inventory
                    FOR EACH ROW EXECUTE FUNCTION audit_trigger_func();
                EXCEPTION
                    WHEN others THEN
                        -- Log the error but don't fail the initialization
                        RAISE NOTICE 'Warning: Could not create audit trigger: %', SQLERRM;
                END $$;
            """)
            
        except Exception as trigger_error:
            # If trigger creation fails, log but continue
            print(f"Warning: Could not create audit triggers: {trigger_error}")
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        raise e

def get_inventory_records(filters=None, limit=None):
    """Get inventory records with optional filters"""
    conn = get_db_connection()
    if not conn:
        return []
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    query = "SELECT * FROM inventory WHERE 1=1"
    params = []
    
    if filters:
        if filters.get('patient_name'):
            query += " AND patient_name ILIKE %s"
            params.append(f"%{filters['patient_name']}%")
        
        if filters.get('drug_item_name'):
            query += " AND drug_item_name ILIKE %s"
            params.append(f"%{filters['drug_item_name']}%")
        
        if filters.get('inventory_type'):
            query += " AND inventory_type = %s"
            params.append(filters['inventory_type'])
        
        if filters.get('date_from'):
            query += " AND date_of_service >= %s"
            params.append(filters['date_from'])
        
        if filters.get('date_to'):
            query += " AND date_of_service <= %s"
            params.append(filters['date_to'])
    
    query += " ORDER BY created_at DESC"
    
    if limit:
        query += f" LIMIT {limit}"
    
    cur.execute(query, params)
    records = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return records

def insert_inventory_record(data):
    """Insert new inventory record"""
    conn = get_db_connection()
    if not conn:
        return False
    
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO inventory (
                patient_name, patient_id, administration_location, drug_item_name,
                date_of_service, date_of_dispense, date_ordered, date_received,
                order_number, invoice_number, po_number, lot_number,
                expiration_date, inventory_number, inventory_type, purchase_price,
                provider, location, inventory_site, username, dose_swap_status,
                created_by, updated_by
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id
        """, (
            data['patient_name'], data['patient_id'], data['administration_location'],
            data['drug_item_name'], data['date_of_service'], data['date_of_dispense'],
            data['date_ordered'], data['date_received'], data['order_number'],
            data['invoice_number'], data['po_number'], data['lot_number'],
            data['expiration_date'], data['inventory_number'], data['inventory_type'],
            data['purchase_price'], data['provider'], data['location'],
            data['inventory_site'], data['username'], data['dose_swap_status'],
            data['created_by'], data['updated_by']
        ))
        
        record_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return record_id
        
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise e

def update_inventory_record(record_id, data):
    """Update existing inventory record"""
    conn = get_db_connection()
    if not conn:
        return False
    
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE inventory SET
                patient_name = %s, patient_id = %s, administration_location = %s,
                drug_item_name = %s, date_of_service = %s, date_of_dispense = %s,
                date_ordered = %s, date_received = %s, order_number = %s,
                invoice_number = %s, po_number = %s, lot_number = %s,
                expiration_date = %s, inventory_number = %s, inventory_type = %s,
                purchase_price = %s, provider = %s, location = %s,
                inventory_site = %s, username = %s, dose_swap_status = %s,
                updated_by = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data['patient_name'], data['patient_id'], data['administration_location'],
            data['drug_item_name'], data['date_of_service'], data['date_of_dispense'],
            data['date_ordered'], data['date_received'], data['order_number'],
            data['invoice_number'], data['po_number'], data['lot_number'],
            data['expiration_date'], data['inventory_number'], data['inventory_type'],
            data['purchase_price'], data['provider'], data['location'],
            data['inventory_site'], data['username'], data['dose_swap_status'],
            data['updated_by'], record_id
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise e

def get_inventory_stats():
    """Get inventory statistics"""
    conn = get_db_connection()
    if not conn:
        return {}
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    stats = {}
    
    # Total records
    cur.execute("SELECT COUNT(*) as count FROM inventory")
    stats['total_records'] = cur.fetchone()['count']
    
    # Records by type
    cur.execute("SELECT inventory_type, COUNT(*) as count FROM inventory GROUP BY inventory_type")
    stats['by_type'] = cur.fetchall()
    
    # Recent activity
    cur.execute("SELECT COUNT(*) as count FROM inventory WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'")
    stats['recent_additions'] = cur.fetchone()['count']
    
    # Expiring items (within 30 days)
    cur.execute("SELECT COUNT(*) as count FROM inventory WHERE expiration_date <= CURRENT_DATE + INTERVAL '30 days' AND expiration_date > CURRENT_DATE")
    stats['expiring_soon'] = cur.fetchone()['count']
    
    cur.close()
    conn.close()
    
    return stats
