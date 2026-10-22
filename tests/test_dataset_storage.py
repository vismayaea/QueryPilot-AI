import io
import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app import app
from core.dataset_manager import (
    get_dataset_db_path,
    get_datasets_dir,
    is_valid_dataset_id,
    normalize_identifier,
    clean_and_deduplicate_columns,
)

client = TestClient(app)


def test_successful_csv_ingestion_and_db_creation(tmp_path, monkeypatch):
    """Test that CSV upload creates an isolated SQLite database file and returns dataset metadata."""
    monkeypatch.setenv("DATASETS_DIR", str(tmp_path))

    csv_data = b"id,name,role,salary\n1,Alice,Engineer,95000\n2,Bob,Designer,85000\n3,Charlie,Product,105000\n"

    response = client.post(
        "/api/upload",
        files={"file": ("team.csv", io.BytesIO(csv_data), "text/csv")}
    )

    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True

    data = res["data"]
    dataset_id = data["dataset_id"]
    assert is_valid_dataset_id(dataset_id)
    assert data["filename"] == "team.csv"
    assert data["table_name"] == "uploaded_data"
    assert data["total_rows"] == 3
    assert data["total_columns"] == 4

    # Verify SQLite database file exists on disk
    expected_db = os.path.join(str(tmp_path), f"{dataset_id}.db")
    assert os.path.exists(expected_db)

    # Verify companion metadata JSON file exists on disk
    expected_json = os.path.join(str(tmp_path), f"{dataset_id}.json")
    assert os.path.exists(expected_json)


