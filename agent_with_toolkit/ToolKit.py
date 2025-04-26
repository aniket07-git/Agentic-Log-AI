import os
import re
import json
import time  # Add missing import for time functions
from typing import List, Dict, Any, Optional, Set, Union
from pydantic import BaseModel, Field
from langchain_community.chat_models import ChatOpenAI
from langchain.agents import Tool, initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory


class FilePathResolver:
    """Helps find files in the codebase, even with partial paths."""
    
    def __init__(self, root_dir="."):
        self.root_dir = os.path.abspath(root_dir)
        self._file_cache = {}
        self._refresh_file_cache()
    
    def _refresh_file_cache(self):
        """Build a cache of all files in the codebase for quick lookup."""
        self._file_cache = {
            "by_name": {},      # filename -> [full_paths]
            "by_extension": {}, # ext -> [full_paths]
            "all_files": set(), # set of all full paths
        }
        
        for dirpath, _, filenames in os.walk(self.root_dir):
            # Skip common directories to ignore
            if any(part.startswith('.') for part in dirpath.split(os.path.sep)) or \
               any(ignore_dir in dirpath for ignore_dir in ["node_modules", "__pycache__", ".git", "venv", "env"]):
                continue
                
            for filename in filenames:
                full_path = os.path.abspath(os.path.join(dirpath, filename))
                self._file_cache["all_files"].add(full_path)
                
                # Index by name
                self._file_cache["by_name"].setdefault(filename, []).append(full_path)
                
                # Index by extension
                ext = os.path.splitext(filename)[1].lower()
                if ext:  # Skip files with no extension
                    self._file_cache["by_extension"].setdefault(ext, []).append(full_path)
    
    def find_file(self, file_hint: str) -> Optional[str]:
        """
        Find a file in the codebase based on a partial path, name, or pattern.
        Returns the full path if found, None otherwise.
        """
        # Case 1: Exact match (absolute or relative path)
        if os.path.isfile(file_hint):
            return os.path.abspath(file_hint)
        
        # Case 2: Try as a relative path from root_dir
        rel_path = os.path.join(self.root_dir, file_hint)
        if os.path.isfile(rel_path):
            return os.path.abspath(rel_path)
        
        # Case 3: Match by filename only
        filename = os.path.basename(file_hint)
        if filename in self._file_cache["by_name"]:
            matches = self._file_cache["by_name"][filename]
            if len(matches) == 1:
                return matches[0]
            
            # If multiple matches, prefer files that match more of the path
            if len(matches) > 1 and '/' in file_hint:
                path_parts = file_hint.split('/')
                best_match = None
                best_score = 0
                for match in matches:
                    score = sum(1 for part in path_parts if part in match)
                    if score > best_score:
                        best_score = score
                        best_match = match
                if best_match:
                    return best_match
            
            # Default to the first match with a warning
            return matches[0]
        
        # Case 4: Fuzzy match - file contains the hint
        possible_matches = []
        for full_path in self._file_cache["all_files"]:
            if filename.lower() in full_path.lower():
                possible_matches.append(full_path)
        
        if possible_matches:
            # Return the shortest match as it's likely the most specific
            return min(possible_matches, key=len)
            
        # No matches found
        return None
    
    def find_files_by_extension(self, ext: str) -> List[str]:
        """Find all files with the given extension."""
        if not ext.startswith('.'):
            ext = '.' + ext
        return self._file_cache["by_extension"].get(ext.lower(), [])
    
    def find_files_by_content(self, pattern: str, file_ext: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find files containing the given pattern.
        Returns list of {file_path, line_number, line_content} for each match.
        """
        results = []
        
        # Get the list of files to search
        files_to_search = []
        if file_ext:
            files_to_search = self.find_files_by_extension(file_ext)
        else:
            files_to_search = list(self._file_cache["all_files"])
        
        # Limit search to a reasonable number of files
        files_to_search = files_to_search[:100]
        
        try:
            pattern_re = re.compile(pattern)
        except:
            # If regex fails, fall back to simple string search
            pattern_re = None
        
        for file_path in files_to_search:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        if pattern_re:
                            if pattern_re.search(line):
                                results.append({
                                    "file_path": file_path,
                                    "line_number": i,
                                    "line_content": line.strip()
                                })
                        else:
                            if pattern.lower() in line.lower():
                                results.append({
                                    "file_path": file_path,
                                    "line_number": i,
                                    "line_content": line.strip()
                                })
            except:
                # Skip files that can't be read
                continue
                
        return results[:20]  # Limit to 20 results for readability


class FileReadRequest(BaseModel):
    """Request to read a file."""
    path: str = Field(..., description="Path to the file to read")
    start_line: int = Field(1, description="Start line (1-indexed)")
    end_line: int = Field(0, description="End line (0 means read to the end)")


class CodeTools:
    """A collection of tools for working with code."""
    
    def __init__(self, root_dir="."):
        """Initialize the code tools."""
        self.root_dir = os.path.abspath(root_dir)
        self.path_resolver = FilePathResolver(root_dir)
        
    def read_file(self, input_str: str) -> str:
        """
        Read a file, optionally specifying line ranges.
        
        Args:
            input_str: String in the format "file_path:start_line-end_line" 
                       or just "file_path" to read the whole file
            
        Returns:
            The file content, or an error message
        """
        try:
            # Parse input
            path = input_str
            start_line = 1
            end_line = 0
            
            # Handle line range format: file_path:start-end
            if ':' in input_str and '-' in input_str.split(':')[1]:
                path, line_range = input_str.split(':')
                try:
                    start_str, end_str = line_range.split('-')
                    start_line = int(start_str)
                    end_line = int(end_str)
                except:
                    pass
                    
            # Find the actual file
            path = self.path_resolver.find_file(path.strip())
            if not path:
                return f"Error: Could not find the specified file."
            
            # Read the file
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Apply line range
            if end_line <= 0:
                end_line = len(lines)
            
            start_line = max(1, start_line)
            end_line = min(len(lines), end_line)
            
            # Extract content
            content = ''.join(lines[start_line-1:end_line])
            
            return f"File: {os.path.basename(path)} (lines {start_line}-{end_line} of {len(lines)})\n\n{content}"
        except Exception as e:
            return f"Error reading file: {str(e)}"
    
    def find_files(self, query: str) -> str:
        """
        Find files matching a pattern in name or extension.
        
        Args:
            query: Search query, can include file extension (e.g., "*.py") 
                  or part of file name
                  
        Returns:
            List of matching files
        """
        results = []
        
        # Case 1: Specific extension search
        if query.startswith('*.'):
            ext = query[1:]  # Remove *
            files = self.path_resolver.find_files_by_extension(ext)
            rel_files = [os.path.relpath(f, self.root_dir) for f in files[:20]]
            return f"Found {len(files)} files with extension {ext}:\n" + "\n".join(rel_files[:20])
        
        # Case 2: Content search
        elif query.startswith('content:'):
            pattern = query[8:].strip()
            matches = self.path_resolver.find_files_by_content(pattern)
            if not matches:
                return f"No files found containing '{pattern}'"
            
            result = f"Found {len(matches)} matches for '{pattern}':\n"
            for match in matches[:10]:  # Limit to 10 for readability
                file_rel = os.path.relpath(match["file_path"], self.root_dir)
                result += f"\n{file_rel}:{match['line_number']}: {match['line_content']}"
            
            return result
        
        # Case 3: Filename search (partial match)
        else:
            all_files = list(self.path_resolver._file_cache["all_files"])
            matches = [f for f in all_files if query.lower() in os.path.basename(f).lower()]
            rel_matches = [os.path.relpath(f, self.root_dir) for f in matches[:20]]
            
            if not rel_matches:
                return f"No files found matching '{query}'"
            
            return f"Found {len(matches)} files matching '{query}':\n" + "\n".join(rel_matches)
    
    def find_definition(self, term: str) -> str:
        """
        Find definition of a class, function or variable in the codebase.
        
        Args:
            term: The class, function or variable name to find
            
        Returns:
            Matching definitions with file and line information
        """
        # Different patterns for different types of definitions
        patterns = [
            # Python function or class definitions
            f"(def|class)\\s+{re.escape(term)}\\s*[\(:]",
            # Variable assignments
            f"{re.escape(term)}\\s*=",
            # Import aliases
            f"import\\s+\\w+\\s+as\\s+{re.escape(term)}",
            # From imports
            f"from\\s+\\w+\\s+import\\s+\\w+\\s+as\\s+{re.escape(term)}"
        ]
        
        all_results = []
        for pattern in patterns:
            matches = self.path_resolver.find_files_by_content(pattern, file_ext='.py')
            all_results.extend(matches)
        
        if not all_results:
            return f"No definition found for '{term}'"
        
        result = f"Found {len(all_results)} definitions for '{term}':\n"
        for match in all_results[:10]:  # Limit to 10
            file_rel = os.path.relpath(match["file_path"], self.root_dir)
            result += f"\n{file_rel}:{match['line_number']}: {match['line_content'].strip()}"
            
            # Try to add a bit of context
            try:
                with open(match["file_path"], 'r') as f:
                    lines = f.readlines()
                    
                line_idx = match["line_number"] - 1
                context_start = max(0, line_idx - 2)
                context_end = min(len(lines), line_idx + 3)
                
                if context_start < line_idx:
                    result += "\nContext:\n"
                    for i in range(context_start, context_end):
                        if i == line_idx:
                            result += f"➤ {i+1}: {lines[i].rstrip()}\n"
                        else:
                            result += f"  {i+1}: {lines[i].rstrip()}\n"
            except:
                pass
                
        return result
    
    def get_codebase_structure(self, input_str: str = "2") -> str:
        """
        Get the high-level structure of the codebase.
        
        Args:
            input_str: Maximum directory depth to include (as a string or int)
                
        Returns:
            Tree-like structure of the codebase asic art
        """
        try:
            # Convert input to integer with fallback to default
            max_depth = 2
            if input_str:
                try:
                    max_depth = int(input_str)
                except ValueError:
                    pass
        
            result = ["Codebase structure:"]
            
            def add_directory(path, prefix="", depth=0):
                if depth > max_depth:
                    return
                    
                # Skip hidden directories and common directories to ignore
                dirname = os.path.basename(path)
                if dirname.startswith('.') or dirname in ["node_modules", "__pycache__", ".git", "venv", "env"]:
                    return
                
                try:
                    entries = sorted(os.listdir(path))
                    dirs = []
                    files = []
                    
                    for entry in entries:
                        if entry.startswith('.'):
                            continue
                            
                        full_path = os.path.join(path, entry)
                        if os.path.isdir(full_path):
                            dirs.append(entry)
                        else:
                            files.append(entry)
                    
                    # Add files first (limit to 5 per directory)
                    for i, file in enumerate(files):
                        if i >= 5:
                            result.append(f"{prefix}├── ... ({len(files) - 5} more files)")
                            break
                        result.append(f"{prefix}├── {file}")
                    
                    # Then directories
                    for i, dir in enumerate(dirs):
                        is_last = (i == len(dirs) - 1)
                        result.append(f"{prefix}{'└──' if is_last else '├──'} {dir}/")
                        add_directory(
                            os.path.join(path, dir),
                            prefix=prefix + ("    " if is_last else "│   "),
                            depth=depth + 1
                        )
                except Exception as e:
                    result.append(f"{prefix}├── Error reading directory: {str(e)}")
            
            add_directory(self.root_dir)
            return "\n".join(result)
        except Exception as e:
            return f"Error getting codebase structure: {str(e)}"

    def get_codebase_stats(self) -> str:
        """Get statistics about the codebase."""
        stats = {
            "file_counts_by_extension": {},
            "total_files": 0,
            "total_lines": 0,
            "largest_files": []
        }
        
        for dirpath, _, filenames in os.walk(self.root_dir):
            # Skip hidden directories and common directories to ignore
            if any(part.startswith('.') for part in dirpath.split(os.path.sep)) or \
               any(ignore_dir in dirpath for ignore_dir in ["node_modules", "__pycache__", ".git", "venv", "env"]):
                continue
                
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, self.root_dir)
                ext = os.path.splitext(filename)[1].lower()
                
                stats["total_files"] += 1
                stats["file_counts_by_extension"][ext] = stats["file_counts_by_extension"].get(ext, 0) + 1
                
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        line_count = len(lines)
                        stats["total_lines"] += line_count
                        
                        # Track largest files
                        stats["largest_files"].append((rel_path, line_count))
                except:
                    pass
        
        # Get top 5 largest files
        stats["largest_files"] = sorted(stats["largest_files"], key=lambda x: x[1], reverse=True)[:5]
        
        # Format the output
        output = ["Codebase Statistics:"]
        output.append(f"Total files: {stats['total_files']}")
        output.append(f"Total lines of code: {stats['total_lines']}")
        
        output.append("\nFile types:")
        for ext, count in sorted(stats["file_counts_by_extension"].items(), key=lambda x: x[1], reverse=True):
            if ext:
                output.append(f"- {ext}: {count} files")
            else:
                output.append(f"- No extension: {count} files")
        
        output.append("\nLargest files:")
        for i, (file, lines) in enumerate(stats["largest_files"], 1):
            output.append(f"{i}. {file} ({lines} lines)")
            
        return "\n".join(output)
    

# --- Error Analysis Tools ---

class ErrorAnalysisTools:
    """A collection of tools for analyzing errors in code."""
    
    def __init__(self, root_dir="."):
        """Initialize the error analysis tools."""
        self.root_dir = os.path.abspath(root_dir)
        self.code_tools = CodeTools(root_dir)
    
    def analyze_traceback(self, traceback_text: str) -> str:
        """
        Analyze a Python traceback to extract meaningful information.
        
        Args:
            traceback_text: The full traceback text from a log
            
        Returns:
            JSON string with structured analysis of the traceback
        """
        try:
            # Extract the most important parts of the traceback
            lines = traceback_text.strip().split("\n")
            result = {
                "execution_path": [], 
                "root_cause": {},
                "affected_modules": set(),
                "affected_functions": []
            }
            
            for i, line in enumerate(lines):
                if "File " in line and ", line " in line:
                    # Extract file and line info
                    file_info = re.search(r'File "([^"]+)", line (\d+), in (\w+)', line)
                    if file_info:
                        file_path = file_info.group(1)
                        line_number = int(file_info.group(2))
                        function = file_info.group(3)
                        
                        # Get the code line if available (usually the next line)
                        code_line = lines[i+1].strip() if i+1 < len(lines) else ""
                        
                        # Add module info
                        module_name = os.path.basename(file_path).replace('.py', '')
                        result["affected_modules"].add(module_name)
                        result["affected_functions"].append(function)
                        
                        result["execution_path"].append({
                            "file": file_path,
                            "line": line_number,
                            "function": function,
                            "code": code_line
                        })
                
                # Extract the actual error
                if "Error: " in line or ": " in line and i == len(lines) - 1:
                    error_parts = line.split(": ", 1)
                    if len(error_parts) == 2:
                        result["root_cause"] = {
                            "error_type": error_parts[0].strip(),
                            "message": error_parts[1].strip()
                        }
            
            # Convert set to list for JSON serialization
            result["affected_modules"] = list(result["affected_modules"])
            
            return json.dumps(result, indent=2)
        
        except Exception as e:
            return f"Error analyzing traceback: {str(e)}"
    
    def find_similar_errors(self, error_type: str) -> str:
        """
        Find similar errors across the codebase.
        
        Args:
            error_type: Error class name like 'ZeroDivisionError'
            
        Returns:
            JSON string with locations and patterns of similar errors
        """
        try:
            # Search for the error name in code
            code_matches = self.code_tools.path_resolver.find_files_by_content(f"except {error_type}")
            
            # Search for the error in logs
            log_matches = self.code_tools.path_resolver.find_files_by_content(error_type, file_ext=".log")
            
            # Combine results
            result = {
                "error_type": error_type,
                "similar_error_handlers": [
                    {"file": match["file_path"], "line": match["line_number"], "content": match["line_content"]}
                    for match in code_matches
                ],
                "similar_error_occurrences": [
                    {"file": match["file_path"], "line": match["line_number"], "content": match["line_content"]}
                    for match in log_matches
                ]
            }
            
            return json.dumps(result, indent=2)
        
        except Exception as e:
            return f"Error finding similar errors: {str(e)}"
    
    def extract_variable_context(self, input_str: str) -> str:
        """
        Extract context around a variable from the code.
        
        Args:
            input_str: String in format 'filename:line_number:variable_name'
            
        Returns:
            Context around the variable including initialization and usage
        """
        try:
            # Parse input
            parts = input_str.split(':')
            if len(parts) != 3:
                return "Input must be in format 'filename:line_number:variable_name'"
                
            filename = parts[0]
            line_number = int(parts[1])
            variable_name = parts[2]
            
            # Get the content around the specified line
            context_before = self.code_tools.read_file(f"{filename}:{max(1, line_number-5)}-{line_number-1}")
            context_current = self.code_tools.read_file(f"{filename}:{line_number}-{line_number}")
            context_after = self.code_tools.read_file(f"{filename}:{line_number+1}-{line_number+5}")
            
            # Look for variable definitions and uses
            full_context = context_before + context_current + context_after
            
            # Find variable assignments
            assignments = []
            for i, line in enumerate(full_context.split('\n')):
                if variable_name in line and ('=' in line or 'def' in line or 'class' in line or 'import' in line):
                    assignments.append({
                        "relative_line": i+1,
                        "actual_line": line_number-5+i+1,
                        "content": line.strip()
                    })
            
            # Find variable uses
            uses = []
            for i, line in enumerate(full_context.split('\n')):
                if variable_name in line and line.strip() not in [a["content"] for a in assignments]:
                    uses.append({
                        "relative_line": i+1,
                        "actual_line": line_number-5+i+1,
                        "content": line.strip()
                    })
            
            result = {
                "variable": variable_name,
                "file": filename,
                "line": line_number,
                "context_window": f"Lines {max(1, line_number-5)} to {line_number+5}",
                "code_context": full_context,
                "variable_assignments": assignments,
                "variable_uses": uses
            }
            
            return json.dumps(result, indent=2)
        
        except Exception as e:
            return f"Error extracting variable context: {str(e)}"
    
    def get_file_history(self, file_path: str) -> str:
        """
        Get recent changes to a file that might relate to the error.
        In a real implementation, this would use git history.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Recent changes to the file
        """
        try:
            if not os.path.exists(file_path):
                return f"File not found: {file_path}"
            
            # Get file stats
            stats = os.stat(file_path)
            modified_time = stats.st_mtime
            
            # In a real implementation, this would use git log
            # Simulate git history with file stats
            result = {
                "file": file_path,
                "last_modified": modified_time,
                "size_bytes": stats.st_size,
                "last_modified_human": time.ctime(modified_time),
                "note": "In a real implementation, this would show git history"
            }
            
            return json.dumps(result, indent=2)
        
        except Exception as e:
            return f"Error getting file history: {str(e)}"


# --- Log Analysis Functions ---

def find_log_files(directory='.', extensions=['.log', '.txt']):
    """Find all log files in directory and subdirectories"""
    log_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                log_files.append(os.path.join(root, file))
    return log_files


def save_analysis_to_json(analysis: str, output_file: str = "error_analysis.json") -> str:
    """
    Save the error analysis results to a JSON file
    
    Args:
        analysis: String containing the analysis (expected to be valid JSON)
        output_file: Path where to save the JSON file
        
    Returns:
        Message indicating success or failure
    """
    try:
        # Try to parse the analysis as JSON first
        try:
            # If it's already a JSON string, parse it
            json_data = json.loads(analysis)
        except json.JSONDecodeError:
            # If not valid JSON, extract JSON-like patterns
            json_pattern = r'(\{[\s\S]*?\})'
            matches = re.findall(json_pattern, analysis)
            if not matches:
                return "Error: No valid JSON found in the analysis"
            
            # Try to parse each match
            json_objects = []
            for match in matches:
                try:
                    json_obj = json.loads(match)
                    json_objects.append(json_obj)
                except:
                    pass
            
            if not json_objects:
                return "Error: Could not extract any valid JSON objects"
            
            json_data = json_objects if len(json_objects) > 1 else json_objects[0]

            res = {"json_object": json_data}
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2)
        
        return res
    
    except Exception as e:
        return None


# --- Tool Creation Functions ---

def create_log_tools() -> List[Tool]:
    """Create tools for log file operations"""
    tools = [
        Tool(
            name="find_log_files",
            func=find_log_files,
            description="Find all log files (with .log or .txt extensions) in the current directory and subdirectories."
        ),
        Tool(
            name="save_analysis",
            func=save_analysis_to_json,
            description="Save error analysis to a JSON file. Input should be a JSON string with the analysis and optionally an output file path."
        )
    ]
    
    return tools


def create_error_analysis_tools() -> List[Tool]:
    """Create tools for error analysis"""
    error_tools = ErrorAnalysisTools()
    
    tools = [
        Tool(
            name="analyze_traceback",
            func=error_tools.analyze_traceback,
            description="Analyze a Python traceback to identify the root cause and execution path. Input should be the traceback text."
        ),
        Tool(
            name="find_similar_errors",
            func=error_tools.find_similar_errors,
            description="Find similar errors that have occurred elsewhere in the codebase. Input should be an error type like 'ZeroDivisionError'."
        ),
        Tool(
            name="extract_variable_context",
            func=error_tools.extract_variable_context,
            description="Extract context around a variable from the code. Input should be 'filename:line_number:variable_name'."
        ),
        Tool(
            name="get_file_history",
            func=error_tools.get_file_history,
            description="Get recent changes to a file that might relate to the error. Input should be a file path."
        )
    ]
    
    return tools


def create_code_tools() -> List[Tool]:
    """Create code explorer tools for an agent."""
    code_tools = CodeTools()
    
    tools = [
        Tool(
            name="read_file",
            func=code_tools.read_file,
            description=(
                "Read the content of a file. "
                "Accepts path with optional line range: 'file.py' or 'file.py:10-20'. "
                "Will attempt to find the file even with partial paths."
            )
        ),
        Tool(
            name="find_files",
            func=code_tools.find_files,
            description=(
                "Find files in the codebase. Ways to search:\n"
                "1. By extension: '*.py' finds all Python files\n"
                "2. By content: 'content:search_term' finds files containing the term\n"
                "3. By name: any other query finds files with matching names"
            )
        ),
        Tool(
            name="find_definition",
            func=code_tools.find_definition,
            description=(
                "Find where a class, function, or variable is defined in the codebase. "
                "Input should be the name of the symbol, like 'MyClass' or 'process_data'."
            )
        ),
        Tool(
            name="get_codebase_structure",
            func=code_tools.get_codebase_structure,
            description=(
                "Get a high-level structure of the codebase showing main directories and files. "
                "Pass a number to control depth, like '3' for deeper nesting."
                "Give it as a asic art representation."
            )
        ),
        Tool(
            name="get_codebase_stats",
            func=code_tools.get_codebase_stats,
            description=(
                "Get statistics about the codebase, including file counts, "
                "total lines of code, and largest files."
            )
        )
    ]
    
    return tools


def create_enhanced_tools() -> List[Tool]:
    """Create comprehensive set of tools for code and error analysis."""
    code_tools = create_code_tools()
    log_tools = create_log_tools()
    error_tools = create_error_analysis_tools()
    
    # Combine all tools
    all_tools = code_tools + log_tools + error_tools
    
    return all_tools


# --- Agent Creation ---

def create_codebase_agent(model_name="gpt-4o", temperature=0):
    """Create an agent for codebase exploration and analysis"""
    tools = create_code_tools()
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    
    # Setup the agent with a system prompt that explains how to use the tools effectively
    llm = ChatOpenAI(model=model_name, temperature=temperature)
    
    system_prompt = """You are CodeExplorer, an AI assistant specialized in helping users understand codebases.

You have these tools available:
1. read_file: Read code files or specific line ranges
2. find_files: Find files by name, extension, or content
3. find_definition: Find where symbols (classes, functions, variables) are defined
4. get_codebase_structure: Get a high-level view of the codebase organization
5. get_codebase_stats: Get statistics about the codebase

When helping users:
1. First use get_codebase_structure or get_codebase_stats to understand the codebase
2. Use find_files to locate relevant files when needed
3. Use read_file to examine specific files
4. Use find_definition when asked about specific functions or classes

Always be specific and reference actual files and line numbers when explaining code.
"""

    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=True,
        memory=memory,
        agent_kwargs={"system_message": system_prompt}
    )
    
    return agent


def create_error_analysis_agent(model_name="gpt-4o", temperature=0.2):
    """Create an agent for error analysis"""
    tools = create_enhanced_tools()
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    
    # Setup the agent with a system prompt specialized for error analysis
    llm = ChatOpenAI(model=model_name, temperature=temperature)
    
    system_prompt = """You are an expert Python error resolver. Your task is to analyze log files for errors and provide comprehensive solutions.

You have specialized tools for error analysis:
1. read_file: Read the content of a file
2. find_log_files: Find all log files in the codebase
3. analyze_traceback: Parse and understand Python tracebacks
4. find_similar_errors: Identify similar errors across the codebase
5. extract_variable_context: Analyze variable context around errors
6. get_file_history: Check file modification history
7. save_analysis: Save your analysis to a JSON file

When analyzing errors:
1. Locate log files with find_log_files
2. Read error logs with read_file
3. Analyze tracebacks with analyze_traceback
4. Check code context using extract_variable_context
5. Look for similar errors with find_similar_errors
6. Check file history with get_file_history
7. Save your analysis with save_analysis

Provide structured answers with detailed explanations and code fixes.
"""

    from langchain.agents import AgentType
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=True,
        memory=memory,
        agent_kwargs={"system_message": system_prompt}
    )
    
    return agent


# --- Main functions ---

def analyze_logs(query="Find all log files and analyze them in detail for errors"):
    """Run error analysis on log files"""
    agent_executor = create_error_analysis_agent()
    result = agent_executor.invoke({"input": query})
    
    # Save the result automatically with timestamp
    if "output" in result:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"error_analysis_{timestamp}.json"
        save_analysis_to_json(result["output"], filename)
        print(f"Analysis saved to {filename}")
    
    return result


def main():
    """Main entry point for the command line tool"""
    import argparse
    parser = argparse.ArgumentParser(description="CodeBase QA and Error Analysis Tools")
    
    # Add subparsers for different modes
    subparsers = parser.add_subparsers(dest="mode", help="Operation mode")
    
    # Codebase explorer mode
    explorer_parser = subparsers.add_parser("explore", help="Explore codebase")
    
    # Error analysis mode
    error_parser = subparsers.add_parser("analyze", help="Analyze errors in logs")
    error_parser.add_argument("--logs", help="Specify log file or directory", default=".")
    
    args = parser.parse_args()
    
    if args.mode == "analyze":
        print("Starting error analysis...")
        analyze_logs(f"Analyze logs in {args.logs} for errors")
    else:  # Default to explorer
        print("Starting codebase explorer...")
        agent = create_codebase_agent()
        
        while True:
            user_input = input("\n> ")
            if user_input.lower() in ("exit", "quit"):
                break
                
            try:
                response = agent.run(user_input)
                print(response)
            except Exception as e:
                print(f"Error: {str(e)}")


if __name__ == "__main__":
    # Remove duplicate function and use the main function
    main()