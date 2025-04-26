import os
import re
import glob
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict
import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from datetime import datetime

load_dotenv()

console = Console()

class LogAnalyzer:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.console = Console()
        self.file_cache = {}  # Cache for file contents
        self.error_patterns = {
            'connection_error': r'connection.*(failed|timeout|refused)',
            'authentication_error': r'authentication.*(failed|error)',
            'permission_error': r'permission.*(denied|error)',
            'resource_error': r'resource.*(not found|unavailable)',
            'validation_error': r'validation.*(failed|error)'
        }
        
        self.resolution_suggestions = {
            'connection_error': [
                "Check network connectivity",
                "Verify service endpoints",
                "Review firewall settings"
            ],
            'authentication_error': [
                "Verify credentials",
                "Check token expiration",
                "Review access permissions"
            ],
            'permission_error': [
                "Check user permissions",
                "Review access control lists",
                "Verify service account roles"
            ],
            'resource_error': [
                "Check resource availability",
                "Verify resource configuration",
                "Review quota limits"
            ],
            'validation_error': [
                "Review input data format",
                "Check data validation rules",
                "Verify required fields"
            ]
        }

    def find_log_files(self, directory: str = '.', extensions: List[str] = ['.log', '.txt'], max_depth: int = 4) -> List[str]:
        """
        Recursively search for log files with specified extensions
        
        Args:
            directory: Starting directory for search
            extensions: File extensions to consider as log files
            max_depth: Maximum recursion depth
            
        Returns:
            List of log file paths found
        """
        log_files = []
        
        def _search_dir(current_dir, current_depth):
            if current_depth > max_depth:
                return
                
            try:
                for item in os.listdir(current_dir):
                    item_path = os.path.join(current_dir, item)
                    
                    # Check if it's a file with log extension
                    if os.path.isfile(item_path):
                        _, ext = os.path.splitext(item_path)
                        if ext.lower() in extensions:
                            if self._is_likely_log_file(item_path):
                                log_files.append(item_path)
                    
                    # Recurse into directories
                    elif os.path.isdir(item_path):
                        _search_dir(item_path, current_depth + 1)
            except Exception as e:
                console.print(f"[yellow]Error accessing {current_dir}: {e}[/yellow]")
        
        _search_dir(directory, 1)
        return log_files

    def _is_likely_log_file(self, file_path: str, sample_lines: int = 10) -> bool:
        """
        Check if a file is likely a log file by examining its content
        
        Args:
            file_path: Path to the file
            sample_lines: Number of lines to check
            
        Returns:
            Boolean indicating if the file is likely a log file
        """
        try:
            if os.path.getsize(file_path) > 10 * 1024 * 1024:  # 10MB limit
                with open(file_path, 'r') as f:
                    sample = ''.join([f.readline() for _ in range(sample_lines)])
            else:
                with open(file_path, 'r') as f:
                    sample = f.read(4096)  # Read first 4KB
                    
            log_patterns = [
                r'Traceback \(most recent call last\):',
                r'\d{4}-\d{2}-\d{2}',
                r'\d{2}:\d{2}:\d{2}',
                r'(ERROR|WARNING|INFO|DEBUG|CRITICAL)',
                r'Exception|Error:',
                r'^\[\w+\]'
            ]
            
            for pattern in log_patterns:
                if re.search(pattern, sample):
                    return True
                    
            return False
        except Exception:
            return False

    def extract_errors(self, log_file: str) -> List[Dict]:
        """Extract all errors from log file."""
        errors = []
        try:
            with open(log_file, 'r') as f:
                content = f.read()
                
            # Look for Python tracebacks
            traceback_pattern = r'Traceback \(most recent call last\):\n(.*?)(?=\n\S|\Z)'
            for match in re.finditer(traceback_pattern, content, re.DOTALL):
                traceback = match.group(0)
                error_line = match.group(1).strip().split('\n')[-1]
                
                # Extract error type and message
                error_match = re.match(r'(\w+Error|\w+Exception):\s*(.*)', error_line)
                if error_match:
                    error_type = error_match.group(1)
                    error_message = error_match.group(2)
                    
                    # Try to extract file and line number
                    file_match = re.search(r'File "([^"]+)", line (\d+)', traceback)
                    if file_match:
                        file_path = file_match.group(1)
                        line_number = file_match.group(2)
                    else:
                        file_path = "Unknown"
                        line_number = "Unknown"
                        
                    errors.append({
                        'error_type': error_type,
                        'error_message': error_message,
                        'file_path': file_path,
                        'line_number': line_number,
                        'full_traceback': traceback
                    })
                    
            return errors
        except Exception as e:
            console.print(f"[red]Error extracting errors from {log_file}: {str(e)}[/red]")
            return []

    def find_file(self, file_path: str) -> Optional[str]:
        """Find the actual file path from a relative path."""
        if os.path.exists(file_path):
            return file_path
            
        # Try to find the file in the current directory
        base_name = os.path.basename(file_path)
        for root, _, files in os.walk('.'):
            if base_name in files:
                return os.path.join(root, base_name)
                
        return None

    def get_file_content(self, file_path: str) -> Optional[str]:
        """Get file content with caching."""
        if file_path in self.file_cache:
            return self.file_cache[file_path]
            
        actual_path = self.find_file(file_path)
        if not actual_path:
            return None
            
        try:
            with open(actual_path, 'r') as f:
                content = f.read()
                self.file_cache[file_path] = content
                return content
        except Exception:
            return None

    def get_relevant_code(self, file_path: str, line_number: int, context_lines: int = 5) -> Dict:
        """Get relevant code context around a specific line."""
        content = self.get_file_content(file_path)
        if not content:
            return {'error': f"Could not read file: {file_path}"}
            
        lines = content.split('\n')
        start_line = max(0, line_number - context_lines - 1)
        end_line = min(len(lines), line_number + context_lines)
        
        return {
            'full_content': content,
            'relevant_lines': '\n'.join(lines[start_line:end_line]),
            'start_line': start_line,
            'end_line': end_line
        }

    def get_fix(self, error: Dict, code_context: Dict) -> str:
        """Get a fix for a specific error."""
        fix_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert software engineer.
            Analyze the error and code context to provide a fix.
            The fix should:
            1. Address the specific error
            2. Maintain code style and conventions
            3. Be minimal and focused
            4. Include comments explaining the fix
            
            Format your response as a complete code block."""),
            ("user", """
            Error Type: {error_type}
            Error Message: {error_message}
            File: {file_path}
            Line: {line_number}
            
            Code Context:
            {code_context}
            
            Please provide a fix:
            """)
        ])
        
        fix_chain = (
            {
                "error_type": lambda x: error.get('error_type', 'Unknown'),
                "error_message": lambda x: error.get('error_message', 'No message'),
                "file_path": lambda x: error.get('file_path', 'Unknown'),
                "line_number": lambda x: error.get('line_number', 'Unknown'),
                "code_context": lambda x: code_context.get('relevant_lines', '')
            }
            | fix_prompt
            | self.llm
            | StrOutputParser()
        )
        
        return fix_chain.invoke({})

    def apply_fix(self, file_path: str, original_content: str, fix: str, start_line: int, end_line: int) -> bool:
        """Apply a fix to a file."""
        try:
            actual_path = self.find_file(file_path)
            if not actual_path:
                return False
                
            lines = original_content.split('\n')
            new_lines = lines[:start_line] + [fix] + lines[end_line:]
            
            with open(actual_path, 'w') as f:
                f.write('\n'.join(new_lines))
                
            self.file_cache[file_path] = '\n'.join(new_lines)
            return True
        except Exception as e:
            console.print(f"[red]Error applying fix: {str(e)}[/red]")
            return False

    def analyze_log_patterns(self, errors: List[Dict], log_content: str) -> Dict:
        """Analyze patterns in the errors to identify common issues."""
        error_by_type = defaultdict(list)
        error_by_file = defaultdict(list)
        
        for error in errors:
            error_type = error.get('error_type', 'Unknown')
            file_path = error.get('file_path', 'Unknown')
            
            error_by_type[error_type].append(error)
            error_by_file[file_path].append(error)
        
        file_contents = {}
        for file_path in error_by_file.keys():
            content = self.get_file_content(file_path)
            if content:
                file_contents[file_path] = content
                
        return {
            'error_by_type': error_by_type,
            'error_by_file': error_by_file,
            'file_contents': file_contents,
            'full_log': log_content
        }

    def get_comprehensive_fix(self, errors: List[Dict], pattern_analysis: Dict) -> Dict:
        """Get comprehensive fixes for patterns of errors with access to full file context."""
        error_summaries = []
        for error_type, error_list in pattern_analysis['error_by_type'].items():
            error_summaries.append(f"Error Type: {error_type} (Count: {len(error_list)})")
            for error in error_list[:3]:
                error_summaries.append(f"- In {error.get('file_path', 'Unknown')} at line {error.get('line_number', 'Unknown')}: {error.get('error_message', 'No message')}")
        
        file_summaries = []
        file_content_samples = []
        for file_path, error_list in pattern_analysis['error_by_file'].items():
            file_summaries.append(f"File: {file_path} (Count: {len(error_list)})")
            for error in error_list[:3]:
                file_summaries.append(f"- {error.get('error_type', 'Unknown')}: {error.get('error_message', 'No message')} at line {error.get('line_number', 'Unknown')}")
            
            if file_path in pattern_analysis['file_contents']:
                file_content = pattern_analysis['file_contents'][file_path]
                file_content_samples.append(f"File: {file_path}\n{file_content[:1500]}...")
        
        comprehensive_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert software engineer specializing in debugging complex applications.
            Analyze the provided error patterns, log file, and source code to provide:
            1. Root cause analysis
            2. Comprehensive solution
            3. Implementation recommendations
            4. Prevention strategies
            
            Be specific and actionable. Format your response with clear sections."""),
            ("user", """
            Error Summary:
            {error_type_summary}
            
            File Summary:
            {file_summary}
            
            File Content Samples:
            {file_content_samples}
            
            Raw Log Sample:
            {raw_log}
            
            Please provide a comprehensive analysis:
            """)
        ])
        
        comprehensive_chain = (
            {
                "error_type_summary": lambda x: "\n".join(error_summaries),
                "file_summary": lambda x: "\n".join(file_summaries),
                "file_content_samples": lambda x: "\n\n".join(file_content_samples),
                "raw_log": lambda x: pattern_analysis['full_log'][:2000]
            }
            | comprehensive_prompt
            | self.llm
            | StrOutputParser()
        )
        
        return {
            'analysis': comprehensive_chain.invoke({})
        }

    def get_file_recommendations(self, error_analysis: Dict) -> Dict[str, str]:
        """Get file-specific recommendations based on comprehensive analysis."""
        file_fixes = {}
        
        for file_path, errors in error_analysis['pattern_analysis']['error_by_file'].items():
            if len(errors) >= 1:
                file_content = self.get_file_content(file_path)
                if not file_content:
                    continue
                    
                try:
                    file_prompt = ChatPromptTemplate.from_messages([
                        ("system", """You are an expert software engineer.
                        Based on the multiple errors in this file, provide a comprehensive fix that addresses all issues.
                        The fix should:
                        1. Address all identified errors
                        2. Maintain code style and conventions
                        3. Include comments explaining the changes
                        4. Be minimal and focused
                        
                        Format your response as a complete code block."""),
                        ("user", """
                        File: {file_path}
                        
                        Current Content:
                        {file_content}
                        
                        Error Analysis:
                        {error_analysis}
                        
                        Please provide a comprehensive fix:
                        """)
                    ])
                    
                    file_chain = (
                        {
                            "file_path": lambda x: file_path,
                            "file_content": lambda x: file_content,
                            "error_analysis": lambda x: error_analysis['analysis']
                        }
                        | file_prompt
                        | self.llm
                        | StrOutputParser()
                    )
                    
                    file_fixes[file_path] = file_chain.invoke({})
                except Exception as e:
                    console.print(f"[red]Error generating fix for {file_path}: {str(e)}[/red]")
        
        return file_fixes

    def basic_log_review(self, log_file: str) -> bool:
        """Perform basic log review with error analysis and possible causes."""
        try:
            with open(log_file, 'r') as f:
                log_content = f.read()
                
            errors = self.extract_errors(log_file)
            
            if not errors:
                console.print(f"[yellow]No errors found in the log file: {log_file}[/yellow]")
                return False

            console.print(f"\n[bold]Found {len(errors)} errors in {log_file}.[/bold]")
            
            # Error type summary
            error_summary = defaultdict(int)
            for error in errors:
                error_type = error.get('error_type', 'Unknown')
                error_summary[error_type] += 1
            
            console.print("\n[bold]Error Type Summary:[/bold]")
            table = Table(title="Error Types")
            table.add_column("Type", style="cyan")
            table.add_column("Count", style="magenta")
            for error_type, count in error_summary.items():
                table.add_row(error_type, str(count))
            console.print(table)
            
            # Analyze each error type
            console.print("\n[bold]Error Analysis:[/bold]")
            for error_type, count in sorted(error_summary.items(), key=lambda x: x[1], reverse=True):
                # Get analysis for this error type
                analysis_prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are an expert software engineer analyzing error logs. For the given error type, provide:
                    1. What this error typically means
                    2. Common causes for this error
                    3. General recommendations to fix it
                    
                    Be concise but helpful. Don't reference specific files since we only have log data.
                    Format your response with clear bullet points."""),
                    ("user", """
                    Error Type: {error_type}
                    Sample Error Message: {sample_message}
                    Sample Traceback: {sample_traceback}
                    
                    Please analyze this error:
                    """)
                ])
                
                # Find a sample error of this type
                sample_error = next((e for e in errors if e.get('error_type') == error_type), None)
                custom_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
                analysis_chain = (
                    {
                        "error_type": lambda x: error_type,
                        "sample_message": lambda x: sample_error.get('error_message', 'No message') if sample_error else 'No message',
                        "sample_traceback": lambda x: sample_error.get('full_traceback', 'No traceback')[:500] if sample_error else 'No traceback'
                    }
                    | analysis_prompt
                    | custom_llm
                    | StrOutputParser()
                )
                
                analysis = analysis_chain.invoke({})
                
                console.print(Panel.fit(
                    f"[bold]{error_type}[/bold] (occurred {count} times)\n{analysis}",
                    border_style="yellow"
                ))
            
            # Show sample error details with analysis
            console.print("\n[bold]Sample Error Details with Analysis:[/bold]")
            for i, error in enumerate(errors[:3], 1):  # Show first 3 errors with detailed analysis
                console.print(f"\n[i]{i}. [red]{error.get('error_type', 'Unknown')}[/red][/i]")
                console.print(f"   File: {error.get('file_path', 'Unknown')}")
                console.print(f"   Line: {error.get('line_number', 'Unknown')}")
                console.print(f"   Message: {error.get('error_message', 'No message')}")
                
                # Get detailed analysis for this specific error
                detailed_prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are debugging an application. Analyze this specific error and provide:
                    1. What likely caused this specific error
                    2. Possible solutions based on the traceback
                    3. Recommended troubleshooting steps
                    
                    Be specific but don't reference code you can't see.
                    Format with clear sections."""),
                    ("user", """
                    Error Type: {error_type}
                    File: {file_path}
                    Line: {line_number}
                    Message: {error_message}
                    Traceback:
                    {traceback}
                    
                    Detailed analysis:
                    """)
                ])
                
                detailed_chain = (
                    {
                        "error_type": lambda x: error.get('error_type', 'Unknown'),
                        "file_path": lambda x: error.get('file_path', 'Unknown'),
                        "line_number": lambda x: error.get('line_number', 'Unknown'),
                        "error_message": lambda x: error.get('error_message', 'No message'),
                        "traceback": lambda x: error.get('full_traceback', 'No traceback')[:1000]
                    }
                    | detailed_prompt
                    | self.llm
                    | StrOutputParser()
                )
                
                detailed_analysis = detailed_chain.invoke({})
                
                console.print(Panel.fit(
                    detailed_analysis,
                    border_style="blue"
                ))
            
            # General recommendations for all errors
            if len(errors) > 0:
                console.print("\n[bold]General Recommendations:[/bold]")
                rec_prompt = ChatPromptTemplate.from_messages([
                    ("system", """Based on the collection of errors found, provide:
                    1. Common patterns you notice
                    2. Recommended next steps for debugging
                    3. Potential system-wide improvements
                    
                    Focus on actionable advice that doesn't require source code access."""),
                    ("user", """
                    Errors Found:
                    {error_summary}
                    
                    Sample Errors:
                    {sample_errors}
                    
                    Recommendations:
                    """)
                ])
                
                sample_errors = "\n".join(
                    f"{e.get('error_type')}: {e.get('error_message')}" 
                    for e in errors[:5]  # Use first 5 errors as sample
                )
                
                rec_chain = (
                    {
                        "error_summary": lambda x: "\n".join(f"{k}: {v} occurrences" for k,v in error_summary.items()),
                        "sample_errors": lambda x: sample_errors
                    }
                    | rec_prompt
                    | self.llm
                    | StrOutputParser()
                )
                
                recommendations = rec_chain.invoke({})
                
                console.print(Panel.fit(
                    recommendations,
                    title="Overall Recommendations",
                    border_style="green"
                ))
            
            return True
            
        except Exception as e:
            console.print(f"[red]Error processing {log_file}: {str(e)}[/red]")
            import traceback
            console.print(traceback.format_exc())
            return False

    def in_depth_review(self, log_file: str) -> bool:
        """Perform in-depth review with code fixes."""
        console.print("[cyan]Performing in-depth analysis with code context...[/cyan]")
        
        try:
            with open(log_file, 'r') as f:
                log_content = f.read()
                
            errors = self.extract_errors(log_file)
            
            if not errors:
                console.print(f"[yellow]No errors found in the log file: {log_file}[/yellow]")
                return False

            pattern_analysis = self.analyze_log_patterns(errors, log_content)
            
            console.print("\n[bold]Error Distribution:[/bold]")
            table = Table(title="Errors by Type")
            table.add_column("Error Type", style="cyan")
            table.add_column("Count", style="magenta")
            
            for error_type, error_list in pattern_analysis['error_by_type'].items():
                table.add_row(error_type, str(len(error_list)))
            console.print(table)
            
            console.print("\n[cyan]Generating comprehensive analysis with full file context...[/cyan]")
            comprehensive_analysis = self.get_comprehensive_fix(errors, pattern_analysis)
            
            console.print(Panel.fit(
                comprehensive_analysis['analysis'],
                title="Comprehensive Analysis",
                border_style="green"
            ))
            
            console.print("\n[cyan]Generating file-specific recommendations with full context...[/cyan]")
            file_fixes = self.get_file_recommendations(comprehensive_analysis)
            
            for file_path, fix in file_fixes.items():
                console.print(f"\n[bold]Recommended fixes for {file_path}:[/bold]")
                console.print(Panel.fit(
                    f"Full file fix generated. Length: {len(fix)} characters",
                    title=f"Fix for {os.path.basename(file_path)}",
                    border_style="yellow"
                ))
                
                if Confirm.ask(f"\nView diff for {file_path}?"):
                    original_content = self.get_file_content(file_path)
                    if original_content:
                        from difflib import unified_diff
                        diff = unified_diff(
                            original_content.splitlines(keepends=True),
                            fix.splitlines(keepends=True),
                            fromfile=f"a/{os.path.basename(file_path)}",
                            tofile=f"b/{os.path.basename(file_path)}"
                        )
                        console.print("".join(diff))
                
                if Confirm.ask(f"\nApply comprehensive fix to {file_path}?"):
                    try:
                        actual_path = self.find_file(file_path)
                        if actual_path:
                            with open(actual_path, 'w') as f:
                                f.write(fix)
                            console.print(f"[green]Comprehensive fix applied to {file_path}![/green]")
                            self.file_cache[file_path] = fix
                    except Exception as e:
                        console.print(f"[red]Error applying fix: {str(e)}[/red]")
            
            return True
            
        except Exception as e:
            console.print(f"[red]Error processing {log_file}: {str(e)}[/red]")
            import traceback
            console.print(traceback.format_exc())
            return False

    def analyze_logs(self, logs: List[Dict]) -> Dict:
        """Analyze logs and provide insights."""
        analysis = {
            'error_count': 0,
            'warning_count': 0,
            'error_types': defaultdict(int),
            'error_trends': [],
            'resolutions': []
        }
        
        for log in logs:
            if 'level' in log and log['level'].lower() == 'error':
                analysis['error_count'] += 1
                error_type = self._classify_error(log.get('message', ''))
                if error_type:
                    analysis['error_types'][error_type] += 1
                    analysis['resolutions'].extend(
                        self.resolution_suggestions.get(error_type, [])
                    )
            elif 'level' in log and log['level'].lower() == 'warning':
                analysis['warning_count'] += 1
        
        return analysis

    def _classify_error(self, message: str) -> Optional[str]:
        """Classify error message into known error types."""
        for error_type, pattern in self.error_patterns.items():
            if re.search(pattern, message.lower()):
                return error_type
        return None

    def get_error_trends(self, logs: List[Dict], time_window: str = '1h') -> List[Dict]:
        """Analyze error trends over time."""
        trends = []
        time_format = '%Y-%m-%d %H:%M:%S'
        
        # Group logs by time window
        time_groups = defaultdict(list)
        for log in logs:
            if 'timestamp' in log:
                timestamp = datetime.strptime(log['timestamp'], time_format)
                time_key = timestamp.strftime('%Y-%m-%d %H:00')
                time_groups[time_key].append(log)
        
        # Calculate trends
        for time_key, group_logs in time_groups.items():
            error_count = sum(1 for log in group_logs if log.get('level', '').lower() == 'error')
            warning_count = sum(1 for log in group_logs if log.get('level', '').lower() == 'warning')
            
            trends.append({
                'timestamp': time_key,
                'error_count': error_count,
                'warning_count': warning_count
            })
        
        return sorted(trends, key=lambda x: x['timestamp'])

    def get_resolution_suggestions(self, error_type: str) -> List[str]:
        """Get resolution suggestions for a specific error type."""
        return self.resolution_suggestions.get(error_type, [])

