"""One-time script to save column descriptions for combineddatalax.sheet1."""
import sqlite3
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import settings

descriptions = {
    "LegalityPostQLAStatusID": "Unique ID for the post-QLA (Quality Legality Assessment) status record",
    "LegalityQLADetailsID": "Foreign key linking to the QLA details record",
    "PostQLAStateID": "State/status of the post-QLA check (e.g., passed, failed, pending)",
    "LegalityContextID": "ID of the legality context being evaluated (values: 1-10)",
    "LegalityPhaseID": "Phase of the legality check process (values: 1=initial, 3=final)",
    "QLARuleID": "ID of the specific QLA rule being evaluated",
    "QLARuleName": "Name of the QLA rule (e.g., 24X7REST, TOUCHFD, DBLSTBY, RSTREQ, SpkrQualCheck)",
    "LegalityQLADetailsID.1": "Duplicate/secondary reference to QLA details ID",
    "Request": "Request value for the QLA rule evaluation",
    "Response": "Response value from the QLA rule evaluation",
    "CreatedBy": "Employee ID of who created this record",
    "CreateDate": "Timestamp when this record was created",
    "UpdatedBy": "Employee ID of who last updated this record",
    "UpdatedDate": "Timestamp when this record was last updated",
    "ReservesLegalityID": "Unique ID for the reserves legality check record",
    "LegalityPhaseID.1": "Duplicate reference to legality phase ID",
    "ReservesLegalityID.1": "Duplicate reference to reserves legality ID",
    "ReservesCrewMemberID": "Unique ID linking to the reserves crew member",
    "BaseDateID": "ID of the base date for scheduling reference",
    "SequencePositionDetailsID": "ID linking to sequence position details",
    "StandByID": "ID of the standby assignment (null if not on standby)",
    "MovableDays": "Number of movable/flexible days for the crew member",
    "LineHolderDays": "Number of line holder days assigned",
    "ReservesLegalityContextDetailsID": "ID for detailed legality context in reserves",
    "LegalityContextsID": "ID of the legality context (values: 1,2,3,4,9,10) - determines which legality rules apply",
    "LegalityPhaseID.2": "Duplicate reference to legality phase ID",
    "IsLegal": "Whether the crew member is legal for this assignment (1=Legal, 0=Not Legal)",
    "ReservesLegalityID.2": "Duplicate reference to reserves legality ID",
    "IsOver35By7": "Flag if over 35 hours in 7 days (1=Yes, 0=No)",
    "IsOver35By7LH": "Flag if over 35 hours in 7 days for line holders (1=Yes, 0=No)",
    "EmployeeID": "Unique employee identifier (numeric, range: 46496-774459, 130 distinct employees in LAX base)",
    "SeniorityNumber": "Seniority ranking number for the crew member",
    "BaseDateID.1": "Duplicate reference to base date ID",
    "AVLDays": "Available days for the crew member",
    "AVLDaysWithFT": "Available days including flight time",
    "ASGDaysWithFT": "Assigned days including flight time",
    "IsVolunteer": "Whether the crew member volunteered (1=Yes, 0=No)",
    "ReservesCrewMemberID.1": "Duplicate reference to reserves crew member ID",
    "FirstName": "Crew member first name",
    "LastName": "Crew member last name",
    "IsSick": "Whether the crew member is on sick status (1=Yes, 0=No)",
    "ASGSequence": "Number of assigned sequences",
    "ASGStandby": "Number of assigned standby duties",
    "ASGDays": "Total number of assigned days",
    "ETBonFD": "Estimated time block on flight duty",
    "IsCompletelyAvailableReserve": "Whether fully available as reserve (1=Yes, 0=No)",
    "SequencePositionDetailsID.1": "Duplicate reference to sequence position details ID",
    "SequencePosition": "Position within the sequence (values: 1-5)",
    "SequenceID": "Unique identifier for the flight sequence (values: 801111, 801112, 801114, 801116)",
    "OpenTime": "Timestamp when the sequence was opened for bidding",
    "ExcludeReasonID": "ID for reason of exclusion (null if not excluded)",
    "DurationInDays": "Duration of the sequence in days",
    "SequenceEndDateTime": "End date and time of the sequence",
    "TotalDutyPeriod": "Total number of duty periods in the sequence",
    "CoTerminalStation": "Co-terminal station code",
    "SatelliteStation": "Satellite station code (if any)",
    "OriginationDate": "Date the sequence originates",
    "TotalCreditNextMonth": "Total credit hours applied to next month",
    "TotalCreditCurrentMonth": "Total credit hours for current month",
    "SequenceDepartureDateTime": "Departure date and time of the sequence",
    "LayOverStations": "Layover station codes during the sequence",
    "LegsPerDutyPeriod": "Number of flight legs per duty period",
    "EquipmentGroup": "Aircraft equipment group ID",
    "MultipleEquipments": "Whether sequence uses multiple aircraft types (1=Yes, 0=No)",
    "SequenceStartDateTime": "Start date and time of the sequence",
    "SequenceID.1": "Duplicate reference to sequence ID",
    "BaseDateID.2": "Duplicate reference to base date ID",
    "SequenceNumber": "Human-readable sequence number",
    "BaseDateID.3": "Duplicate reference to base date ID",
    "BaseID": "ID of the crew base location",
    "ProcessingDate": "Date the record was processed",
    "StartDateTime": "Start date and time of the assignment period",
    "EndDateTime": "End date and time of the assignment period",
    "InitiatedEmployeeID": "Employee ID of who initiated the process",
    "InitiatedFirstName": "First name of the initiator",
    "InitiatedLastName": "Last name of the initiator",
    "ModifiedEmployeeID": "Employee ID of who modified the record",
    "ModifiedLastName": "Last name of modifier",
    "ModifiedFirstName": "First name of modifier",
    "CancelledProcessingDate": "Date when processing was cancelled (null if not cancelled)",
    "CancelledEmployeeID": "Employee ID of who cancelled (null if not cancelled)",
    "CancelledFirstName": "First name of canceller (null if not cancelled)",
    "CancelledLastName": "Last name of canceller (null if not cancelled)",
    "MockProcessingDate": "Mock/test processing date (null in production)",
    "BaseID.1": "Duplicate reference to base ID",
    "BaseCD": "Base code (all records are LAX)",
    "BaseName": "Base name (all records are Los Angeles)",
    "TimeZoneID": "ID of the timezone for the base",
    "TimeZone": "Timezone name for the base",
}


