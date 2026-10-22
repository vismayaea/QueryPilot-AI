import ast
import datetime
import json
import logging
import os
import random
import re
import sqlite3
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import sqlglot
from sqlglot import exp

from dotenv import load_dotenv

from core.dataset_manager import (
    TABLE_NAME,
    DatasetNotFoundError,
    InvalidDatasetIdError,
    get_dataset_db_path,
    get_dataset_metadata,
    is_valid_dataset_id,
)

logger = logging.getLogger("querypilot.query_service")

# Derive project root from source file location: core/ -> project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

_ENV_LOADED = False


def load_project_env(force: bool = False) -> None:
    """
    Ensure environment variables are loaded from the project root .env file
    using a path derived from the source file location.
    """
    global _ENV_LOADED
    if not _ENV_LOADED or force:
        if os.path.exists(ENV_PATH):
            load_dotenv(dotenv_path=ENV_PATH, override=False)
        _ENV_LOADED = True


# Initialize on module load
load_project_env()

# Security constants
MAX_ROW_LIMIT = 100
DEFAULT_QUERY_TIMEOUT_SECONDS = 5.0
ALLOWED_TABLE = TABLE_NAME.lower()  # "uploaded_data"

# Retry configuration for transient model failures
DEFAULT_MAX_RETRIES = 2
DEFAULT_INITIAL_BACKOFF = 0.5
DEFAULT_MAX_BACKOFF = 3.0


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class UnsafeSQLError(ValueError):
    """Raised when generated SQL fails security validation."""
    pass


class QueryExecutionError(RuntimeError):
    """Raised when query execution in SQLite fails."""
    pass


class QueryTimeoutError(QueryExecutionError):
    """Raised when a query exceeds the execution time limit."""
    pass


