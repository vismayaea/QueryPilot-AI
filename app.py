import logging
import os
from dotenv import load_dotenv

# Ensure .env is loaded from the project root derived from this source file
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(ENV_PATH):
    load_dotenv(dotenv_path=ENV_PATH, override=False)

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.csv_loader import (
    CSVValidationError,
    get_max_upload_size_bytes,
)
from core.dataset_manager import (
    DatasetNotFoundError,
    InvalidDatasetIdError,
    create_and_persist_dataset,
    get_dataset_metadata,
    list_available_datasets,
)
from core.query_service import (
    MissingCredentialsError,
    ModelAuthError,
    ModelNotFoundError,
    ModelOverloadedError,
    ModelQuotaExceededError,
    ModelResponseMalformedError,
    ModelServiceError,
    ModelTimeoutError,
    QueryExecutionError,
    QueryTimeoutError,
    UnsafeSQLError,
    query_dataset,
)

# Set up logging - ensure sensitive tokens are never logged
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("querypilot.api")

app = FastAPI(
    title="QueryPilot AI API",
    description="Backend API for QueryPilot AI - Natural Language Data Analysis",
    version="0.3.0"
)

# Enable CORS for local development and future web client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    dataset_id: str = Field(..., description="Opaque 32-character hexadecimal dataset ID")
    question: str = Field(..., min_length=1, description="Natural language question to query")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "QueryPilot AI", "stage": 3}


@app.post("/api/upload")
@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """
    Accepts a CSV file upload, validates its structure, infers column types,
    persists it into an isolated SQLite database, and returns dataset metadata.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in upload."
        )

    # Filename extension check
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only .csv files are supported."
        )

    max_size = get_max_upload_size_bytes()
    chunk_size = 1024 * 1024  # 1 MB chunks
    total_bytes = 0
    chunks = []

    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_size:
                limit_mb = max_size / (1024 * 1024)
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"File size exceeds the maximum allowed limit of {limit_mb:.1f} MB."
                )
            chunks.append(chunk)

        file_bytes = b"".join(chunks)

        # Validate CSV, persist into isolated SQLite database, and generate metadata
        dataset_metadata = create_and_persist_dataset(
            file_bytes=file_bytes,
            filename=file.filename,
            max_size_bytes=max_size
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": "CSV uploaded and dataset created successfully.",
                "data": dataset_metadata
            }
        )

    except CSVValidationError as e:
        logger.warning(f"CSV validation error for file '{file.filename}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing upload '{file.filename}': {e}", exc_info=False)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the CSV file."
        )
    finally:
        await file.close()


@app.get("/api/datasets")
@app.get("/datasets")
async def list_datasets():
    """
    Retrieves metadata for all available datasets in the system.
    """
    try:
        datasets = list_available_datasets()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": datasets
            }
        )
    except Exception as e:
        logger.error(f"Error listing datasets: {e}", exc_info=False)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving datasets."
        )


@app.get("/api/datasets/{dataset_id}")
@app.get("/datasets/{dataset_id}")
async def get_dataset(dataset_id: str):
    """
    Retrieves metadata for an existing dataset by its opaque ID.
    Returns 400 for invalid ID format, 404 if dataset is not found.
    """
    try:
        metadata = get_dataset_metadata(dataset_id)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": metadata
            }
        )
    except InvalidDatasetIdError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except DatasetNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error retrieving dataset '{dataset_id}': {e}", exc_info=False)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving dataset metadata."
        )


@app.post("/api/query")
@app.post("/query")
async def query_dataset_endpoint(req: QueryRequest):
    """
    Translates a natural language question into safe SQL, executes it against
    the isolated SQLite database, and returns structured results with explanation.
    """
    question = req.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty."
        )

    try:
        result = query_dataset(
            dataset_id=req.dataset_id,
            question=question
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "dataset_id": result["dataset_id"],
                "question": result["question"],
                "sql": result["sql"],
                "columns": result["columns"],
                "rows": result["rows"],
                "row_count": result["row_count"],
                "answer": result["answer"],
                "data": result
            }
        )
    except InvalidDatasetIdError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except DatasetNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except UnsafeSQLError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SQL Security Rejection: {str(e)}"
        )
    except QueryTimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=str(e)
        )
    except QueryExecutionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query Execution Error: {str(e)}"
        )
    except MissingCredentialsError as e:
        logger.warning("Query rejected: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API is not configured on the backend. Please ensure GOOGLE_API_KEY is set in your .env file."
        )
    except ModelAuthError as e:
        logger.error("Gemini API authentication failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Gemini API Authentication Failed: {e.message}"
        )
    except ModelQuotaExceededError as e:
        logger.error("Gemini API quota or rate limit exceeded: %s", e)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Gemini API Quota Exceeded: {e.message}"
        )
    except ModelOverloadedError as e:
        logger.warning("Gemini model overloaded: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Gemini Service Temporarily Unavailable: {e.message}"
        )
    except ModelNotFoundError as e:
        logger.error("Gemini model not found: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gemini Model Configuration Error: {e.message}"
        )
    except ModelTimeoutError as e:
        logger.error("Gemini request timed out: %s", e)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Gemini Gateway Timeout: {e.message}"
        )
    except ModelResponseMalformedError as e:
        logger.error("Gemini malformed response: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini Response Error: {e.message}"
        )
    except ModelServiceError as e:
        logger.error("Gemini model service error: %s", e)
        raise HTTPException(
            status_code=e.status_code if hasattr(e, "status_code") else status.HTTP_502_BAD_GATEWAY,
            detail=e.message if hasattr(e, "message") else str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected query error: {e}", exc_info=False)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your query."
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
