-- ============================================================
-- Fleet Maintenance Database (MSSQL Dialect)
-- Database: fleet_maintenance
-- 4 tables: maintenance_work_orders, spare_parts_inventory,
--           aircraft_inspections, maintenance_staff
-- ============================================================

-- Create database
USE [master]
GO

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'fleet_maintenance')
BEGIN
    CREATE DATABASE [fleet_maintenance]
END
GO

USE [fleet_maintenance]
GO

-- ============================================================
-- Table 1: maintenance_staff
-- ============================================================
IF OBJECT_ID(N'[dbo].[maintenance_staff]', N'U') IS NOT NULL
    DROP TABLE [dbo].[maintenance_staff]
GO

CREATE TABLE [dbo].[maintenance_staff] (
    [staff_id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [employee_id] NVARCHAR(20) NOT NULL,
    [first_name] NVARCHAR(50) NOT NULL,
    [last_name] NVARCHAR(50) NOT NULL,
    [certification_type] NVARCHAR(50) NOT NULL,
    [specialty] NVARCHAR(100) NULL,
    [years_experience] INT NOT NULL DEFAULT 0,
    [base_airport] NVARCHAR(10) NOT NULL,
    [shift_pattern] NVARCHAR(20) NOT NULL DEFAULT 'Day',
    [is_active] BIT NOT NULL DEFAULT 1,
    [hire_date] DATETIME NOT NULL,
    [last_training_date] DATETIME NULL
)
GO

INSERT INTO [dbo].[maintenance_staff] ([employee_id],[first_name],[last_name],[certification_type],[specialty],[years_experience],[base_airport],[shift_pattern],[is_active],[hire_date],[last_training_date]) VALUES
('MT-5001','Carlos','Rivera','A&P','Engine Overhaul',14,'DFW','Day',1,'2011-03-15','2025-01-10'),
('MT-5002','Sarah','Mitchell','A&P','Avionics',9,'DFW','Night',1,'2016-06-22','2025-02-18'),
('MT-5003','James','Okoye','IA','Structural Repair',22,'ORD','Day',1,'2003-01-08','2024-11-30'),
('MT-5004','Linda','Nguyen','A&P','Hydraulics',7,'ORD','Swing',1,'2018-04-01','2025-03-05'),
('MT-5005','Robert','Kowalski','A&P','Landing Gear',11,'MIA','Day',1,'2014-09-12','2025-01-22'),
('MT-5006','Maria','Santos','IA','NDT Inspection',18,'DFW','Day',1,'2007-07-20','2024-12-15'),
('MT-5007','David','Thompson','A&P','Composites',5,'LAX','Night',1,'2020-02-10','2025-03-01'),
('MT-5008','Angela','Freeman','A&P','Electrical Systems',13,'MIA','Day',1,'2012-11-05','2025-02-28'),
('MT-5009','Kevin','Park','A&P','APU Systems',8,'LAX','Swing',1,'2017-08-14','2025-01-15'),
('MT-5010','Patricia','Williams','IA','Engine Overhaul',25,'DFW','Day',1,'2000-05-30','2024-10-20'),
('MT-5011','Brian','Murphy','A&P','Avionics',3,'ORD','Night',1,'2022-01-17','2025-03-10'),
('MT-5012','Yuki','Tanaka','A&P','Fuel Systems',6,'LAX','Day',1,'2019-10-01','2025-02-05')
GO

-- ============================================================
-- Table 2: maintenance_work_orders
-- ============================================================
IF OBJECT_ID(N'[dbo].[maintenance_work_orders]', N'U') IS NOT NULL
    DROP TABLE [dbo].[maintenance_work_orders]
GO

CREATE TABLE [dbo].[maintenance_work_orders] (
    [work_order_id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [work_order_number] NVARCHAR(20) NOT NULL,
    [aircraft_registration] NVARCHAR(10) NOT NULL,
    [aircraft_type] NVARCHAR(50) NOT NULL,
    [work_type] NVARCHAR(30) NOT NULL,
    [priority] NVARCHAR(20) NOT NULL DEFAULT 'Routine',
    [description] NVARCHAR(500) NOT NULL,
    [assigned_staff_id] NVARCHAR(20) NULL,
    [status] NVARCHAR(20) NOT NULL DEFAULT 'Open',
    [estimated_hours] DECIMAL(5,1) NOT NULL,
    [actual_hours] DECIMAL(5,1) NULL,
    [parts_cost_usd] DECIMAL(10,2) NULL,
    [labor_cost_usd] DECIMAL(10,2) NULL,
    [created_date] DATETIME NOT NULL,
    [scheduled_date] DATETIME NULL,
    [completed_date] DATETIME NULL,
    [station] NVARCHAR(10) NOT NULL,
    [sign_off_by] NVARCHAR(20) NULL
)
GO

INSERT INTO [dbo].[maintenance_work_orders] ([work_order_number],[aircraft_registration],[aircraft_type],[work_type],[priority],[description],[assigned_staff_id],[status],[estimated_hours],[actual_hours],[parts_cost_usd],[labor_cost_usd],[created_date],[scheduled_date],[completed_date],[station],[sign_off_by]) VALUES
('WO-2025-0001','N301AA','Boeing 737-800','A Check','Routine','Scheduled A Check - 500 flight hour interval','MT-5001','Completed',48.0,52.5,12500.00,7875.00,'2025-01-02','2025-01-05','2025-01-08','DFW','MT-5010'),
('WO-2025-0002','N455AA','Airbus A321neo','Line Maintenance','Routine','Cabin pressurization sensor replacement','MT-5002','Completed',3.0,2.5,850.00,375.00,'2025-01-03','2025-01-04','2025-01-04','DFW','MT-5006'),
('WO-2025-0003','N672AA','Boeing 787-9','Engine','AOG','Left engine oil leak detected during preflight','MT-5003','Completed',8.0,10.0,4200.00,1500.00,'2025-01-05','2025-01-05','2025-01-06','ORD','MT-5003'),
('WO-2025-0004','N210AA','Boeing 737-800','Avionics','Urgent','FMS software update - mandatory AD compliance','MT-5002','Completed',4.0,4.5,0.00,675.00,'2025-01-06','2025-01-07','2025-01-07','DFW','MT-5006'),
('WO-2025-0005','N819AA','Embraer E175','Landing Gear','Routine','Nose gear steering actuator servicing','MT-5005','Completed',6.0,5.0,1200.00,750.00,'2025-01-08','2025-01-10','2025-01-10','MIA','MT-5005'),
('WO-2025-0006','N301AA','Boeing 737-800','Structural','Routine','Fuselage skin panel corrosion treatment area 41','MT-5003','Completed',12.0,14.0,3800.00,2100.00,'2025-01-10','2025-01-12','2025-01-13','ORD','MT-5003'),
('WO-2025-0007','N540AA','Boeing 777-300ER','C Check','Routine','Scheduled C Check - 18 month interval','MT-5001','In Progress',240.0,NULL,85000.00,NULL,'2025-01-15','2025-01-20',NULL,'DFW',NULL),
('WO-2025-0008','N455AA','Airbus A321neo','Hydraulic','Urgent','Green hydraulic system pressure fluctuation','MT-5004','Completed',5.0,6.5,2100.00,975.00,'2025-01-16','2025-01-16','2025-01-17','ORD','MT-5003'),
('WO-2025-0009','N672AA','Boeing 787-9','Electrical','Routine','Galley power distribution unit replacement','MT-5008','Completed',3.5,3.0,4500.00,450.00,'2025-01-18','2025-01-19','2025-01-19','MIA','MT-5008'),
('WO-2025-0010','N910AA','Airbus A320','Line Maintenance','Routine','Windshield heat controller replacement','MT-5007','Completed',2.0,2.0,1800.00,300.00,'2025-01-20','2025-01-21','2025-01-21','LAX','MT-5007'),
('WO-2025-0011','N819AA','Embraer E175','APU','Routine','APU exhaust duct inspection and cleaning','MT-5009','In Progress',4.0,NULL,0.00,NULL,'2025-01-22','2025-01-25',NULL,'LAX',NULL),
('WO-2025-0012','N301AA','Boeing 737-800','Engine','Routine','Right engine fan blade borescope inspection','MT-5001','Open',6.0,NULL,NULL,NULL,'2025-01-23','2025-01-28',NULL,'DFW',NULL),
('WO-2025-0013','N210AA','Boeing 737-800','Cabin','Routine','Seat track repair rows 14-18','MT-5007','Open',8.0,NULL,NULL,NULL,'2025-01-24','2025-01-30',NULL,'LAX',NULL),
('WO-2025-0014','N540AA','Boeing 777-300ER','Avionics','AOG','Weather radar antenna failure - grounded','MT-5002','In Progress',6.0,NULL,22000.00,NULL,'2025-01-25','2025-01-25',NULL,'DFW',NULL),
('WO-2025-0015','N672AA','Boeing 787-9','Fuel','Routine','Center fuel tank quantity indication system test','MT-5012','Open',3.0,NULL,NULL,NULL,'2025-01-26','2025-02-01',NULL,'LAX',NULL),
('WO-2025-0016','N455AA','Airbus A321neo','Structural','Routine','Wing-to-body fairing inspection per SB A321-57-1042','MT-5003','Open',10.0,NULL,NULL,NULL,'2025-01-27','2025-02-03',NULL,'ORD',NULL),
('WO-2025-0017','N910AA','Airbus A320','Landing Gear','Urgent','Main gear brake assembly overheated - pilot report','MT-5005','In Progress',5.0,NULL,3500.00,NULL,'2025-01-28','2025-01-28',NULL,'MIA',NULL),
('WO-2025-0018','N301AA','Boeing 737-800','Composites','Routine','Radome lightning strike damage repair','MT-5007','Open',4.0,NULL,NULL,NULL,'2025-01-28','2025-02-05',NULL,'LAX',NULL)
GO

-- ============================================================
-- Table 3: spare_parts_inventory
-- ============================================================
IF OBJECT_ID(N'[dbo].[spare_parts_inventory]', N'U') IS NOT NULL
    DROP TABLE [dbo].[spare_parts_inventory]
GO

CREATE TABLE [dbo].[spare_parts_inventory] (
    [part_id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [part_number] NVARCHAR(30) NOT NULL,
    [description] NVARCHAR(200) NOT NULL,
    [category] NVARCHAR(50) NOT NULL,
    [aircraft_applicability] NVARCHAR(100) NOT NULL,
    [quantity_on_hand] INT NOT NULL DEFAULT 0,
    [minimum_stock] INT NOT NULL DEFAULT 1,
    [reorder_quantity] INT NOT NULL DEFAULT 5,
    [unit_cost_usd] DECIMAL(10,2) NOT NULL,
    [warehouse_location] NVARCHAR(20) NOT NULL,
    [station] NVARCHAR(10) NOT NULL,
    [condition_code] NVARCHAR(5) NOT NULL DEFAULT 'NEW',
    [last_received_date] DATETIME NULL,
    [shelf_life_months] INT NULL,
    [is_hazmat] BIT NOT NULL DEFAULT 0
)
GO

INSERT INTO [dbo].[spare_parts_inventory] ([part_number],[description],[category],[aircraft_applicability],[quantity_on_hand],[minimum_stock],[reorder_quantity],[unit_cost_usd],[warehouse_location],[station],[condition_code],[last_received_date],[shelf_life_months],[is_hazmat]) VALUES
('PN-7371001','Fan Blade Assembly','Engine','Boeing 737',4,2,3,18500.00,'A-12-03','DFW','NEW','2025-01-10',NULL,0),
('PN-7871002','Brake Assembly Main Gear','Landing Gear','Boeing 787',6,3,4,8200.00,'B-05-01','DFW','NEW','2025-01-15',NULL,0),
('PN-A321003','Cabin Pressurization Sensor','Avionics','Airbus A321',12,5,10,850.00,'C-01-08','DFW','NEW','2025-01-03',NULL,0),
('PN-7771004','Weather Radar Antenna','Avionics','Boeing 777',1,1,2,22000.00,'A-20-01','DFW','NEW','2024-12-20',NULL,0),
('PN-GEN005','Hydraulic Fluid Skydrol LD-4','Consumable','All Types',48,20,30,125.00,'H-01-01','ORD','NEW','2025-01-12',36,1),
('PN-E175006','APU Exhaust Duct Gasket','APU','Embraer E175',8,3,5,340.00,'C-08-02','MIA','NEW','2024-11-28',24,0),
('PN-7371007','Windshield Heat Controller','Electrical','Boeing 737',3,2,3,1800.00,'D-03-05','LAX','NEW','2025-01-18',NULL,0),
('PN-A320008','Nose Gear Steering Actuator','Landing Gear','Airbus A320',2,1,2,6500.00,'B-02-04','MIA','NEW','2024-12-05',NULL,0),
('PN-7871009','Galley Power Distribution Unit','Electrical','Boeing 787',4,2,3,4500.00,'D-07-01','MIA','NEW','2025-01-08',NULL,0),
('PN-GEN010','Engine Oil - MIL-PRF-23699','Consumable','All Types',120,50,60,45.00,'H-02-03','DFW','NEW','2025-01-20',24,0),
('PN-7371011','FMS Computer Unit','Avionics','Boeing 737',2,1,1,35000.00,'A-15-01','DFW','OH','2024-10-15',NULL,0),
('PN-A321012','Green Hydraulic Pump','Hydraulic','Airbus A321',3,2,2,12000.00,'B-10-02','ORD','NEW','2025-01-05',NULL,0),
('PN-7371013','Radome Assembly','Structural','Boeing 737',1,1,1,15000.00,'E-01-01','LAX','NEW','2024-09-20',NULL,0),
('PN-GEN014','Sealant PR-1422 Class B','Consumable','All Types',35,15,20,85.00,'H-03-01','DFW','NEW','2025-01-14',12,1),
('PN-7771015','Seat Track Fitting','Cabin','Boeing 777',25,10,15,120.00,'F-02-03','LAX','NEW','2025-01-22',NULL,0)
GO

-- ============================================================
-- Table 4: aircraft_inspections
-- ============================================================
IF OBJECT_ID(N'[dbo].[aircraft_inspections]', N'U') IS NOT NULL
    DROP TABLE [dbo].[aircraft_inspections]
GO

CREATE TABLE [dbo].[aircraft_inspections] (
    [inspection_id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [aircraft_registration] NVARCHAR(10) NOT NULL,
    [aircraft_type] NVARCHAR(50) NOT NULL,
    [inspection_type] NVARCHAR(30) NOT NULL,
    [inspection_date] DATETIME NOT NULL,
    [next_due_date] DATETIME NULL,
    [next_due_flight_hours] DECIMAL(8,1) NULL,
    [inspector_id] NVARCHAR(20) NOT NULL,
    [result] NVARCHAR(20) NOT NULL DEFAULT 'Pass',
    [findings_count] INT NOT NULL DEFAULT 0,
    [critical_findings] INT NOT NULL DEFAULT 0,
    [remarks] NVARCHAR(500) NULL,
    [ad_compliance_verified] BIT NOT NULL DEFAULT 1,
    [station] NVARCHAR(10) NOT NULL,
    [total_flight_hours_at_inspection] DECIMAL(8,1) NULL
)
GO

INSERT INTO [dbo].[aircraft_inspections] ([aircraft_registration],[aircraft_type],[inspection_type],[inspection_date],[next_due_date],[next_due_flight_hours],[inspector_id],[result],[findings_count],[critical_findings],[remarks],[ad_compliance_verified],[station],[total_flight_hours_at_inspection]) VALUES
('N301AA','Boeing 737-800','A Check','2025-01-08','2025-04-08',NULL,'MT-5010','Pass',3,0,'Minor corrosion treated on belly panels. All ADs current.',1,'DFW',24500.5),
('N301AA','Boeing 737-800','Daily Check','2025-01-28','2025-01-29',NULL,'MT-5006','Pass',0,0,'All systems nominal. Aircraft released for service.',1,'DFW',24680.0),
('N455AA','Airbus A321neo','Transit Check','2025-01-17','2025-01-18',NULL,'MT-5003','Pass',1,0,'Cabin reading light row 22 inop. Deferred per MEL 33-42-01.',1,'ORD',12350.0),
('N455AA','Airbus A321neo','Weekly Check','2025-01-20','2025-01-27',NULL,'MT-5003','Pass',0,0,'All fluid levels within limits. Tire pressures nominal.',1,'ORD',12420.5),
('N672AA','Boeing 787-9','Special Inspection','2025-01-06','2025-07-06',NULL,'MT-5003','Conditional',2,1,'Left engine oil leak from #3 bearing seal. Seal replaced. Monitoring required per EHM.',1,'ORD',8900.0),
('N672AA','Boeing 787-9','Daily Check','2025-01-27','2025-01-28',NULL,'MT-5006','Pass',0,0,'Battery voltage normal. No anomalies.',1,'DFW',9120.5),
('N210AA','Boeing 737-800','B Check','2024-12-15','2025-06-15',NULL,'MT-5010','Pass',5,0,'All findings routine. Landing gear serviced. Oxygen bottles checked.',1,'DFW',31200.0),
('N210AA','Boeing 737-800','Daily Check','2025-01-28','2025-01-29',NULL,'MT-5006','Pass',1,0,'Cargo door seal wear noted. Monitoring.',1,'DFW',31480.0),
('N819AA','Embraer E175','A Check','2025-01-10','2025-04-10',NULL,'MT-5005','Pass',2,0,'Nose gear shimmy dampener replaced. APU oil consumption within limits.',1,'MIA',18700.0),
('N540AA','Boeing 777-300ER','C Check','2025-01-20',NULL,NULL,'MT-5010','In Progress',8,2,'C Check in progress. Weather radar antenna failure found. Cargo smoke detector sensitivity low.',1,'DFW',45600.0),
('N910AA','Airbus A320','Transit Check','2025-01-27','2025-01-28',NULL,'MT-5005','Conditional',1,1,'Main gear brake temperature exceedance reported by crew. Inspection in progress.',1,'MIA',27800.0),
('N910AA','Airbus A320','Daily Check','2025-01-25','2025-01-26',NULL,'MT-5008','Pass',0,0,'All systems normal. Aircraft released.',1,'MIA',27750.5)
GO
