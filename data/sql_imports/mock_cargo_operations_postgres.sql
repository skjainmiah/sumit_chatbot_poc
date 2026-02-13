-- ============================================================
-- Cargo Operations Database (PostgreSQL Dialect)
-- Database: cargo_operations
-- 3 tables: cargo_shipments, cargo_containers, cargo_handling_staff
-- ============================================================

-- Connect to default database first to create new database
-- \c postgres

-- Drop and create database
DROP DATABASE IF EXISTS cargo_operations;
CREATE DATABASE cargo_operations;

-- Connect to the new database
-- \c cargo_operations

-- ============================================================
-- Table 1: cargo_handling_staff
-- ============================================================
DROP TABLE IF EXISTS cargo_handling_staff CASCADE;

CREATE TABLE cargo_handling_staff (
    staff_id SERIAL PRIMARY KEY,
    employee_id VARCHAR(20) NOT NULL UNIQUE,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    role VARCHAR(50) NOT NULL,
    certification_level VARCHAR(20) NOT NULL DEFAULT 'Standard',
    hazmat_certified BOOLEAN NOT NULL DEFAULT FALSE,
    live_animal_certified BOOLEAN NOT NULL DEFAULT FALSE,
    base_airport VARCHAR(10) NOT NULL,
    shift VARCHAR(20) NOT NULL DEFAULT 'Day',
    hire_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Active',
    supervisor_id VARCHAR(20),
    hourly_rate_usd DECIMAL(6,2) NOT NULL
);

INSERT INTO cargo_handling_staff (employee_id, first_name, last_name, role, certification_level, hazmat_certified, live_animal_certified, base_airport, shift, hire_date, status, supervisor_id, hourly_rate_usd) VALUES
('CG-3001', 'Marcus', 'Johnson', 'Cargo Supervisor', 'Senior', TRUE, TRUE, 'DFW', 'Day', '2010-05-15', 'Active', NULL, 38.50),
('CG-3002', 'Elena', 'Rodriguez', 'Load Planner', 'Senior', TRUE, FALSE, 'DFW', 'Day', '2014-08-22', 'Active', 'CG-3001', 32.00),
('CG-3003', 'William', 'Chen', 'Cargo Handler', 'Standard', FALSE, FALSE, 'DFW', 'Day', '2019-03-10', 'Active', 'CG-3001', 24.50),
('CG-3004', 'Aisha', 'Patel', 'Cargo Handler', 'Standard', TRUE, FALSE, 'DFW', 'Night', '2020-11-05', 'Active', 'CG-3001', 25.50),
('CG-3005', 'Robert', 'Williams', 'Cargo Supervisor', 'Senior', TRUE, TRUE, 'ORD', 'Day', '2008-02-28', 'Active', NULL, 40.00),
('CG-3006', 'Jennifer', 'Kim', 'Load Planner', 'Senior', TRUE, TRUE, 'ORD', 'Day', '2012-07-14', 'Active', 'CG-3005', 33.50),
('CG-3007', 'David', 'Brown', 'Cargo Handler', 'Standard', FALSE, TRUE, 'ORD', 'Swing', '2021-06-01', 'Active', 'CG-3005', 24.00),
('CG-3008', 'Maria', 'Garcia', 'Cargo Handler', 'Advanced', TRUE, TRUE, 'MIA', 'Day', '2016-09-20', 'Active', 'CG-3010', 28.00),
('CG-3009', 'James', 'Taylor', 'Cargo Handler', 'Standard', FALSE, FALSE, 'MIA', 'Night', '2022-01-15', 'Active', 'CG-3010', 23.50),
('CG-3010', 'Patricia', 'Martinez', 'Cargo Supervisor', 'Senior', TRUE, TRUE, 'MIA', 'Day', '2009-11-30', 'Active', NULL, 39.00),
('CG-3011', 'Michael', 'Lee', 'Load Planner', 'Advanced', TRUE, FALSE, 'LAX', 'Day', '2017-04-12', 'Active', 'CG-3012', 31.00),
('CG-3012', 'Susan', 'Anderson', 'Cargo Supervisor', 'Senior', TRUE, TRUE, 'LAX', 'Day', '2011-08-05', 'Active', NULL, 38.00),
('CG-3013', 'Kevin', 'Thompson', 'Cargo Handler', 'Advanced', TRUE, FALSE, 'LAX', 'Night', '2018-12-10', 'Active', 'CG-3012', 27.50),
('CG-3014', 'Lisa', 'White', 'Cargo Handler', 'Standard', FALSE, TRUE, 'DFW', 'Swing', '2023-02-20', 'Active', 'CG-3001', 24.00),
('CG-3015', 'Daniel', 'Harris', 'Load Planner', 'Standard', FALSE, FALSE, 'MIA', 'Night', '2022-08-08', 'Active', 'CG-3010', 28.50);

