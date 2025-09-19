import streamlit as st
import os
from auth import authenticate_user, hash_password, create_user_table
from database import init_database
import pandas as pd

# Initialize database and user table
init_database()
create_user_table()

def main():
    st.set_page_config(
        page_title="Inventory Management System",
        page_icon="📋",
        layout="wide"
    )
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'username' not in st.session_state:
        st.session_state.username = None
    
    # Authentication
    if not st.session_state.authenticated:
        show_login_page()
    else:
        show_main_app()

def show_login_page():
    st.title("🔐 Inventory Management System Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.subheader("Please Login to Continue")
        
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        col_login, col_register = st.columns(2)
        
        with col_login:
            if st.button("Login", use_container_width=True):
                if username and password:
                    user = authenticate_user(username, password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user_role = user['role']
                        st.session_state.username = username
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                else:
                    st.warning("Please enter both username and password")
        
        with col_register:
            if st.button("Register New User", use_container_width=True):
                st.session_state.show_register = True
                st.rerun()
    
    # Registration form
    if 'show_register' in st.session_state and st.session_state.show_register:
        with col2:
            st.subheader("Register New User")
            reg_username = st.text_input("New Username", key="reg_username")
            reg_password = st.text_input("New Password", type="password", key="reg_password")
            # Security: Only employees can be created via self-registration
            reg_role = "employee"
            st.info("New users are created with Employee role by default. Contact an admin to upgrade permissions.")
            
            col_save, col_cancel = st.columns(2)
            
            with col_save:
                if st.button("Create User", use_container_width=True):
                    if reg_username and reg_password:
                        from database import get_db_connection
                        conn = get_db_connection()
                        cur = conn.cursor()
                        
                        # Check if user exists
                        cur.execute("SELECT username FROM users WHERE username = %s", (reg_username,))
                        if cur.fetchone():
                            st.error("Username already exists")
                        else:
                            hashed_pw = hash_password(reg_password)
                            cur.execute(
                                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                                (reg_username, hashed_pw, reg_role)
                            )
                            conn.commit()
                            st.success("User created successfully!")
                            st.session_state.show_register = False
                            st.rerun()
                        
                        cur.close()
                        conn.close()
                    else:
                        st.warning("Please fill all fields")
            
            with col_cancel:
                if st.button("Cancel", use_container_width=True):
                    st.session_state.show_register = False
                    st.rerun()

def show_main_app():
    # Header
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.title("📋 Inventory Management System")
    
    with col2:
        st.write(f"Welcome, **{st.session_state.username}** ({st.session_state.user_role})")
    
    with col3:
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.user_role = None
            st.session_state.username = None
            st.rerun()
    
    st.divider()
    
    # Navigation
    if st.session_state.user_role == "admin":
        show_admin_interface()
    else:
        show_employee_interface()

def show_admin_interface():
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "📊 Dashboard", 
        "📦 Inventory Management", 
        "📄 Document Upload", 
        "📂 Bulk Import",
        "📱 Barcode Scanner",
        "🚨 Alerts",
        "📈 Reports & Export",
        "📋 Audit Trail",
        "👥 User Management"
    ])
    
    with tab1:
        from pages.admin_dashboard import show_admin_dashboard
        show_admin_dashboard()
    
    with tab2:
        from pages.inventory_management import show_inventory_management
        show_inventory_management()
    
    with tab3:
        from pages.document_upload import show_document_upload
        show_document_upload()
    
    with tab4:
        from pages.bulk_import import show_bulk_import
        show_bulk_import()
    
    with tab5:
        from pages.barcode_scanner import show_barcode_scanner
        show_barcode_scanner()
    
    with tab6:
        from pages.alerts import show_alerts
        show_alerts()
    
    with tab7:
        from pages.reports import show_reports
        show_reports()
    
    with tab8:
        from pages.audit_trail import show_audit_trail
        show_audit_trail()
    
    with tab9:
        show_user_management()

def show_employee_interface():
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Dashboard", 
        "📦 Inventory Management", 
        "📄 Document Upload", 
        "📈 Reports"
    ])
    
    with tab1:
        from pages.employee_dashboard import show_employee_dashboard
        show_employee_dashboard()
    
    with tab2:
        from pages.inventory_management import show_inventory_management
        show_inventory_management()
    
    with tab3:
        from pages.document_upload import show_document_upload
        show_document_upload()
    
    with tab4:
        from pages.reports import show_reports
        show_reports()

def show_user_management():
    st.subheader("👥 User Management")
    
    from database import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Display users
    cur.execute("SELECT username, role, created_at FROM users ORDER BY created_at DESC")
    users = cur.fetchall()
    
    if users:
        df = pd.DataFrame(users, columns=['Username', 'Role', 'Created At'])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No users found")
    
    # Add new user form
    st.subheader("Add New User")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        new_username = st.text_input("Username")
    with col2:
        new_password = st.text_input("Password", type="password")
    with col3:
        new_role = st.selectbox("Role", ["employee", "admin"])
    
    if st.button("Add User"):
        if new_username and new_password:
            # Check if user exists
            cur.execute("SELECT username FROM users WHERE username = %s", (new_username,))
            if cur.fetchone():
                st.error("Username already exists")
            else:
                hashed_pw = hash_password(new_password)
                cur.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                    (new_username, hashed_pw, new_role)
                )
                conn.commit()
                st.success("User added successfully!")
                st.rerun()
        else:
            st.warning("Please fill all fields")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
