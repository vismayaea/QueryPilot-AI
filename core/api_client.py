import os
from typing import Any, Dict, Optional, Tuple
import requests

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"


def get_api_base_url() -> str:
    """Retrieve the backend API base URL from environment or default."""
    url = (
        os.environ.get("QUERYPILOT_API_BASE_URL")
        or os.environ.get("API_BASE_URL")
        or DEFAULT_API_BASE_URL
    )
    return url.rstrip("/")


def check_backend_health(base_url: Optional[str] = None) -> Tuple[bool, str]:
    """Checks whether the FastAPI backend is running and reachable."""
    url = (base_url or get_api_base_url()).rstrip("/")
    try:
        resp = requests.get(f"{url}/api/health", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            stage = data.get("stage", "?")
            return True, f"Online (Stage {stage})"
        return False, f"Backend returned status {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to {url}. Please ensure FastAPI is running."
    except Exception as e:
        return False, f"Health check failed: {str(e)}"


def upload_csv_file(
    file_bytes: bytes,
    filename: str,
    base_url: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """
    Sends CSV file bytes to POST /api/upload.
    Returns (success, data, error_message).
    """
    url = (base_url or get_api_base_url()).rstrip("/")
    try:
        files = {"file": (filename, file_bytes, "text/csv")}
        resp = requests.post(f"{url}/api/upload", files=files, timeout=30.0)
        if resp.status_code == 200:
            res_json = resp.json()
            return True, res_json.get("data", {}), None
        else:
            try:
                err_detail = resp.json().get("detail", resp.text)
            except Exception:
                err_detail = resp.text
            return False, {}, f"Upload failed ({resp.status_code}): {err_detail}"
    except requests.exceptions.ConnectionError:
        return False, {}, f"Cannot connect to backend at {url}. Is FastAPI running?"
    except Exception as e:
        return False, {}, f"Upload error: {str(e)}"


def query_dataset(
    dataset_id: str,
    question: str,
    base_url: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """
    Sends a natural-language question to POST /api/query.
    Returns (success, result_data, error_message).
    """
    url = (base_url or get_api_base_url()).rstrip("/")
    try:
        payload = {"dataset_id": dataset_id, "question": question}
        resp = requests.post(f"{url}/api/query", json=payload, timeout=45.0)
        if resp.status_code == 200:
            res_json = resp.json()
            data = res_json.get("data", res_json)
            return True, data, None
        else:
            try:
                err_detail = resp.json().get("detail", resp.text)
            except Exception:
                err_detail = resp.text
            return False, {}, f"Query failed ({resp.status_code}): {err_detail}"
    except requests.exceptions.ConnectionError:
        return False, {}, f"Cannot connect to backend at {url}. Is FastAPI running?"
    except Exception as e:
        return False, {}, f"Query error: {str(e)}"


def get_dataset_metadata(
    dataset_id: str,
    base_url: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """
    Retrieves metadata for a dataset via GET /api/datasets/{dataset_id}.
    Returns (success, metadata, error_message).
    """
    url = (base_url or get_api_base_url()).rstrip("/")
    try:
        resp = requests.get(f"{url}/api/datasets/{dataset_id}", timeout=10.0)
        if resp.status_code == 200:
            return True, resp.json().get("data", {}), None
        else:
            try:
                err_detail = resp.json().get("detail", resp.text)
            except Exception:
                err_detail = resp.text
            return False, {}, f"Metadata request failed ({resp.status_code}): {err_detail}"
    except requests.exceptions.ConnectionError:
        return False, {}, f"Cannot connect to backend at {url}. Is FastAPI running?"
    except Exception as e:
        return False, {}, f"Metadata error: {str(e)}"
