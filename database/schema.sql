-- Smart IMS — Database Schema
-- Run this in MySQL Workbench (or any MySQL client) to create a fresh
-- copy of the database structure used by this project.

CREATE DATABASE IF NOT EXISTS smart_ims;
USE smart_ims;

-- ============================================================
-- users — login credentials and role
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'staff') DEFAULT 'staff',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- suppliers — supplier directory
-- (created before products, since products references it)
-- ============================================================
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    contact_person VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(100),
    address VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- products — catalog and live stock
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    sku VARCHAR(50) UNIQUE,
    price DECIMAL(10,2) NOT NULL DEFAULT 0,
    quantity INT NOT NULL DEFAULT 0,
    reorder_level INT NOT NULL DEFAULT 10,
    supplier VARCHAR(100),
    supplier_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);

-- ============================================================
-- transactions — every purchase/sale, with automatic stock adjustment
-- ============================================================
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    type ENUM('purchase', 'sale') NOT NULL,
    quantity INT NOT NULL,
    transaction_date DATE NOT NULL,
    notes VARCHAR(255),
    payment_method VARCHAR(30) NULL,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- ============================================================
-- payments — supplier payment records (Online/Card/UPI or Cash on Delivery)
-- ============================================================
CREATE TABLE IF NOT EXISTS payments (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    payment_method ENUM('Online', 'Cash on Delivery') NOT NULL,
    payment_mode VARCHAR(20) NULL,
    payment_reference VARCHAR(50) NULL,
    status VARCHAR(20) DEFAULT 'Success',
    payment_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);