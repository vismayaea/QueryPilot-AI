import io
import os
import pytest
from fastapi.testclient import TestClient

from app import app
from core.csv_loader import validate_and_preview, CSVValidationError

client = TestClient(app)


def test_health_check():
    """Ensure API health endpoint is operational."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_valid_csv_upload_and_preview():
    """Test standard valid CSV upload with varied column types and preview limit."""
    # 15 rows with varied types: int, float, string, date, boolean
    csv_rows = ["id,name,salary,hire_date,is_active"]
    for i in range(1, 16):
        csv_rows.append(f"{i},Employee_{i},{50000 + i * 1500.50},2023-01-{i:02d},{'true' if i % 2 == 0 else 'false'}")
    csv_data = "\n".join(csv_rows).encode("utf-8")

    response = client.post(
        "/api/upload",
        files={"file": ("employees.csv", io.BytesIO(csv_data), "text/csv")}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    result = data["data"]
    assert result["filename"] == "employees.csv"
    assert result["total_rows"] == 15
    assert result["total_columns"] == 5
    assert len(result["preview_rows"]) == 10  # Capped at 10 preview rows

    # Verify column type inference
    col_types = {col["name"]: col["inferred_type"] for col in result["columns"]}
    assert col_types["id"] == "INTEGER"
    assert col_types["name"] == "TEXT"
    assert col_types["salary"] == "FLOAT"
    assert col_types["hire_date"] in ("DATE", "DATETIME")
    assert col_types["is_active"] == "BOOLEAN"


def test_empty_file_rejected():
    """Test that zero-byte empty files are rejected with clear error."""
    response = client.post(
        "/api/upload",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_whitespace_only_file_rejected():
    """Test that whitespace-only files are rejected with clear error."""
    response = client.post(
        "/api/upload",
        files={"file": ("blank.csv", io.BytesIO(b"   \n\n   \t  "), "text/csv")}
    )
    assert response.status_code == 400
    assert "no data" in response.json()["detail"].lower()


def test_header_only_file_rejected():
    """Test that CSV with header but zero data rows is rejected."""
    csv_data = b"id,name,age\n"
    response = client.post(
        "/api/upload",
        files={"file": ("header_only.csv", io.BytesIO(csv_data), "text/csv")}
    )
    assert response.status_code == 400
    assert "at least one data row" in response.json()["detail"].lower()


def test_duplicate_columns_rejected():
    """Test that duplicate column names in header are rejected with clear message."""
    csv_data = b"id,name,email,name\n1,Alice,alice@example.com,AliceB"
    response = client.post(
        "/api/upload",
        files={"file": ("duplicate_cols.csv", io.BytesIO(csv_data), "text/csv")}
    )
    assert response.status_code == 400
    assert "duplicate" in response.json()["detail"].lower()
    assert "name" in response.json()["detail"].lower()


def test_empty_column_name_in_header_rejected():
    """Test that empty column headers like 'id,,age' are rejected."""
    csv_data = b"id,,age\n1,Alice,30"
    response = client.post(
        "/api/upload",
        files={"file": ("empty_col.csv", io.BytesIO(csv_data), "text/csv")}
    )
    assert response.status_code == 400
    assert "empty column name" in response.json()["detail"].lower()


def test_malformed_csv_rejected():
    """Test that corrupted CSVs with bad quoting are rejected."""
    csv_data = b'id,description\n1,"Unterminated string\n2,Normal'
    response = client.post(
        "/api/upload",
        files={"file": ("malformed.csv", io.BytesIO(csv_data), "text/csv")}
    )
    assert response.status_code == 400
    assert "malformed" in response.json()["detail"].lower() or "error" in response.json()["detail"].lower()


def test_non_csv_binary_file_rejected():
    """Test that binary non-CSV files (like images or binaries) are rejected."""
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00\x00\x01\x00\x08\x06\x00\x00\x00"
    response = client.post(
        "/api/upload",
        files={"file": ("image.csv", io.BytesIO(fake_png), "text/csv")}
    )
    assert response.status_code == 400
    assert "decoded as text" in response.json()["detail"].lower()


def test_non_csv_extension_rejected():
    """Test that files without .csv extension are rejected."""
    response = client.post(
        "/api/upload",
        files={"file": ("data.txt", io.BytesIO(b"id,name\n1,A"), "text/plain")}
    )
    assert response.status_code == 400
    assert "only .csv files are supported" in response.json()["detail"].lower()


def test_max_upload_size_enforced(monkeypatch):
    """Test that files exceeding configured max upload size are rejected with 413."""
    # Set limit to 1 MB for testing
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
    oversized_data = b"a" * (1024 * 1024 + 100)

    response = client.post(
        "/api/upload",
        files={"file": ("large.csv", io.BytesIO(oversized_data), "text/csv")}
    )
    assert response.status_code == 413
    assert "maximum allowed limit" in response.json()["detail"].lower()
    assert "exceeds" in response.json()["detail"].lower()


def test_api_keys_not_exposed_in_response():
    """Verify backend responses never leak API keys or secrets."""
    csv_data = b"id,val\n1,100"
    response = client.post(
        "/api/upload",
        files={"file": ("sample.csv", io.BytesIO(csv_data), "text/csv")}
    )
    text = response.text
    assert "GOOGLE_API_KEY" not in text
    assert "AIza" not in text  # Standard Google API key prefix


def test_agent_cli_workflow_unbroken():
    """Verify that importing agent and its CLI functions remains intact."""
    import agent
    assert hasattr(agent, "create_sql_agent")
    assert hasattr(agent, "SYSTEM_PROMPT")
    assert callable(agent.create_sql_agent)
