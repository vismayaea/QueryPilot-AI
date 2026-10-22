import pytest
from unittest.mock import MagicMock, patch
import requests

from core.api_client import (
    DEFAULT_API_BASE_URL,
    check_backend_health,
    get_api_base_url,
    get_dataset_metadata,
    query_dataset,
    upload_csv_file,
)


def test_get_api_base_url_default(monkeypatch):
    """Test default API base URL."""
    monkeypatch.delenv("QUERYPILOT_API_BASE_URL", raising=False)
    monkeypatch.delenv("API_BASE_URL", raising=False)
    assert get_api_base_url() == DEFAULT_API_BASE_URL


def test_get_api_base_url_env_override(monkeypatch):
    """Test environment variable overrides."""
    monkeypatch.setenv("QUERYPILOT_API_BASE_URL", "http://custom-host:9000/")
    assert get_api_base_url() == "http://custom-host:9000"


def test_check_backend_health_success():
    """Test healthy backend response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "stage": 3}

    with patch("requests.get", return_value=mock_resp):
        ok, msg = check_backend_health("http://127.0.0.1:8000")
        assert ok is True
        assert "Online (Stage 3)" in msg


def test_check_backend_health_connection_error():
    """Test unreachable backend."""
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Connection refused")):
        ok, msg = check_backend_health("http://127.0.0.1:8000")
        assert ok is False
        assert "Cannot connect to" in msg


def test_upload_csv_file_success():
    """Test successful CSV file upload."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "data": {"dataset_id": "123", "filename": "test.csv", "total_rows": 5}
    }

    with patch("requests.post", return_value=mock_resp):
        success, data, err = upload_csv_file(b"id,name\n1,Alice", "test.csv", "http://127.0.0.1:8000")
        assert success is True
        assert err is None
        assert data["dataset_id"] == "123"


def test_upload_csv_file_error():
    """Test CSV file upload failure response from backend."""
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"detail": "CSV file must contain a header row."}

    with patch("requests.post", return_value=mock_resp):
        success, data, err = upload_csv_file(b"", "empty.csv", "http://127.0.0.1:8000")
        assert success is False
        assert "CSV file must contain a header row." in err


def test_query_dataset_success():
    """Test query dataset successful execution."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "data": {
            "dataset_id": "abc",
            "question": "Count rows",
            "sql": "SELECT COUNT(*) FROM uploaded_data",
            "columns": ["count"],
            "rows": [[5]],
            "row_count": 1,
            "answer": "There are 5 matching records."
        }
    }

    with patch("requests.post", return_value=mock_resp):
        success, data, err = query_dataset("abc", "Count rows", "http://127.0.0.1:8000")
        assert success is True
        assert err is None
        assert data["row_count"] == 1
        assert "There are 5" in data["answer"]


def test_query_dataset_error():
    """Test query dataset error handling."""
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"detail": "SQL Security Rejection: Forbidden statement."}

    with patch("requests.post", return_value=mock_resp):
        success, data, err = query_dataset("abc", "Bad query", "http://127.0.0.1:8000")
        assert success is False
        assert "Security Rejection" in err


def test_get_dataset_metadata():
    """Test fetching dataset metadata."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True, "data": {"dataset_id": "xyz", "total_rows": 10}}

    with patch("requests.get", return_value=mock_resp):
        success, data, err = get_dataset_metadata("xyz", "http://127.0.0.1:8000")
        assert success is True
        assert data["total_rows"] == 10
