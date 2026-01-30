"""Populate schema_metadata table with descriptions - uses LLM for uploaded DBs."""
import sys
import os
import sqlite3
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import settings


def _generate_llm_description(db_name: str, table_name: str,
                               col_details: str, sample_str: str) -> str:
    """Generate a rich table description using LLM. Returns empty string on failure."""
    try:
        from backend.llm.client import get_llm_client
        from backend.llm.prompts import SCHEMA_DESCRIPTION_PROMPT

        client = get_llm_client()
        prompt = SCHEMA_DESCRIPTION_PROMPT.format(
            db_name=db_name,
            table_name=table_name,
            columns=col_details,
            sample_data=sample_str
        )

        description = client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
            use_fast_model=True
        )
        return description.strip() if description else ""
    except Exception as e:
        print(f"  LLM description failed for {db_name}.{table_name}: {e}")
        return ""


def get_db_mapping():
    """Get database mapping from registry or fallback to static."""
    try:
        from backend.db.registry import get_database_registry
        registry = get_database_registry()
        mapping = registry.get_all_db_mapping()
        if mapping:
            # Add app database
            mapping["app"] = settings.app_db_path
            return mapping
    except Exception as e:
        print(f"Note: Using static DB mapping (registry not available: {e})")

    # Fallback to static mapping
    from backend.db.session import DB_MAPPING
    return DB_MAPPING

# Hand-written descriptions for each table (used by vector search)
TABLE_DESCRIPTIONS = {
    "crew_management": {
        "crew_members": "Master crew records with employee_id, name, email, phone, date of birth, passport, hire date, seniority, crew role (Captain, First Officer, Purser, Cabin Crew), base airport, and status. Use this to find crew by name, role, base, status. The employee_id column links to all other databases.",
        "crew_qualifications": "Crew licenses, type ratings, medical certificates, language proficiency, security clearances, dangerous goods and first aid certifications. Linked by employee_id. Use this to check expiring qualifications or find crew with specific ratings.",
        "crew_assignments": "Crew-to-flight assignments with duty start/end times, report/release times, assignment role and status. Linked by employee_id. Use this to find who is assigned to which flight and duty schedules.",
        "crew_rest_records": "Rest period tracking for FAR 117 compliance. Records rest start/end, location, type (minimum/reduced/extended/weekly/split/layover), duration, and whether it meets FAR 117. Linked by employee_id. Use for rest compliance queries.",
        "crew_documents": "Uploaded crew documents like passport, visa, license, medical certificate, training certificate. Tracks expiry dates and verification status. Linked by employee_id.",
        "crew_contacts": "Emergency contacts for crew members - name, relationship, phone, email, address, and whether primary contact. Linked by employee_id.",
        "crew_roster": "Monthly crew roster/rota data with assignment status (Awarded, Reserve, Standby, Not Awarded, Training, Leave). Contains bid submission, awarded flag, not_awarded_reason (Seniority, Qualification Gap, Schedule Conflict, Base Mismatch, Medical Hold, Training Conflict, Visa Issue, Staffing Requirement, Rest Requirement, Disciplinary Action, Probation Period, Union Dispute, Crew Complement Full, Aircraft Type Mismatch, Insufficient Flight Hours, Administrative Error, Voluntary Withdrawal, FAA Restriction, Fatigue Risk Flag), assigned flights count, reserve days, standby days, training days, leave days, off days, total duty days, flight hours, block hours. Linked by employee_id. Use this for roster queries, awarded vs not awarded analysis, reserve/standby counts, and why crew were not awarded.",
    },
    "flight_operations": {
        "airports": "Airport master data with IATA/ICAO codes, name, city, country, timezone, lat/long, and whether it is an American Airlines hub. Contains 30 US airports.",
        "aircraft": "Fleet information with registration, aircraft type (Boeing 737/777/787, Airbus A321/A320, Embraer E175), seat capacity, range, year manufactured, maintenance dates, status, and home base.",
        "flights": "Flight schedule with flight number, aircraft, departure/arrival airports, scheduled/actual times, status (Scheduled/Departed/Arrived/Cancelled/Delayed), block time, delay minutes and reason. Contains 200+ flights.",
        "flight_legs": "Multi-segment flight legs with sequence, departure/arrival airports and times for each leg.",
        "crew_pairings": "Duty trip groupings (pairings) with pairing code, dates, base airport, total duty/flight hours, number of legs, and status.",
        "pairing_flights": "Junction table linking pairings to flights with sequence number and duty day.",
        "disruptions": "Irregular operations - delays, cancellations, diversions, aircraft/crew swaps, weather/ATC holds. Includes reported_by_employee_id, severity, reason, resolution, and affected crew count.",
        "hotels": "Crew layover hotels with name, airport code, address, phone, star rating, crew rate per night, and distance to airport.",
    },
    "hr_payroll": {
        "pay_grades": "Salary structures by crew role and seniority band. Includes base monthly salary, flight hour rate, per diem rate. Roles: Captain, First Officer, Purser, Senior Cabin Crew, Cabin Crew.",
        "payroll_records": "Monthly payroll records per crew member with base pay, flight hours, flight hour pay, per diem, overtime, deductions, tax, and net pay. 6 months of data for 50 crew. Linked by employee_id.",
        "leave_records": "Leave requests with type (Annual/Sick/Emergency/Training), dates, total days, approval status, and approver. Linked by employee_id.",
        "leave_balances": "Current leave entitlements per crew member - entitled days, used days, pending days, carried over, by leave type and year. Linked by employee_id.",
        "benefits": "Benefits enrollment - health/dental/vision/life insurance, 401k, travel benefits. Shows employee and employer contributions. Linked by employee_id.",
        "performance_reviews": "Annual performance reviews with ratings for flight skills, safety compliance, teamwork, customer service, punctuality. Scale 1-5. Linked by employee_id.",
        "expense_claims": "Expense reimbursement claims for hotel, meals, transportation, uniform, medical. Tracks amount, status, and approval. Linked by employee_id.",
    },
    "compliance_training": {
        "training_courses": "Available training programs with course code, name, type (Recurrent/Initial/Emergency/CRM/Upgrade), aircraft type, duration, validity months, passing score.",
        "training_records": "Crew training completions with date, score, pass/fail result, instructor, facility, certificate number, and expiry date. Linked by employee_id.",
        "training_schedules": "Upcoming training sessions with date, time, instructor, facility, max participants, and enrollment count.",
        "training_enrollments": "Crew enrollment in training sessions - links crew to scheduled sessions with enrollment status. Linked by employee_id.",
        "compliance_checks": "Regulatory compliance checks - medical exams, proficiency checks, line checks, drug tests, emergency drills. Tracks result, next due date, and overdue status. Linked by employee_id.",
        "safety_incidents": "Safety incident reports with type (concern/near miss/turbulence injury/equipment failure/medical), severity, description, corrective action, investigation status. Linked by reported_by_employee_id.",
        "audit_logs": "System audit trail tracking entity changes - who did what, when, from which IP address.",
    },
}


