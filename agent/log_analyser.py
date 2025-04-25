# import os
# import re
# from pathlib import Path
# from typing import List, Dict, Optional, Set, Tuple
# from collections import defaultdict
# import click
# from rich.console import Console
# from rich.panel import Panel
# from rich.prompt import Confirm
# from rich.table import Table
# from dotenv import load_dotenv
# from langchain.chat_models import ChatOpenAI
# from langchain.prompts import ChatPromptTemplate
# from langchain.schema import StrOutputParser
# from langchain.schema.runnable import RunnablePassthrough

# # Load environment variables
# load_dotenv()

# console = Console()

# class LogAnalyzer:
#     def __init__(self):
#         self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
#         self.console = Console()

#     def extract_errors(self, log_file: str) -> List[Dict]:
#         """Extract all errors from log file."""
#         with open(log_file, 'r') as f:
#             log_content = f.read()
        
#         # Split log content into individual error blocks
#         error_blocks = re.split(r'(?=Traceback \(most recent call last\):)', log_content)
#         error_blocks = [block.strip() for block in error_blocks if block.strip()]
        
#         errors = []
#         for block in error_blocks:
#             # Extract error context for each block
#             error_patterns = {
#                 'file_path': r'File "([^"]+)"',
#                 'line_number': r'line (\d+)',
#                 'error_type': r'([A-Za-z]+Error|Exception):',
#                 'error_message': r'([A-Za-z]+Error|Exception):\s*(.*)',
#                 'full_traceback': block
#             }
            
#             context = {}
#             for key, pattern in error_patterns.items():
#                 if key == 'full_traceback':
#                     context[key] = block
#                 else:
#                     match = re.search(pattern, block)
#                     if match:
#                         if key == 'error_message' and match.group(2):
#                             context[key] = match.group(2).strip()
#                         else:
#                             context[key] = match.group(1)
            
#             if context.get('file_path') and context.get('line_number'):
#                 errors.append(context)
        
#         return errors

#     def find_file(self, file_path: str) -> Optional[str]:
#         """Find file in the project structure."""
#         # First try the exact path
#         if os.path.exists(file_path):
#             return file_path
            
#         # If not found, search in the project directory
#         project_root = os.getcwd()
#         for root, _, files in os.walk(project_root):
#             for file in files:
#                 if file == os.path.basename(file_path):
#                     return os.path.join(root, file)
#         return None

#     def get_relevant_code(self, file_path: str, line_number: int, context_lines: int = 5) -> Dict:
#         """Get relevant code around the error line."""
#         try:
#             with open(file_path, 'r') as f:
#                 lines = f.readlines()
            
#             start = max(0, line_number - context_lines - 1)
#             end = min(len(lines), line_number + context_lines)
            
#             relevant_code = ''.join(lines[start:end])
#             return {
#                 'code': relevant_code,
#                 'start_line': start,
#                 'end_line': end,
#                 'full_content': ''.join(lines)
#             }
#         except Exception as e:
#             return {'error': f"Could not read file: {str(e)}"}

#     def apply_fix(self, file_path: str, original_content: str, fix_content: str, start_line: int, end_line: int) -> bool:
#         """Apply the fix to the specific part of the file."""
#         try:
#             lines = original_content.split('\n')
#             new_lines = lines[:start_line] + fix_content.split('\n') + lines[end_line:]
#             with open(file_path, 'w') as f:
#                 f.write('\n'.join(new_lines))
#             return True
#         except Exception as e:
#             console.print(f"[red]Error applying fix: {str(e)}[/red]")
#             return False

#     def get_fix(self, error_context: Dict, code_context: Dict) -> str:
#         """Get the best fix for the error."""
#         fix_prompt = ChatPromptTemplate.from_messages([
#             ("system", """You are an expert software engineer. 
#             Based on the error and code context, provide the BEST fix for the code.
#             Return ONLY the code that needs to be changed dont add anything else like backticks or words like python just give the code with proper indentation.
#             No explanations, no markdown formatting, just the raw code.
#             Include only the lines that need to be modified.
#             Make sure the code is properly formatted and indented.
#             **NOTE** Please maintain proper indentation.
             