def test_querying_created_sqlite_database(tmp_path, monkeypatch):
    """Directly query the created SQLite database to verify data integrity, rows, and schema."""
    monkeypatch.setenv("DATASETS_DIR", str(tmp_path))

    csv_data = b"product_id,price,in_stock\n101,19.99,true\n102,49.50,false\n"
    response = client.post(
        "/api/upload",
        files={"file": ("inventory.csv", io.BytesIO(csv_data), "text/csv")}
    )
    dataset_id = response.json()["data"]["dataset_id"]

    db_path = os.path.join(str(tmp_path), f"{dataset_id}.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query row count
    cursor.execute('SELECT COUNT(*) FROM "uploaded_data";')
    row_count = cursor.fetchone()[0]
    assert row_count == 2

    # Query specific rows
    cursor.execute('SELECT "product_id", "price", "in_stock" FROM "uploaded_data" ORDER BY "product_id" ASC;')
    rows = cursor.fetchall()
    assert len(rows) == 2
    assert rows[0] == (101, 19.99, 1)  # Boolean true stored as 1
    assert rows[1] == (102, 49.50, 0)  # Boolean false stored as 0

    # Verify internal metadata table exists
    cursor.execute('SELECT value FROM "_dataset_metadata" WHERE key = "metadata";')
    meta_row = cursor.fetchone()
    assert meta_row is not None
    assert "inventory.csv" in meta_row[0]

    conn.close()


def test_unusual_column_names_and_reserved_words(tmp_path, monkeypatch):
    """
    Test handling of spaces, punctuation, SQL reserved words, leading numbers, and unicode.
    Ensures safe normalization, quoting, and queryability without SQL injection.
    """
    monkeypatch.setenv("DATASETS_DIR", str(tmp_path))

    # Header with spaces, reserved words ('select', 'order', 'table'), punctuation ('#', '$'), leading digit
    csv_data = (
        b"Customer Name,select,Order #,Total ($),1st_priority,caf\xc3\xa9\n"
        b"Acme Corp,Alpha,9901,1250.75,High,Espresso\n"
        b"Globex,Beta,9902,3400.00,Low,Latte\n"
    )

    response = client.post(
        "/api/upload",
        files={"file": ("complex_cols.csv", io.BytesIO(csv_data), "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    dataset_id = data["dataset_id"]

    # Verify column mappings
    cols = data["columns"]
    clean_names = [col["clean_name"] for col in cols]
    assert "customer_name" in clean_names
    assert "select" in clean_names
    assert "order" in clean_names
    assert "total" in clean_names
    assert "col_1st_priority" in clean_names
    assert "cafe" in clean_names

    # Directly open SQLite and query each column
    db_path = os.path.join(str(tmp_path), f"{dataset_id}.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        'SELECT "customer_name", "select", "order", "total", "col_1st_priority", "cafe" '
        'FROM "uploaded_data";'
    )
    results = cursor.fetchall()
    assert len(results) == 2
    assert results[0] == ("Acme Corp", "Alpha", 9901, 1250.75, "High", "Espresso")
    assert results[1] == ("Globex", "Beta", 9902, 3400.00, "Low", "Latte")

    conn.close()


def test_isolation_between_two_uploads(tmp_path, monkeypatch):
    """Verify that two independent uploads produce completely isolated SQLite databases."""
    monkeypatch.setenv("DATASETS_DIR", str(tmp_path))

    csv_a = b"book_id,title\n1,Dune\n2,Foundation\n3,Hyperion\n"
    csv_b = b"car_id,model,year\n10,Mustang,1969\n20,Corvette,1963\n"

    res_a = client.post("/api/upload", files={"file": ("books.csv", io.BytesIO(csv_a), "text/csv")})
    res_b = client.post("/api/upload", files={"file": ("cars.csv", io.BytesIO(csv_b), "text/csv")})

    assert res_a.status_code == 200
    assert res_b.status_code == 200

    id_a = res_a.json()["data"]["dataset_id"]
    id_b = res_b.json()["data"]["dataset_id"]
    assert id_a != id_b

    # Verify separate files exist
    db_a = os.path.join(str(tmp_path), f"{id_a}.db")
    db_b = os.path.join(str(tmp_path), f"{id_b}.db")
    assert os.path.exists(db_a)
    assert os.path.exists(db_b)

    # Check database A contains only books
    conn_a = sqlite3.connect(db_a)
    cur_a = conn_a.cursor()
    cur_a.execute('SELECT "title" FROM "uploaded_data" ORDER BY "book_id";')
    books = [r[0] for r in cur_a.fetchall()]
    assert books == ["Dune", "Foundation", "Hyperion"]
    conn_a.close()

    # Check database B contains only cars
    conn_b = sqlite3.connect(db_b)
    cur_b = conn_b.cursor()
    cur_b.execute('SELECT "model" FROM "uploaded_data" ORDER BY "car_id";')
    cars = [r[0] for r in cur_b.fetchall()]
    assert cars == ["Mustang", "Corvette"]
    conn_b.close()


def test_get_dataset_metadata_by_id(tmp_path, monkeypatch):
    """Test retrieving dataset metadata via GET /api/datasets/{dataset_id}."""
    monkeypatch.setenv("DATASETS_DIR", str(tmp_path))

    csv_data = b"item,qty\nPen,10\nNotebook,5\n"
    res_upload = client.post("/api/upload", files={"file": ("office.csv", io.BytesIO(csv_data), "text/csv")})
    dataset_id = res_upload.json()["data"]["dataset_id"]

    # Fetch metadata by ID
    response = client.get(f"/api/datasets/{dataset_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    meta = data["data"]
    assert meta["dataset_id"] == dataset_id
    assert meta["filename"] == "office.csv"
    assert meta["total_rows"] == 2
    assert meta["total_columns"] == 2
    assert len(meta["preview_rows"]) == 2


def test_invalid_dataset_id_handling():
    """Test that malformed dataset IDs and path traversal attempts are rejected with 400."""
    # Path traversal attempt
    res = client.get("/api/datasets/../../etc/passwd")
    assert res.status_code in (400, 404)

    # Malformed ID with special chars
    res2 = client.get("/api/datasets/invalid-id-with-symbols!!")
    assert res2.status_code == 400
    assert "invalid dataset id format" in res2.json()["detail"].lower()

    # Non-existent valid hex ID
    res3 = client.get("/api/datasets/00000000000000000000000000000000")
    assert res3.status_code == 404
    assert "not found" in res3.json()["detail"].lower()


def test_identifier_sanitization_helpers():
    """Test internal column normalization and deduplication helpers."""
    assert normalize_identifier("First Name") == "first_name"
    assert normalize_identifier("123 Rank") == "col_123_rank"
    assert normalize_identifier("Total ($USD)") == "total_usd"
    assert normalize_identifier("---") == "col_unnamed"

    cols = ["Total", "Total ($)", "Total (%)"]
    deduped = clean_and_deduplicate_columns(cols)
    clean_names = [clean for _, clean in deduped]
    assert len(clean_names) == 3
    assert len(set(clean_names)) == 3  # All clean names must be unique
