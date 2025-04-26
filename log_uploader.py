import os
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import tempfile
from agent.log_analyser import LogAnalyzer

class LogUploader:
    def __init__(self):
        self.log_analyzer = LogAnalyzer()
        self.supported_formats = ['.log', '.txt']
        
    def process_upload(self, uploaded_file) -> Tuple[bool, List[Dict], str]:
        """
        Process an uploaded log file.
        
        Args:
            uploaded_file: Streamlit UploadedFile object
            
        Returns:
            Tuple of (success, log_entries, error_message)
        """
        try:
            # Check file extension
            _, ext = os.path.splitext(uploaded_file.name)
            if ext.lower() not in self.supported_formats:
                return False, [], f"Unsupported file format. Supported formats: {', '.join(self.supported_formats)}"
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            try:
                # Process the log file
                log_entries = self._parse_log_file(tmp_file_path)
                
                # Extract errors using the log analyzer
                errors = self.log_analyzer.extract_errors(tmp_file_path)
                
                # Add error information to log entries
                self._enrich_log_entries(log_entries, errors)
                
                return True, log_entries, ""
                
            finally:
                # Clean up temporary file
                os.unlink(tmp_file_path)
                
        except Exception as e:
            return False, [], f"Error processing log file: {str(e)}"
    
    def _parse_log_file(self, file_path: str) -> List[Dict]:
        """
        Parse a log file into structured entries.
        
        Args:
            file_path: Path to the log file
            
        Returns:
            List of parsed log entries
        """
        log_entries = []
        
        # Common log format patterns
        patterns = [
            # Standard datetime format
            r'(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+-\s+'
            r'(?P<level>\w+)\s+-\s+'
            r'(?P<source>[\w\-\.]+)\s+-\s+'
            r'(?P<message>.*)',
            
            # Alternative format with square brackets
            r'\[(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d{3})?)\]\s+'
            r'\[(?P<level>\w+)\]\s+'
            r'\[(?P<source>[\w\-\.]+)\]\s+'
            r'(?P<message>.*)',
            
            # Simple format
            r'(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+'
            r'(?P<level>\w+)\s+'
            r'(?P<message>.*)'
        ]
        
        compiled_patterns = [re.compile(pattern) for pattern in patterns]
        
        with open(file_path, 'r') as f:
            current_entry = None
            
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Try each pattern
                matched = False
                for pattern in compiled_patterns:
                    match = pattern.match(line)
                    if match:
                        # If we have a previous entry, add it to the list
                        if current_entry:
                            log_entries.append(current_entry)
                        
                        # Create new entry
                        current_entry = match.groupdict()
                        
                        # Parse timestamp
                        try:
                            timestamp = datetime.strptime(
                                current_entry['timestamp'],
                                '%Y-%m-%d %H:%M:%S,%f' if ',' in current_entry['timestamp']
                                else '%Y-%m-%d %H:%M:%S.%f' if '.' in current_entry['timestamp']
                                else '%Y-%m-%d %H:%M:%S'
                            )
                            current_entry['timestamp'] = timestamp
                        except ValueError:
                            # If timestamp parsing fails, use current time
                            current_entry['timestamp'] = datetime.now()
                        
                        # Set default source if not present
                        if 'source' not in current_entry:
                            current_entry['source'] = 'unknown'
                        
                        matched = True
                        break
                
                # If no pattern matched, append to current entry's message
                if not matched and current_entry:
                    current_entry['message'] += '\n' + line
            
            # Add the last entry
            if current_entry:
                log_entries.append(current_entry)
        
        return log_entries
    
    def _enrich_log_entries(self, log_entries: List[Dict], errors: List[Dict]):
        """
        Add error information to log entries.
        
        Args:
            log_entries: List of parsed log entries
            errors: List of errors from log analyzer
        """
        # Create a map of error messages to their analysis
        error_map = {}
        for error in errors:
            key = f"{error.get('file_path')}:{error.get('line_number')}"
            error_map[key] = error
        
        # Enrich log entries with error information
        for entry in log_entries:
            if entry.get('level', '').upper() == 'ERROR':
                message = entry.get('message', '')
                
                # Try to find matching error analysis
                for key, error in error_map.items():
                    if error.get('error_message', '') in message:
                        entry['error_analysis'] = error
                        break 