-- ============================================================
-- Table 2: cargo_containers
-- ============================================================
DROP TABLE IF EXISTS cargo_containers CASCADE;

CREATE TABLE cargo_containers (
    container_id SERIAL PRIMARY KEY,
    container_number VARCHAR(20) NOT NULL UNIQUE,
    container_type VARCHAR(30) NOT NULL,
    max_weight_kg DECIMAL(8,2) NOT NULL,
    tare_weight_kg DECIMAL(6,2) NOT NULL,
    dimensions_cm VARCHAR(30) NOT NULL,
    aircraft_compatibility VARCHAR(100) NOT NULL,
    current_status VARCHAR(20) NOT NULL DEFAULT 'Available',
    current_location VARCHAR(10),
    last_inspection_date DATE NOT NULL,
    next_inspection_due DATE NOT NULL,
    owner VARCHAR(50) NOT NULL DEFAULT 'American Airlines',
    is_temperature_controlled BOOLEAN NOT NULL DEFAULT FALSE,
    condition_rating VARCHAR(10) NOT NULL DEFAULT 'Good'
);

INSERT INTO cargo_containers (container_number, container_type, max_weight_kg, tare_weight_kg, dimensions_cm, aircraft_compatibility, current_status, current_location, last_inspection_date, next_inspection_due, owner, is_temperature_controlled, condition_rating) VALUES
('AKE-AA-0001', 'LD3', 1588.00, 70.00, '156x153x163', 'A320/A321/B737/B787/B777', 'In Use', 'DFW', '2024-12-15', '2025-06-15', 'American Airlines', FALSE, 'Good'),
('AKE-AA-0002', 'LD3', 1588.00, 70.00, '156x153x163', 'A320/A321/B737/B787/B777', 'Available', 'DFW', '2025-01-10', '2025-07-10', 'American Airlines', FALSE, 'Good'),
('AKE-AA-0003', 'LD3', 1588.00, 70.00, '156x153x163', 'A320/A321/B737/B787/B777', 'In Use', 'ORD', '2024-11-20', '2025-05-20', 'American Airlines', FALSE, 'Good'),
('PMC-AA-0001', 'P1P', 4626.00, 105.00, '318x224x163', 'B777/B787', 'Available', 'DFW', '2025-01-05', '2025-07-05', 'American Airlines', FALSE, 'Excellent'),
('PMC-AA-0002', 'P1P', 4626.00, 105.00, '318x224x163', 'B777/B787', 'In Use', 'LAX', '2024-12-01', '2025-06-01', 'American Airlines', FALSE, 'Good'),
('RKN-AA-0001', 'LD3 Reefer', 1400.00, 180.00, '156x153x163', 'A320/A321/B737/B787/B777', 'Available', 'MIA', '2025-01-08', '2025-04-08', 'American Airlines', TRUE, 'Excellent'),
('RKN-AA-0002', 'LD3 Reefer', 1400.00, 180.00, '156x153x163', 'A320/A321/B737/B787/B777', 'In Use', 'MIA', '2024-12-20', '2025-03-20', 'American Airlines', TRUE, 'Good'),
('AKE-AA-0004', 'LD3', 1588.00, 70.00, '156x153x163', 'A320/A321/B737/B787/B777', 'Maintenance', 'DFW', '2024-10-15', '2025-01-30', 'American Airlines', FALSE, 'Fair'),
('ALP-AA-0001', 'LD26 Pallet', 6033.00, 120.00, '318x224x163', 'B777/B787', 'Available', 'ORD', '2025-01-12', '2025-07-12', 'American Airlines', FALSE, 'Excellent'),
('ALP-AA-0002', 'LD26 Pallet', 6033.00, 120.00, '318x224x163', 'B777/B787', 'In Use', 'DFW', '2024-11-25', '2025-05-25', 'American Airlines', FALSE, 'Good'),
('HMA-AA-0001', 'LD3 Hazmat', 1400.00, 90.00, '156x153x163', 'B737/B787/B777', 'Available', 'DFW', '2025-01-15', '2025-04-15', 'American Airlines', FALSE, 'Excellent'),
('AVI-AA-0001', 'LD3 Animal', 1200.00, 85.00, '156x153x163', 'B737/B787/B777', 'Available', 'LAX', '2025-01-02', '2025-04-02', 'American Airlines', TRUE, 'Good'),
('AKE-AA-0005', 'LD3', 1588.00, 70.00, '156x153x163', 'A320/A321/B737/B787/B777', 'In Transit', 'JFK', '2024-12-28', '2025-06-28', 'American Airlines', FALSE, 'Good'),
('PMC-AA-0003', 'P1P', 4626.00, 105.00, '318x224x163', 'B777/B787', 'In Transit', 'LHR', '2025-01-03', '2025-07-03', 'American Airlines', FALSE, 'Good'),
('AKE-LH-0001', 'LD3', 1588.00, 72.00, '156x153x163', 'A320/A321/B737/B787/B777', 'Available', 'ORD', '2024-12-10', '2025-06-10', 'Lufthansa', FALSE, 'Good');

