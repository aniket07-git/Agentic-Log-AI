from fastapi import FastAPI, File, UploadFile, HTTPException
from typing import List, Dict
import os
import logging

# Import the LogAnalyzer class
try:
    from log_analyzer import LogAnalyzer
except ImportError:
    # Handle the case where log_analyzer might not be found initially
    # You might need to adjust PYTHONPATH or ensure it's discoverable
    logging.error("Could not import LogAnalyzer. Ensure log_analyzer.py is accessible.")
    # Exit or provide a fallback if critical
    import sys
    sys.exit("LogAnalyzer module not found.")

app = FastAPI(
    title="Log Analytics API",
    description="API for analyzing log files and getting AI-powered fixes.",
    version="0.1.0"
)

# --- In-Memory Storage (Replace with DB for persistence) ---
# Simple dictionary to store errors associated with an upload ID (filename for now)
# This will reset every time the server restarts.
error_storage: Dict[str, List[Dict]] = {}

# --- Analyzer Instance ---
# Create a single instance of LogAnalyzer
# Consider lifespan management if it becomes resource-intensive
analyzer = LogAnalyzer()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Helper Functions (Copied/Adapted from Streamlit version) ---

def safe_find_file(file_path: str):
    """Wrapper for find_file that handles potential errors."""
    try:
        return analyzer.find_file(file_path)
    except Exception as e:
        logger.warning(f"Error finding file {file_path}: {e}")
        return None

def safe_get_relevant_code(file_path: str, line_number: int):
    """Wrapper for get_relevant_code that handles potential errors."""
    try:
        return analyzer.get_relevant_code(file_path, line_number)
    except Exception as e:
        logger.warning(f"Error getting code context for {file_path}:{line_number}: {e}")
        return {'error': str(e)}

def safe_get_error_analysis(error: Dict, code_context: Dict):
    """Wrapper for get_error_analysis."""
    try:
        return analyzer.get_error_analysis(error, code_context)
    except Exception as e:
        logger.error(f"Error generating analysis: {e}")
        return "Could not generate analysis due to an internal error."

def safe_get_fix(error: Dict, code_context: Dict):
    """Wrapper for get_fix."""
    try:
        return analyzer.get_fix(error, code_context)
    except Exception as e:
        logger.error(f"Error generating fix: {e}")
        return "Could not generate fix due to an internal error."

# --- API Endpoints ---

@app.post("/upload/", summary="Upload Log File for Analysis")
async def upload_log_file(file: UploadFile = File(...)):
    """
    Uploads a log file, extracts errors, stores them, and returns the list of errors.
    
    - **file**: The log file (.log or .txt) to upload.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file name provided.")

    logger.info(f"Received file: {file.filename}")
    
    # Read content
    try:
        content_bytes = await file.read()
        log_content = content_bytes.decode("utf-8")
    except Exception as e:
        logger.error(f"Error reading file {file.filename}: {e}")
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")
    finally:
        await file.close()

    # Extract errors using the refactored method
    try:
        extracted_errors = analyzer.extract_errors(log_content)
        logger.info(f"Extracted {len(extracted_errors)} errors from {file.filename}")
    except Exception as e:
        logger.error(f"Error extracting errors from {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Error during error extraction: {e}")

    # Store errors using filename as key (simple approach)
    # Add an index/ID to each error dictionary for later retrieval
    for i, error in enumerate(extracted_errors):
        error['id'] = i 
    
    upload_id = file.filename # Use filename as a simple ID for this session
    error_storage[upload_id] = extracted_errors
    
    return {"upload_id": upload_id, "errors_found": len(extracted_errors), "errors": extracted_errors}

@app.get("/errors/{upload_id}/", summary="Get All Errors for an Upload")
async def get_errors(upload_id: str):
    """
    Retrieves the list of all errors extracted from a specific log file upload.
    
    - **upload_id**: The ID (filename) returned by the /upload/ endpoint.
    """
    if upload_id not in error_storage:
        raise HTTPException(status_code=404, detail="Upload ID not found.")
        
    return {"upload_id": upload_id, "errors": error_storage[upload_id]}

@app.get("/errors/{upload_id}/{error_id}/details/", summary="Get Detailed Analysis and Fix for an Error")
async def get_error_details(upload_id: str, error_id: int):
    """
    Retrieves detailed information, AI analysis, and a suggested fix for a specific error.
    
    - **upload_id**: The ID (filename) returned by the /upload/ endpoint.
    - **error_id**: The index (ID) of the specific error within the upload.
    """
    if upload_id not in error_storage:
        raise HTTPException(status_code=404, detail="Upload ID not found.")
        
    errors = error_storage[upload_id]
    if error_id < 0 or error_id >= len(errors):
        raise HTTPException(status_code=404, detail="Error ID not found for this upload.")
        
    error = errors[error_id]
    
    logger.info(f"Fetching details for error {error_id} from upload {upload_id}")
    
    response = {
        "error_details": error,
        "code_context": None,
        "analysis": None,
        "fix": None
    }

    # Find file and get code context
    file_path_original = error.get('file_path')
    line_number_original = error.get('line_number')

    if not file_path_original or not line_number_original:
        logger.warning(f"Missing file path or line number for error {error_id}")
        response["analysis"] = "Cannot generate analysis: Missing file path or line number in log."
        response["fix"] = "Cannot generate fix: Missing file path or line number in log."
        return response

    try:
        line_number_int = int(line_number_original)
    except ValueError:
        logger.warning(f"Invalid line number format for error {error_id}: {line_number_original}")
        response["analysis"] = "Cannot generate analysis: Invalid line number format."
        response["fix"] = "Cannot generate fix: Invalid line number format."
        return response

    file_path_abs = safe_find_file(file_path_original)
    
    if not file_path_abs:
        logger.warning(f"Could not locate the file '{file_path_original}' for error {error_id}")
        response["analysis"] = f"Cannot generate analysis: Could not locate file '{file_path_original}'."
        response["fix"] = f"Cannot generate fix: Could not locate file '{file_path_original}'."
        return response
        
    code_context = safe_get_relevant_code(file_path_abs, line_number_int)
    
    if code_context and 'error' not in code_context:
        response["code_context"] = code_context.get('code') # Only send the relevant code snippet
        
        # Generate Analysis and Fix
        logger.info(f"Generating analysis for error {error_id}...")
        response["analysis"] = safe_get_error_analysis(error, code_context)
        
        logger.info(f"Generating fix for error {error_id}...")
        response["fix"] = safe_get_fix(error, code_context)
    else:
        error_msg = code_context.get('error', 'Unknown error getting code context')
        logger.warning(f"Could not get code context for error {error_id}: {error_msg}")
        response["analysis"] = f"Cannot generate analysis: {error_msg}"
        response["fix"] = f"Cannot generate fix: {error_msg}"

    return response


# --- Root Endpoint (Optional) ---
@app.get("/", summary="API Root")
async def read_root():
    return {"message": "Welcome to the Log Analytics API. Go to /docs for documentation."}

# --- Running the App (Example) ---
# Use uvicorn to run the app:
# uvicorn main:app --reload 