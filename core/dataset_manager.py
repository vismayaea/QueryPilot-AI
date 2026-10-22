import datetime
import io
import json
import os
import re
import sqlite3
import unicodedata
import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.csv_loader import (
    CSVValidationError,
    _clean_value_for_json,
    _infer_column_type,
    get_max_upload_size_bytes,
    validate_and_preview,
)

# Base directory for isolated SQLite databases
DEFAULT_DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "datasets")
)
TABLE_NAME = "uploaded_data"
METADATA_TABLE_NAME = "_dataset_metadata"

# Regex for strict validation of server-generated opaque dataset IDs (UUIDv4 hex)
DATASET_ID_REGEX = re.compile(r"^[a-f0-9]{32}$")


class DatasetNotFoundError(Exception):
    """Raised when a requested dataset ID does not exist."""
    pass


class InvalidDatasetIdError(ValueError):
    """Raised when a dataset ID format is invalid."""
    pass


def get_datasets_dir() -> str:
    """Return the resolved absolute datasets directory and ensure it exists."""
    datasets_dir = os.environ.get("DATASETS_DIR", DEFAULT_DATA_DIR)
    os.makedirs(datasets_dir, exist_ok=True)
    return datasets_dir


def is_valid_dataset_id(dataset_id: str) -> bool:
    """Validate that the dataset ID conforms strictly to opaque 32-character hex format."""
    if not isinstance(dataset_id, str):
        return False
    return bool(DATASET_ID_REGEX.match(dataset_id))


def get_dataset_db_path(dataset_id: str) -> str:
    """
    Get the SQLite file path for a dataset ID.
    Raises InvalidDatasetIdError if the ID contains invalid characters or path traversal.
    """
    if not is_valid_dataset_id(dataset_id):
        raise InvalidDatasetIdError(f"Invalid dataset ID: '{dataset_id}'. Must be a 32-character hex string.")
    return os.path.join(get_datasets_dir(), f"{dataset_id}.db")


def normalize_identifier(col_name: str) -> str:
    """
    Safely normalize a column name into an ASCII alphanumeric identifier.
    Strips whitespace, converts accents/unicode, replaces punctuation with '_',
    collapses underscores, and handles leading digits or empty names.
    """
    if not col_name or not str(col_name).strip():
        return "col_unnamed"

    # Normalize unicode to ASCII equivalent (e.g. café -> cafe)
    normalized = unicodedata.normalize("NFKD", str(col_name)).encode("ASCII", "ignore").decode("ASCII")
    # Replace non-alphanumeric characters with underscore
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", normalized).strip("_")
    # Collapse multiple underscores
    cleaned = re.sub(r"_+", "_", cleaned).lower()

    if not cleaned:
        return "col_unnamed"
    if cleaned[0].isdigit():
        cleaned = f"col_{cleaned}"

    return cleaned


def clean_and_deduplicate_columns(columns: List[str]) -> List[Tuple[str, str]]:
    """
    Maps a list of raw column names to unique normalized SQL identifiers.
    Returns a list of tuples: (original_name, clean_sql_name).
    """
    seen: Dict[str, int] = {}
    result: List[Tuple[str, str]] = []

    for col in columns:
        base = normalize_identifier(col)
        if base not in seen:
            seen[base] = 1
            clean_name = base
        else:
            seen[base] += 1
            clean_name = f"{base}_{seen[base]}"
        result.append((str(col), clean_name))

    return result


def quote_identifier(identifier: str) -> str:
    """Safely quote a SQL table or column identifier using standard double quotes."""
    return f'"{identifier.replace("\"", "\"\"")}"'


def _map_inferred_to_sqlite_type(inferred_type: str) -> str:
    """Map high-level inferred types to standard SQLite affinities."""
    mapping = {
        "INTEGER": "INTEGER",
        "FLOAT": "REAL",
        "BOOLEAN": "INTEGER",
        "DATE": "TEXT",
        "DATETIME": "TEXT",
        "TEXT": "TEXT",
    }
    return mapping.get(inferred_type.upper(), "TEXT")


