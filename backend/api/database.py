"""Database management API endpoints."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os

from backend.db.registry import get_database_registry
from backend.sql_upload.upload_service import UploadService, refresh_schema_for_visible_databases, remove_schema_for_database
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


@router.get("/list", response_model=DatabaseListResponse)
async def list_databases(
    include_hidden: bool = Query(False, description="Include hidden databases"),
    current_user: dict = Depends(get_current_user)
):
    """List all registered databases.

    - Regular users see only visible databases
    - Admins can see all databases with include_hidden=true
    """
    registry = get_database_registry()

    # Check if user can see hidden databases
    is_admin = current_user.get("role") == "admin"
    show_hidden = include_hidden and is_admin

    all_dbs = registry.get_all_databases()

    databases = []
    for db_name, info in all_dbs.items():
        if db_name == "app":
            continue  # Skip app database

        if not show_hidden and not info["is_visible"]:
            continue

        databases.append(DatabaseInfo(
            db_name=db_name,
            db_path=info["db_path"],
            display_name=info.get("display_name"),
            description=info.get("description"),
            source_type=info.get("source_type", "unknown"),
            is_visible=bool(info.get("is_visible")),
            is_system=bool(info.get("is_system")),
            table_count=info.get("table_count", 0),
            upload_filename=info.get("upload_filename"),
            uploaded_by=info.get("uploaded_by"),
            created_at=info.get("created_at")
        ))

    visible_count = sum(1 for db in databases if db.is_visible)

    return DatabaseListResponse(
        databases=databases,
        total=len(databases),
        visible_count=visible_count
    )


@router.put("/{db_name}/visibility", response_model=dict)
async def set_database_visibility(
    db_name: str,
    request: VisibilityRequest,
    current_user: dict = Depends(require_admin)
):
    """Toggle database visibility for chat queries.

    - Visible databases are included in SQL query schema retrieval
    - Hidden databases are excluded from chat but still accessible via explorer
    - At least one database must remain visible
    - Automatically rebuilds FAISS index when visibility changes
    """
    registry = get_database_registry()

    # Check if database exists
    db_info = registry.get_database_info(db_name)
    if not db_info:
        raise HTTPException(status_code=404, detail=f"Database '{db_name}' not found")

    # Check if trying to hide the last visible database
    if not request.is_visible:
        visible_count = registry.get_visible_count()
        if visible_count <= 1 and db_info["is_visible"]:
            raise HTTPException(
                status_code=400,
                detail="Cannot hide the last visible database. At least one database must remain visible."
            )

    # Update visibility
    success = registry.set_visibility(db_name, request.is_visible)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update database visibility")

    # Refresh FAISS index to reflect visibility change
    try:
        refresh_schema_for_visible_databases()
    except Exception as e:
        # Log but don't fail the request
        print(f"Warning: Failed to refresh schema index: {e}")

    return {
        "success": True,
        "db_name": db_name,
        "is_visible": request.is_visible,
        "message": f"Database '{db_name}' is now {'visible' if request.is_visible else 'hidden'}. Schema index refreshed."
    }


@router.delete("/{db_name}", response_model=dict)
async def delete_database(
    db_name: str,
    current_user: dict = Depends(require_admin)
):
    """Delete an uploaded database.

    - Only uploaded databases can be deleted
    - Mock databases cannot be deleted (they can only be hidden)
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
            detail="Cannot delete mock databases. Use visibility toggle to hide them instead."
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

    # Non-admins can only see visible databases
    is_admin = current_user.get("role") == "admin"
    if not is_admin and not db_info["is_visible"]:
        raise HTTPException(status_code=404, detail=f"Database '{db_name}' not found")

    return DatabaseInfo(
        db_name=db_name,
        db_path=db_info["db_path"],
        display_name=db_info.get("display_name"),
        description=db_info.get("description"),
        source_type=db_info.get("source_type", "unknown"),
        is_visible=bool(db_info.get("is_visible")),
        is_system=bool(db_info.get("is_system")),
        table_count=db_info.get("table_count", 0),
        upload_filename=db_info.get("upload_filename"),
        uploaded_by=db_info.get("uploaded_by"),
        created_at=db_info.get("created_at")
    )
