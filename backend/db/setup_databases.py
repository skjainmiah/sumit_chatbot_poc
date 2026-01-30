"""
Database setup script — creates 5 SQLite databases with tables and seed data.
American Airlines themed with US airports.

All crew-related tables use employee_id (TEXT, e.g. 'AA-10001') as the
consistent crew identifier across every database, enabling cross-DB joins.
"""
import sqlite3
import os
import random
from datetime import datetime, date, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_DIR = BASE_DIR / "data" / "databases"


def ensure_dirs():
    DB_DIR.mkdir(parents=True, exist_ok=True)


def get_db_path(name: str) -> str:
    return str(DB_DIR / name)


# Helper: generate employee_id for a 0-based index
def emp_id(index: int) -> str:
    return f'AA-{10001 + index}'


# ============================================================
# DATABASE 1: crew_management.db
# ============================================================
def setup_crew_management_db():
    db_path = get_db_path("crew_management.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Table 1: crew_members
    c.execute("""
    CREATE TABLE IF NOT EXISTS crew_members (
        crew_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT UNIQUE NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        date_of_birth TEXT NOT NULL,
        nationality TEXT,
        passport_number TEXT,
        passport_expiry TEXT,
        hire_date TEXT NOT NULL,
        seniority_number INTEGER,
        crew_role TEXT NOT NULL CHECK (crew_role IN (
            'Captain', 'First Officer', 'Senior First Officer',
            'Flight Engineer', 'Purser', 'Senior Cabin Crew',
            'Cabin Crew', 'Trainee')),
        base_airport TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN (
            'Active', 'On Leave', 'Suspended', 'Inactive', 'Retired')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Table 2: crew_qualifications
    c.execute("""
    CREATE TABLE IF NOT EXISTS crew_qualifications (
        qualification_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT NOT NULL,
        qualification_type TEXT NOT NULL CHECK (qualification_type IN (
            'Type Rating', 'License', 'Medical Certificate',
            'Language Proficiency', 'Security Clearance',
            'Dangerous Goods', 'First Aid', 'CRM')),
        qualification_name TEXT NOT NULL,
        issuing_authority TEXT,
        issue_date TEXT NOT NULL,
        expiry_date TEXT,
        status TEXT DEFAULT 'Valid' CHECK (status IN (
            'Valid', 'Expired', 'Suspended', 'Revoked', 'Pending Renewal')),
        document_number TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Table 3: crew_assignments
    c.execute("""
    CREATE TABLE IF NOT EXISTS crew_assignments (
        assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT NOT NULL,
        flight_id INTEGER NOT NULL,
        assignment_role TEXT NOT NULL,
        duty_start_utc TEXT NOT NULL,
        duty_end_utc TEXT,
        report_time_utc TEXT NOT NULL,
        release_time_utc TEXT,
        assignment_status TEXT DEFAULT 'Scheduled' CHECK (assignment_status IN (
            'Scheduled', 'Confirmed', 'Checked In', 'Completed',
            'Cancelled', 'No Show', 'Swapped')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Table 4: crew_rest_records
    c.execute("""
    CREATE TABLE IF NOT EXISTS crew_rest_records (
        rest_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT NOT NULL,
        rest_start_utc TEXT NOT NULL,
        rest_end_utc TEXT,
        rest_location TEXT,
        rest_type TEXT NOT NULL CHECK (rest_type IN (
            'Minimum Rest', 'Reduced Rest', 'Extended Rest',
            'Weekly Rest', 'Split Duty Rest', 'Layover Rest')),
        rest_duration_hours REAL,
        meets_far117 INTEGER DEFAULT 1,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Table 5: crew_documents
    c.execute("""
    CREATE TABLE IF NOT EXISTS crew_documents (
        document_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT NOT NULL,
        document_type TEXT NOT NULL CHECK (document_type IN (
            'Passport', 'Visa', 'License', 'Medical Certificate',
            'Training Certificate', 'ID Card', 'Contract')),
        document_name TEXT NOT NULL,
        file_path TEXT,
        upload_date TEXT DEFAULT CURRENT_TIMESTAMP,
        expiry_date TEXT,
        verified INTEGER DEFAULT 0,
        verified_by TEXT
    )
    """)

    # Table 6: crew_contacts
    c.execute("""
    CREATE TABLE IF NOT EXISTS crew_contacts (
        contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT NOT NULL,
        contact_name TEXT NOT NULL,
        relationship TEXT NOT NULL,
        phone_primary TEXT NOT NULL,
        phone_secondary TEXT,
        email TEXT,
        address TEXT,
        is_primary INTEGER DEFAULT 0
    )
    """)

    # SEED DATA
    first_names = ['James', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph', 'Thomas', 'Christopher', 'Charles',
                   'Patricia', 'Jennifer', 'Linda', 'Barbara', 'Elizabeth', 'Susan', 'Jessica', 'Sarah', 'Karen', 'Lisa',
                   'Daniel', 'Matthew', 'Anthony', 'Mark', 'Donald', 'Steven', 'Andrew', 'Paul', 'Joshua', 'Kenneth',
                   'Nancy', 'Betty', 'Margaret', 'Sandra', 'Ashley', 'Dorothy', 'Kimberly', 'Emily', 'Donna', 'Michelle',
                   'Brian', 'Kevin', 'Timothy', 'Ronald', 'Edward', 'Jason', 'Jeffrey', 'Ryan', 'Jacob', 'Gary']
    last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
                  'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin',
                  'Lee', 'Perez', 'Thompson', 'White', 'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson',
                  'Walker', 'Young', 'Allen', 'King', 'Wright', 'Scott', 'Torres', 'Nguyen', 'Hill', 'Flores',
                  'Green', 'Adams', 'Nelson', 'Baker', 'Hall', 'Rivera', 'Campbell', 'Mitchell', 'Carter', 'Roberts']
    bases = ['DFW', 'ORD', 'MIA', 'JFK', 'LAX', 'CLT', 'PHL', 'PHX', 'DCA']
    roles = ['Captain', 'First Officer', 'Purser', 'Senior Cabin Crew', 'Cabin Crew']
    statuses = ['Active'] * 40 + ['On Leave'] * 5 + ['Suspended'] * 2 + ['Inactive'] * 2 + ['Retired'] * 1

    crew_data = []
    for i in range(50):
        fn = first_names[i]
        ln = last_names[i]
        role = roles[i % len(roles)]
        base = bases[i % len(bases)]
        status = statuses[i % len(statuses)]
        dob = date(1965 + (i % 30), (i % 12) + 1, (i % 28) + 1).isoformat()
        hire = date(2005 + (i % 18), (i % 12) + 1, 1).isoformat()
        passport_exp = date(2026 + (i % 5), (i % 12) + 1, (i % 28) + 1).isoformat()
        crew_data.append((
            emp_id(i),
            fn, ln,
            f'{fn.lower()}.{ln.lower()}@aa.com',
            f'+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}',
            dob, 'American', f'US{random.randint(10000000, 99999999)}',
            passport_exp, hire, i + 1, role, base, status
        ))

    c.executemany("""
        INSERT OR IGNORE INTO crew_members
        (employee_id, first_name, last_name, email, phone, date_of_birth,
         nationality, passport_number, passport_expiry, hire_date,
         seniority_number, crew_role, base_airport, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, crew_data)

    # Seed qualifications (3 per crew member)
    qual_types = [
        ('Type Rating', 'Boeing 737-800 Type Rating', 'FAA'),
        ('Type Rating', 'Boeing 777-300ER Type Rating', 'FAA'),
        ('Type Rating', 'Airbus A321 Type Rating', 'FAA'),
        ('License', 'ATP License', 'FAA'),
        ('Medical Certificate', 'Class 1 Medical', 'FAA AME'),
        ('Medical Certificate', 'Class 2 Medical', 'FAA AME'),
        ('Language Proficiency', 'English Level 6', 'ICAO'),
        ('Security Clearance', 'TSA Security Clearance', 'TSA'),
        ('Dangerous Goods', 'DG Category 6 Certification', 'IATA'),
        ('First Aid', 'Advanced First Aid', 'Red Cross'),
        ('CRM', 'CRM Recurrent 2025', 'AA Training Center'),
    ]
    qual_data = []
    for i in range(50):
        eid = emp_id(i)
        selected = random.sample(qual_types, 3)
        for qt, qn, ia in selected:
            issue = date(2023 + random.randint(0, 1), random.randint(1, 12), random.randint(1, 28)).isoformat()
            expiry = date(2026 + random.randint(0, 2), random.randint(1, 12), random.randint(1, 28)).isoformat()
            doc_num = f'DOC-{random.randint(100000, 999999)}'
            stat = random.choice(['Valid'] * 8 + ['Pending Renewal'] * 1 + ['Expired'] * 1)
            qual_data.append((eid, qt, qn, ia, issue, expiry, stat, doc_num))

    c.executemany("""
        INSERT INTO crew_qualifications
        (employee_id, qualification_type, qualification_name, issuing_authority,
         issue_date, expiry_date, status, document_number)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, qual_data)

    # Seed assignments (300 records)
    assignment_data = []
    assign_statuses = ['Completed'] * 20 + ['Scheduled'] * 5 + ['Confirmed'] * 3 + ['Cancelled'] * 2
    for i in range(300):
        eid = emp_id(i % 50)
        flight_id = (i % 200) + 1
        role = roles[i % len(roles)]
        day_offset = random.randint(-30, 15)
        duty_start = (datetime.now() + timedelta(days=day_offset, hours=random.randint(5, 20))).strftime('%Y-%m-%d %H:%M:%S')
        duty_end = (datetime.now() + timedelta(days=day_offset, hours=random.randint(8, 23))).strftime('%Y-%m-%d %H:%M:%S')
        report = (datetime.now() + timedelta(days=day_offset, hours=random.randint(4, 19))).strftime('%Y-%m-%d %H:%M:%S')
        release = (datetime.now() + timedelta(days=day_offset, hours=random.randint(9, 23), minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
        status = random.choice(assign_statuses)
        assignment_data.append((eid, flight_id, role, duty_start, duty_end, report, release, status))

    c.executemany("""
        INSERT INTO crew_assignments
        (employee_id, flight_id, assignment_role, duty_start_utc, duty_end_utc,
         report_time_utc, release_time_utc, assignment_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, assignment_data)

    # Seed rest records (200)
    rest_types = ['Minimum Rest', 'Reduced Rest', 'Extended Rest', 'Weekly Rest', 'Split Duty Rest', 'Layover Rest']
    rest_locations = ['Home Base', 'Hilton DFW Airport', 'Marriott ORD', 'Hyatt MIA', 'Holiday Inn JFK', 'Sheraton LAX']
    rest_data = []
    for i in range(200):
        eid = emp_id(i % 50)
        day_offset = random.randint(-30, 0)
        start = (datetime.now() + timedelta(days=day_offset, hours=random.randint(0, 12))).strftime('%Y-%m-%d %H:%M:%S')
        duration = round(random.uniform(8.0, 36.0), 2)
        end = (datetime.now() + timedelta(days=day_offset, hours=int(duration))).strftime('%Y-%m-%d %H:%M:%S')
        rt = random.choice(rest_types)
        loc = random.choice(rest_locations)
        meets = 1 if duration >= 10 else 0
        rest_data.append((eid, start, end, loc, rt, duration, meets, None))

    c.executemany("""
        INSERT INTO crew_rest_records
        (employee_id, rest_start_utc, rest_end_utc, rest_location, rest_type,
         rest_duration_hours, meets_far117, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, rest_data)

    # Seed documents (100)
    doc_types = ['Passport', 'License', 'Medical Certificate', 'Training Certificate', 'ID Card']
    doc_data = []
    for i in range(100):
        eid = emp_id(i % 50)
        dt = doc_types[i % len(doc_types)]
        name = f'{dt}_{eid}_{i}.pdf'
        expiry = date(2025 + random.randint(0, 3), random.randint(1, 12), random.randint(1, 28)).isoformat()
        verified = random.choice([0, 1, 1, 1])
        verifier = 'HR Admin' if verified else None
        doc_data.append((eid, dt, name, f'/docs/{name}', expiry, verified, verifier))

    c.executemany("""
        INSERT INTO crew_documents
        (employee_id, document_type, document_name, file_path, expiry_date, verified, verified_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, doc_data)

    # Seed contacts (50)
    relationships = ['Spouse', 'Parent', 'Sibling', 'Child', 'Partner']
    contact_data = []
    for i in range(50):
        eid = emp_id(i)
        cname = f'{random.choice(first_names)} {random.choice(last_names)}'
        rel = random.choice(relationships)
        phone = f'+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}'
        email = cname.lower().replace(' ', '.') + '@gmail.com'
        contact_data.append((eid, cname, rel, phone, None, email, None, 1))

    c.executemany("""
        INSERT INTO crew_contacts
        (employee_id, contact_name, relationship, phone_primary, phone_secondary, email, address, is_primary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, contact_data)

    # Table 7: crew_roster - Monthly roster assignments and bid awards
    c.execute("""
    CREATE TABLE IF NOT EXISTS crew_roster (
        roster_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT NOT NULL,
        roster_month TEXT NOT NULL,
        roster_year INTEGER NOT NULL,
        roster_status TEXT NOT NULL CHECK (roster_status IN (
            'Awarded', 'Reserve', 'Standby', 'Not Awarded', 'Training', 'Leave', 'Mixed')),
        bid_submitted INTEGER DEFAULT 1,
        bid_preference TEXT,
        awarded INTEGER DEFAULT 0,
        not_awarded_reason TEXT CHECK (not_awarded_reason IN (
            NULL,
            'Seniority',
            'Qualification Gap',
            'Schedule Conflict',
            'Base Mismatch',
            'Medical Hold',
            'Training Conflict',
            'Visa Issue',
            'Staffing Requirement',
            'Bid Not Submitted',
            'Pairing Unavailable',
            'Rest Requirement',
            'Disciplinary Action',
            'Probation Period',
            'Union Dispute',
            'Crew Complement Full',
            'Aircraft Type Mismatch',
            'Insufficient Flight Hours',
            'Administrative Error',
            'Voluntary Withdrawal',
            'FAA Restriction',
            'Fatigue Risk Flag')),
        assigned_pairing_code TEXT,
        duty_type TEXT CHECK (duty_type IN (
            'Line Flying', 'Reserve', 'Standby', 'Training', 'Leave', 'Admin', 'Mixed')),
        assigned_flights_count INTEGER DEFAULT 0,
        reserve_days INTEGER DEFAULT 0,
        standby_days INTEGER DEFAULT 0,
        training_days INTEGER DEFAULT 0,
        leave_days INTEGER DEFAULT 0,
        off_days INTEGER DEFAULT 0,
        total_duty_days INTEGER DEFAULT 0,
        total_flight_hours REAL DEFAULT 0,
        total_block_hours REAL DEFAULT 0,
        per_diem_days INTEGER DEFAULT 0,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(employee_id, roster_month, roster_year)
    )
    """)

    # SEED crew_roster data (6 months for 50 crew = 300 records)
    roster_statuses = ['Awarded'] * 35 + ['Reserve'] * 25 + ['Standby'] * 15 + ['Not Awarded'] * 10 + ['Training'] * 10 + ['Leave'] * 5
    not_awarded_reasons = [
        'Seniority', 'Qualification Gap', 'Schedule Conflict', 'Base Mismatch',
        'Medical Hold', 'Training Conflict', 'Staffing Requirement', 'Rest Requirement',
        'Disciplinary Action', 'Probation Period', 'Union Dispute',
        'Crew Complement Full', 'Aircraft Type Mismatch', 'Insufficient Flight Hours',
        'Administrative Error', 'Voluntary Withdrawal', 'FAA Restriction', 'Fatigue Risk Flag'
    ]
    duty_types = ['Line Flying', 'Reserve', 'Standby', 'Training', 'Leave', 'Mixed']
    pairing_codes = [f'PR-2025{m:02d}{i:02d}' for m in range(1, 13) for i in range(1, 20)]

    roster_data = []
    months = ['January', 'February', 'March', 'April', 'May', 'June']

    for i in range(50):
        eid = emp_id(i)
        for month_idx, month_name in enumerate(months):
            status = random.choice(roster_statuses)
            bid_submitted = 1 if random.random() > 0.1 else 0
            awarded = 1 if status in ('Awarded', 'Mixed') else 0

            # Not awarded reason only if not awarded
            not_awarded_reason = None
            if status == 'Not Awarded' or (status not in ('Awarded', 'Training', 'Leave') and random.random() > 0.7):
                not_awarded_reason = random.choice(not_awarded_reasons)
            if not bid_submitted:
                not_awarded_reason = 'Bid Not Submitted'
                status = 'Not Awarded'
                awarded = 0

            # Determine duty type based on status
            if status == 'Awarded':
                duty_type = 'Line Flying'
            elif status == 'Reserve':
                duty_type = 'Reserve'
            elif status == 'Standby':
                duty_type = 'Standby'
            elif status == 'Training':
                duty_type = 'Training'
            elif status == 'Leave':
                duty_type = 'Leave'
            else:
                duty_type = random.choice(duty_types)

            # Generate realistic counts based on duty type
            if duty_type == 'Line Flying':
                assigned_flights = random.randint(15, 30)
                reserve_days = 0
                standby_days = random.randint(0, 2)
                training_days = random.randint(0, 2)
                leave_days = random.randint(0, 3)
                flight_hours = round(random.uniform(60, 90), 1)
            elif duty_type == 'Reserve':
                assigned_flights = random.randint(5, 15)
                reserve_days = random.randint(10, 18)
                standby_days = random.randint(2, 6)
                training_days = random.randint(0, 2)
                leave_days = random.randint(0, 3)
                flight_hours = round(random.uniform(25, 55), 1)
            elif duty_type == 'Standby':
                assigned_flights = random.randint(3, 10)
                reserve_days = random.randint(5, 10)
                standby_days = random.randint(8, 15)
                training_days = random.randint(0, 2)
                leave_days = random.randint(0, 3)
                flight_hours = round(random.uniform(15, 40), 1)
            elif duty_type == 'Training':
                assigned_flights = 0
                reserve_days = 0
                standby_days = 0
                training_days = random.randint(15, 25)
                leave_days = random.randint(0, 5)
                flight_hours = 0
            elif duty_type == 'Leave':
                assigned_flights = 0
                reserve_days = 0
                standby_days = 0
                training_days = 0
                leave_days = random.randint(20, 30)
                flight_hours = 0
            else:  # Mixed
                assigned_flights = random.randint(8, 18)
                reserve_days = random.randint(4, 10)
                standby_days = random.randint(2, 6)
                training_days = random.randint(0, 4)
                leave_days = random.randint(0, 5)
                flight_hours = round(random.uniform(30, 65), 1)

            off_days = max(0, 30 - reserve_days - standby_days - training_days - leave_days - (assigned_flights // 2))
            total_duty = 30 - off_days - leave_days
            block_hours = round(flight_hours * 0.85, 1)
            per_diem = total_duty - training_days

            pairing_code = random.choice(pairing_codes) if assigned_flights > 0 else None
            bid_pref = f'Pairing {random.randint(1, 50)}' if bid_submitted else None

            roster_data.append((
                eid, month_name, 2025, status, bid_submitted, bid_pref,
                awarded, not_awarded_reason, pairing_code, duty_type,
                assigned_flights, reserve_days, standby_days, training_days,
                leave_days, off_days, total_duty, flight_hours, block_hours,
                per_diem, None
            ))

    c.executemany("""
        INSERT OR IGNORE INTO crew_roster
        (employee_id, roster_month, roster_year, roster_status, bid_submitted, bid_preference,
         awarded, not_awarded_reason, assigned_pairing_code, duty_type,
         assigned_flights_count, reserve_days, standby_days, training_days,
         leave_days, off_days, total_duty_days, total_flight_hours, total_block_hours,
         per_diem_days, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, roster_data)

    conn.commit()
    conn.close()
    print(f"[OK] crew_management.db created at {db_path}")


# ============================================================
# DATABASE 2: flight_operations.db
# ============================================================
def setup_flight_operations_db():
    db_path = get_db_path("flight_operations.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS airports (
        airport_id INTEGER PRIMARY KEY AUTOINCREMENT,
        iata_code TEXT UNIQUE NOT NULL,
        icao_code TEXT UNIQUE NOT NULL,
        airport_name TEXT NOT NULL,
        city TEXT NOT NULL,
        country TEXT NOT NULL,
        timezone TEXT NOT NULL,
        latitude REAL,
        longitude REAL,
        is_hub INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS aircraft (
        aircraft_id INTEGER PRIMARY KEY AUTOINCREMENT,
        registration TEXT UNIQUE NOT NULL,
        aircraft_type TEXT NOT NULL,
        manufacturer TEXT NOT NULL,
        model TEXT NOT NULL,
        seat_capacity_economy INTEGER,
        seat_capacity_business INTEGER,
        seat_capacity_first INTEGER,
        max_range_nm INTEGER,
        year_manufactured INTEGER,
        status TEXT DEFAULT 'Active' CHECK (status IN ('Active', 'Maintenance', 'Grounded', 'Retired')),
        home_base TEXT,
        last_maintenance TEXT,
        next_maintenance TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS flights (
        flight_id INTEGER PRIMARY KEY AUTOINCREMENT,
        flight_number TEXT NOT NULL,
        aircraft_id INTEGER REFERENCES aircraft(aircraft_id),
        departure_airport TEXT NOT NULL,
        arrival_airport TEXT NOT NULL,
        scheduled_departure TEXT NOT NULL,
        scheduled_arrival TEXT NOT NULL,
        actual_departure TEXT,
        actual_arrival TEXT,
        flight_status TEXT DEFAULT 'Scheduled' CHECK (flight_status IN (
            'Scheduled', 'Boarding', 'Departed', 'In Air',
            'Landed', 'Arrived', 'Cancelled', 'Diverted', 'Delayed')),
        block_time_minutes INTEGER,
        flight_type TEXT DEFAULT 'Passenger',
        delay_minutes INTEGER DEFAULT 0,
        delay_reason TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS flight_legs (
        leg_id INTEGER PRIMARY KEY AUTOINCREMENT,
        flight_id INTEGER NOT NULL REFERENCES flights(flight_id),
        leg_sequence INTEGER NOT NULL,
        departure_airport TEXT NOT NULL,
        arrival_airport TEXT NOT NULL,
        scheduled_departure TEXT NOT NULL,
        scheduled_arrival TEXT NOT NULL,
        actual_departure TEXT,
        actual_arrival TEXT,
        UNIQUE(flight_id, leg_sequence)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS crew_pairings (
        pairing_id INTEGER PRIMARY KEY AUTOINCREMENT,
        pairing_code TEXT UNIQUE NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        base_airport TEXT NOT NULL,
        total_duty_hours REAL,
        total_flight_hours REAL,
        total_legs INTEGER,
        pairing_status TEXT DEFAULT 'Open' CHECK (pairing_status IN (
            'Open', 'Assigned', 'In Progress', 'Completed', 'Cancelled')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS pairing_flights (
        pairing_flight_id INTEGER PRIMARY KEY AUTOINCREMENT,
        pairing_id INTEGER NOT NULL REFERENCES crew_pairings(pairing_id),
        flight_id INTEGER NOT NULL REFERENCES flights(flight_id),
        sequence_number INTEGER NOT NULL,
        duty_day INTEGER NOT NULL,
        UNIQUE(pairing_id, flight_id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS disruptions (
        disruption_id INTEGER PRIMARY KEY AUTOINCREMENT,
        flight_id INTEGER REFERENCES flights(flight_id),
        reported_by_employee_id TEXT,
        disruption_type TEXT NOT NULL CHECK (disruption_type IN (
            'Delay', 'Cancellation', 'Diversion', 'Aircraft Swap',
            'Crew Swap', 'Weather Hold', 'ATC Hold')),
        disruption_reason TEXT NOT NULL,
        severity TEXT CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
        start_time_utc TEXT NOT NULL,
        end_time_utc TEXT,
        resolution TEXT,
        affected_crew_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS hotels (
        hotel_id INTEGER PRIMARY KEY AUTOINCREMENT,
        hotel_name TEXT NOT NULL,
        airport_code TEXT NOT NULL,
        address TEXT,
        phone TEXT,
        star_rating INTEGER CHECK (star_rating BETWEEN 1 AND 5),
        has_crew_rate INTEGER DEFAULT 1,
        crew_rate_per_night REAL,
        distance_to_airport_km REAL,
        is_active INTEGER DEFAULT 1
    )
    """)

    # SEED airports
    airports_data = [
        ('DFW', 'KDFW', 'Dallas/Fort Worth International', 'Dallas-Fort Worth', 'United States', 'America/Chicago', 32.8968, -97.0380, 1),
        ('ORD', 'KORD', 'O\'Hare International', 'Chicago', 'United States', 'America/Chicago', 41.9742, -87.9073, 1),
        ('MIA', 'KMIA', 'Miami International', 'Miami', 'United States', 'America/New_York', 25.7959, -80.2870, 1),
        ('JFK', 'KJFK', 'John F. Kennedy International', 'New York', 'United States', 'America/New_York', 40.6413, -73.7781, 1),
        ('LAX', 'KLAX', 'Los Angeles International', 'Los Angeles', 'United States', 'America/Los_Angeles', 33.9425, -118.4081, 1),
        ('CLT', 'KCLT', 'Charlotte Douglas International', 'Charlotte', 'United States', 'America/New_York', 35.2140, -80.9431, 1),
        ('PHL', 'KPHL', 'Philadelphia International', 'Philadelphia', 'United States', 'America/New_York', 39.8721, -75.2411, 1),
        ('PHX', 'KPHX', 'Phoenix Sky Harbor International', 'Phoenix', 'United States', 'America/Phoenix', 33.4373, -112.0078, 1),
        ('DCA', 'KDCA', 'Reagan National', 'Washington D.C.', 'United States', 'America/New_York', 38.8512, -77.0402, 1),
        ('BOS', 'KBOS', 'Boston Logan International', 'Boston', 'United States', 'America/New_York', 42.3656, -71.0096, 0),
        ('SFO', 'KSFO', 'San Francisco International', 'San Francisco', 'United States', 'America/Los_Angeles', 37.6213, -122.3790, 0),
        ('SEA', 'KSEA', 'Seattle-Tacoma International', 'Seattle', 'United States', 'America/Los_Angeles', 47.4502, -122.3088, 0),
        ('EWR', 'KEWR', 'Newark Liberty International', 'Newark', 'United States', 'America/New_York', 40.6895, -74.1745, 0),
        ('ATL', 'KATL', 'Hartsfield-Jackson Atlanta', 'Atlanta', 'United States', 'America/New_York', 33.6407, -84.4277, 0),
        ('DEN', 'KDEN', 'Denver International', 'Denver', 'United States', 'America/Denver', 39.8561, -104.6737, 0),
        ('IAH', 'KIAH', 'George Bush Intercontinental', 'Houston', 'United States', 'America/Chicago', 29.9902, -95.3368, 0),
        ('LAS', 'KLAS', 'Harry Reid International', 'Las Vegas', 'United States', 'America/Los_Angeles', 36.0840, -115.1537, 0),
        ('MCO', 'KMCO', 'Orlando International', 'Orlando', 'United States', 'America/New_York', 28.4312, -81.3081, 0),
        ('MSP', 'KMSP', 'Minneapolis-Saint Paul', 'Minneapolis', 'United States', 'America/Chicago', 44.8848, -93.2223, 0),
        ('DTW', 'KDTW', 'Detroit Metro Wayne County', 'Detroit', 'United States', 'America/Detroit', 42.2124, -83.3534, 0),
        ('SAN', 'KSAN', 'San Diego International', 'San Diego', 'United States', 'America/Los_Angeles', 32.7336, -117.1897, 0),
        ('TPA', 'KTPA', 'Tampa International', 'Tampa', 'United States', 'America/New_York', 27.9755, -82.5332, 0),
        ('BWI', 'KBWI', 'Baltimore/Washington', 'Baltimore', 'United States', 'America/New_York', 39.1754, -76.6684, 0),
        ('STL', 'KSTL', 'St. Louis Lambert', 'St. Louis', 'United States', 'America/Chicago', 38.7487, -90.3700, 0),
        ('AUS', 'KAUS', 'Austin-Bergstrom', 'Austin', 'United States', 'America/Chicago', 30.1975, -97.6664, 0),
        ('RDU', 'KRDU', 'Raleigh-Durham', 'Raleigh', 'United States', 'America/New_York', 35.8801, -78.7880, 0),
        ('SJC', 'KSJC', 'San Jose International', 'San Jose', 'United States', 'America/Los_Angeles', 37.3626, -121.9290, 0),
        ('PDX', 'KPDX', 'Portland International', 'Portland', 'United States', 'America/Los_Angeles', 45.5898, -122.5951, 0),
        ('MCI', 'KMCI', 'Kansas City International', 'Kansas City', 'United States', 'America/Chicago', 39.2976, -94.7139, 0),
        ('IND', 'KIND', 'Indianapolis International', 'Indianapolis', 'United States', 'America/Indiana/Indianapolis', 39.7173, -86.2944, 0),
    ]
    c.executemany("INSERT OR IGNORE INTO airports (iata_code, icao_code, airport_name, city, country, timezone, latitude, longitude, is_hub) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", airports_data)

    # SEED aircraft (20)
    aircraft_types = [
        ('Boeing', '737-800', 160, 16, 0, 3115),
        ('Boeing', '737 MAX 8', 172, 16, 0, 3550),
        ('Boeing', '777-300ER', 260, 52, 8, 7370),
        ('Boeing', '787-9', 215, 48, 0, 7635),
        ('Airbus', 'A321neo', 190, 20, 0, 4000),
        ('Airbus', 'A320', 150, 12, 0, 3300),
        ('Embraer', 'E175', 76, 12, 0, 2000),
    ]
    bases = ['DFW', 'ORD', 'MIA', 'JFK', 'LAX', 'CLT', 'PHL', 'PHX', 'DCA']
    aircraft_data = []
    for i in range(20):
        at = aircraft_types[i % len(aircraft_types)]
        reg = f'N{100 + i}AA'
        base = bases[i % len(bases)]
        year = random.randint(2010, 2023)
        last_mx = (date.today() - timedelta(days=random.randint(10, 90))).isoformat()
        next_mx = (date.today() + timedelta(days=random.randint(30, 180))).isoformat()
        status = random.choice(['Active'] * 17 + ['Maintenance'] * 2 + ['Grounded'] * 1)
        aircraft_data.append((reg, f'{at[0]} {at[1]}', at[0], at[1], at[2], at[3], at[4], at[5], year, status, base, last_mx, next_mx))
    c.executemany("INSERT OR IGNORE INTO aircraft (registration, aircraft_type, manufacturer, model, seat_capacity_economy, seat_capacity_business, seat_capacity_first, max_range_nm, year_manufactured, status, home_base, last_maintenance, next_maintenance) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", aircraft_data)

    # SEED flights (200)
    hubs = ['DFW', 'ORD', 'MIA', 'JFK', 'LAX', 'CLT', 'PHL', 'PHX', 'DCA']
    all_airports = [a[0] for a in airports_data]
    statuses = ['Scheduled'] * 8 + ['Departed'] * 3 + ['Arrived'] * 5 + ['Cancelled'] * 1 + ['Delayed'] * 3
    delay_reasons = [None, None, None, 'Weather', 'Mechanical', 'ATC Delay', 'Late Crew', 'Late Aircraft']
    flight_data = []
    for i in range(200):
        fn = f'AA{100 + i}'
        acid = (i % 20) + 1
        dep = random.choice(hubs)
        arr = random.choice([a for a in all_airports if a != dep])
        day_offset = random.randint(-15, 15)
        hour = random.randint(5, 22)
        sd = (datetime.now() + timedelta(days=day_offset, hours=hour)).strftime('%Y-%m-%d %H:%M:%S')
        flight_mins = random.randint(90, 360)
        sa = (datetime.now() + timedelta(days=day_offset, hours=hour, minutes=flight_mins)).strftime('%Y-%m-%d %H:%M:%S')
        fs = random.choice(statuses)
        delay = random.randint(0, 120) if fs == 'Delayed' else 0
        dr = random.choice(delay_reasons) if delay > 0 else None
        ad = sd if fs in ('Departed', 'Arrived', 'In Air') else None
        aa = sa if fs == 'Arrived' else None
        ft = random.choice(['Passenger'] * 18 + ['Cargo'] * 1 + ['Charter'] * 1)
        flight_data.append((fn, acid, dep, arr, sd, sa, ad, aa, fs, flight_mins, ft, delay, dr))
    c.executemany("INSERT INTO flights (flight_number, aircraft_id, departure_airport, arrival_airport, scheduled_departure, scheduled_arrival, actual_departure, actual_arrival, flight_status, block_time_minutes, flight_type, delay_minutes, delay_reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", flight_data)

    # SEED pairings (40)
    pairing_data = []
    for i in range(40):
        code = f'PR-{date.today().strftime("%Y%m%d")}-{i+1:03d}'
        base = random.choice(hubs)
        days = random.randint(1, 4)
        sd = (date.today() + timedelta(days=random.randint(-10, 10))).isoformat()
        ed = (date.today() + timedelta(days=random.randint(-10, 10) + days)).isoformat()
        dh = round(random.uniform(8, 40), 2)
        fh = round(random.uniform(6, 30), 2)
        legs = random.randint(2, 8)
        status = random.choice(['Open', 'Assigned', 'Completed', 'In Progress'])
        pairing_data.append((code, sd, ed, base, dh, fh, legs, status))
    c.executemany("INSERT OR IGNORE INTO crew_pairings (pairing_code, start_date, end_date, base_airport, total_duty_hours, total_flight_hours, total_legs, pairing_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", pairing_data)

    # SEED disruptions (25)
    disrupt_reasons = ['Thunderstorm at departure', 'Mechanical issue', 'ATC ground stop', 'Crew exceeded duty time', 'Bird strike inspection', 'Snow/ice', 'Medical emergency', 'Late inbound']
    disrupt_data = []
    for i in range(25):
        fid = random.randint(1, 200)
        eid = emp_id(random.randint(0, 49))
        dt = random.choice(['Delay', 'Cancellation', 'Diversion', 'Aircraft Swap', 'Crew Swap', 'Weather Hold', 'ATC Hold'])
        dr = random.choice(disrupt_reasons)
        sev = random.choice(['Low', 'Medium', 'High', 'Critical'])
        start = (datetime.now() - timedelta(days=random.randint(0, 30))).strftime('%Y-%m-%d %H:%M:%S')
        end = (datetime.now() - timedelta(days=random.randint(0, 30))).strftime('%Y-%m-%d %H:%M:%S')
        res = 'Resolved'
        disrupt_data.append((fid, eid, dt, dr, sev, start, end, res, random.randint(2, 10)))
    c.executemany("INSERT INTO disruptions (flight_id, reported_by_employee_id, disruption_type, disruption_reason, severity, start_time_utc, end_time_utc, resolution, affected_crew_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", disrupt_data)

    # SEED hotels (15)
    hotel_data = [
        ('Hilton DFW Lakes', 'DFW', '1800 Hwy 26E, Grapevine, TX', '+1-817-481-8444', 4, 1, 109.00, 3.2),
        ('Marriott DFW Airport', 'DFW', '8440 Freeport Pkwy, Irving, TX', '+1-972-929-8800', 4, 1, 119.00, 2.1),
        ('Hyatt Regency O\'Hare', 'ORD', '9300 Bryn Mawr Ave, Rosemont, IL', '+1-847-696-1234', 4, 1, 129.00, 1.5),
        ('Hilton Miami Airport', 'MIA', '5101 Blue Lagoon Dr, Miami, FL', '+1-305-262-1000', 4, 1, 139.00, 2.0),
        ('TWA Hotel JFK', 'JFK', 'One Idlewild Dr, Jamaica, NY', '+1-212-806-9000', 4, 1, 159.00, 0.5),
        ('Marriott LAX', 'LAX', '5855 W Century Blvd, Los Angeles, CA', '+1-310-641-5700', 4, 1, 149.00, 1.8),
        ('Sheraton Charlotte', 'CLT', '3315 I-85 Service Rd, Charlotte, NC', '+1-704-392-1200', 3, 1, 99.00, 2.5),
        ('Holiday Inn PHL', 'PHL', '45 Industrial Hwy, Essington, PA', '+1-610-521-2400', 3, 1, 89.00, 3.0),
        ('Hilton Phoenix Airport', 'PHX', '2435 S 47th St, Phoenix, AZ', '+1-480-894-1600', 4, 1, 109.00, 2.8),
        ('Marriott Crystal City', 'DCA', '1999 Richmond Hwy, Arlington, VA', '+1-703-413-5500', 4, 1, 139.00, 4.5),
        ('Hilton Boston Logan', 'BOS', '1 Hotel Dr, Boston, MA', '+1-617-568-6700', 4, 1, 159.00, 0.3),
        ('Grand Hyatt SFO', 'SFO', '190 Gateway Blvd, South SF, CA', '+1-650-375-1234', 4, 1, 169.00, 2.0),
        ('Hilton Seattle Airport', 'SEA', '17620 International Blvd, SeaTac, WA', '+1-206-244-4800', 3, 1, 119.00, 1.2),
        ('Newark Liberty Marriott', 'EWR', '1 Hotel Rd, Newark, NJ', '+1-973-623-0006', 4, 1, 149.00, 1.0),
        ('Atlanta Airport Marriott', 'ATL', '4711 Best Rd, Atlanta, GA', '+1-404-766-7900', 4, 1, 129.00, 2.3),
    ]
    c.executemany("INSERT OR IGNORE INTO hotels (hotel_name, airport_code, address, phone, star_rating, has_crew_rate, crew_rate_per_night, distance_to_airport_km) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", hotel_data)

    conn.commit()
    conn.close()
    print(f"[OK] flight_operations.db created at {db_path}")


# ============================================================
# DATABASE 3: hr_payroll.db
# ============================================================
def setup_hr_payroll_db():
    db_path = get_db_path("hr_payroll.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS pay_grades (
        grade_id INTEGER PRIMARY KEY AUTOINCREMENT, grade_code TEXT UNIQUE NOT NULL,
        crew_role TEXT NOT NULL, seniority_band TEXT NOT NULL, base_salary_monthly REAL NOT NULL,
        flight_hour_rate REAL NOT NULL, per_diem_rate REAL NOT NULL, currency TEXT DEFAULT 'USD',
        effective_from TEXT NOT NULL, effective_to TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS payroll_records (
        payroll_id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL,
        pay_period_start TEXT NOT NULL, pay_period_end TEXT NOT NULL, base_pay REAL NOT NULL,
        flight_hours REAL DEFAULT 0, flight_hour_pay REAL DEFAULT 0, per_diem_days INTEGER DEFAULT 0,
        per_diem_pay REAL DEFAULT 0, overtime_hours REAL DEFAULT 0, overtime_pay REAL DEFAULT 0,
        deductions REAL DEFAULT 0, tax_withheld REAL DEFAULT 0, net_pay REAL NOT NULL,
        payment_date TEXT, payment_status TEXT DEFAULT 'Pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS leave_records (
        leave_id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL,
        leave_type TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
        total_days INTEGER NOT NULL, status TEXT DEFAULT 'Pending', approved_by TEXT,
        approval_date TEXT, reason TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS leave_balances (
        balance_id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL,
        leave_type TEXT NOT NULL, year INTEGER NOT NULL, entitled_days INTEGER NOT NULL,
        used_days INTEGER DEFAULT 0, pending_days INTEGER DEFAULT 0, carried_over INTEGER DEFAULT 0,
        UNIQUE(employee_id, leave_type, year))""")

    c.execute("""CREATE TABLE IF NOT EXISTS benefits (
        benefit_id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL,
        benefit_type TEXT NOT NULL, plan_name TEXT, enrollment_date TEXT NOT NULL,
        coverage_start TEXT NOT NULL, coverage_end TEXT, employee_contribution REAL DEFAULT 0,
        employer_contribution REAL DEFAULT 0, status TEXT DEFAULT 'Active')""")

    c.execute("""CREATE TABLE IF NOT EXISTS performance_reviews (
        review_id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL,
        review_period_start TEXT NOT NULL, review_period_end TEXT NOT NULL,
        reviewer_name TEXT NOT NULL, reviewer_role TEXT, overall_rating INTEGER,
        flight_skills INTEGER, safety_compliance INTEGER, teamwork INTEGER,
        customer_service INTEGER, punctuality INTEGER, comments TEXT,
        improvement_areas TEXT, review_date TEXT NOT NULL, acknowledged INTEGER DEFAULT 0,
        acknowledged_date TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS expense_claims (
        claim_id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL,
        claim_date TEXT NOT NULL, expense_type TEXT NOT NULL, description TEXT NOT NULL,
        amount REAL NOT NULL, currency TEXT DEFAULT 'USD', receipt_path TEXT,
        status TEXT DEFAULT 'Submitted', approved_by TEXT, approved_date TEXT,
        payment_date TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    # SEED pay_grades
    grades = [
        ('CPT-1', 'Captain', '0-5yr', 15000, 250, 85, 'USD', '2025-01-01', None),
        ('CPT-2', 'Captain', '5-10yr', 18000, 290, 95, 'USD', '2025-01-01', None),
        ('CPT-3', 'Captain', '10+yr', 22000, 340, 105, 'USD', '2025-01-01', None),
        ('FO-1', 'First Officer', '0-5yr', 9000, 150, 75, 'USD', '2025-01-01', None),
        ('FO-2', 'First Officer', '5-10yr', 11000, 180, 80, 'USD', '2025-01-01', None),
        ('FO-3', 'First Officer', '10+yr', 13500, 210, 85, 'USD', '2025-01-01', None),
        ('PUR-1', 'Purser', '0-5yr', 5500, 65, 60, 'USD', '2025-01-01', None),
        ('PUR-2', 'Purser', '5+yr', 6500, 75, 65, 'USD', '2025-01-01', None),
        ('SCC-1', 'Senior Cabin Crew', '0-5yr', 4800, 55, 55, 'USD', '2025-01-01', None),
        ('SCC-2', 'Senior Cabin Crew', '5+yr', 5500, 62, 60, 'USD', '2025-01-01', None),
        ('CC-1', 'Cabin Crew', '0-3yr', 3500, 42, 50, 'USD', '2025-01-01', None),
        ('CC-2', 'Cabin Crew', '3+yr', 4200, 48, 55, 'USD', '2025-01-01', None),
    ]
    c.executemany("INSERT OR IGNORE INTO pay_grades (grade_code, crew_role, seniority_band, base_salary_monthly, flight_hour_rate, per_diem_rate, currency, effective_from, effective_to) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", grades)

    # SEED payroll_records (300)
    payroll_data = []
    base_pays = [18000, 11000, 5500, 4800, 3500]
    fh_rates = [290, 180, 65, 55, 42]
    for i in range(50):
        eid = emp_id(i)
        role_idx = i % 5
        bp = base_pays[role_idx]
        for month_offset in range(6):
            m = 7 + month_offset
            ps = date(2025, m, 1).isoformat()
            pe = date(2025, m, 28).isoformat()
            fh = round(random.uniform(50, 90), 1)
            fhp = round(fh * fh_rates[role_idx], 2)
            pdd = random.randint(8, 20)
            pdp = round(pdd * [95, 80, 60, 55, 50][role_idx], 2)
            ot = round(random.uniform(0, 15), 1)
            otp = round(ot * fh_rates[role_idx] * 1.5, 2)
            gross = bp + fhp + pdp + otp
            deduct = round(gross * 0.05, 2)
            tax = round(gross * 0.22, 2)
            net = round(gross - deduct - tax, 2)
            payroll_data.append((eid, ps, pe, bp, fh, fhp, pdd, pdp, ot, otp, deduct, tax, net, pe, 'Paid'))
    c.executemany("INSERT INTO payroll_records (employee_id, pay_period_start, pay_period_end, base_pay, flight_hours, flight_hour_pay, per_diem_days, per_diem_pay, overtime_hours, overtime_pay, deductions, tax_withheld, net_pay, payment_date, payment_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", payroll_data)

    # SEED leave_records (80)
    leave_types = ['Annual Leave', 'Sick Leave', 'Emergency Leave', 'Training Leave']
    leave_data = []
    for i in range(80):
        eid = emp_id(i % 50)
        lt = random.choice(leave_types)
        sd = (date.today() + timedelta(days=random.randint(-60, 60))).isoformat()
        days = random.randint(1, 10)
        ed = (date.fromisoformat(sd) + timedelta(days=days)).isoformat()
        status = random.choice(['Approved', 'Taken', 'Pending'])
        leave_data.append((eid, lt, sd, ed, days, status, 'Capt. Wilson' if status != 'Pending' else None, sd if status != 'Pending' else None, 'Personal'))
    c.executemany("INSERT INTO leave_records (employee_id, leave_type, start_date, end_date, total_days, status, approved_by, approval_date, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", leave_data)

    # SEED leave_balances
    balance_data = []
    for i in range(50):
        eid = emp_id(i)
        for lt, entitled in [('Annual Leave', random.randint(15, 30)), ('Sick Leave', 12), ('Emergency Leave', 5)]:
            used = random.randint(0, min(entitled, 10))
            balance_data.append((eid, lt, 2025, entitled, used, 0, 0))
    c.executemany("INSERT OR IGNORE INTO leave_balances (employee_id, leave_type, year, entitled_days, used_days, pending_days, carried_over) VALUES (?, ?, ?, ?, ?, ?, ?)", balance_data)

    # SEED benefits (100)
    btypes = ['Health Insurance', 'Dental Insurance', 'Vision Insurance', 'Life Insurance', '401k', 'Travel Benefits']
    benefit_data = []
    for i in range(100):
        eid = emp_id(i % 50)
        bt = btypes[i % len(btypes)]
        benefit_data.append((eid, bt, f'{bt} Plan', '2025-01-01', '2025-01-01', '2025-12-31', round(random.uniform(50, 300), 2), round(random.uniform(100, 500), 2), 'Active'))
    c.executemany("INSERT INTO benefits (employee_id, benefit_type, plan_name, enrollment_date, coverage_start, coverage_end, employee_contribution, employer_contribution, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", benefit_data)

    # SEED performance_reviews (50)
    review_data = []
    for i in range(50):
        eid = emp_id(i)
        review_data.append((eid, '2025-01-01', '2025-12-31', 'Capt. Robert Wilson', 'Fleet Captain', random.randint(3, 5), random.randint(3, 5), random.randint(3, 5), random.randint(3, 5), random.randint(3, 5), random.randint(3, 5), 'Good performance', None, '2025-06-15', 1, '2025-06-20'))
    c.executemany("INSERT INTO performance_reviews (employee_id, review_period_start, review_period_end, reviewer_name, reviewer_role, overall_rating, flight_skills, safety_compliance, teamwork, customer_service, punctuality, comments, improvement_areas, review_date, acknowledged, acknowledged_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", review_data)

    # SEED expense_claims (60)
    exp_types = ['Hotel', 'Meals', 'Transportation', 'Uniform', 'Medical']
    exp_data = []
    for i in range(60):
        eid = emp_id(i % 50)
        et = random.choice(exp_types)
        cd = (date.today() - timedelta(days=random.randint(0, 90))).isoformat()
        exp_data.append((eid, cd, et, f'{et} expense', round(random.uniform(25, 500), 2), 'USD', None, 'Paid', 'HR Admin', cd, cd))
    c.executemany("INSERT INTO expense_claims (employee_id, claim_date, expense_type, description, amount, currency, receipt_path, status, approved_by, approved_date, payment_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", exp_data)

    conn.commit()
    conn.close()
    print(f"[OK] hr_payroll.db created at {db_path}")


# ============================================================
# DATABASE 4: compliance_training.db
# ============================================================
def setup_compliance_training_db():
    db_path = get_db_path("compliance_training.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS training_courses (
        course_id INTEGER PRIMARY KEY AUTOINCREMENT, course_code TEXT UNIQUE NOT NULL,
        course_name TEXT NOT NULL, course_type TEXT NOT NULL, aircraft_type TEXT,
        duration_hours INTEGER NOT NULL, validity_months INTEGER NOT NULL,
        is_mandatory INTEGER DEFAULT 1, passing_score INTEGER DEFAULT 80,
        description TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS training_records (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL,
        course_id INTEGER NOT NULL, training_date TEXT NOT NULL, completion_date TEXT,
        score INTEGER, result TEXT, instructor_name TEXT, facility TEXT,
        certificate_number TEXT, expiry_date TEXT, notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS training_schedules (
        schedule_id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER NOT NULL,
        session_date TEXT NOT NULL, session_time TEXT NOT NULL, duration_hours INTEGER NOT NULL,
        instructor_name TEXT, facility TEXT, max_participants INTEGER DEFAULT 20,
        enrolled_count INTEGER DEFAULT 0, status TEXT DEFAULT 'Scheduled',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS training_enrollments (
        enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL,
        schedule_id INTEGER NOT NULL, enrollment_date TEXT DEFAULT CURRENT_DATE,
        status TEXT DEFAULT 'Enrolled', UNIQUE(employee_id, schedule_id))""")

    c.execute("""CREATE TABLE IF NOT EXISTS compliance_checks (
        check_id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT NOT NULL,
        check_type TEXT NOT NULL, check_date TEXT NOT NULL, result TEXT NOT NULL,
        next_due_date TEXT, examiner_name TEXT, remarks TEXT, is_overdue INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS safety_incidents (
        incident_id INTEGER PRIMARY KEY AUTOINCREMENT, reported_by_employee_id TEXT NOT NULL,
        flight_id INTEGER, incident_date TEXT NOT NULL, incident_type TEXT NOT NULL,
        severity TEXT, description TEXT NOT NULL, corrective_action TEXT,
        investigation_status TEXT DEFAULT 'Open', resolution_date TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL, action TEXT NOT NULL, performed_by TEXT NOT NULL,
        old_value TEXT, new_value TEXT, ip_address TEXT,
        performed_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    # SEED training_courses (25)
    courses = [
        ('B737-REC', 'Boeing 737 Recurrent', 'Recurrent', 'Boeing 737-800', 16, 12, 1, 80, 'Annual recurrent for B737'),
        ('B777-REC', 'Boeing 777 Recurrent', 'Recurrent', 'Boeing 777-300ER', 16, 12, 1, 80, 'Annual recurrent for B777'),
        ('B787-REC', 'Boeing 787 Recurrent', 'Recurrent', 'Boeing 787-9', 16, 12, 1, 80, 'Annual recurrent for B787'),
        ('A321-REC', 'Airbus A321 Recurrent', 'Recurrent', 'Airbus A321neo', 16, 12, 1, 80, 'Annual recurrent for A321'),
        ('B737-INIT', 'Boeing 737 Initial Type Rating', 'Initial', 'Boeing 737-800', 120, 60, 1, 75, 'Initial type rating'),
        ('CRM-2025', 'Crew Resource Management', 'CRM', None, 8, 12, 1, 80, 'Annual CRM training'),
        ('EVAC-REC', 'Emergency Evacuation Recurrent', 'Emergency', None, 4, 12, 1, 85, 'Emergency procedures'),
        ('SEC-AWR', 'Security Awareness', 'Security', None, 4, 24, 1, 80, 'TSA security training'),
        ('DG-CAT6', 'Dangerous Goods Cat 6', 'Dangerous Goods', None, 8, 24, 1, 80, 'DG awareness'),
        ('FA-ADV', 'Advanced First Aid', 'First Aid', None, 8, 12, 1, 80, 'First aid recurrent'),
        ('LINE-CHK', 'Line Proficiency Check', 'Line Check', None, 4, 12, 1, 80, 'Annual line check'),
        ('PROF-CHK', 'Simulator Proficiency Check', 'Recurrent', None, 4, 6, 1, 80, 'Six-monthly sim check'),
        ('CC-INIT', 'Cabin Crew Initial', 'Initial', None, 160, 36, 1, 80, 'Initial cabin crew'),
        ('CC-REC', 'Cabin Crew Recurrent', 'Recurrent', None, 16, 12, 1, 80, 'Annual cabin crew'),
        ('PUR-TRNG', 'Purser Qualification', 'Upgrade', None, 40, 36, 0, 80, 'Purser upgrade'),
        ('WNDSHR', 'Windshear Recovery', 'Recurrent', None, 4, 12, 1, 85, 'Windshear training'),
        ('ETOPS', 'ETOPS Operations', 'Differences', 'Boeing 777-300ER', 8, 24, 1, 80, 'Extended ops'),
        ('RVSM', 'RVSM Operations', 'Differences', None, 4, 24, 1, 80, 'RVSM ops'),
        ('AVSEC', 'Aviation Security Recurrent', 'Security', None, 4, 12, 1, 80, 'Security recurrent'),
        ('TCAS-ADV', 'Advanced TCAS Operations', 'Recurrent', None, 2, 12, 1, 80, 'TCAS training'),
        ('EFB-OPS', 'Electronic Flight Bag', 'Differences', None, 4, 24, 1, 80, 'EFB usage'),
        ('ICING', 'Icing Conditions', 'Recurrent', None, 4, 12, 1, 80, 'Icing ops'),
        ('CABIN-FIRE', 'Cabin Fire Fighting', 'Emergency', None, 4, 12, 1, 85, 'Fire response'),
        ('UPINIT-FO', 'FO to Captain Upgrade', 'Upgrade', None, 200, 60, 0, 80, 'Captain upgrade'),
        ('B777-TRANS', 'Boeing 777 Transition', 'Transition', 'Boeing 777-300ER', 40, 36, 1, 80, 'B737 to B777'),
    ]
    c.executemany("INSERT OR IGNORE INTO training_courses (course_code, course_name, course_type, aircraft_type, duration_hours, validity_months, is_mandatory, passing_score, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", courses)

    # SEED training_records (200)
    instructors = ['Capt. David Clark', 'Capt. Jennifer White', 'Instructor Sarah Davis']
    facilities = ['AA DFW Training Center', 'AA ORD Training Center', 'CAE Miami']
    tr_data = []
    for i in range(200):
        eid = emp_id(i % 50)
        cid = random.randint(1, 25)
        td = (date.today() - timedelta(days=random.randint(30, 365))).isoformat()
        score = random.randint(75, 100)
        result = 'Pass' if score >= 80 else 'Fail'
        exp = (date.fromisoformat(td) + timedelta(days=365)).isoformat()
        tr_data.append((eid, cid, td, td, score, result, random.choice(instructors), random.choice(facilities), f'CERT-{random.randint(100000, 999999)}', exp, None))
    c.executemany("INSERT INTO training_records (employee_id, course_id, training_date, completion_date, score, result, instructor_name, facility, certificate_number, expiry_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", tr_data)

    # SEED training_schedules (30)
    sched_data = []
    for i in range(30):
        cid = random.randint(1, 25)
        sd = (date.today() + timedelta(days=random.randint(1, 60))).isoformat()
        sched_data.append((cid, sd, f'{random.randint(8, 14):02d}:00', random.choice([4, 8, 16]), random.choice(instructors), random.choice(facilities), 20, random.randint(0, 15), 'Scheduled'))
    c.executemany("INSERT INTO training_schedules (course_id, session_date, session_time, duration_hours, instructor_name, facility, max_participants, enrolled_count, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", sched_data)

    # SEED training_enrollments (75)
    enroll_data = []
    seen = set()
    for i in range(75):
        eid = emp_id(i % 50)
        sid = random.randint(1, 30)
        if (eid, sid) not in seen:
            seen.add((eid, sid))
            enroll_data.append((eid, sid, 'Enrolled'))
    c.executemany("INSERT OR IGNORE INTO training_enrollments (employee_id, schedule_id, status) VALUES (?, ?, ?)", enroll_data)

    # SEED compliance_checks (100)
    check_types = ['Medical Exam', 'Proficiency Check', 'Line Check', 'Drug Test', 'Emergency Drill']
    examiners = ['Dr. Robert Green', 'Capt. Thomas King', 'TSA Officer Adams']
    check_data = []
    for i in range(100):
        eid = emp_id(i % 50)
        ct = random.choice(check_types)
        cd = (date.today() - timedelta(days=random.randint(0, 300))).isoformat()
        result = random.choice(['Pass'] * 9 + ['Fail'])
        next_due = (date.fromisoformat(cd) + timedelta(days=365)).isoformat()
        overdue = 1 if date.fromisoformat(next_due) < date.today() else 0
        check_data.append((eid, ct, cd, result, next_due, random.choice(examiners), None, overdue))
    c.executemany("INSERT INTO compliance_checks (employee_id, check_type, check_date, result, next_due_date, examiner_name, remarks, is_overdue) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", check_data)

    # SEED safety_incidents (15)
    inc_types = ['Safety Concern', 'Near Miss', 'Turbulence Injury', 'Equipment Failure', 'Medical Emergency']
    inc_data = []
    for i in range(15):
        eid = emp_id(random.randint(0, 49))
        inc_data.append((eid, random.randint(1, 200), (date.today() - timedelta(days=random.randint(0, 180))).isoformat(), random.choice(inc_types), random.choice(['Low', 'Medium', 'High']), f'Incident description {i+1}', 'Corrective action taken', random.choice(['Open', 'Resolved', 'Closed']), None))
    c.executemany("INSERT INTO safety_incidents (reported_by_employee_id, flight_id, incident_date, incident_type, severity, description, corrective_action, investigation_status, resolution_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", inc_data)

    # SEED audit_logs (50)
    audit_data = []
    for i in range(50):
        audit_data.append((random.choice(['crew_member', 'flight', 'training_record']), random.randint(1, 50), random.choice(['CREATE', 'UPDATE', 'VIEW']), random.choice(['admin', 'hr_manager', 'system']), None, None, f'10.0.1.{random.randint(1, 254)}'))
    c.executemany("INSERT INTO audit_logs (entity_type, entity_id, action, performed_by, old_value, new_value, ip_address) VALUES (?, ?, ?, ?, ?, ?, ?)", audit_data)

    conn.commit()
    conn.close()
    print(f"[OK] compliance_training.db created at {db_path}")


# ============================================================
# DATABASE 5: app.db
# ============================================================
def setup_app_db():
    db_path = get_db_path("app.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, full_name TEXT,
        role TEXT DEFAULT 'user', is_active INTEGER DEFAULT 1, last_login TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS conversations (
        conversation_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        session_id TEXT NOT NULL, started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_message_at TEXT DEFAULT CURRENT_TIMESTAMP, message_count INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1)""")

    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER NOT NULL,
        role TEXT NOT NULL, content TEXT NOT NULL, intent TEXT, confidence REAL,
        sql_generated TEXT, sql_result TEXT, source_documents TEXT,
        pii_masked INTEGER DEFAULT 0, processing_time_ms INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS feedback (
        feedback_id INTEGER PRIMARY KEY AUTOINCREMENT, message_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL, rating TEXT NOT NULL, comment TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS schema_metadata (
        metadata_id INTEGER PRIMARY KEY AUTOINCREMENT, db_name TEXT NOT NULL,
        table_name TEXT NOT NULL, column_details TEXT NOT NULL, row_count INTEGER,
        sample_values TEXT, ddl_statement TEXT NOT NULL, llm_description TEXT NOT NULL,
        detected_foreign_keys TEXT,
        last_crawled_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(db_name, table_name))""")

    c.execute("""CREATE TABLE IF NOT EXISTS document_chunks (
        chunk_id INTEGER PRIMARY KEY AUTOINCREMENT, document_name TEXT NOT NULL,
        document_title TEXT NOT NULL, chunk_index INTEGER NOT NULL,
        chunk_text TEXT NOT NULL, chunk_tokens INTEGER, metadata TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    # Database registry - tracks all available databases
    c.execute("""CREATE TABLE IF NOT EXISTS database_registry (
        db_id INTEGER PRIMARY KEY AUTOINCREMENT,
        db_name TEXT UNIQUE NOT NULL,
        db_path TEXT NOT NULL,
        display_name TEXT,
        description TEXT,
        source_type TEXT DEFAULT 'mock',
        is_visible INTEGER DEFAULT 1,
        is_system INTEGER DEFAULT 0,
        upload_filename TEXT,
        uploaded_by INTEGER,
        table_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    # Upload history - tracks SQL file uploads
    c.execute("""CREATE TABLE IF NOT EXISTS upload_history (
        upload_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        status TEXT DEFAULT 'processing',
        databases_created TEXT,
        tables_created INTEGER DEFAULT 0,
        error_message TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    conn.commit()
    conn.close()
    print(f"[OK] app.db created at {db_path}")


def seed_database_registry():
    """Seed the database_registry table with existing mock databases.

    Always recomputes absolute paths from the current machine's DB_DIR
    so that the registry stays correct after cloning/deploying to a new machine.
    """
    db_path = get_db_path("app.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Define mock databases to register
    mock_databases = [
        {
            "db_name": "crew_management",
            "db_path": str(DB_DIR / "crew_management.db"),
            "display_name": "Crew Management",
            "description": "Crew members, qualifications, assignments, rest records, documents, contacts, rosters",
            "source_type": "mock",
            "is_visible": 1,
            "is_system": 0,
            "table_count": 7
        },
        {
            "db_name": "flight_operations",
            "db_path": str(DB_DIR / "flight_operations.db"),
            "display_name": "Flight Operations",
            "description": "Airports, aircraft, flights, pairings, disruptions, hotels",
            "source_type": "mock",
            "is_visible": 1,
            "is_system": 0,
            "table_count": 8
        },
        {
            "db_name": "hr_payroll",
            "db_path": str(DB_DIR / "hr_payroll.db"),
            "display_name": "HR & Payroll",
            "description": "Pay grades, payroll records, leave, benefits, performance reviews, expenses",
            "source_type": "mock",
            "is_visible": 1,
            "is_system": 0,
            "table_count": 7
        },
        {
            "db_name": "compliance_training",
            "db_path": str(DB_DIR / "compliance_training.db"),
            "display_name": "Compliance & Training",
            "description": "Training courses/records, schedules, compliance checks, safety incidents, audit logs",
            "source_type": "mock",
            "is_visible": 1,
            "is_system": 0,
            "table_count": 7
        },
    ]

    for db in mock_databases:
        c.execute("""
            INSERT OR REPLACE INTO database_registry
            (db_name, db_path, display_name, description, source_type, is_visible, is_system, table_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (db["db_name"], db["db_path"], db["display_name"], db["description"],
              db["source_type"], db["is_visible"], db["is_system"], db["table_count"]))

    # Also fix paths for any uploaded databases whose paths have stale absolute paths
    c.execute("SELECT db_name, db_path FROM database_registry WHERE source_type != 'mock'")
    for row in c.fetchall():
        old_path = row[0] if isinstance(row, tuple) else row["db_path"]
        db_name = row[0] if isinstance(row, tuple) else row["db_name"]
        filename = os.path.basename(old_path if isinstance(row, tuple) else row[1])
        new_path = str(DB_DIR / filename)
        if old_path != new_path and os.path.exists(new_path):
            c.execute("UPDATE database_registry SET db_path = ? WHERE db_name = ?", (new_path, db_name))

    conn.commit()
    conn.close()
    print(f"[OK] database_registry seeded with mock databases (DB_DIR={DB_DIR})")


def setup_all():
    """Create all databases with tables and seed data."""
    print("=" * 60)
    print("Setting up American Airlines Crew Chatbot databases...")
    print("=" * 60)
    ensure_dirs()
    setup_crew_management_db()
    setup_flight_operations_db()
    setup_hr_payroll_db()
    setup_compliance_training_db()
    setup_app_db()
    seed_database_registry()
    print("=" * 60)
    print("All databases created successfully!")
    print(f"Location: {DB_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    setup_all()
