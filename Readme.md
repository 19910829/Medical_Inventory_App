# Overview

This is a comprehensive Inventory Management System built with Streamlit for healthcare/pharmaceutical inventory tracking. The application manages drug inventory records including patient information, medication details, expiration dates, and financial data. It features role-based authentication (admin/employee), document upload capabilities, analytics dashboards, and email notifications for inventory updates.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Framework**: Streamlit for web-based user interface
- **Page Structure**: Multi-page application with role-based navigation
  - Admin Dashboard: Full system analytics and user management
  - Employee Dashboard: Limited analytics and personal activity tracking
  - Inventory Management: CRUD operations for inventory records
  - Document Upload: File management and scanning integration
  - Reports: Analytics, data export, and email reporting
- **Authentication**: Session-based authentication with role-based access control
- **UI Components**: Streamlit widgets for forms, tables, charts, and file uploads

## Backend Architecture
- **Database Layer**: PostgreSQL with psycopg2 driver for data persistence
- **Authentication System**: bcrypt for password hashing and verification
- **Data Models**: 
  - Users table with role-based permissions (admin/employee)
  - Inventory table with comprehensive drug tracking fields
  - Document storage system for uploaded files
- **Business Logic**: Modular design with separate modules for auth, database, email, and utilities

## Data Storage Solutions
- **Primary Database**: PostgreSQL for structured inventory data
- **Schema Design**: 
  - Inventory records with patient info, drug details, dates, financial data
  - User management with roles and authentication
  - Audit trails with timestamps and user tracking
- **File Storage**: Local file system for document uploads with metadata tracking

## Authentication & Authorization
- **User Roles**: Two-tier system (admin/employee) with different permission levels
- **Password Security**: bcrypt hashing with salt for secure password storage
- **Session Management**: Streamlit session state for user authentication persistence
- **Default Accounts**: Auto-creation of admin and employee accounts on first run

## Core Features
- **Inventory Tracking**: Comprehensive drug inventory with expiration monitoring
- **Document Management**: File upload and scanning integration for inventory documentation
- **Analytics & Reporting**: Dashboard analytics with charts and data export capabilities
- **Email Notifications**: Automated notifications for inventory updates and reports
- **Search & Filtering**: Advanced search functionality across inventory records

# External Dependencies

## Third-Party Services
- **SendGrid**: Email service for notifications and reports
  - Requires SENDGRID_API_KEY environment variable
  - Used for inventory update notifications and automated reporting

## Database
- **PostgreSQL**: Primary database system
  - Connection via environment variables (PGHOST, PGDATABASE, PGUSER, PGPASSWORD, PGPORT)
  - Default connection assumes localhost setup

## Python Libraries
- **Core Framework**: streamlit for web interface
- **Database**: psycopg2 for PostgreSQL connectivity
- **Authentication**: bcrypt for password security
- **Data Processing**: pandas for data manipulation and analysis
- **Visualization**: plotly for charts and analytics
- **Email**: sendgrid for email services
- **Image Processing**: PIL (Pillow) for document image handling
- **Utilities**: Standard library modules (os, hashlib, datetime, re, io)

## Environment Configuration
- Database connection parameters via environment variables
- SendGrid API key for email functionality
- FROM_EMAIL configuration for notification sender address
- Flexible configuration supporting both local development and production deployment