#              Example:
#              *Wrong reponse*:
#              │ ```python                                                                                                            │
# │                 elif operation == 'db_query':                                                                        │
# │                     query = random.choice(["SELECT * FROM users", "SELECT * FROM transactions", "SELECT * FROM       │
# │ orders"])                                                                                                            │
# │                                                                                                                      │
# │                     net_client.request(query)                                                                        │
# │ ```   
             
#              *Correct response*:
#                                                                                                                          │
# │                 elif operation == 'db_query':                                                                        │
# │                     query = random.choice(["SELECT * FROM users", "SELECT * FROM transactions", "SELECT * FROM       │
# │ orders"])                                                                                                            │
# │                                                                                                                      │
# │                     net_client.request(query)                                                                        │
 

#             Choose the most robust and maintainable solution."""),
#             ("user", """
#             Error Context:
#             {error_context}
            
#             Original Code:
#             {code_context}
            
#             Provide the best fix:
#             """)
#         ])

#         fix_chain = (
#             {"error_context": lambda x: str(error_context), "code_context": lambda x: code_context['code']}
#             | fix_prompt
#             | self.llm
#             | StrOutputParser()
#         )

#         return fix_chain.invoke({})

#     def analyze_log_patterns(self, errors: List[Dict]) -> Dict:
#         """Analyze patterns in the errors to identify common issues."""
#         # Group errors by type and file
#         error_by_type = defaultdict(list)
#         error_by_file = defaultdict(list)
        
#         for error in errors:
#             error_type = error.get('error_type', 'Unknown')
#             file_path = error.get('file_path', 'Unknown')
            
#             error_by_type[error_type].append(error)
#             error_by_file[file_path].append(error)
        
#         return {
#             'total_errors': len(errors),
#             'error_by_type': error_by_type,
#             'error_by_file': error_by_file,
#         }

#     def get_comprehensive_fix(self, errors: List[Dict], pattern_analysis: Dict) -> Dict:
#         """Get comprehensive fixes for patterns of errors."""
#         # Prepare context for LLM
#         error_summaries = []
#         for error_type, error_list in pattern_analysis['error_by_type'].items():
#             error_summaries.append(f"Error Type: {error_type} (Count: {len(error_list)})")
#             for error in error_list[:3]:  # Limit to 3 examples per type
#                 error_summaries.append(f"- In {error.get('file_path', 'Unknown')} at line {error.get('line_number', 'Unknown')}: {error.get('error_message', 'No message')}")
        
#         file_summaries = []
#         for file_path, error_list in pattern_analysis['error_by_file'].items():
#             file_summaries.append(f"File: {file_path} (Count: {len(error_list)})")
#             for error in error_list[:3]:  # Limit to 3 examples per file
#                 file_summaries.append(f"- {error.get('error_type', 'Unknown')}: {error.get('error_message', 'No message')} at line {error.get('line_number', 'Unknown')}")
        
#         # Get overall analysis and comprehensive fixes
#         comprehensive_prompt = ChatPromptTemplate.from_messages([
#             ("system", """You are an expert software engineer specializing in debugging complex applications.
#             Analyze the provided error patterns and provide:
#             1. A comprehensive analysis of the main root causes
#             2. A list of recommended fixes grouped by error type or common cause
#             3. Any architectural or systemic improvements that would prevent similar errors
            
#             Be thorough but concise. Focus on identifying underlying patterns rather than individual bugs."""),
#             ("user", """
#             Total Errors: {total_errors}
            
#             Errors By Type:
#             {error_type_summary}
            
#             Errors By File:
#             {file_summary}
            
#             Raw Error Data (Sample):
#             {raw_errors}
            
#             Provide your comprehensive analysis and solution recommendations:
#             """)
#         ])

#         comprehensive_chain = (
#             {
#                 "total_errors": lambda x: pattern_analysis['total_errors'],
#                 "error_type_summary": lambda x: "\n".join(error_summaries),
#                 "file_summary": lambda x: "\n".join(file_summaries),
#                 "raw_errors": lambda x: str(errors[:5])  # Sample of raw errors
#             }
#             | comprehensive_prompt
#             | self.llm
#             | StrOutputParser()
#         )

#         return {
#             'analysis': comprehensive_chain.invoke({}),
#             'pattern_analysis': pattern_analysis
#         }

