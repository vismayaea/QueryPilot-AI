import io
import os
import pytest
from fastapi.testclient import TestClient

from app import app
from core.query_service import (
    MissingCredentialsError,
    ModelAuthError,
    ModelNotFoundError,
    ModelOverloadedError,
    ModelQuotaExceededError,
    ModelResponseMalformedError,
    ModelServiceError,
    ModelTimeoutError,
    QueryTimeoutError,
    UnsafeSQLError,
    classify_gemini_exception,
    sanitize_error_details,
    validate_and_sanitize_sql,
)

client = TestClient(app)


@pytest.fixture
def sample_dataset(tmp_path, monkeypatch):
    """Creates a sample dataset for testing."""
    monkeypatch.setenv("DATASETS_DIR", str(tmp_path))
    csv_data = (
        b"id,name,role,salary\n"
        b"1,Alice,Engineer,95000\n"
        b"2,Bob,Designer,80000\n"
        b"3,Charlie,Product,105000\n"
    )
    res = client.post("/api/upload", files={"file": ("staff.csv", io.BytesIO(csv_data), "text/csv")})
    assert res.status_code == 200
    return res.json()["data"]["dataset_id"]


def test_successful_natural_language_query(sample_dataset, monkeypatch):
    """Test full query workflow with mocked Gemini returning valid SQL."""
    # Mock Gemini returning SQL
    monkeypatch.setattr(
        "core.query_service.call_gemini_model",
        lambda prompt: "SELECT name, salary FROM uploaded_data WHERE salary >= 95000 ORDER BY salary DESC"
    )

    response = client.post(
        "/api/query",
        json={
            "dataset_id": sample_dataset,
            "question": "Which employees make $95,000 or more?"
        }
    )

    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert res["dataset_id"] == sample_dataset
    assert "salary >= 95000" in res["sql"]
    assert res["columns"] == ["name", "salary"]
    assert res["row_count"] == 2
    assert res["rows"][0] == ["Charlie", 105000]
    assert res["rows"][1] == ["Alice", 95000]
    assert "Found 2 records" in res["answer"]


