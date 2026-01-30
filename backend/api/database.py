"""Database management API endpoints."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Query, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os

from backend.db.registry import get_database_registry
from backend.sql_upload.upload_service import UploadService, refresh_all_schema, remove_schema_for_database
from backend.api.auth import get_current_user, require_admin


router = APIRouter()


# Request/Response Models
class VisibilityRequest(BaseModel):
    is_visible: bool


class DatabaseInfo(BaseModel):
    db_name: str
    db_path: str
    display_name: Optional[str]
    description: Optional[str]
    source_type: str
    is_visible: bool
    is_system: bool
    table_count: int
    upload_filename: Optional[str]
    uploaded_by: Optional[int]
    created_at: Optional[str]


class DatabaseListResponse(BaseModel):
    databases: List[DatabaseInfo]
    total: int
    visible_count: int


class UploadResponse(BaseModel):
    success: bool
    upload_id: Optional[int]
    dialect: str = "unknown"
    databases_created: List[Dict[str, Any]]
    total_tables: int
    total_rows: int
    errors: List[str]
    warnings: List[str]


class UploadHistoryItem(BaseModel):
    upload_id: int
    user_id: int
    filename: str
    status: str
    databases_created: Optional[str]
    tables_created: int
    error_message: Optional[str]
    created_at: str


@router.post("/upload", response_model=UploadResponse)
async def upload_sql_file(
    file: UploadFile = File(...),
    auto_visible: bool = Query(True, description="Make database visible after upload"),
    current_user: dict = Depends(require_admin)
):
    """Upload a PostgreSQL SQL dump file and create SQLite database.

    - Accepts .sql files up to 100MB
    - Supports both pg_dump (single DB) and pg_dumpall (multi-DB) formats
    - Automatically converts PostgreSQL syntax to SQLite
    - Registers created databases in the database registry
    """
    # Validate file type
    if not file.filename.lower().endswith(".sql"):
        raise HTTPException(status_code=400, detail="File must have .sql extension")

    try:
        # Read file content
        content = await file.read()

        # Check file size
        if len(content) > 100 * 1024 * 1024:  # 100MB
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 100MB")

        # Decode content
        try:
            sql_content = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                sql_content = content.decode("latin-1")
            except UnicodeDecodeError:
                raise HTTPException(status_code=400, detail="Unable to decode file. Please use UTF-8 encoding.")

        # Process upload
        service = UploadService()

        # Validate file
        is_valid, error_msg = service.validate_file(sql_content, file.filename)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Process the SQL file
        result = service.process_upload(
            file_content=sql_content,
            filename=file.filename,
            user_id=current_user["user_id"],
            auto_visible=auto_visible
        )

        return UploadResponse(
            success=result.success,
            upload_id=result.upload_id,
            dialect=result.dialect,
            databases_created=result.databases_created,
            total_tables=result.total_tables,
            total_rows=result.total_rows,
            errors=result.errors,
            warnings=result.warnings
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")


@router.post("/upload-csv", response_model=UploadResponse)
async def upload_csv_files(
    files: List[UploadFile] = File(...),
    db_name: str = Form(...),
    is_new_db: bool = Form(True),
    auto_visible: bool = Form(True),
    current_user: dict = Depends(require_admin)
):
    """Upload CSV/Excel files to create tables in a SQLite database.

    - Accepts .csv, .xlsx, .xls files
    - Each file becomes a table (filename -> table name)
    - Can create a new database or add tables to an existing one
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    if not db_name or not db_name.strip():
        raise HTTPException(status_code=400, detail="Database name is required")

    # Validate file extensions
    allowed_extensions = {'.csv', '.xlsx', '.xls'}
    file_tuples = []
    for f in files:
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {f.filename}. Allowed: .csv, .xlsx, .xls"
            )
        content = await f.read()
        if len(content) > 100 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"File '{f.filename}' too large. Max 100MB.")
        file_tuples.append((f.filename, content))

    try:
        service = UploadService()
        result = service.process_csv_upload(
            files=file_tuples,
            db_name=db_name,
            user_id=current_user["user_id"],
            is_new_db=is_new_db,
            auto_visible=auto_visible
        )

        return UploadResponse(
            success=result.success,
            upload_id=result.upload_id,
            dialect=result.dialect,
            databases_created=result.databases_created,
            total_tables=result.total_tables,
            total_rows=result.total_rows,
            errors=result.errors,
            warnings=result.warnings
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV upload failed: {str(e)}")


@router.get("/list", response_model=DatabaseListResponse)
async def list_databases(
    current_user: dict = Depends(get_current_user)
):
    """List all registered databases."""
    registry = get_database_registry()

    all_dbs = registry.get_all_databases()

    databases = []
    for db_name, info in all_dbs.items():
        if db_name == "app":
            continue  # Skip app database

        databases.append(DatabaseInfo(
            db_name=db_name,
            db_path=info["db_path"],
            display_name=info.get("display_name"),
            description=info.get("description"),
            source_type=info.get("source_type", "unknown"),
            is_visible=True,  # All databases are now visible
            is_system=bool(info.get("is_system")),
            table_count=info.get("table_count", 0),
            upload_filename=info.get("upload_filename"),
            uploaded_by=info.get("uploaded_by"),
            created_at=info.get("created_at")
        ))

    return DatabaseListResponse(
        databases=databases,
        total=len(databases),
        visible_count=len(databases)
    )


@router.put("/{db_name}/visibility", response_model=dict)
async def set_database_visibility(
    db_name: str,
    request: VisibilityRequest,
    current_user: dict = Depends(require_admin)
):
    """Deprecated: All databases are now always visible.

    This endpoint is kept for backward compatibility but no longer changes visibility.
    """
    registry = get_database_registry()

    # Check if database exists
    db_info = registry.get_database_info(db_name)
    if not db_info:
        raise HTTPException(status_code=404, detail=f"Database '{db_name}' not found")

    return {
        "success": True,
        "db_name": db_name,
        "is_visible": True,
        "message": "Visibility feature has been removed. All databases are always visible."
    }


@router.delete("/{db_name}", response_model=dict)
async def delete_database(
    db_name: str,
    current_user: dict = Depends(require_admin)
):
    """Delete an uploaded database.

    - Only uploaded databases can be deleted
    - Mock databases cannot be deleted
    - Deletes both the registry entry and the database file
    - Removes schema metadata and refreshes FAISS index
    """
    registry = get_database_registry()

    # Check if database exists
    db_info = registry.get_database_info(db_name)
    if not db_info:
        raise HTTPException(status_code=404, detail=f"Database '{db_name}' not found")

    # Check if it's a mock database
    if db_info.get("source_type") == "mock":
        raise HTTPException(
            status_code=400,
            detail="Cannot delete mock databases."
        )

    # Delete the database
    success = registry.delete_uploaded_database(db_name)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete database")

    # Remove schema metadata and refresh FAISS index
    try:
        remove_schema_for_database(db_name)
    except Exception as e:
        print(f"Warning: Failed to remove schema for {db_name}: {e}")

    return {
        "success": True,
        "db_name": db_name,
        "message": f"Database '{db_name}' has been deleted and schema index refreshed"
    }


@router.get("/upload-history", response_model=List[UploadHistoryItem])
async def get_upload_history(
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_admin)
):
    """Get upload history for admin review."""
    service = UploadService()
    history = service.get_upload_history(limit=limit)

    return [
        UploadHistoryItem(
            upload_id=h["upload_id"],
            user_id=h["user_id"],
            filename=h["filename"],
            status=h["status"],
            databases_created=h.get("databases_created"),
            tables_created=h.get("tables_created", 0),
            error_message=h.get("error_message"),
            created_at=h["created_at"]
        )
        for h in history
    ]


@router.get("/{db_name}/info", response_model=DatabaseInfo)
async def get_database_info(
    db_name: str,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed information about a specific database."""
    registry = get_database_registry()

    db_info = registry.get_database_info(db_name)
    if not db_info:
        raise HTTPException(status_code=404, detail=f"Database '{db_name}' not found")

    return DatabaseInfo(
        db_name=db_name,
        db_path=db_info["db_path"],
        display_name=db_info.get("display_name"),
        description=db_info.get("description"),
        source_type=db_info.get("source_type", "unknown"),
        is_visible=True,  # All databases are now visible
        is_system=bool(db_info.get("is_system")),
        table_count=db_info.get("table_count", 0),
        upload_filename=db_info.get("upload_filename"),
        uploaded_by=db_info.get("uploaded_by"),
        created_at=db_info.get("created_at")
    )