#     def get_file_recommendations(self, error_analysis: Dict) -> Dict[str, str]:
#         """Generate file-specific fix recommendations."""
#         file_fixes = {}
        
#         for file_path, errors in error_analysis['pattern_analysis']['error_by_file'].items():
#             if len(errors) >= 2:  # Only for files with multiple errors
#                 actual_file = self.find_file(file_path)
#                 if not actual_file:
#                     continue
                    
#                 try:
#                     with open(actual_file, 'r') as f:
#                         file_content = f.read()
                        
#                     # Prepare context for specific file fixes
#                     file_prompt = ChatPromptTemplate.from_messages([
#                         ("system", """You are an expert software engineer.
#                         Based on the multiple errors in this file, provide a comprehensive fix that addresses all issues.
#                         Focus on the most efficient solution that solves the underlying problems.
#                         Return only the code that needs to be changed or added, with proper indentation.
#                         No explanations or markdown formatting, just the raw code with clear comments indicating what each change addresses."""),
#                         ("user", """
#                         File Path: {file_path}
                        
#                         Errors in this file:
#                         {errors}
                        
#                         File Content:
#                         {file_content}
                        
#                         Provide a comprehensive fix for this file:
#                         """)
#                     ])
                    
#                     file_chain = (
#                         {
#                             "file_path": lambda x: file_path,
#                             "errors": lambda x: str(errors),
#                             "file_content": lambda x: file_content
#                         }
#                         | file_prompt
#                         | self.llm
#                         | StrOutputParser()
#                     )
                    
#                     file_fixes[file_path] = file_chain.invoke({})
#                 except Exception as e:
#                     console.print(f"[red]Error generating fix for {file_path}: {str(e)}[/red]")
        
#         return file_fixes


# @click.command()
# @click.argument('log_file', type=click.Path(exists=True))
# @click.option('--comprehensive', is_flag=True, help='Perform comprehensive analysis instead of error-by-error')
# def main(log_file: str, comprehensive: bool = False):
#     """Analyze log files and provide AI-powered solutions."""
#     analyzer = LogAnalyzer()
    
#     console.print(Panel.fit(
#         f"Analyzing log file: {log_file}",
#         title="Smart Log Analyzer",
#         border_style="blue"
#     ))
    
#     try:
#         # Extract all errors from the log file
#         errors = analyzer.extract_errors(log_file)
        
#         if not errors:
#             console.print("[yellow]No errors found in the log file.[/yellow]")
#             return

#         # Show overview of all errors
#         console.print(f"\n[bold]Found {len(errors)} errors.[/bold]")
        
#         if comprehensive or len(errors) > 3:
#             # Perform comprehensive analysis
#             console.print("[cyan]Performing comprehensive analysis of error patterns...[/cyan]")
            
#             # Analyze patterns in errors
#             pattern_analysis = analyzer.analyze_log_patterns(errors)
            
#             # Show error distribution
#             console.print("\n[bold]Error Distribution:[/bold]")
#             table = Table(title="Errors by Type")
#             table.add_column("Error Type", style="cyan")
#             table.add_column("Count", style="magenta")
            
#             for error_type, error_list in pattern_analysis['error_by_type'].items():
#                 table.add_row(error_type, str(len(error_list)))
#             console.print(table)
            
#             # Get comprehensive analysis and fixes
#             console.print("\n[cyan]Generating comprehensive analysis and fixes...[/cyan]")
#             comprehensive_analysis = analyzer.get_comprehensive_fix(errors, pattern_analysis)
            
#             console.print(Panel.fit(
#                 comprehensive_analysis['analysis'],
#                 title="Comprehensive Analysis",
#                 border_style="green"
#             ))
            
#             # Generate file-specific recommendations
#             console.print("\n[cyan]Generating file-specific recommendations...[/cyan]")
#             file_fixes = analyzer.get_file_recommendations(comprehensive_analysis)
            
#             for file_path, fix in file_fixes.items():
#                 console.print(f"\n[bold]Recommended fixes for {file_path}:[/bold]")
#                 console.print(Panel.fit(
#                     fix,
#                     title=f"Fix for {os.path.basename(file_path)}",
#                     border_style="yellow"
#                 ))
                
#                 actual_file = analyzer.find_file(file_path)
#                 if actual_file and Confirm.ask(f"\nApply comprehensive fix to {file_path}?"):
#                     try:
#                         with open(actual_file, 'r') as f:
#                             original_content = f.read()
                            