def test_query_dataset_with_unfamiliar_column_names(tmp_path, monkeypatch):
    """Test querying datasets that contain spaces, punctuation, and reserved words."""
    monkeypatch.setenv("DATASETS_DIR", str(tmp_path))
    csv_data = (
        b"Customer Name,Order #,Total ($),select\n"
        b"Acme Corp,101,1500.50,Yes\n"
        b"Globex,102,450.00,No\n"
    )
    res = client.post("/api/upload", files={"file": ("orders.csv", io.BytesIO(csv_data), "text/csv")})
    dataset_id = res.json()["data"]["dataset_id"]

    # Mock Gemini referencing normalized and quoted column names
    mock_sql = 'SELECT "customer_name", "total" FROM uploaded_data WHERE "total" > 1000'
    monkeypatch.setattr("core.query_service.call_gemini_model", lambda p: mock_sql)

    response = client.post(
        "/api/query",
        json={
            "dataset_id": dataset_id,
            "question": "Show customers with total over 1000"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["row_count"] == 1
    assert data["rows"][0] == ["Acme Corp", 1500.50]


def test_two_datasets_remain_isolated(tmp_path, monkeypatch):
    """Verify that queries execute strictly in the target dataset without crosstalk."""
    monkeypatch.setenv("DATASETS_DIR", str(tmp_path))

    csv_a = b"book_id,title\n1,Dune\n2,Hyperion\n"
    csv_b = b"car_id,model\n10,Mustang\n20,Corvette\n"

    id_a = client.post("/api/upload", files={"file": ("a.csv", io.BytesIO(csv_a), "text/csv")}).json()["data"]["dataset_id"]
    id_b = client.post("/api/upload", files={"file": ("b.csv", io.BytesIO(csv_b), "text/csv")}).json()["data"]["dataset_id"]

    monkeypatch.setattr("core.query_service.call_gemini_model", lambda p: "SELECT * FROM uploaded_data")

    res_a = client.post("/api/query", json={"dataset_id": id_a, "question": "Get all records"})
    res_b = client.post("/api/query", json={"dataset_id": id_b, "question": "Get all records"})

    assert res_a.status_code == 200
    assert res_b.status_code == 200

    # Ensure dataset A has book titles and dataset B has car models
    assert "title" in res_a.json()["columns"]
    assert "model" in res_b.json()["columns"]
    assert "Dune" in str(res_a.json()["rows"])
    assert "Mustang" in str(res_b.json()["rows"])


def test_empty_result_set(sample_dataset, monkeypatch):
    """Test queries that return 0 rows produce deterministic, user-friendly output."""
    monkeypatch.setattr(
        "core.query_service.call_gemini_model",
        lambda p: "SELECT * FROM uploaded_data WHERE salary > 1000000"
    )

    response = client.post(
        "/api/query",
        json={"dataset_id": sample_dataset, "question": "Who earns over a million?"}
    )

    assert response.status_code == 200
    res = response.json()
    assert res["row_count"] == 0
    assert res["rows"] == []
    assert "no matching records were found" in res["answer"].lower()


@pytest.mark.parametrize("malicious_sql", [
    "DROP TABLE uploaded_data",
    "DELETE FROM uploaded_data",
    "UPDATE uploaded_data SET salary = 0",
    "INSERT INTO uploaded_data VALUES (4, 'Hacker', 'None', 0)",
    "ALTER TABLE uploaded_data ADD COLUMN hacked TEXT",
    "PRAGMA table_info(uploaded_data)",
    "ATTACH DATABASE 'evil.db' AS evil",
    "SELECT * FROM uploaded_data; DROP TABLE uploaded_data;",
    "SELECT * FROM _dataset_metadata",
    "SELECT * FROM sqlite_master",
])
def test_rejection_of_destructive_and_forbidden_sql(sample_dataset, monkeypatch, malicious_sql):
    """Ensure SQLGlot rejects destructive, multi-statement, PRAGMA, or metadata queries."""
    monkeypatch.setattr("core.query_service.call_gemini_model", lambda p: malicious_sql)

    response = client.post(
        "/api/query",
        json={"dataset_id": sample_dataset, "question": "Do something unsafe"}
    )

    assert response.status_code == 400
    assert "security rejection" in response.json()["detail"].lower()


def test_invalid_and_unknown_dataset_ids():
    """Verify appropriate 400 and 404 errors for invalid dataset IDs."""
    # Invalid ID format
    res_bad = client.post(
        "/api/query",
        json={"dataset_id": "../../etc/passwd", "question": "Find data"}
    )
    assert res_bad.status_code == 400
    assert "invalid dataset id format" in res_bad.json()["detail"].lower()

    # Unknown dataset ID
    res_404 = client.post(
        "/api/query",
        json={"dataset_id": "00000000000000000000000000000000", "question": "Find data"}
    )
    assert res_404.status_code == 404
    assert "not found" in res_404.json()["detail"].lower()


def test_empty_question_rejected(sample_dataset):
    """Test that empty or whitespace-only questions are rejected with 400."""
    res = client.post(
        "/api/query",
        json={"dataset_id": sample_dataset, "question": "   "}
    )
    assert res.status_code == 400
    assert "question cannot be empty" in res.json()["detail"].lower()


def test_missing_gemini_credentials_error(sample_dataset, monkeypatch):
    """Verify 503 error when GOOGLE_API_KEY is not configured or empty."""
    monkeypatch.setenv("GOOGLE_API_KEY", "")

    response = client.post(
        "/api/query",
        json={"dataset_id": sample_dataset, "question": "How many records?"}
    )

    assert response.status_code == 503
    assert "google_api_key" in response.json()["detail"].lower()


def test_configured_gemini_credentials_and_model_init(monkeypatch):
    """Test get_gemini_model initializes properly when credentials are configured."""
    from unittest.mock import MagicMock
    from core.query_service import get_gemini_model, call_gemini_model

    monkeypatch.setenv("GOOGLE_API_KEY", "test-fake-key-for-unit-test")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")

    # Mock ChatGoogleGenerativeAI so no network calls are made
    mock_model_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "SELECT COUNT(*) FROM uploaded_data"
    mock_model_instance.invoke.return_value = mock_response

    mock_chat_cls = MagicMock(return_value=mock_model_instance)

    with monkeypatch.context() as m:
        m.setattr("langchain_google_genai.ChatGoogleGenerativeAI", mock_chat_cls)
        model = get_gemini_model()
        assert model is not None
        mock_chat_cls.assert_called_once_with(model="gemini-3.6-flash", temperature=0, max_retries=0)

        # Also test call_gemini_model with mocked invocation
        result = call_gemini_model("Write query")
        assert "SELECT" in result


def test_load_project_env_derived_from_file():
    """Verify that ENV_PATH is derived from project root and exists."""
    from core.query_service import ENV_PATH, PROJECT_ROOT
    assert os.path.isabs(ENV_PATH)
    assert os.path.basename(ENV_PATH) == ".env"
    assert os.path.exists(ENV_PATH)


def test_gemini_model_failure_error(sample_dataset, monkeypatch):
    """Verify 502 Bad Gateway and actionable detail when Gemini API general failure occurs."""
    def fail_llm(prompt):
        raise ModelServiceError("Model processing failed unexpectedly")

    monkeypatch.setattr("core.query_service.call_gemini_model", fail_llm)

    response = client.post(
        "/api/query",
        json={"dataset_id": sample_dataset, "question": "How many records?"}
    )

    assert response.status_code == 502
    assert "model processing failed" in response.json()["detail"].lower()


def test_gemini_authentication_failure(sample_dataset, monkeypatch):
    """Verify HTTP 401 when Gemini returns authentication or permission denied errors."""
    def fail_auth(prompt):
        raise ModelAuthError("Gemini API authentication failed for model 'gemini-3.5-flash-lite'. Invalid API key.")

    monkeypatch.setattr("core.query_service.call_gemini_model", fail_auth)

    response = client.post(
        "/api/query",
        json={"dataset_id": sample_dataset, "question": "How many records?"}
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert "authentication failed" in detail.lower()


def test_gemini_daily_quota_exceeded_returns_429(sample_dataset, monkeypatch):
    """Verify HTTP 429 with actionable message when Gemini daily quota is exhausted."""
    def fail_quota(prompt):
        raise ModelQuotaExceededError(
            "Gemini API daily free-tier quota exceeded for model 'gemini-3.6-flash'. "
            "To continue querying immediately, switch GEMINI_MODEL in .env (e.g. gemini-3.5-flash-lite).",
            upstream_status=429,
            retryable=False,
        )

    monkeypatch.setattr("core.query_service.call_gemini_model", fail_quota)

    response = client.post(
        "/api/query",
        json={"dataset_id": sample_dataset, "question": "How many records?"}
    )

    assert response.status_code == 429
    detail = response.json()["detail"]
    assert "quota exceeded" in detail.lower()
    assert "switch gemini_model" in detail.lower()


def test_gemini_model_not_found_returns_400(sample_dataset, monkeypatch):
    """Verify HTTP 400 when configured model name is deprecated or unknown."""
    def fail_not_found(prompt):
        raise ModelNotFoundError("Gemini model 'gemini-1.5-flash' was not found or is no longer available.")

    monkeypatch.setattr("core.query_service.call_gemini_model", fail_not_found)

    response = client.post(
        "/api/query",
        json={"dataset_id": sample_dataset, "question": "How many records?"}
    )

    assert response.status_code == 400
    assert "model configuration error" in response.json()["detail"].lower()


def test_gemini_gateway_timeout_returns_504(sample_dataset, monkeypatch):
    """Verify HTTP 504 when Gemini upstream call times out."""
    def fail_timeout(prompt):
        raise ModelTimeoutError("Request to Gemini model timed out.")

    monkeypatch.setattr("core.query_service.call_gemini_model", fail_timeout)

    response = client.post(
        "/api/query",
        json={"dataset_id": sample_dataset, "question": "How many records?"}
    )

    assert response.status_code == 504
    assert "gateway timeout" in response.json()["detail"].lower()


def test_gemini_malformed_response_returns_502(sample_dataset, monkeypatch):
    """Verify HTTP 502 when Gemini returns an empty or unparseable response."""
    def fail_malformed(prompt):
        raise ModelResponseMalformedError("Gemini model returned an empty response.")

    monkeypatch.setattr("core.query_service.call_gemini_model", fail_malformed)

    response = client.post(
        "/api/query",
        json={"dataset_id": sample_dataset, "question": "How many records?"}
    )

    assert response.status_code == 502
    assert "gemini response error" in response.json()["detail"].lower()


def test_bounded_retry_succeeds_on_transient_overload(monkeypatch):
    """Verify that call_gemini_model retries on transient 503 and returns SQL when 2nd attempt succeeds."""
    from unittest.mock import MagicMock
    from core.query_service import call_gemini_model

    call_count = 0

    class TransientModelMock:
        def invoke(self, prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 503 high demand transient error on 1st attempt
                raise Exception("503 UNAVAILABLE. This model is currently experiencing high demand. Please try again later.")
            # 2nd attempt succeeds
            res = MagicMock()
            res.content = "SELECT COUNT(*) FROM uploaded_data"
            return res

    monkeypatch.setattr("core.query_service.get_gemini_model", lambda name=None: TransientModelMock())

    # Call with reduced backoff for fast testing
    sql = call_gemini_model("How many records?", max_retries=2, initial_backoff=0.01)
    assert "SELECT COUNT(*)" in sql
    assert call_count == 2


def test_bounded_retry_exhaustion_on_persistent_503(monkeypatch):
    """Verify that call_gemini_model terminates after bounded retries on persistent 503."""
    from core.query_service import call_gemini_model

    call_count = 0

    class AlwaysFailingModelMock:
        def invoke(self, prompt):
            nonlocal call_count
            call_count += 1
            raise Exception("503 UNAVAILABLE. Model experiencing high demand.")

    monkeypatch.setattr("core.query_service.get_gemini_model", lambda name=None: AlwaysFailingModelMock())

    with pytest.raises(ModelOverloadedError) as exc_info:
        call_gemini_model("Query", max_retries=2, initial_backoff=0.01)

    assert exc_info.value.upstream_status == 503
    assert call_count == 3  # 1 initial + 2 retries


def test_non_transient_auth_error_does_not_retry(monkeypatch):
    """Verify that 401/403 authentication failures fail immediately without retrying."""
    from core.query_service import call_gemini_model

    call_count = 0

    class AuthFailingModelMock:
        def invoke(self, prompt):
            nonlocal call_count
            call_count += 1
            raise Exception("401 UNAUTHENTICATED. The request is missing a valid API key.")

    monkeypatch.setattr("core.query_service.get_gemini_model", lambda name=None: AuthFailingModelMock())

    with pytest.raises(ModelAuthError):
        call_gemini_model("Query", max_retries=2, initial_backoff=0.01)

    assert call_count == 1  # No retries on auth errors


def test_sanitize_error_details_scrubs_keys():
    """Verify that error sanitizer cleans raw API keys and query parameters."""
    for raw_error_1 in ['Failed with key: AIzaSyB1234567890abcdefghijklmnopqrstuvwxyz and token', 'Failed with key: AIzaSyDummyTestExampleKeyNotReal12345 and token']:
        clean_1 = sanitize_error_details(raw_error_1)
        assert 'AIzaSy' not in clean_1
        assert '[REDACTED_API_KEY]' in clean_1

    raw_error_2 = "Error: https://generativelanguage.googleapis.com/v1/models?key=AQ.Ab8FakeTestDummyKeyNotReal1234567890 failed"
    clean_2 = sanitize_error_details(raw_error_2)
    assert "FakeTestDummy" not in clean_2
    assert "key=[REDACTED]" in clean_2


def test_row_limit_enforced_in_sql_and_execution(tmp_path, monkeypatch):
    """Verify queries enforce maximum 100 row limit on AST and result."""
    monkeypatch.setenv("DATASETS_DIR", str(tmp_path))

    # Create CSV with 120 rows
    rows = ["id,val"]
    for i in range(120):
        rows.append(f"{i},{i * 2}")
    csv_bytes = "\n".join(rows).encode("utf-8")

    res = client.post("/api/upload", files={"file": ("large.csv", io.BytesIO(csv_bytes), "text/csv")})
    dataset_id = res.json()["data"]["dataset_id"]

    # Model returned query without limit or with excessive limit
    monkeypatch.setattr("core.query_service.call_gemini_model", lambda p: "SELECT * FROM uploaded_data LIMIT 500")

    response = client.post(
        "/api/query",
        json={"dataset_id": dataset_id, "question": "Get all rows"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "LIMIT 100" in data["sql"]
    assert data["row_count"] == 100
    assert len(data["rows"]) == 100


def test_sql_validation_unit_tests():
    """Unit tests for validate_and_sanitize_sql logic."""
    # Valid SELECT
    safe = validate_and_sanitize_sql("SELECT name, age FROM uploaded_data WHERE age > 25")
    assert "LIMIT 100" in safe

    # Valid CTE
    safe_cte = validate_and_sanitize_sql("WITH sub AS (SELECT * FROM uploaded_data) SELECT * FROM sub")
    assert "LIMIT 100" in safe_cte

    # Code fence stripping in query service
    from core.query_service import clean_model_sql_output
    fenced = "```sql\nSELECT COUNT(*) FROM uploaded_data;\n```"
    assert clean_model_sql_output(fenced) == "SELECT COUNT(*) FROM uploaded_data"


# ---------------------------------------------------------------------------
# Regression tests for the inline-backtick / Column-node bug
# ---------------------------------------------------------------------------

def test_inline_backtick_stripping():
    """Gemini may return SQL wrapped in inline backticks.  clean_model_sql_output
    must strip them so SQLGlot does not interpret the entire query as a Column."""
    from core.query_service import clean_model_sql_output

    assert clean_model_sql_output("`SELECT COUNT(*) FROM uploaded_data`") == "SELECT COUNT(*) FROM uploaded_data"
    assert clean_model_sql_output("`SELECT * FROM uploaded_data`") == "SELECT * FROM uploaded_data"
    # Triple-backtick fences should still be handled
    assert clean_model_sql_output("```sql\nSELECT 1;\n```") == "SELECT 1"


def test_validate_select_count_star():
    """SELECT COUNT(*) FROM uploaded_data must pass validation."""
    result = validate_and_sanitize_sql("SELECT COUNT(*) FROM uploaded_data")
    assert "COUNT(*)" in result
    assert "uploaded_data" in result
    assert "LIMIT" in result


def test_validate_select_star():
    """SELECT * FROM uploaded_data must pass validation."""
    result = validate_and_sanitize_sql("SELECT * FROM uploaded_data")
    assert "uploaded_data" in result
    assert "LIMIT 100" in result


def test_validate_select_group_by():
    """SELECT with GROUP BY on uploaded_data must pass validation."""
    result = validate_and_sanitize_sql(
        "SELECT department, COUNT(*) FROM uploaded_data GROUP BY department"
    )
    assert "GROUP BY" in result
    assert "uploaded_data" in result


def test_validate_safe_cte():
    """A CTE that only references uploaded_data must pass validation."""
    result = validate_and_sanitize_sql(
        "WITH sub AS (SELECT * FROM uploaded_data) SELECT * FROM sub"
    )
    assert "WITH" in result
    assert "uploaded_data" in result
    assert "LIMIT" in result


def test_destructive_sql_still_rejected():
    """Destructive statements must continue to be rejected."""
    for bad_sql in [
        "DROP TABLE uploaded_data",
        "DELETE FROM uploaded_data",
        "UPDATE uploaded_data SET salary = 0",
        "INSERT INTO uploaded_data VALUES (1, 'x', 'y', 0)",
    ]:
        with pytest.raises(UnsafeSQLError):
            validate_and_sanitize_sql(bad_sql)


def test_multiple_statements_still_rejected():
    """Multiple statements separated by semicolons must be rejected."""
    with pytest.raises(UnsafeSQLError):
        validate_and_sanitize_sql("SELECT * FROM uploaded_data; DROP TABLE uploaded_data")


def test_full_pipeline_with_inline_backtick_sql(sample_dataset, monkeypatch):
    """End-to-end: Gemini returns inline-backtick-wrapped SQL and the query succeeds."""
    monkeypatch.setattr(
        "core.query_service.call_gemini_model",
        lambda prompt: "`SELECT COUNT(*) FROM uploaded_data`"
    )

    response = client.post(
        "/api/query",
        json={
            "dataset_id": sample_dataset,
            "question": "How many rows are in this dataset?"
        }
    )

    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert res["row_count"] == 1
    assert res["rows"][0][0] == 3  # 3 rows in sample dataset


def test_extract_text_from_structured_and_serialized_content():
    """Gemini may return response.content as a list of dicts, or serialized string thereof."""
    from core.query_service import clean_model_sql_output, extract_text_from_model_content

    # Exact Gemini content block list
    raw_list = [{'type': 'text', 'text': 'SELECT COUNT(*) FROM "uploaded_data";', 'extras': {'signature': 'sig123'}}]
    assert extract_text_from_model_content(raw_list) == 'SELECT COUNT(*) FROM "uploaded_data";'
    assert clean_model_sql_output(raw_list) == 'SELECT COUNT(*) FROM "uploaded_data"'

    # Python repr / stringified list
    raw_repr = '[{\'type\': \'text\', \'text\': \'SELECT COUNT(*) FROM "uploaded_data";\', \'extras\': {\'signature\': \'sig123\'}}]'
    assert clean_model_sql_output(raw_repr) == 'SELECT COUNT(*) FROM "uploaded_data"'

    # Double-quoted full SELECT query
    assert clean_model_sql_output('"SELECT COUNT(*) FROM uploaded_data"') == "SELECT COUNT(*) FROM uploaded_data"


def test_destructive_sql_in_structured_response_rejected():
    """Destructive statements inside structured responses must still be rejected."""
    from core.query_service import clean_model_sql_output

    malicious_inputs = [
        [{'type': 'text', 'text': 'DROP TABLE uploaded_data;'}],
        "[{'type': 'text', 'text': 'DELETE FROM uploaded_data;'}]",
        "[{'type': 'text', 'text': 'UPDATE uploaded_data SET salary = 0;'}]",
        "[{'type': 'text', 'text': 'SELECT * FROM uploaded_data; DROP TABLE uploaded_data;'}]",
    ]

    for item in malicious_inputs:
        cleaned = clean_model_sql_output(item)
        with pytest.raises(UnsafeSQLError):
            validate_and_sanitize_sql(cleaned)


def test_full_pipeline_with_gemini_content_block_list(sample_dataset, monkeypatch):
    """End-to-end: Gemini returns a list of content blocks (the exact failing format) and query succeeds."""
    monkeypatch.setattr(
        "core.query_service.call_gemini_model",
        lambda prompt: [{'type': 'text', 'text': 'SELECT COUNT(*) FROM "uploaded_data";', 'extras': {'signature': 'EooGCoc...'}}]
    )

    response = client.post(
        "/api/query",
        json={
            "dataset_id": sample_dataset,
            "question": "How many rows are in this dataset?"
        }
    )

    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert res["row_count"] == 1
    assert res["rows"][0][0] == 3
    assert "There are 3 matching records" in res["answer"]


def test_full_pipeline_with_serialized_content_block_repr(sample_dataset, monkeypatch):
    """End-to-end: Gemini returns serialized Python repr of content blocks and query succeeds."""
    serialized_repr = '[{\'type\': \'text\', \'text\': \'SELECT COUNT(*) FROM "uploaded_data";\', \'extras\': {\'signature\': \'EooGCoc...\'}}]'
    monkeypatch.setattr(
        "core.query_service.call_gemini_model",
        lambda prompt: serialized_repr
    )

    response = client.post(
        "/api/query",
        json={
            "dataset_id": sample_dataset,
            "question": "How many rows are in this dataset?"
        }
    )

    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert res["row_count"] == 1
    assert res["rows"][0][0] == 3
    assert "There are 3 matching records" in res["answer"]