-- ============================================================
-- Table 3: cargo_shipments
-- ============================================================
DROP TABLE IF EXISTS cargo_shipments CASCADE;

CREATE TABLE cargo_shipments (
    shipment_id SERIAL PRIMARY KEY,
    awb_number VARCHAR(20) NOT NULL UNIQUE,
    shipper_name VARCHAR(100) NOT NULL,
    consignee_name VARCHAR(100) NOT NULL,
    origin_airport VARCHAR(10) NOT NULL,
    destination_airport VARCHAR(10) NOT NULL,
    flight_number VARCHAR(10),
    shipment_type VARCHAR(30) NOT NULL,
    commodity_description VARCHAR(200) NOT NULL,
    piece_count INT NOT NULL,
    gross_weight_kg DECIMAL(8,2) NOT NULL,
    chargeable_weight_kg DECIMAL(8,2) NOT NULL,
    volume_cbm DECIMAL(6,3),
    container_id VARCHAR(20),
    special_handling_codes VARCHAR(50),
    declared_value_usd DECIMAL(12,2),
    status VARCHAR(30) NOT NULL DEFAULT 'Booked',
    booked_date TIMESTAMP NOT NULL,
    departure_date TIMESTAMP,
    arrival_date TIMESTAMP,
    delivered_date TIMESTAMP,
    handler_employee_id VARCHAR(20),
    priority VARCHAR(20) NOT NULL DEFAULT 'Standard',
    revenue_usd DECIMAL(10,2) NOT NULL
);