#                         with open(actual_file, 'w') as f:
#                             f.write(fix)
#                         console.print(f"[green]Comprehensive fix applied to {file_path}![/green]")
#                     except Exception as e:
#                         console.print(f"[red]Error applying fix: {str(e)}[/red]")
#         else:
#             # Show individual errors
#             for i, error in enumerate(errors, 1):
#                 console.print(f"\n{i}. [red]{error.get('error_type', 'Unknown')}[/red] in [blue]{error.get('file_path', 'Unknown')}[/blue] at line {error.get('line_number', 'Unknown')}")
#                 console.print(f"   Message: {error.get('error_message', 'No message')}")

#             # Ask if user wants to proceed with fixes
#             if not Confirm.ask("\nWould you like to see and apply fixes for these errors?"):
#                 return

#             # Process fixes
#             for i, error in enumerate(errors, 1):
#                 console.print(f"\n[bold]Processing error {i} of {len(errors)}[/bold]")
                
#                 file_path = analyzer.find_file(error['file_path'])
#                 if not file_path:
#                     console.print(f"[red]Could not find file: {error['file_path']}[/red]")
#                     continue

#                 code_context = analyzer.get_relevant_code(
#                     file_path,
#                     int(error['line_number'])
#                 )

#                 if 'error' in code_context:
#                     console.print(f"[red]Error: {code_context['error']}[/red]")
#                     continue

#                 # Get and show the fix
#                 fix = analyzer.get_fix(error, code_context)
                
#                 console.print("\n[bold]Proposed Fix:[/bold]")
#                 console.print(Panel.fit(
#                     fix,
#                     title="Fix",
#                     border_style="yellow"
#                 ))

#                 if Confirm.ask("\nWould you like to apply this fix?"):
#                     if analyzer.apply_fix(
#                         file_path,
#                         code_context["full_content"],
#                         fix,
#                         code_context["start_line"],
#                         code_context["end_line"]
#                     ):
#                         console.print("[green]Fix applied successfully![/green]")
#                     else:
#                         console.print("[red]Failed to apply fix.[/red]")
                
#                 if i < len(errors):
#                     if not Confirm.ask("\nContinue to next error?"):
#                         break
        
#     except Exception as e:
#         console.print(f"[red]Error: {str(e)}[/red]")

# if __name__ == '__main__':
#     main()

import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict
import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough

# Load environment variables
load_dotenv()

console = Console()