@click.command()
@click.option('--log-file', '-f', type=click.Path(exists=True), help='Specific log file to analyze')
@click.option('--directory', '-d', type=click.Path(exists=True), default='.', help='Directory to search for log files')
@click.option('--recursive', '-r', is_flag=True, help='Search recursively for log files')
@click.option('--max-depth', type=int, default=4, help='Maximum depth for recursive search')
@click.option('--extensions', '-e', multiple=True, default=['.log', '.txt'], help='Log file extensions to search for')
@click.option('--grep', '-g', help='Filter log files containing specific pattern (uses grep-like functionality)')
def main(log_file, directory, recursive, max_depth, extensions, grep):
    """Analyze log files and provide AI-powered solutions."""
    analyzer = LogAnalyzer()
    
    console.print(Panel.fit(
        "Smart Log Analyzer",
        border_style="blue"
    ))
    
    log_files = []
    
    if log_file:
        log_files = [log_file]
    elif recursive:
        console.print(f"[cyan]Searching for log files in {directory} (recursive, max depth: {max_depth})...[/cyan]")
        log_files = analyzer.find_log_files(directory, extensions, max_depth)
    else:
        console.print(f"[cyan]Searching for log files in {directory} (non-recursive)...[/cyan]")
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isfile(item_path):
                    _, ext = os.path.splitext(item_path)
                    if ext.lower() in extensions and analyzer._is_likely_log_file(item_path):
                        log_files.append(item_path)
        except Exception as e:
            console.print(f"[red]Error accessing directory {directory}: {e}[/red]")
    
    if grep and log_files:
        filtered_files = []
        console.print(f"[cyan]Filtering log files containing pattern: {grep}[/cyan]")
        
        for file_path in log_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    if re.search(grep, content):
                        filtered_files.append(file_path)
            except Exception:
                pass
                
        log_files = filtered_files
    
    if not log_files:
        console.print("[yellow]No log files found.[/yellow]")
        return
    
    console.print(f"[green]Found {len(log_files)} log file(s).[/green]")
    
    table = Table(title="Found Log Files")
    table.add_column("Index", style="cyan")
    table.add_column("Log File", style="magenta")
    table.add_column("Size", style="blue")
    
    for i, file_path in enumerate(log_files, 1):
        size = os.path.getsize(file_path)
        size_str = f"{size / 1024:.2f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.2f} MB"
        table.add_row(str(i), file_path, size_str)
    
    console.print(table)
    
    # Ask user to choose review mode
    review_mode = Prompt.ask(
        "\nSelect review mode",
        choices=[
            "1. Basic log review (fast, log-only)",
            "2. In-depth review with code fixes (slower, analyzes source files)"
        ],
        default="1"
    )
    
    if review_mode.startswith("1"):
        mode = "basic"
    else:
        mode = "in-depth"
    
    choices = [
        "Process all log files",
        "Select specific log file(s)",
        "Exit"
    ]
    
    choice = Prompt.ask(
        "\nWhat would you like to do?",
        choices=[str(i) for i in range(1, len(choices) + 1)],
        default="1"
    )
    
    if choice == "1":
        for log_file in log_files:
            if mode == "basic":
                analyzer.basic_log_review(log_file)
            else:
                analyzer.in_depth_review(log_file)
            
            if log_file != log_files[-1]:
                if not Confirm.ask("\nContinue to next log file?"):
                    break
    elif choice == "2":
        indices_str = Prompt.ask(
            "\nEnter the indices of log files to process (comma-separated)",
            default="1"
        )
        
        try:
            indices = [int(idx.strip()) for idx in indices_str.split(",")]
            selected_files = [log_files[idx - 1] for idx in indices if 1 <= idx <= len(log_files)]
            
            if not selected_files:
                console.print("[yellow]No valid log files selected.[/yellow]")
                return
                
            for log_file in selected_files:
                if mode == "basic":
                    analyzer.basic_log_review(log_file)
                else:
                    analyzer.in_depth_review(log_file)
                
                if log_file != selected_files[-1]:
                    if not Confirm.ask("\nContinue to next log file?"):
                        break
        except Exception as e:
            console.print(f"[red]Error selecting log files: {e}[/red]")
    else:
        console.print("[cyan]Exiting Smart Log Analyzer.[/cyan]")
        return

if __name__ == '__main__':
    main()