INSERT INTO cargo_shipments (awb_number, shipper_name, consignee_name, origin_airport, destination_airport, flight_number, shipment_type, commodity_description, piece_count, gross_weight_kg, chargeable_weight_kg, volume_cbm, container_id, special_handling_codes, declared_value_usd, status, booked_date, departure_date, arrival_date, delivered_date, handler_employee_id, priority, revenue_usd) VALUES
('001-12345678', 'TechCorp Industries', 'Samsung Electronics', 'DFW', 'ICN', 'AA280', 'General Cargo', 'Electronic components - semiconductors', 45, 680.50, 850.00, 2.850, 'AKE-AA-0001', 'ELI', 125000.00, 'Delivered', '2025-01-10 08:00:00', '2025-01-12 14:30:00', '2025-01-13 18:45:00', '2025-01-14 10:00:00', 'CG-3002', 'Express', 4250.00),
('001-12345679', 'FreshFarms LLC', 'Restaurant Depot UK', 'MIA', 'LHR', 'AA106', 'Perishable', 'Fresh seafood - lobster tails', 20, 450.00, 520.00, 1.200, 'RKN-AA-0002', 'PER/COL', 18500.00, 'In Transit', '2025-01-25 06:00:00', '2025-01-27 19:00:00', NULL, NULL, 'CG-3008', 'Express', 2860.00),
('001-12345680', 'AutoParts Global', 'BMW Manufacturing', 'ORD', 'MUC', 'AA70', 'General Cargo', 'Automotive spare parts - engine components', 85, 1250.00, 1250.00, 3.500, 'PMC-AA-0002', NULL, 45000.00, 'Manifested', '2025-01-26 10:00:00', '2025-01-28 21:00:00', NULL, NULL, 'CG-3006', 'Standard', 3125.00),
('001-12345681', 'PharmaCare Inc', 'NHS Trust London', 'DFW', 'LHR', 'AA50', 'Pharma', 'Temperature-sensitive vaccines', 12, 85.00, 200.00, 0.450, 'RKN-AA-0001', 'PIL/COL/TIM', 280000.00, 'Booked', '2025-01-27 14:00:00', NULL, NULL, NULL, 'CG-3004', 'Critical', 1800.00),
('001-12345682', 'PetWorld Transport', 'Tokyo Zoo', 'LAX', 'NRT', 'AA175', 'Live Animal', 'Live tropical fish - 50 bags', 50, 120.00, 300.00, 0.800, 'AVI-AA-0001', 'AVI/LHO', 8500.00, 'Accepted', '2025-01-26 09:00:00', NULL, NULL, NULL, 'CG-3013', 'Express', 1650.00),
('001-12345683', 'ChemSolutions Ltd', 'BASF Germany', 'DFW', 'FRA', 'AA72', 'Dangerous Goods', 'Class 3 flammable liquids - paint samples', 8, 95.00, 95.00, 0.280, 'HMA-AA-0001', 'RFL/CAO', 3200.00, 'Booked', '2025-01-27 11:00:00', NULL, NULL, NULL, 'CG-3002', 'Standard', 580.00),
('001-12345684', 'Fashion House Milan', 'Nordstrom Corp', 'MXP', 'DFW', 'AA237', 'General Cargo', 'High-fashion garments - spring collection', 120, 380.00, 650.00, 2.100, 'AKE-AA-0003', 'VAL', 95000.00, 'Delivered', '2025-01-15 07:00:00', '2025-01-16 10:00:00', '2025-01-16 18:30:00', '2025-01-17 09:00:00', 'CG-3003', 'Priority', 2925.00),
('001-12345685', 'Medical Devices Inc', 'Apollo Hospitals', 'ORD', 'DEL', 'AA292', 'Pharma', 'MRI machine components', 6, 890.00, 1200.00, 4.200, 'PMC-AA-0001', 'HEA', 520000.00, 'Manifested', '2025-01-24 15:00:00', '2025-01-28 23:30:00', NULL, NULL, 'CG-3005', 'Critical', 6000.00),
('001-12345686', 'Vintage Wines Co', 'Wine Merchant Tokyo', 'LAX', 'NRT', 'AA169', 'Perishable', 'Fine wines - Napa Valley collection', 48, 720.00, 720.00, 1.800, 'AKE-AA-0005', 'PER', 42000.00, 'In Transit', '2025-01-23 12:00:00', '2025-01-25 16:00:00', NULL, NULL, 'CG-3011', 'Priority', 2520.00),
('001-12345687', 'SportsGear Unlimited', 'Decathlon France', 'MIA', 'CDG', 'AA44', 'General Cargo', 'Sports equipment - golf clubs and bags', 200, 1650.00, 2200.00, 6.500, 'ALP-AA-0002', NULL, 28000.00, 'Accepted', '2025-01-26 08:00:00', NULL, NULL, NULL, 'CG-3010', 'Standard', 4400.00),
('001-12345688', 'Aerospace Components LLC', 'Airbus Hamburg', 'DFW', 'HAM', 'AA74', 'General Cargo', 'Aircraft interior panels - certified parts', 35, 420.00, 580.00, 1.950, 'AKE-AA-0002', 'AOG', 75000.00, 'Booked', '2025-01-28 06:00:00', NULL, NULL, NULL, 'CG-3001', 'Critical', 3190.00),
('001-12345689', 'Flower Express NL', 'Whole Foods Market', 'AMS', 'ORD', 'AA241', 'Perishable', 'Fresh cut flowers - tulips and roses', 80, 320.00, 480.00, 1.600, 'RKN-AA-0001', 'PER/FLO', 12000.00, 'Delivered', '2025-01-20 04:00:00', '2025-01-20 09:00:00', '2025-01-20 15:30:00', '2025-01-20 18:00:00', 'CG-3007', 'Express', 1920.00),
('001-12345690', 'E-Commerce Giant', 'Distribution Center West', 'JFK', 'LAX', 'AA1', 'E-Commerce', 'Mixed consumer goods - electronics and apparel', 350, 2800.00, 3500.00, 12.000, 'ALP-AA-0001', NULL, 85000.00, 'Delivered', '2025-01-22 11:00:00', '2025-01-22 14:30:00', '2025-01-22 17:45:00', '2025-01-22 20:00:00', 'CG-3012', 'Standard', 5250.00),
('001-12345691', 'Art Gallery NYC', 'Louvre Museum', 'JFK', 'CDG', 'AA48', 'Valuable', 'Fine art paintings - insured shipment', 3, 45.00, 200.00, 0.650, 'AKE-AA-0001', 'VAL/ART', 2500000.00, 'Booked', '2025-01-28 09:00:00', NULL, NULL, NULL, 'CG-3002', 'Critical', 2200.00),
('001-12345692', 'Machinery Export Co', 'Toyota Japan', 'LAX', 'NRT', 'AA175', 'Heavy Cargo', 'Industrial robot arms - assembly line equipment', 4, 3200.00, 3200.00, 8.500, 'PMC-AA-0003', 'HEA/BIG', 180000.00, 'In Transit', '2025-01-24 10:00:00', '2025-01-26 13:00:00', NULL, NULL, 'CG-3011', 'Priority', 8000.00);

-- Create indexes for better query performance
CREATE INDEX idx_shipments_status ON cargo_shipments(status);
CREATE INDEX idx_shipments_origin ON cargo_shipments(origin_airport);
CREATE INDEX idx_shipments_destination ON cargo_shipments(destination_airport);
CREATE INDEX idx_shipments_type ON cargo_shipments(shipment_type);
CREATE INDEX idx_containers_status ON cargo_containers(current_status);
CREATE INDEX idx_containers_location ON cargo_containers(current_location);
CREATE INDEX idx_staff_airport ON cargo_handling_staff(base_airport);