class LogAnalyzer:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.console = Console()
        self.file_cache = {}  # Cache for file contents

    def extract_errors(self, log_file: str) -> List[Dict]:
        """Extract all errors from log file."""
        with open(log_file, 'r') as f:
            log_content = f.read()
        
        # Split log content into individual error blocks
        error_blocks = re.split(r'(?=Traceback \(most recent call last\):)', log_content)
        error_blocks = [block.strip() for block in error_blocks if block.strip()]
        
        errors = []
        for block in error_blocks:
            # Extract error context for each block
            error_patterns = {
                'file_path': r'File "([^"]+)"',
                'line_number': r'line (\d+)',
                'error_type': r'([A-Za-z]+Error|Exception):',
                'error_message': r'([A-Za-z]+Error|Exception):\s*(.*)',
                'full_traceback': block
            }
            
            context = {}
            for key, pattern in error_patterns.items():
                if key == 'full_traceback':
                    context[key] = block
                else:
                    match = re.search(pattern, block)
                    if match:
                        if key == 'error_message' and match.group(2):
                            context[key] = match.group(2).strip()
                        else:
                            context[key] = match.group(1)
            
            if context.get('file_path') and context.get('line_number'):
                errors.append(context)
        
        return errors

    def find_file(self, file_path: str) -> Optional[str]:
        """Find file in the project structure."""
        # First try the exact path
        if os.path.exists(file_path):
            return file_path
            
        # If not found, search in the project directory
        project_root = os.getcwd()
        for root, _, files in os.walk(project_root):
            for file in files:
                if file == os.path.basename(file_path):
                    return os.path.join(root, file)
        return None

    def get_file_content(self, file_path: str) -> Optional[str]:
        """Get the entire content of a file with caching."""
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
        except Exception as e:
            console.print(f"[red]Error reading file {file_path}: {str(e)}[/red]")
            return None

    def get_relevant_code(self, file_path: str, line_number: int, context_lines: int = 5) -> Dict:
        """Get relevant code around the error line and full file content."""
        full_content = self.get_file_content(file_path)
        if not full_content:
            return {'error': f"Could not read file: {file_path}"}
            
        try:
            lines = full_content.split('\n')
            
            start = max(0, line_number - context_lines - 1)
            end = min(len(lines), line_number + context_lines)
            
            relevant_code = '\n'.join(lines[start:end])
            return {
                'code': relevant_code,
                'start_line': start,
                'end_line': end,
                'full_content': full_content
            }
        except Exception as e:
            return {'error': f"Could not process file: {str(e)}"}

    def apply_fix(self, file_path: str, original_content: str, fix_content: str, start_line: int, end_line: int) -> bool:
        """Apply the fix to the specific part of the file."""
        try:
            lines = original_content.split('\n')
            new_lines = lines[:start_line] + fix_content.split('\n') + lines[end_line:]
            
            actual_path = self.find_file(file_path)
            if not actual_path:
                return False
                
            with open(actual_path, 'w') as f:
                f.write('\n'.join(new_lines))
                
            # Update cache
            self.file_cache[file_path] = '\n'.join(new_lines)
            return True
        except Exception as e:
            console.print(f"[red]Error applying fix: {str(e)}[/red]")
            return False

    def get_fix(self, error_context: Dict, code_context: Dict) -> str:
        """Get the best fix for the error with access to the entire file."""
        fix_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert software engineer. 
            Based on the error and full file context, provide the BEST fix for the code.
            Return ONLY the code that needs to be changed. Don't add anything else like backticks or words.
            No explanations, no markdown formatting, just the raw code with proper indentation.
            Include only the lines that need to be modified.
            Make sure the code is properly formatted and indented.
            **NOTE** Please maintain proper indentation.
            
            Choose the most robust and maintainable solution."""),
            ("user", """
            Error Context:
            {error_context}
            
            Error Location (specific code around the error):
            {error_location}
            
            Full File Content:
            {full_file_content}
            
            Provide the best fix for the code around line {line_number}:
            """)
        ])

        fix_chain = (
            {
                "error_context": lambda x: str(error_context),
                "error_location": lambda x: code_context['code'],
                "full_file_content": lambda x: code_context['full_content'],
                "line_number": lambda x: error_context['line_number']
            }
            | fix_prompt
            | self.llm
            | StrOutputParser()
        )

        return fix_chain.invoke({})

    def analyze_log_patterns(self, errors: List[Dict], log_content: str) -> Dict:
        """Analyze patterns in the errors to identify common issues."""
        # Group errors by type and file
        error_by_type = defaultdict(list)
        error_by_file = defaultdict(list)
        
        for error in errors:
            error_type = error.get('error_type', 'Unknown')
            file_path = error.get('file_path', 'Unknown')
            
            error_by_type[error_type].append(error)
            error_by_file[file_path].append(error)
        
        # Load full file contents
        file_contents = {}
        for file_path in error_by_file.keys():
            content = self.get_file_content(file_path)
            if content:
                file_contents[file_path] = content
        
        return {
            'total_errors': len(errors),
            'error_by_type': error_by_type,
            'error_by_file': error_by_file,
            'file_contents': file_contents,
            'full_log': log_content
        }

    def get_comprehensive_fix(self, errors: List[Dict], pattern_analysis: Dict) -> Dict:
        """Get comprehensive fixes for patterns of errors with access to full file context."""
        # Prepare context for LLM
        error_summaries = []
        for error_type, error_list in pattern_analysis['error_by_type'].items():
            error_summaries.append(f"Error Type: {error_type} (Count: {len(error_list)})")
            for error in error_list[:3]:  # Limit to 3 examples per type
                error_summaries.append(f"- In {error.get('file_path', 'Unknown')} at line {error.get('line_number', 'Unknown')}: {error.get('error_message', 'No message')}")
        
        file_summaries = []
        file_content_samples = []
        for file_path, error_list in pattern_analysis['error_by_file'].items():
            file_summaries.append(f"File: {file_path} (Count: {len(error_list)})")
            for error in error_list[:3]:  # Limit to 3 examples per file
                file_summaries.append(f"- {error.get('error_type', 'Unknown')}: {error.get('error_message', 'No message')} at line {error.get('line_number', 'Unknown')}")
            
            # Add sample of file content
            if file_path in pattern_analysis['file_contents']:
                file_content = pattern_analysis['file_contents'][file_path]
                file_content_samples.append(f"File: {file_path}\n{file_content[:1500]}...")  # Show first 1500 chars
        
        # Get overall analysis and comprehensive fixes
        comprehensive_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert software engineer specializing in debugging complex applications.
            Analyze the provided error patterns, log file, and source code to provide:
            1. A comprehensive analysis of the main root causes
            2. A list of recommended fixes grouped by error type or common cause
            3. Any architectural or systemic improvements that would prevent similar errors
            
            Be thorough but concise. Focus on identifying underlying patterns rather than individual bugs.
            Consider the full context of the code when suggesting fixes."""),
            ("user", """
            Full Log File Analysis:
            ----------------------
            Total Errors: {total_errors}
            
            Errors By Type:
            {error_type_summary}
            
            Errors By File:
            {file_summary}
            
            Sample Source Code:
            {file_content_samples}
            
            Raw Log Data (Sample):
            {raw_log}
            
            Provide your comprehensive analysis and solution recommendations:
            """)
        ])

        comprehensive_chain = (
            {
                "total_errors": lambda x: pattern_analysis['total_errors'],
                "error_type_summary": lambda x: "\n".join(error_summaries),
                "file_summary": lambda x: "\n".join(file_summaries),
                "file_content_samples": lambda x: "\n\n".join(file_content_samples),
                "raw_log": lambda x: pattern_analysis['full_log'][:2000]  # First 2000 chars of log
            }
            | comprehensive_prompt
            | self.llm
            | StrOutputParser()
        )

        return {
            'analysis': comprehensive_chain.invoke({}),
            'pattern_analysis': pattern_analysis
        }

    def get_file_recommendations(self, error_analysis: Dict) -> Dict[str, str]:
        """Generate file-specific fix recommendations with full file context."""
        file_fixes = {}
        
        for file_path, errors in error_analysis['pattern_analysis']['error_by_file'].items():
            if len(errors) >= 1:  # Generate recommendations for any file with errors
                file_content = self.get_file_content(file_path)
                if not file_content:
                    continue
                    
                try:
                    # Prepare context for specific file fixes
                    file_prompt = ChatPromptTemplate.from_messages([
                        ("system", """You are an expert software engineer.
                        Based on the multiple errors in this file, provide a comprehensive fix that addresses all issues.
                        Focus on the most efficient solution that solves the underlying problems.
                        Return the updated full file content with all necessary changes.
                        Add comments where you've made changes to explain what issues each change addresses."""),
                        ("user", """
                        File Path: {file_path}
                        
                        Errors in this file:
                        {errors}
                        
                        Original File Content:
                        {file_content}
                        
                        Provide the completely updated file content with all fixes applied:
                        """)
                    ])
                    
                    file_chain = (
                        {
                            "file_path": lambda x: file_path,
                            "errors": lambda x: str(errors),
                            "file_content": lambda x: file_content
                        }
                        | file_prompt
                        | self.llm
                        | StrOutputParser()
                    )
                    
                    file_fixes[file_path] = file_chain.invoke({})
                except Exception as e:
                    console.print(f"[red]Error generating fix for {file_path}: {str(e)}[/red]")
        
        return file_fixes


