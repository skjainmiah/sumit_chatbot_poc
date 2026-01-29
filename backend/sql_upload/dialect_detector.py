"""SQL dialect auto-detector.

Automatically detects whether SQL content is PostgreSQL or MSSQL based on syntax patterns.
"""
import re
from enum import Enum
from typing import Tuple


class SqlDialect(Enum):
    """Supported SQL dialects."""
    POSTGRESQL = "postgresql"
    MSSQL = "mssql"
    UNKNOWN = "unknown"


class DialectDetector:
    """Detect SQL dialect from script content."""

    # PostgreSQL-specific patterns
    PG_PATTERNS = [
        (r'\bSERIAL\b', 10),                              # PostgreSQL auto-increment
        (r'\bBIGSERIAL\b', 10),
        (r'\bSMALLSERIAL\b', 10),
        (r'::[\w\[\]]+', 8),                              # PostgreSQL type casting
        (r'\bTIMESTAMPTZ\b', 10),                         # PostgreSQL timestamp with tz
        (r'\bJSONB\b', 10),                               # PostgreSQL JSONB
        (r'\bBYTEA\b', 10),                               # PostgreSQL binary
        (r'\bTEXT\[\]', 10),                              # PostgreSQL arrays
        (r'\\connect\s+\w+', 15),                         # pg_dump database switch
        (r'COPY\s+\w+.*FROM\s+stdin', 15),                # pg_dump COPY command
        (r'\bON\s+CONFLICT\b', 8),                        # PostgreSQL upsert
        (r'\bRETURNING\b', 5),                            # PostgreSQL RETURNING clause
        (r'pg_catalog', 10),                              # PostgreSQL catalog
        (r'pg_dump', 15),                                 # pg_dump marker
        (r'\bINET\b', 8),                                 # PostgreSQL network type
        (r'\bCIDR\b', 8),                                 # PostgreSQL network type
        (r'\bUUID\b', 3),                                 # Both support UUID
        (r"'[^']*'::\w+", 8),                             # Cast syntax
        (r'\bARRAY\[', 10),                               # PostgreSQL array constructor
        (r'\bBOOLEAN\b', 5),                              # PostgreSQL boolean
        (r'SET\s+search_path', 10),                       # PostgreSQL schema path
        (r'CREATE\s+EXTENSION', 10),                      # PostgreSQL extensions
        (r'\$\$.*?\$\$', 5),                              # PostgreSQL dollar quoting
    ]

    # MSSQL-specific patterns
    MSSQL_PATTERNS = [
        (r'\bIDENTITY\s*\(\d+\s*,\s*\d+\)', 15),          # MSSQL auto-increment
        (r'\bNVARCHAR\b', 10),                            # MSSQL unicode varchar
        (r'\bNCHAR\b', 10),                               # MSSQL unicode char
        (r'\bNTEXT\b', 10),                               # MSSQL unicode text
        (r'\bDATETIME2\b', 10),                           # MSSQL datetime2
        (r'\bSMALLDATETIME\b', 10),                       # MSSQL smalldatetime
        (r'\bDATETIMEOFFSET\b', 10),                      # MSSQL datetimeoffset
        (r'\bMONEY\b', 8),                                # MSSQL money type
        (r'\bSMALLMONEY\b', 8),                           # MSSQL smallmoney
        (r'\bBIT\b', 5),                                  # MSSQL bit type
        (r'\bIMAGE\b', 8),                                # MSSQL image type
        (r'\bUNIQUEIDENTIFIER\b', 10),                    # MSSQL GUID
        (r'\bHIERARCHYID\b', 10),                         # MSSQL hierarchyid
        (r'\bGEOGRAPHY\b', 8),                            # MSSQL geography
        (r'\bGEOMETRY\b', 8),                             # MSSQL geometry
        (r'\[[\w\s]+\]', 3),                              # MSSQL bracket identifiers
        (r'^\s*GO\s*$', 15),                              # MSSQL batch separator
        (r'\bUSE\s+\[?\w+\]?', 8),                        # MSSQL USE database
        (r'\bGETDATE\s*\(\)', 10),                        # MSSQL getdate()
        (r'\bSYSDATETIME\s*\(\)', 10),                    # MSSQL sysdatetime()
        (r'\bNEWID\s*\(\)', 10),                          # MSSQL newid()
        (r'\bISNULL\s*\(', 8),                            # MSSQL isnull()
        (r"N'[^']*'", 5),                                 # MSSQL unicode string
        (r'\bTOP\s+\d+', 10),                             # MSSQL TOP clause
        (r'\bWITH\s*\(\s*NOLOCK\s*\)', 10),               # MSSQL table hints
        (r'\bCLUSTERED\b', 8),                            # MSSQL clustered index
        (r'\bNONCLUSTERED\b', 8),                         # MSSQL nonclustered index
        (r'\bON\s+\[PRIMARY\]', 10),                      # MSSQL filegroup
        (r'\bTEXTIMAGE_ON\b', 10),                        # MSSQL textimage
        (r'\bSET\s+ANSI_NULLS', 10),                      # MSSQL settings
        (r'\bSET\s+QUOTED_IDENTIFIER', 10),               # MSSQL settings
        (r'\bSET\s+NOCOUNT', 8),                          # MSSQL settings
        (r'@@IDENTITY', 10),                              # MSSQL identity
        (r'@@ROWCOUNT', 8),                               # MSSQL rowcount
        (r'\bdbo\.\w+', 8),                               # MSSQL default schema
        (r'sp_\w+', 5),                                   # MSSQL system procs
        (r'xp_\w+', 5),                                   # MSSQL extended procs
    ]

    def detect(self, sql_content: str) -> Tuple[SqlDialect, float]:
        """Detect SQL dialect from content.

        Returns:
            Tuple of (SqlDialect, confidence_score)
            Confidence score is between 0.0 and 1.0
        """
        pg_score = 0
        mssql_score = 0

        # Check PostgreSQL patterns
        for pattern, weight in self.PG_PATTERNS:
            matches = len(re.findall(pattern, sql_content, re.IGNORECASE | re.MULTILINE))
            pg_score += matches * weight

        # Check MSSQL patterns
        for pattern, weight in self.MSSQL_PATTERNS:
            matches = len(re.findall(pattern, sql_content, re.IGNORECASE | re.MULTILINE))
            mssql_score += matches * weight

        total_score = pg_score + mssql_score

        if total_score == 0:
            return SqlDialect.UNKNOWN, 0.0

        if pg_score > mssql_score:
            confidence = pg_score / total_score
            return SqlDialect.POSTGRESQL, confidence
        elif mssql_score > pg_score:
            confidence = mssql_score / total_score
            return SqlDialect.MSSQL, confidence
        else:
            # Equal scores - check for definitive markers
            if re.search(r'pg_dump|\\connect|COPY.*FROM stdin', sql_content, re.IGNORECASE):
                return SqlDialect.POSTGRESQL, 0.6
            if re.search(r'^\s*GO\s*$|IDENTITY\s*\(\d', sql_content, re.IGNORECASE | re.MULTILINE):
                return SqlDialect.MSSQL, 0.6

            return SqlDialect.UNKNOWN, 0.5

    def detect_simple(self, sql_content: str) -> SqlDialect:
        """Simple detection that returns just the dialect."""
        dialect, _ = self.detect(sql_content)
        return dialect


def detect_sql_dialect(sql_content: str) -> Tuple[SqlDialect, float]:
    """Convenience function to detect SQL dialect."""
    detector = DialectDetector()
    return detector.detect(sql_content)
