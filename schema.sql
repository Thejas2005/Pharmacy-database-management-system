-- Database: Pharmacy

-- DROP DATABASE IF EXISTS "Pharmacy";

CREATE DATABASE "Pharmacy"
    WITH
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'English_India.1252'
    LC_CTYPE = 'English_India.1252'
    LOCALE_PROVIDER = 'libc'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1
    IS_TEMPLATE = False;

	-- Create the database (run separately, outside the current DB)
-- CREATE DATABASE pharmacy_management;

-- Switch to the database before running the below schema
-- \c pharmacy_management

-- Table: suppliers
CREATE TABLE suppliers (
    supplier_id SERIAL PRIMARY KEY,
    supplier_name VARCHAR(255),
    contact_person VARCHAR(255),
    phone_number VARCHAR(50),
    email CHARACTER VARYING(255),
    address TEXT,
    created_at TIMESTAMP WITH TIME ZONE
);

-- Table: employees
CREATE TABLE employees (
    username TEXT PRIMARY KEY,
    password VARCHAR(255),
    role VARCHAR(50)
);

-- Table: patients
CREATE TABLE patients (
    patient_id SERIAL PRIMARY KEY,
    full_name VARCHAR(255),
    date_of_birth DATE,
    gender CHARACTER VARYING(20),
    phone_number VARCHAR(50),
    email CHARACTER VARYING(255),
    address TEXT,
    allergies_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    last_updated_at TIMESTAMP WITH TIME ZONE
);

-- Table: medicines
CREATE TABLE medicines (
    ref_no TEXT PRIMARY KEY,
    medicine_name TEXT,
    issue_date DATE,
    exp_date DATE,
    stock_qty INTEGER,
    age_gap TEXT,
    uses TEXT,
    storage TEXT,
    price NUMERIC(10,2),
    dose TEXT
);

-- Table: purchase_orders
CREATE TABLE purchase_orders (
    order_id SERIAL PRIMARY KEY,
    supplier_id INTEGER REFERENCES suppliers(supplier_id),
    employee_username VARCHAR(100) REFERENCES employees(username),
    order_date DATE,
    expected_delivery_date DATE,
    status CHARACTER VARYING(50),
    total_cost NUMERIC(10,2)
);

-- Table: purchase_order_items
CREATE TABLE purchase_order_items (
    po_item_id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES purchase_orders(order_id),
    medicine_ref_no CHARACTER VARYING(50),
    medicine_name_ordered CHARACTER VARYING(255),
    quantity_ordered INTEGER,
    cost_price_per_unit NUMERIC(10,2),
    quantity_received INTEGER
);

-- Table: sales_transactions
CREATE TABLE sales_transactions (
    transaction_id SERIAL PRIMARY KEY,
    patient_name VARCHAR(255),
    employee_username VARCHAR(100) REFERENCES employees(username),
    transaction_date TIMESTAMP WITHOUT TIME ZONE,
    total_amount NUMERIC(10,2)
);

-- Table: sales_items
CREATE TABLE sales_items (
    item_id SERIAL PRIMARY KEY,
    transaction_id INTEGER REFERENCES sales_transactions(transaction_id),
    medicine_ref_no CHARACTER VARYING(50),
    medicine_name CHARACTER VARYING(255),
    quantity_sold INTEGER,
    unit_price NUMERIC(10,2),
    item_total NUMERIC(10,2)
);
