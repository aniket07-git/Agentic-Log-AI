"""
Analyze log files using OpenAI to identify errors and suggest fixes.
"""

import re
import sys
from typing import List, Dict, Any, Optional, Tuple
import os
import hashlib
import concurrent.futures
from collections import defaultdict

from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


class ErrorAnalysis(BaseModel):
    """Error analysis model with explanation and fixes."""
    error_type: str = Field(description="The type of error detected")
    error_message: str = Field(description="The error message extracted from the log")
    explanation: str = Field(description="A detailed explanation of what the error means and why it occurred")
    potential_fixes: List[str] = Field(description="List of potential fixes for the error")
    code_fix: Optional[str] = Field(description="Example code snippet to fix the issue, if applicable")
    severity: str = Field(description="The severity of the error: critical, high, medium, or low")
    error_hash: Optional[str] = Field(default=None, description="A hash to identify similar errors")


class LogAnalyzer:
    """Analyze log files to identify and explain errors."""
    
    def __init__(self, openai_api_key: Optional[str] = None, model: str = "gpt-3.5-turbo", max_workers: int = 3):
        """
        Initialize the log analyzer.
        
        Args:
            openai_api_key: OpenAI API key (will default to environment variable OPENAI_API_KEY if not provided)
            model: OpenAI model to use for analysis
            max_workers: Maximum number of parallel workers for processing multiple log files
        """
        self.api_key_set = True
        if openai_api_key is not None:
            os.environ["OPENAI_API_KEY"] = openai_api_key
        elif "OPENAI_API_KEY" not in os.environ:
            print("WARNING: OPENAI_API_KEY environment variable not set")
            print("You must provide an API key when making analysis requests")
            self.api_key_set = False
        
        self.max_workers = max_workers
        
        # Only initialize LLM components if we have an API key
        if self.api_key_set:
            self.model = ChatOpenAI(model=model, temperature=0)
            self.parser = PydanticOutputParser(pydantic_object=ErrorAnalysis)
            
            # Create the prompt template
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an expert log analyzer. Your task is to analyze error logs, explain the errors, and suggest fixes. "
                        "Provide a detailed explanation of what the error means and potential fixes. "
                        "If possible, provide exact code fixes that would resolve the issue. "
                        "Also determine the severity of the error (critical, high, medium, or low) based on its impact. "
                        "Critical errors are those that cause application crashes or data loss. "
                        "High severity errors significantly impair functionality but don't crash the application. "
                        "Medium severity errors cause partial functionality loss or degraded performance. "
                        "Low severity errors are minor issues like formatting problems or non-essential features. "
                        "Output your analysis in a structured format."),
                ("user", "Analyze the following log entry and provide an explanation and potential fixes:\n\n{log_content}")
            ])
            
            # Create the chain
            self.chain = self.prompt | self.model | self.parser
        else:
            self.model = None
            self.parser = None
            self.prompt = None
            self.chain = None
        
        # Cache to store already analyzed errors to avoid duplicate analysis
        self.analysis_cache = {}
    
    def extract_error_logs(self, log_content: str) -> List[str]:
        """
        Extract error logs from log content.
        
        Args:
            log_content: Content of the log file
            
        Returns:
            List of error log entries
        """
        # This is a simple pattern that looks for lines with 'error', 'exception', 'fail', etc.
        # In a real application, you might want to use more sophisticated patterns based on your specific log format
        error_patterns = [
            r'(?i)error[:\s].*',
            r'(?i)exception[:\s].*',
            r'(?i)fail(ed|ure)?[:\s].*',
            r'(?i)critical[:\s].*',
            r'(?i)stack\s?trace[:\s].*',
            r'Traceback \(most recent call last\):.*',
        ]
        
        # Combine all patterns into one
        combined_pattern = '|'.join(f'({pattern})' for pattern in error_patterns)
        regex = re.compile(combined_pattern, re.DOTALL | re.MULTILINE)
        
        # Find all matches in the log content
        error_logs = []
        for match in regex.finditer(log_content):
            # Extract the error message and some context
            start = max(0, match.start() - 200)  # Get some context before the error
            end = min(len(log_content), match.end() + 500)  # Get some context after the error
            error_logs.append(log_content[start:end])
            
        return error_logs
    
    def generate_error_hash(self, error_log: str) -> str:
        """
        Generate a hash for an error log to identify similar errors.
        
        Args:
            error_log: The error log content
            
        Returns:
            A hash string that can be used to identify similar errors
        """
        # Extract the main error message (usually the last line of a traceback)
        lines = error_log.strip().split('\n')
        error_msg = lines[-1] if lines else error_log
        
        # Remove variable parts like memory addresses, line numbers, timestamps
        # This helps to group similar errors together
        clean_error = re.sub(r'0x[0-9a-f]+', 'MEMORY_ADDR', error_msg)
        clean_error = re.sub(r'line \d+', 'LINE_NUM', clean_error)
        clean_error = re.sub(r'\d{2}:\d{2}:\d{2}', 'TIMESTAMP', clean_error)
        clean_error = re.sub(r'\d{4}-\d{2}-\d{2}', 'DATE', clean_error)
        
        # Generate a hash for the cleaned error message
        return hashlib.md5(clean_error.encode()).hexdigest()
    
    def _analyze_single_error(self, error_log: str) -> Dict[str, Any]:
        """
        Analyze a single error log entry.
        
        Args:
            error_log: The error log content
            
        Returns:
            Analysis result dictionary
        """
        # Check if API key is set
        if not self.api_key_set:
            return {
                "error_type": "Configuration Error",
                "error_message": "OpenAI API key not set",
                "explanation": "The log analyzer requires an OpenAI API key to function. Please provide an API key.",
                "potential_fixes": ["Set the OPENAI_API_KEY environment variable", "Provide an API key parameter when calling the API"],
                "code_fix": None,
                "severity": "critical",
                "error_hash": "no_api_key"
            }
            
        # Generate a hash for cache lookup and error grouping
        error_hash = self.generate_error_hash(error_log)
        
        # Check if we've already analyzed this type of error
        if error_hash in self.analysis_cache:
            analysis = self.analysis_cache[error_hash].copy()
            analysis['error_hash'] = error_hash
            return analysis
        
        # Analyze new error
        try:
            # Invoke the LLM chain
            analysis = self.chain.invoke({"log_content": error_log})
            result = analysis.model_dump()
            
            # Add the error hash
            result['error_hash'] = error_hash
            
            # Cache the result
            self.analysis_cache[error_hash] = result
            
            return result
        except Exception as e:
            print(f"Error analyzing log entry: {e}")
            return {
                "error_type": "Analysis Error",
                "error_message": f"Failed to analyze: {str(e)}",
                "explanation": "The log analyzer encountered an error while processing this log entry.",
                "potential_fixes": ["Check the format of the log entry", "Try again with a different model"],
                "code_fix": None,
                "severity": "medium",
                "error_hash": error_hash
            }
    
    def analyze_log(self, log_file: str) -> List[Dict[str, Any]]:
        """
        Analyze a log file and return a list of error analyses.
        
        Args:
            log_file: Path to the log file
            
        Returns:
            List of error analyses
        """
        print(f"Analyzing log file: {log_file}")
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
        except Exception as e:
            print(f"Error reading log file {log_file}: {e}")
            return []
            
        error_logs = self.extract_error_logs(log_content)
        if not error_logs:
            print(f"No errors found in log file: {log_file}")
            return []
            
        analyses = []
        for i, error_log in enumerate(error_logs):
            print(f"Analyzing error {i+1}/{len(error_logs)} from {log_file}...")
            analysis = self._analyze_single_error(error_log)
            analyses.append(analysis)
                
        return analyses
    
    def analyze_multiple_logs(self, log_files: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Analyze multiple log files in parallel.
        
        Args:
            log_files: List of paths to log files
            
        Returns:
            Dictionary mapping file paths to their analysis results
        """
        print(f"Analyzing {len(log_files)} log files in parallel with {self.max_workers} workers")
        
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(self.analyze_log, file): file for file in log_files}
            for future in concurrent.futures.as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    analyses = future.result()
                    results[file] = analyses
                except Exception as e:
                    print(f"Error analyzing file {file}: {e}")
                    results[file] = []
                    
        return results
    
    def group_similar_errors(self, analyses: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group similar errors by their hash.
        
        Args:
            analyses: List of error analyses
            
        Returns:
            Dictionary mapping error hashes to lists of similar errors
        """
        grouped_errors = defaultdict(list)
        
        for analysis in analyses:
            error_hash = analysis.get('error_hash')
            if error_hash:
                grouped_errors[error_hash].append(analysis)
            
        return dict(grouped_errors)
    
    def get_error_statistics(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get statistics about the analyzed errors.
        
        Args:
            analyses: List of error analyses
            
        Returns:
            Dictionary with error statistics
        """
        if not analyses:
            return {
                "total_errors": 0,
                "severity_counts": {},
                "error_type_counts": {},
                "unique_error_count": 0
            }
            
        # Count errors by severity
        severity_counts = defaultdict(int)
        for analysis in analyses:
            severity = analysis.get('severity', 'unknown')
            severity_counts[severity] += 1
            
        # Count errors by type
        error_type_counts = defaultdict(int)
        for analysis in analyses:
            error_type = analysis.get('error_type', 'unknown')
            error_type_counts[error_type] += 1
            
        # Count unique errors by hash
        unique_errors = set()
        for analysis in analyses:
            error_hash = analysis.get('error_hash')
            if error_hash:
                unique_errors.add(error_hash)
                
        return {
            "total_errors": len(analyses),
            "severity_counts": dict(severity_counts),
            "error_type_counts": dict(error_type_counts),
            "unique_error_count": len(unique_errors)
        }