def main():
    app_db = settings.app_db_path
    print(f"Using app DB: {app_db}")

    conn = sqlite3.connect(app_db)
    cursor = conn.cursor()

    # Check if record exists
    cursor.execute(
        "SELECT COUNT(*) FROM schema_metadata WHERE db_name = ? AND table_name = ?",
        ("combineddatalax", "sheet1")
    )
    count = cursor.fetchone()[0]

    if count == 0:
        print("ERROR: No schema_metadata entry for combineddatalax.sheet1")
        print("The database may need to be re-uploaded or schema metadata populated first.")
        conn.close()
        return

    # Update column descriptions
    desc_json = json.dumps(descriptions)
    cursor.execute(
        "UPDATE schema_metadata SET column_descriptions = ? WHERE db_name = ? AND table_name = ?",
        (desc_json, "combineddatalax", "sheet1")
    )
    conn.commit()
    print(f"Saved {len(descriptions)} column descriptions for combineddatalax.sheet1")

    # Also update the table description to be more helpful
    table_desc = (
        "Reserves legality assessment data for LAX base crew members. "
        "Contains QLA (Quality Legality Assessment) rule evaluations showing whether "
        "crew members are legal for specific flight sequences and positions. "
        "Key columns: EmployeeID (numeric 46496-774459), SequenceID (801111-801116), "
        "SequencePosition (1-5), IsLegal (0/1), LegalityContextsID (1-10), "
        "QLARuleName (rule names like 24X7REST, TOUCHFD). "
        "All data is for LAX (Los Angeles) base. 130 distinct employees, 18588 total records."
    )
    cursor.execute(
        "UPDATE schema_metadata SET llm_description = ? WHERE db_name = ? AND table_name = ?",
        (table_desc, "combineddatalax", "sheet1")
    )
    conn.commit()
    print("Updated table description")

    conn.close()
    print("Done!")


if __name__ == "__main__":
    main()
