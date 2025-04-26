import logging
import random
import traceback
import time
import sys
import os
from datetime import datetime
import importlib
from contextlib import contextmanager
import json
import numpy as np  # Intentional use for errors
import requests
import xml.etree.ElementTree as ET
import sqlite3
import pandas as pd
from collections import namedtuple

# Configure logging with a custom formatter to include tags
class TaggedFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, 'tag'):
            record.tag = 'GENERAL'
        return super().format(record)

# Set up logging configuration
logger = logging.getLogger('application')
logger.setLevel(logging.DEBUG)

# Create file handler
file_handler = logging.FileHandler('simulated_system.log')
file_handler.setLevel(logging.DEBUG)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create formatter
formatter = TaggedFormatter('%(asctime)s [%(levelname)s] [%(tag)s] - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Helper function to log with a tag
def log_with_tag(level, message, tag='GENERAL', exc_info=None):
    record = logging.LogRecord(
        name=logger.name,
        level=level,
        pathname=__file__,
        lineno=0,
        msg=message,
        args=(),
        exc_info=exc_info,
        func=None
    )
    record.tag = tag
    logger.handle(record)

# Context manager for error capture
@contextmanager
def capture_error(tag='ERROR'):
    try:
        yield
    except Exception as e:
        exc_info = sys.exc_info()
        log_with_tag(logging.ERROR, f"Exception caught: {str(e)}", tag, exc_info)

# Generate info logs
def generate_info_logs():
    info_messages = [
        ("Starting application server on port 8080", "SERVER"),
        ("User authentication successful for user 'admin'", "AUTH"),
        ("Loading configuration from environment variables", "CONFIG"),
        ("Established database connection to PostgreSQL", "DATABASE"),
        ("API rate limit set to 100 requests per minute", "API"),
        ("Cache hit ratio: 87.5% for the last 1000 requests", "CACHE"),
        ("Background task scheduler initialized with 3 workers", "TASK"),
        ("Successfully processed 157 records in batch job", "BATCH"),
        ("Metrics collection service started successfully", "METRICS")
    ]
    
    for message, tag in info_messages:
        log_with_tag(logging.INFO, message, tag)
        time.sleep(0.05)

# Generate error logs with actual Python libraries
def generate_error_logs():
    # 1. NumPy dimension mismatch error
    with capture_error("NUMPY"):
        a = np.array([1, 2, 3])
        b = np.array([[1, 2], [3, 4]])
        result = a + b  # Dimension mismatch
    
    # 2. Pandas KeyError
    with capture_error("PANDAS"):
        df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
        value = df['C']  # Column doesn't exist
    
    # 3. JSON parsing error
    with capture_error("JSON"):
        invalid_json = '{"name": "John", "age": 30, "city": "New York"'  # Missing closing brace
        parsed_data = json.loads(invalid_json)
    
    # 4. Requests connection error
    with capture_error("HTTP"):
        response = requests.get('http://nonexistent-domain-12345.com', timeout=1)
    
    # 5. SQLite operational error
    with capture_error("DATABASE"):
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nonexistent_table")
    
    # 6. XML parsing error
    with capture_error("XML"):
        invalid_xml = '<root><element>Text</element><unpaired>'
        root = ET.fromstring(invalid_xml)
    
    # 7. AttributeError from trying to use old/renamed method
    with capture_error("DEPRECATED"):
        # Simulate use of a deprecated function
        class DeprecatedAPI:
            def __init__(self):
                pass
                
            # Method was renamed in "newer version"
            def connect(self):
                pass
                
        api = DeprecatedAPI()
        api.connect_to_server()  # This method doesn't exist, simulating renamed API
    
    # 8. TypeError with wrong argument type
    with capture_error("TYPE"):
        def process_numbers(numbers_list):
            return sum(numbers_list)
            
        process_numbers("not a list")
    
    # 9. FileNotFoundError
    with capture_error("FILE"):
        with open('/path/to/nonexistent/file.txt', 'r') as f:
            content = f.read()
    
    # 10. OS error with permissions
    with capture_error("OS"):
        # Try to write to a location that typically requires elevated permissions
        if os.name == 'posix':  # Unix/Linux/Mac
            with open('/etc/restricted_file.txt', 'w') as f:
                f.write('test')
        else:  # Windows or other
            with open('C:\\Windows\\restricted_file.txt', 'w') as f:
                f.write('test')

# Generate critical logs
def generate_critical_logs():
    critical_messages = [
        ("DATABASE PRIMARY SERVER DOWN: Failover initiated to secondary server", "DB_CRITICAL"),
        ("MEMORY EXHAUSTION: Process using 98% of available system memory", "SYSTEM_CRITICAL")
    ]
    
    for message, tag in critical_messages:
        log_with_tag(logging.CRITICAL, message, tag)
        time.sleep(0.05)

# Main function
def main():
    print("Starting error log generator with real Python libraries...")
    
    # Generate logs in interleaved fashion
    generate_info_logs()
    generate_error_logs()
    generate_critical_logs()
    
    print("Log generation completed. Check application.log for results.")

if __name__ == "__main__":
    main()