def create_and_persist_dataset(
    file_bytes: bytes,
    filename: str = "upload.csv",
    max_size_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Validates CSV bytes, creates an isolated SQLite database, populates the dataset table,
    and returns comprehensive dataset metadata.
    """
    # 1. Run full Stage 1 validation and preview logic
    preview_data = validate_and_preview(
        file_bytes=file_bytes,
        filename=filename,
        max_size_bytes=max_size_bytes,
    )

    # 2. Parse into DataFrame with pandas using verified text content
    text_content = file_bytes.decode("utf-8-sig")
    df = pd.read_csv(io.StringIO(text_content), dtype=None, on_bad_lines="error")
    df.columns = [str(c).strip() for c in df.columns]

    # 3. Generate opaque dataset ID and database path
    dataset_id = uuid.uuid4().hex
    db_path = get_dataset_db_path(dataset_id)

    # 4. Normalize and deduplicate column names for safe SQL usage
    col_mapping = clean_and_deduplicate_columns(list(df.columns))
    # Rename DataFrame columns to clean SQL names for storage
    clean_col_names = [clean for _, clean in col_mapping]
    df.columns = clean_col_names

    # Build column schema info
    columns_metadata = []
    type_dict = {}
    for (orig, clean), col_info in zip(col_mapping, preview_data["columns"]):
        inferred = col_info["inferred_type"]
        sqlite_type = _map_inferred_to_sqlite_type(inferred)
        type_dict[clean] = sqlite_type
        columns_metadata.append({
            "name": orig,
            "clean_name": clean,
            "original_name": orig,
            "inferred_type": inferred,
            "sqlite_type": sqlite_type,
            "sample_values": col_info["sample_values"],
        })

    # 5. Persist to isolated SQLite database
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # Build CREATE TABLE statement with quoted identifiers
        column_defs = [
            f"{quote_identifier(clean)} {type_dict[clean]}"
            for clean in clean_col_names
        ]
        create_sql = f"CREATE TABLE {quote_identifier(TABLE_NAME)} ({', '.join(column_defs)});"
        cursor.execute(create_sql)

        # Prepare parameterized INSERT statement
        placeholders = ", ".join(["?"] * len(clean_col_names))
        quoted_cols = ", ".join([quote_identifier(c) for c in clean_col_names])
        insert_sql = f"INSERT INTO {quote_identifier(TABLE_NAME)} ({quoted_cols}) VALUES ({placeholders});"

        # Insert rows in chunks to keep memory bounded
        chunk_size = 1000
        for i in range(0, len(df), chunk_size):
            chunk = df.iloc[i : i + chunk_size]
            # Replace NaN/inf with None for clean SQLite NULL insertion
            records = []
            for _, row in chunk.iterrows():
                row_vals = []
                for val in row:
                    if pd.isna(val):
                        row_vals.append(None)
                    elif isinstance(val, (pd.Timestamp, datetime.datetime, datetime.date)):
                        row_vals.append(val.isoformat())
                    elif isinstance(val, (bool, np.bool_)):
                        row_vals.append(1 if val else 0)
                    else:
                        row_vals.append(val)
                records.append(tuple(row_vals))
            cursor.executemany(insert_sql, records)

        # Build metadata object
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        metadata = {
            "dataset_id": dataset_id,
            "filename": filename,
            "table_name": TABLE_NAME,
            "total_rows": int(len(df)),
            "total_columns": int(len(clean_col_names)),
            "columns": columns_metadata,
            "preview_rows": preview_data["preview_rows"],
            "created_at": created_at,
        }

        # Store metadata inside the database in a dedicated metadata table
        cursor.execute(
            f"CREATE TABLE {quote_identifier(METADATA_TABLE_NAME)} (key TEXT PRIMARY KEY, value TEXT);"
        )
        cursor.execute(
            f"INSERT INTO {quote_identifier(METADATA_TABLE_NAME)} (key, value) VALUES (?, ?);",
            ("metadata", json.dumps(metadata)),
        )

        conn.commit()

        # Also store companion JSON metadata file for fast access
        meta_json_path = os.path.join(get_datasets_dir(), f"{dataset_id}.json")
        with open(meta_json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    except Exception:
        conn.rollback()
        # Clean up database file on failure
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass
        raise
    finally:
        conn.close()


def get_dataset_metadata(dataset_id: str) -> Dict[str, Any]:
    """
    Retrieve stored metadata for a dataset by ID.
    Raises InvalidDatasetIdError if ID is malformed.
    Raises DatasetNotFoundError if dataset does not exist.
    """
    if not is_valid_dataset_id(dataset_id):
        raise InvalidDatasetIdError(f"Invalid dataset ID format: '{dataset_id}'. Must be a 32-character hex string.")

    meta_json_path = os.path.join(get_datasets_dir(), f"{dataset_id}.json")
    db_path = get_dataset_db_path(dataset_id)

    if not os.path.exists(db_path):
        raise DatasetNotFoundError(f"Dataset with ID '{dataset_id}' not found.")

    # Try fast read from JSON companion
    if os.path.exists(meta_json_path):
        try:
            with open(meta_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Fallback to reading from SQLite database directly
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT value FROM {quote_identifier(METADATA_TABLE_NAME)} WHERE key = 'metadata';"
        )
        row = cursor.fetchone()
        if row and row[0]:
            return json.loads(row[0])
        raise DatasetNotFoundError(f"Metadata for dataset '{dataset_id}' not found in database.")
    finally:
        conn.close()


def list_available_datasets() -> List[Dict[str, Any]]:
    """
    List metadata for all existing valid datasets in the datasets directory.
    Sorts by created_at descending.
    """
    datasets_dir = get_datasets_dir()
    datasets: List[Dict[str, Any]] = []
    if not os.path.exists(datasets_dir):
        return datasets

    for fname in os.listdir(datasets_dir):
        if fname.endswith(".json"):
            dataset_id = fname[:-5]
            if is_valid_dataset_id(dataset_id):
                try:
                    meta = get_dataset_metadata(dataset_id)
                    datasets.append(meta)
                except Exception:
                    pass

    datasets.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return datasets