def populate():
    """Populate schema_metadata in app.db."""
    print("Populating schema metadata...")

    # Get database mapping from registry or static config
    db_mapping = get_db_mapping()

    app_conn = sqlite3.connect(settings.app_db_path)
    app_c = app_conn.cursor()

    # Clear existing
    app_c.execute("DELETE FROM schema_metadata")

    count = 0
    for db_name, db_path in db_mapping.items():
        if db_name == "app":
            continue
        if not os.path.exists(db_path):
            print(f"  Skipping {db_name} - not found")
            continue

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [r['name'] for r in c.fetchall()]

        for table_name in tables:
            # Get columns
            c.execute(f"PRAGMA table_info([{table_name}])")
            columns = []
            for col in c.fetchall():
                columns.append(f"{col['name']} ({col['type']})")
            col_details = ", ".join(columns)

            # Get row count
            c.execute(f"SELECT COUNT(*) as cnt FROM [{table_name}]")
            row_count = c.fetchone()['cnt']

            # Get DDL
            c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            ddl = c.fetchone()['sql'] or ""

            # Get sample values
            c.execute(f"SELECT * FROM [{table_name}] LIMIT 2")
            sample = [dict(r) for r in c.fetchall()]
            sample_str = json.dumps(sample, default=str)[:500]

            # Get description: hand-written for mock DBs, LLM for uploaded DBs
            desc = TABLE_DESCRIPTIONS.get(db_name, {}).get(table_name, "")

            if not desc:
                # No hand-written description — try LLM if API key is available
                if settings.LLM_API_KEY:
                    desc = _generate_llm_description(db_name, table_name, col_details, sample_str)

                # Fallback to improved template
                if not desc:
                    col_names_lower = col_details.lower()
                    heuristic = "general data"
                    if "employee" in col_names_lower or "name" in col_names_lower:
                        heuristic = "personnel or employee records"
                    elif "amount" in col_names_lower or "price" in col_names_lower or "pay" in col_names_lower:
                        heuristic = "financial or payment data"
                    elif "date" in col_names_lower and "flight" in col_names_lower:
                        heuristic = "flight schedule or operations data"
                    elif "score" in col_names_lower or "training" in col_names_lower:
                        heuristic = "training or assessment records"

                    desc = (f"Table {table_name} in {db_name} database. "
                            f"Contains {row_count} rows. "
                            f"Columns: {col_details[:200]}. "
                            f"Sample values suggest this table stores {heuristic}.")

            app_c.execute("""
                INSERT OR REPLACE INTO schema_metadata
                (db_name, table_name, column_details, row_count, sample_values, ddl_statement, llm_description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (db_name, table_name, col_details, row_count, sample_str, ddl, desc))
            count += 1
            print(f"  {db_name}.{table_name} ({row_count} rows)")

        conn.close()

    app_conn.commit()
    app_conn.close()
    print(f"\nDone! Indexed {count} tables into schema_metadata.")


if __name__ == "__main__":
    populate()
