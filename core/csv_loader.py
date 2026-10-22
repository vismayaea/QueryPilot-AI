import csv
import io
import os
import re
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

# Configurable max upload size (default 10 MB)
DEFAULT_MAX_UPLOAD_SIZE_MB = 10
DEFAULT_MAX_UPLOAD_SIZE_BYTES = DEFAULT_MAX_UPLOAD_SIZE_MB * 1024 * 1024


class CSVValidationError(ValueError):
    """Exception raised when CSV validation fails."""
    pass


def get_max_upload_size_bytes() -> int:
    """Retrieve maximum upload size in bytes from environment or default."""
    env_val = os.environ.get("MAX_UPLOAD_SIZE_MB")
    if env_val:
        try:
            return int(env_val) * 1024 * 1024
        except ValueError:
            pass
    return DEFAULT_MAX_UPLOAD_SIZE_BYTES


def _infer_column_type(series: pd.Series) -> str:
    """Infer a clean, user-friendly SQL-compatible data type for a pandas Series."""
    # Drop NA values for type inspection
    non_null = series.dropna()
    if non_null.empty:
        return "TEXT"

    # Boolean detection
    if pd.api.types.is_bool_dtype(series):
        return "BOOLEAN"

    # Numeric detection
    if pd.api.types.is_integer_dtype(series):
        return "INTEGER"
    if pd.api.types.is_float_dtype(series):
        # Check if float values are all integers (e.g. 1.0, 2.0 due to NaN presence)
        if (non_null % 1 == 0).all():
            return "INTEGER"
        return "FLOAT"

    # Datetime detection for object/string columns
    if pd.api.types.is_datetime64_any_dtype(series):
        return "DATETIME"

    # If it's string/object, test for dates if values look like dates
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        # Sample non-null strings to avoid heavy processing on large text
        sample = non_null.astype(str).head(50)
        # Only attempt datetime parsing if strings contain common date/time separators
        has_date_separators = sample.str.contains(r"[-/:]", regex=True).all()
        if has_date_separators:
            try:
                parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
                if parsed.notna().all():
                    # Check if time component exists
                    if (parsed.dt.time == pd.Timestamp("00:00:00").time()).all():
                        return "DATE"
                    return "DATETIME"
            except Exception:
                pass

        # Check for boolean strings like 'true'/'false' or 'yes'/'no'
        lower_sample = sample.str.strip().str.lower()
        if lower_sample.isin({"true", "false", "yes", "no", "t", "f", "1", "0"}).all():
            if set(lower_sample.unique()).issubset({"true", "false"}):
                return "BOOLEAN"

    return "TEXT"


def _clean_value_for_json(val: Any) -> Any:
    """Convert pandas/numpy values to standard JSON-serializable Python values."""
    if pd.isna(val):
        return None
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        if np.isnan(val) or np.isinf(val):
            return None
        return float(val)
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    if isinstance(val, (pd.Timestamp, np.datetime64)):
        return val.isoformat()
    return str(val)


def validate_and_preview(
    file_bytes: bytes,
    filename: str = "upload.csv",
    max_size_bytes: Optional[int] = None
) -> Dict[str, Any]:
    """
    Validates uploaded CSV file bytes and returns preview metadata and rows.

    Checks:
    - File size within configurable limit
    - Non-empty byte content
    - Valid text encoding (UTF-8)
    - Valid CSV structure
    - Presence of a non-empty header row
    - No duplicate column names in header
    - Presence of at least one data row
    - No malformed lines

    Returns:
    {
        "filename": str,
        "total_rows": int,
        "total_columns": int,
        "columns": [
            {"name": str, "inferred_type": str, "sample_values": list}
        ],
        "preview_rows": list of dicts (up to 10 rows)
    }
    """
    if max_size_bytes is None:
        max_size_bytes = get_max_upload_size_bytes()

    # 1. Size checks
    if not file_bytes or len(file_bytes) == 0:
        raise CSVValidationError("The uploaded file is empty. Please upload a valid CSV file.")

    if len(file_bytes) > max_size_bytes:
        limit_mb = max_size_bytes / (1024 * 1024)
        actual_mb = len(file_bytes) / (1024 * 1024)
        raise CSVValidationError(
            f"File size ({actual_mb:.2f} MB) exceeds maximum allowed limit of {limit_mb:.1f} MB."
        )

    # 2. Text decoding
    try:
        # utf-8-sig handles potential BOM transparently
        text_content = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CSVValidationError(
            "The file could not be decoded as text. Please ensure it is a valid UTF-8 encoded CSV."
        )

    # Check for empty or whitespace-only content
    if not text_content.strip():
        raise CSVValidationError("The uploaded file contains no data or only whitespace.")

    # 3. CSV syntax and header inspection
    try:
        reader = csv.reader(io.StringIO(text_content))
        rows_iter = iter(reader)
        header = None
        for row in rows_iter:
            if row and any(cell.strip() for cell in row):
                header = row
                break
    except csv.Error as e:
        raise CSVValidationError(f"Malformed CSV syntax: {e}")

    if header is None:
        raise CSVValidationError("CSV file must have a header row with column names.")

    # Clean header column names
    cleaned_header = [col.strip() for col in header]

    # Check for empty column names
    if any(col == "" for col in cleaned_header):
        raise CSVValidationError("CSV header contains one or more empty column names.")

    # Check for duplicate column names
    seen = set()
    duplicates = []
    for col in cleaned_header:
        lower_col = col.lower()
        if lower_col in seen:
            if col not in duplicates:
                duplicates.append(col)
        else:
            seen.add(lower_col)

    if duplicates:
        raise CSVValidationError(
            f"Duplicate column names detected in header: {', '.join(duplicates)}. Column names must be unique."
        )

    # Check for at least one data row
    first_data_row = None
    try:
        for row in rows_iter:
            if row and any(cell.strip() for cell in row):
                first_data_row = row
                break
    except csv.Error as e:
        raise CSVValidationError(f"Malformed CSV syntax in data rows: {e}")

    if first_data_row is None:
        raise CSVValidationError("CSV file must contain at least one data row.")

    # 4. Parse full dataset with pandas
    try:
        df = pd.read_csv(
            io.StringIO(text_content),
            dtype=None,
            on_bad_lines="error"
        )
    except pd.errors.ParserError as e:
        raise CSVValidationError(f"Malformed CSV file: {e}")
    except pd.errors.EmptyDataError:
        raise CSVValidationError("The CSV file contains no readable data.")
    except Exception as e:
        raise CSVValidationError(f"Error parsing CSV file: {e}")

    # Strip column names in dataframe
    df.columns = [str(c).strip() for c in df.columns]

    if df.empty:
        raise CSVValidationError("CSV file contains no data rows after parsing.")

    # 5. Type inference and sample extraction
    columns_info = []
    for col in df.columns:
        series = df[col]
        inferred = _infer_column_type(series)
        # Extract up to 3 non-null sample values
        samples = [
            _clean_value_for_json(v)
            for v in series.dropna().head(3).tolist()
        ]
        columns_info.append({
            "name": col,
            "inferred_type": inferred,
            "sample_values": samples
        })

    # 6. Generate preview (up to 10 rows)
    preview_df = df.head(10)
    preview_records: List[Dict[str, Any]] = []
    for row in preview_df.to_dict(orient="records"):
        cleaned_row = {k: _clean_value_for_json(v) for k, v in row.items()}
        preview_records.append(cleaned_row)

    return {
        "filename": filename,
        "total_rows": int(len(df)),
        "total_columns": int(len(df.columns)),
        "columns": columns_info,
        "preview_rows": preview_records
    }