class ModelServiceError(RuntimeError):
    """Base exception for Gemini API or model invocation failures."""
    def __init__(
        self,
        message: str,
        status_code: int = 502,
        error_type: str = "model_error",
        retryable: bool = False,
        upstream_status: Optional[int] = None,
        retry_after: Optional[float] = None,
        model_name: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.retryable = retryable
        self.upstream_status = upstream_status
        self.retry_after = retry_after
        self.model_name = model_name


class MissingCredentialsError(ModelServiceError):
    """Raised when GOOGLE_API_KEY is not configured."""
    def __init__(self, message: str = "GOOGLE_API_KEY environment variable is not configured."):
        super().__init__(
            message=message,
            status_code=503,
            error_type="missing_credentials",
            retryable=False,
            upstream_status=503,
        )


class ModelAuthError(ModelServiceError):
    """Raised when Gemini API authentication or permission verification fails."""
    def __init__(
        self,
        message: str,
        upstream_status: Optional[int] = 401,
        model_name: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=401,
            error_type="authentication_error",
            retryable=False,
            upstream_status=upstream_status,
            model_name=model_name,
        )


class ModelQuotaExceededError(ModelServiceError):
    """Raised when Gemini API quota or rate limits are exceeded."""
    def __init__(
        self,
        message: str,
        upstream_status: Optional[int] = 429,
        retry_after: Optional[float] = None,
        model_name: Optional[str] = None,
        retryable: bool = False,
    ):
        super().__init__(
            message=message,
            status_code=429,
            error_type="quota_exceeded",
            retryable=retryable,
            upstream_status=upstream_status,
            retry_after=retry_after,
            model_name=model_name,
        )


class ModelOverloadedError(ModelServiceError):
    """Raised when the Gemini model is temporarily overloaded (503 Service Unavailable)."""
    def __init__(
        self,
        message: str,
        upstream_status: Optional[int] = 503,
        model_name: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=503,
            error_type="model_overloaded",
            retryable=True,
            upstream_status=upstream_status,
            model_name=model_name,
        )


class ModelNotFoundError(ModelServiceError):
    """Raised when the configured Gemini model is deprecated or does not exist."""
    def __init__(
        self,
        message: str,
        upstream_status: Optional[int] = 404,
        model_name: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=400,
            error_type="model_not_found",
            retryable=False,
            upstream_status=upstream_status,
            model_name=model_name,
        )


class ModelTimeoutError(ModelServiceError):
    """Raised when a request to Gemini times out."""
    def __init__(
        self,
        message: str,
        upstream_status: Optional[int] = 504,
        model_name: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=504,
            error_type="timeout",
            retryable=True,
            upstream_status=upstream_status,
            model_name=model_name,
        )


class ModelResponseMalformedError(ModelServiceError):
    """Raised when Gemini returns an empty or unparseable response."""
    def __init__(
        self,
        message: str = "Gemini model returned an empty or malformed response.",
        model_name: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=502,
            error_type="malformed_response",
            retryable=False,
            upstream_status=502,
            model_name=model_name,
        )


# ---------------------------------------------------------------------------
# Sanitization & Key Verification Helpers
# ---------------------------------------------------------------------------

_KEY_PARAM_REGEX = re.compile(r'(key=)[^\s&"\']+', re.IGNORECASE)


def sanitize_error_details(text: str) -> str:
    """
    Strips raw API keys, bearer tokens, or query param credentials from error strings.
    Never exposes secrets in logs or user-facing error messages.
    """
    if not text:
        return ""
    # Redact query param key=...
    sanitized = _KEY_PARAM_REGEX.sub(r'\1[REDACTED]', text)
    # Redact bearer tokens
    sanitized = re.sub(r'(Bearer\s+)[A-Za-z0-9_\-\.]+', r'\1[REDACTED]', sanitized, flags=re.IGNORECASE)
    # Redact actual Google API key patterns (AIza... and AQ....) of any length
    sanitized = re.sub(r'AIza[0-9A-Za-z\-_]+', '[REDACTED_API_KEY]', sanitized)
    sanitized = re.sub(r'AQ\.[0-9A-Za-z\-_]+', '[REDACTED_API_KEY]', sanitized)
    return sanitized


def mask_secret(secret: Optional[str]) -> str:
    """Masks a secret key for safe logging (e.g. 'AQ.A...*** (len 53)')."""
    if not secret:
        return "[NOT SET]"
    s = secret.strip()
    if len(s) <= 8:
        return "***"
    return f"{s[:4]}...{s[-3:]} (len {len(s)})"


def classify_gemini_exception(e: Exception, model_name: str) -> ModelServiceError:
    """
    Inspects upstream exception type, HTTP status, and error payload to categorize
    into specific ModelServiceError subclasses with clear, actionable messages.
    """
    if isinstance(e, ModelServiceError):
        return e

    err_str = str(e)
    sanitized_msg = sanitize_error_details(err_str)
    err_cls_name = type(e).__name__

    # Extract upstream HTTP status code if present
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if code is None:
        code_match = re.search(r'\b(400|401|403|404|408|429|500|502|503|504)\b', err_str)
        if code_match:
            try:
                code = int(code_match.group(1))
            except ValueError:
                code = None

    # 1. Authentication / Permission failures (401 / 403)
    if (
        code in (401, 403)
        or "unauthenticated" in err_str.lower()
        or "permission_denied" in err_str.lower()
        or "authentication" in err_cls_name.lower()
        or "permissiondenied" in err_cls_name.lower()
    ):
        return ModelAuthError(
            message=(
                f"Gemini API authentication failed for model '{model_name}'. "
                f"Please verify that your GOOGLE_API_KEY is valid and has the Gemini API enabled."
            ),
            upstream_status=code or 401,
            model_name=model_name,
        )

    # 2. Model not found / deprecated (404)
    if (
        code == 404
        or "not_found" in err_str.lower()
        or "modelnotfound" in err_cls_name.lower()
    ):
        return ModelNotFoundError(
            message=(
                f"Gemini model '{model_name}' was not found or is no longer available. "
                f"Please update GEMINI_MODEL in your .env file (recommended: gemini-3.5-flash-lite)."
            ),
            upstream_status=404,
            model_name=model_name,
        )

    # 3. Quota or rate limit exceeded (429 / RESOURCE_EXHAUSTED)
    if (
        code == 429
        or "resource_exhausted" in err_str.lower()
        or "ratelimit" in err_cls_name.lower()
        or "quota" in err_str.lower()
    ):
        is_daily_limit = (
            "free_tier" in err_str.lower()
            or "perday" in err_str.lower()
            or "generaterequestsperday" in err_str.lower()
            or "exceeded your current quota" in err_str.lower()
        )
        delay_match = re.search(r'retry in\s+([0-9a-zA-Z\.]+)', err_str, re.IGNORECASE)
        retry_text = f" (upstream indicates reset in {delay_match.group(1)})" if delay_match else ""

        if is_daily_limit:
            actionable_msg = (
                f"Gemini API daily free-tier quota exceeded for model '{model_name}'{retry_text}. "
                f"To continue querying immediately, switch GEMINI_MODEL in .env (e.g. gemini-3.5-flash-lite) or check plan details at https://ai.google.dev."
            )
            return ModelQuotaExceededError(
                message=actionable_msg,
                upstream_status=429,
                model_name=model_name,
                retryable=False,
            )
        else:
            actionable_msg = (
                f"Gemini API rate limit reached for model '{model_name}'{retry_text}. "
                f"Please wait a moment before sending additional queries."
            )
            return ModelQuotaExceededError(
                message=actionable_msg,
                upstream_status=429,
                model_name=model_name,
                retryable=True,
            )

    # 4. Model overload / high demand (503)
    if (
        code == 503
        or "high demand" in err_str.lower()
        or "unavailable" in err_str.lower()
        or "servererror" in err_cls_name.lower()
    ):
        return ModelOverloadedError(
            message=(
                f"Gemini model '{model_name}' is temporarily experiencing high demand (503 Service Unavailable). "
                f"Please try again in a few moments."
            ),
            upstream_status=503,
            model_name=model_name,
        )

    # 5. Timeout (408 / 504)
    if (
        code in (408, 504)
        or "timeout" in err_str.lower()
        or "timed out" in err_str.lower()
    ):
        return ModelTimeoutError(
            message=(
                f"Request to Gemini model '{model_name}' timed out. "
                f"Upstream service took too long to respond."
            ),
            upstream_status=code or 504,
            model_name=model_name,
        )

    # 6. Generic or fallback ModelServiceError
    return ModelServiceError(
        message=f"Gemini API invocation error for model '{model_name}': {sanitized_msg}",
        status_code=502,
        error_type="model_invocation_failure",
        retryable=False,
        upstream_status=code or 502,
        model_name=model_name,
    )


def build_schema_prompt_context(metadata: Dict[str, Any]) -> str:
    """
    Builds a concise schema description for the dataset to pass to Gemini.
    Only passes column names, clean SQL names, types, and sample values.
    Never sends full dataset rows.
    """
    lines = [
        f"Database Dialect: SQLite",
        f"Table Name: \"{metadata['table_name']}\"",
        "Columns:"
    ]
    for col in metadata.get("columns", []):
        clean_name = col.get("clean_name", col.get("name"))
        orig_name = col.get("original_name", col.get("name"))
        sql_type = col.get("sqlite_type", col.get("inferred_type", "TEXT"))
        samples = col.get("sample_values", [])
        sample_str = f" (Sample values: {samples})" if samples else ""
        if clean_name != orig_name:
            lines.append(f"  - \"{clean_name}\" ({sql_type}) [original CSV header: '{orig_name}']{sample_str}")
        else:
            lines.append(f"  - \"{clean_name}\" ({sql_type}){sample_str}")
    return "\n".join(lines)


def get_gemini_model(model_name: Optional[str] = None):
    """Initializes and returns ChatGoogleGenerativeAI using project configuration."""
    # Ensure configuration is loaded from .env before checking credentials
    load_project_env()

    api_key = os.environ.get("GOOGLE_API_KEY", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.error("Missing Gemini API credentials: GOOGLE_API_KEY is not set.")
        raise MissingCredentialsError("GOOGLE_API_KEY environment variable is not configured.")

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as e:
        raise ModelServiceError(f"langchain_google_genai is not installed: {e}")

    gemini_model_name = (model_name or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")).strip()
    logger.info(
        "Configured Gemini model: model='%s', key=%s",
        gemini_model_name,
        mask_secret(api_key),
    )

    # Disable LangChain's internal 6 unconstrained retries (max_retries=0)
    # so bounded retries with exponential backoff are controlled in query_service.
    return ChatGoogleGenerativeAI(
        model=gemini_model_name,
        temperature=0,
        max_retries=0,
    )


def extract_text_from_model_content(content: Any) -> str:
    """
    Extracts plain text string from model response content.
    LangChain / Gemini may return content as:
    - str
    - list of content blocks, e.g. [{'type': 'text', 'text': '...'}, ...]
    - an object with a .text attribute
    - a serialized string representation of a list or dict
    """
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
            elif hasattr(item, "text"):
                parts.append(str(item.text))
            else:
                parts.append(str(item))
        return "".join(parts)
    elif isinstance(content, dict) and "text" in content:
        return str(content["text"])
    elif hasattr(content, "text") and not isinstance(content, str):
        return str(content.text)
    elif isinstance(content, str):
        v = content.strip()
        if (v.startswith("[") and v.endswith("]")) or (v.startswith("{") and v.endswith("}")):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, (list, dict)):
                    return extract_text_from_model_content(parsed)
            except Exception:
                try:
                    parsed = ast.literal_eval(v)
                    if isinstance(parsed, (list, dict)):
                        return extract_text_from_model_content(parsed)
                except Exception:
                    pass
        return content
    return str(content)


def call_gemini_model(
    prompt: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_backoff: float = DEFAULT_INITIAL_BACKOFF,
) -> str:
    """
    Invokes Gemini to generate SQL with bounded retries and exponential backoff
    for transient errors (e.g. 503 high demand or temporary rate spikes).
    Non-transient errors (401, 403, 404, daily quota 429) fail fast without retrying.
    """
    load_project_env()
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    model = get_gemini_model(model_name)

    attempts = max_retries + 1
    last_error: Optional[ModelServiceError] = None

    for attempt in range(1, attempts + 1):
        try:
            response = model.invoke(prompt)
            raw_content = response.content if hasattr(response, "content") else response
            text = extract_text_from_model_content(raw_content)
            if not text or not text.strip():
                raise ModelResponseMalformedError(
                    f"Gemini model '{model_name}' returned an empty response.",
                    model_name=model_name,
                )
            return text
        except Exception as e:
            classified = classify_gemini_exception(e, model_name)
            last_error = classified

            # Safe, sanitized logging with zero secret disclosure
            logger.warning(
                "Gemini invocation failure (attempt %d/%d): model='%s', exception_type='%s', upstream_status=%s, error_type='%s', retryable=%s, detail='%s'",
                attempt,
                attempts,
                model_name,
                type(e).__name__,
                classified.upstream_status,
                classified.error_type,
                classified.retryable,
                sanitize_error_details(str(e))[:250],
            )

            # Do not retry non-transient errors or when max attempts reached
            if not classified.retryable or attempt >= attempts:
                raise classified

            # Bounded exponential backoff with jitter for transient errors
            backoff = min(initial_backoff * (2 ** (attempt - 1)), DEFAULT_MAX_BACKOFF)
            jitter = random.uniform(0.1, 0.3)
            sleep_time = backoff + jitter
            logger.info("Retrying Gemini invocation in %.2f seconds (attempt %d/%d)...", sleep_time, attempt + 1, attempts)
            time.sleep(sleep_time)

    if last_error:
        raise last_error
    raise ModelServiceError(f"Gemini API invocation failed for model '{model_name}'.")


def clean_model_sql_output(raw_output: Any) -> str:
    """Strips markdown code fences, packaging artifacts, and unnecessary whitespace from model response."""
    text = extract_text_from_model_content(raw_output)
    sql = text.strip()
    # Remove leading markdown code fence
    if sql.startswith("```"):
        lines = sql.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        sql = "\n".join(lines).strip()
    # Remove single-line triple backticks (e.g. ```SELECT ...``` or ```sql SELECT ...```)
    if sql.startswith("```") and sql.endswith("```") and len(sql) >= 6:
        inner = sql[3:-3].strip()
        if inner.lower().startswith("sql"):
            inner = inner[3:].strip()
        sql = inner
    # Remove inline backtick wrapping (e.g. `SELECT ...`)
    if sql.startswith("`") and sql.endswith("`") and not sql.startswith("``"):
        sql = sql[1:-1].strip()
    # Remove surrounding double quotes if wrapping a full query (e.g. "SELECT ...")
    if sql.startswith('"') and sql.endswith('"') and len(sql) > 2:
        inner = sql[1:-1].strip()
        if inner.upper().startswith("SELECT") or inner.upper().startswith("WITH"):
            sql = inner
    # Remove trailing semicolons
    sql = sql.rstrip(";").strip()
    return sql


def validate_and_sanitize_sql(sql_query: str) -> str:
    """
    Validates that the SQL query is strictly a read-only SELECT or safe CTE statement
    targeting ONLY 'uploaded_data'. Enforces a maximum LIMIT of 100 rows.
    Uses SQLGlot AST analysis.
    """
    if not sql_query or not sql_query.strip():
        raise UnsafeSQLError("Empty SQL query.")

    try:
        parsed = sqlglot.parse(sql_query, read="sqlite")
    except Exception as e:
        logger.warning("SQL syntax parsing failed for query: %s (error: %s)", sql_query, e)
        raise UnsafeSQLError(f"Invalid SQL syntax: {e}")

    if not parsed or len(parsed) != 1:
        raise UnsafeSQLError("Query must contain exactly one SQL statement.")

    stmt = parsed[0]
    root_node_type = type(stmt).__name__
    logger.info("SQLGlot parsed root node type '%s' for SQL query: %s", root_node_type, sql_query)

    # Root statement must be Select or Union
    if not isinstance(stmt, (exp.Select, exp.Union)):
        logger.warning(
            "Rejected non-SELECT statement of type '%s': %s",
            root_node_type,
            sql_query,
        )
        raise UnsafeSQLError(
            f"Only read-only SELECT queries are allowed. Forbidden statement type: '{root_node_type}'."
        )

    # Disallow destructive or administrative AST nodes anywhere in the query
    disallowed_nodes = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Alter,
        exp.Create,
        exp.Command,
        exp.Pragma,
        exp.Attach,
        exp.Detach,
        exp.Commit,
        exp.Rollback,
        exp.Transaction,
    )

    for node in stmt.walk():
        if isinstance(node, disallowed_nodes):
            raise UnsafeSQLError(
                f"Forbidden SQL operation '{type(node).__name__}' is not allowed."
            )

    # Validate table references: only 'uploaded_data' and declared CTE aliases are allowed
    cte_names: Set[str] = set()
    if hasattr(stmt, "ctes"):
        for cte in stmt.ctes:
            if hasattr(cte, "alias") and cte.alias:
                cte_names.add(cte.alias.lower())

    for table_node in stmt.find_all(exp.Table):
        tname = table_node.name.lower()
        if tname != ALLOWED_TABLE and tname not in cte_names:
            raise UnsafeSQLError(
                f"Access to table '{table_node.name}' is forbidden. Queries must only target '{TABLE_NAME}'."
            )

    # Enforce maximum row limit of 100
    existing_limit = None
    if isinstance(stmt, exp.Select) and stmt.args.get("limit"):
        try:
            existing_limit = int(stmt.args["limit"].expression.this)
        except Exception:
            pass

    if existing_limit is None or existing_limit > MAX_ROW_LIMIT:
        stmt.set("limit", None)
        stmt = stmt.limit(MAX_ROW_LIMIT)

    return stmt.sql(dialect="sqlite")


def execute_safe_query(
    db_path: str,
    sql: str,
    timeout_seconds: float = DEFAULT_QUERY_TIMEOUT_SECONDS,
) -> Tuple[List[str], List[List[Any]]]:
    """
    Executes validated SQL against the SQLite database in strict read-only mode,
    enforcing query timeout and row limit capping.
    """
    if not os.path.exists(db_path):
        raise DatasetNotFoundError(f"Database file not found: {db_path}")

    # Connect using SQLite URI read-only mode
    uri_path = f"file:{os.path.abspath(db_path)}?mode=ro"
    conn = sqlite3.connect(uri_path, uri=True)

    # Configure timeout via progress handler
    start_time = time.time()

    def timeout_handler() -> int:
        if time.time() - start_time > timeout_seconds:
            return 1  # Interrupts execution with OperationalError: interrupted
        return 0

    conn.set_progress_handler(timeout_handler, 200)

    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        raw_rows = cursor.fetchmany(MAX_ROW_LIMIT)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        # Convert rows into standard JSON-serializable Python values
        cleaned_rows = []
        for row in raw_rows:
            cleaned_rows.append([
                val if val is not None else None
                for val in row
            ])

        return columns, cleaned_rows

    except sqlite3.OperationalError as e:
        if "interrupted" in str(e).lower():
            raise QueryTimeoutError(f"Query timed out after {timeout_seconds} seconds.")
        raise QueryExecutionError(f"SQLite execution error: {e}")
    except Exception as e:
        raise QueryExecutionError(f"Database query error: {e}")
    finally:
        conn.close()


def generate_deterministic_answer(
    question: str,
    columns: List[str],
    rows: List[List[Any]],
    row_count: int,
) -> str:
    """
    Produces a concise, accurate explanation of query results deterministically in Python.
    Avoids unnecessary LLM calls and prevents model hallucinations.
    """
    if row_count == 0:
        return "No matching records were found for your question."

    # Single value result (e.g. COUNT, SUM, AVG, MAX, MIN)
    if row_count == 1 and len(columns) == 1:
        col = columns[0]
        val = rows[0][0]
        if val is None:
            return f"The result for {col} is NULL (no value)."
        col_lower = col.lower()
        if "count" in col_lower:
            return f"There are {val:,} matching records."
        if "sum" in col_lower or "total" in col_lower:
            return f"The total {col} is {val:,.2f}" if isinstance(val, (int, float)) else f"The total is {val}."
        if "avg" in col_lower or "average" in col_lower:
            return f"The average {col} is {val:,.2f}" if isinstance(val, (int, float)) else f"The average is {val}."
        if "max" in col_lower or "maximum" in col_lower:
            return f"The maximum {col} is {val}."
        if "min" in col_lower or "minimum" in col_lower:
            return f"The minimum {col} is {val}."
        return f"The result is {val}."

    # Single row with multiple columns
    if row_count == 1:
        pairs = [f"{col}: {val}" for col, val in zip(columns, rows[0])]
        return f"Found 1 record: {', '.join(pairs)}."

    # Multiple rows
    if row_count <= 5:
        return f"Found {row_count} records matching your query."
    return f"Found {row_count} records (capped at {MAX_ROW_LIMIT} rows)."


def query_dataset(
    dataset_id: str,
    question: str,
    llm_invoker: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    """
    Full pipeline for Stage 3:
    1. Validates dataset ID & retrieves metadata.
    2. Constructs schema-only prompt.
    3. Invokes Gemini to generate SQL.
    4. Validates and sanitizes SQL with SQLGlot (read-only, table whitelist, LIMIT 100).
    5. Executes query against isolated SQLite database.
    6. Returns structured result with deterministic answer.
    """
    if not is_valid_dataset_id(dataset_id):
        raise InvalidDatasetIdError(f"Invalid dataset ID format: '{dataset_id}'.")

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    metadata = get_dataset_metadata(dataset_id)
    db_path = get_dataset_db_path(dataset_id)

    schema_context = build_schema_prompt_context(metadata)

    prompt = f"""You are a helpful text-to-SQL translator for SQLite.
Given the following database schema, write a single syntactically correct SQLite query to answer the user's question.

{schema_context}

Guidelines:
1. Use only the table "{TABLE_NAME}".
2. Use the column names exactly as defined in the schema. If a column name contains spaces or special characters, quote it with double quotes.
3. Write ONLY a read-only SELECT query. Do not execute DML (INSERT, UPDATE, DELETE, DROP, ALTER).
4. Do not query internal metadata or SQLite system tables.
5. Return ONLY the raw SQL query. Do not include markdown code fences or explanations.

Question: {question.strip()}
SQL Query:"""

    invoker = llm_invoker or call_gemini_model
    raw_sql = invoker(prompt)
    clean_sql = clean_model_sql_output(raw_sql)
    logger.info("Generated cleaned SQL for dataset '%s': %s", dataset_id, clean_sql)

    # Security validation & limit injection
    safe_sql = validate_and_sanitize_sql(clean_sql)

    # Execute against isolated SQLite DB
    columns, rows = execute_safe_query(db_path, safe_sql)
    row_count = len(rows)

    # Generate answer
    answer = generate_deterministic_answer(question, columns, rows, row_count)

    return {
        "dataset_id": dataset_id,
        "question": question.strip(),
        "sql": safe_sql,
        "columns": columns,
        "rows": rows,
        "row_count": row_count,
        "answer": answer,
    }