@click.command()
@click.argument('log_file', type=click.Path(exists=True))
@click.option('--comprehensive', is_flag=True, help='Perform comprehensive analysis instead of error-by-error')
def main(log_file: str, comprehensive: bool = False):
    """Analyze log files and provide AI-powered solutions."""
    analyzer = LogAnalyzer()
    
    console.print(Panel.fit(
        f"Analyzing log file: {log_file}",
        title="Smart Log Analyzer",
        border_style="blue"
    ))
    
    try:
        # Extract all errors from the log file
        with open(log_file, 'r') as f:
            log_content = f.read()
            
        errors = analyzer.extract_errors(log_file)
        
        if not errors:
            console.print("[yellow]No errors found in the log file.[/yellow]")
            return

        # Show overview of all errors
        console.print(f"\n[bold]Found {len(errors)} errors.[/bold]")
        
        if comprehensive or len(errors) > 3:
            # Perform comprehensive analysis
            console.print("[cyan]Performing comprehensive analysis of error patterns...[/cyan]")
            
            # Analyze patterns in errors
            pattern_analysis = analyzer.analyze_log_patterns(errors, log_content)
            
            # Show error distribution
            console.print("\n[bold]Error Distribution:[/bold]")
            table = Table(title="Errors by Type")
            table.add_column("Error Type", style="cyan")
            table.add_column("Count", style="magenta")
            
            for error_type, error_list in pattern_analysis['error_by_type'].items():
                table.add_row(error_type, str(len(error_list)))
            console.print(table)
            
            # Get comprehensive analysis and fixes
            console.print("\n[cyan]Generating comprehensive analysis with full file context...[/cyan]")
            comprehensive_analysis = analyzer.get_comprehensive_fix(errors, pattern_analysis)
            
            console.print(Panel.fit(
                comprehensive_analysis['analysis'],
                title="Comprehensive Analysis",
                border_style="green"
            ))
            
            # Generate file-specific recommendations
            console.print("\n[cyan]Generating file-specific recommendations with full context...[/cyan]")
            file_fixes = analyzer.get_file_recommendations(comprehensive_analysis)
            
            for file_path, fix in file_fixes.items():
                console.print(f"\n[bold]Recommended fixes for {file_path}:[/bold]")
                console.print(Panel.fit(
                    f"Full file fix generated. Length: {len(fix)} characters",
                    title=f"Fix for {os.path.basename(file_path)}",
                    border_style="yellow"
                ))
                
                if Confirm.ask(f"\nView diff for {file_path}?"):
                    # Show diff if requested
                    original_content = analyzer.get_file_content(file_path)
                    if original_content:
                        # Simple diff visualization
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
                        actual_path = analyzer.find_file(file_path)
                        if actual_path:
                            with open(actual_path, 'w') as f:
                                f.write(fix)
                            console.print(f"[green]Comprehensive fix applied to {file_path}![/green]")
                            # Update cache
                            analyzer.file_cache[file_path] = fix
                    except Exception as e:
                        console.print(f"[red]Error applying fix: {str(e)}[/red]")
        else:
            # Show individual errors
            for i, error in enumerate(errors, 1):
                console.print(f"\n{i}. [red]{error.get('error_type', 'Unknown')}[/red] in [blue]{error.get('file_path', 'Unknown')}[/blue] at line {error.get('line_number', 'Unknown')}")
                console.print(f"   Message: {error.get('error_message', 'No message')}")

            # Ask if user wants to proceed with fixes
            if not Confirm.ask("\nWould you like to see and apply fixes for these errors?"):
                return

            # Process fixes
            for i, error in enumerate(errors, 1):
                console.print(f"\n[bold]Processing error {i} of {len(errors)}[/bold]")
                
                file_path = error.get('file_path')
                if not file_path or not analyzer.find_file(file_path):
                    console.print(f"[red]Could not find file: {file_path}[/red]")
                    continue

                code_context = analyzer.get_relevant_code(
                    file_path,
                    int(error.get('line_number', 0))
                )

                if 'error' in code_context:
                    console.print(f"[red]Error: {code_context['error']}[/red]")
                    continue

                # Get and show the fix
                fix = analyzer.get_fix(error, code_context)
                
                console.print("\n[bold]Proposed Fix:[/bold]")
                console.print(Panel.fit(
                    fix,
                    title="Fix",
                    border_style="yellow"
                ))

                if Confirm.ask("\nWould you like to apply this fix?"):
                    if analyzer.apply_fix(
                        file_path,
                        code_context["full_content"],
                        fix,
                        code_context["start_line"],
                        code_context["end_line"]
                    ):
                        console.print("[green]Fix applied successfully![/green]")
                    else:
                        console.print("[red]Failed to apply fix.[/red]")
                
                if i < len(errors):
                    if not Confirm.ask("\nContinue to next error?"):
                        break
        
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        import traceback
        console.print(traceback.format_exc())

if __name__ == '__main__':
    main()