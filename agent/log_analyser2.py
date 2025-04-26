import os
import re
from pathlib import Path
from typing import List, Dict, Optional
import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
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

    def get_relevant_code(self, file_path: str, line_number: int, context_lines: int = 5) -> Dict:
        """Get relevant code around the error line."""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            start = max(0, line_number - context_lines - 1)
            end = min(len(lines), line_number + context_lines)
            
            relevant_code = ''.join(lines[start:end])
            return {
                'code': relevant_code,
                'start_line': start,
                'end_line': end,
                'full_content': ''.join(lines)
            }
        except Exception as e:
            return {'error': f"Could not read file: {str(e)}"}

    def apply_fix(self, file_path: str, original_content: str, fix_content: str, start_line: int, end_line: int) -> bool:
        """Apply the fix to the specific part of the file."""
        try:
            lines = original_content.split('\n')
            new_lines = lines[:start_line] + fix_content.split('\n') + lines[end_line:]
            with open(file_path, 'w') as f:
                f.write('\n'.join(new_lines))
            return True
        except Exception as e:
            console.print(f"[red]Error applying fix: {str(e)}[/red]")
            return False

    def get_fix(self, error_context: Dict, code_context: Dict) -> str:
        """Get the best fix for the error."""
        fix_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert software engineer. 
            Based on the error and code context, provide the BEST fix for the code.
            Return ONLY the code that needs to be changed dont add anything else like backticks or words like python just give the code with proper indentation.
            No explanations, no markdown formatting, just the raw code.
            Include only the lines that need to be modified.
            Make sure the code is properly formatted and indented.
            **NOTE** Please maintain proper indentation.
             
             Example:
             *Wrong reponse*:
             │ ```python                                                                                                            │
│                 elif operation == 'db_query':                                                                        │
│                     query = random.choice(["SELECT * FROM users", "SELECT * FROM transactions", "SELECT * FROM       │
│ orders"])                                                                                                            │
│                                                                                                                      │
│                     net_client.request(query)                                                                        │
│ ```   
             
             *Correct response*:
                                                                                                                         │
│                 elif operation == 'db_query':                                                                        │
│                     query = random.choice(["SELECT * FROM users", "SELECT * FROM transactions", "SELECT * FROM       │
│ orders"])                                                                                                            │
│                                                                                                                      │
│                     net_client.request(query)                                                                        │
 

            Choose the most robust and maintainable solution."""),
            ("user", """
            Error Context:
            {error_context}
            
            Original Code:
            {code_context}
            
            Provide the best fix:
            """)
        ])

        fix_chain = (
            {"error_context": lambda x: str(error_context), "code_context": lambda x: code_context['code']}
            | fix_prompt
            | self.llm
            | StrOutputParser()
        )

        return fix_chain.invoke({})

@click.command()
@click.argument('log_file', type=click.Path(exists=True))
def main(log_file: str):
    """Analyze log files and provide AI-powered solutions."""
    analyzer = LogAnalyzer()
    
    console.print(Panel.fit(
        f"Analyzing log file: {log_file}",
        title="Log Analyzer",
        border_style="blue"
    ))
    
    try:
        # Extract all errors from the log file
        errors = analyzer.extract_errors(log_file)
        
        if not errors:
            console.print("[yellow]No errors found in the log file.[/yellow]")
            return

        # Show overview of all errors
        console.print(f"\n[bold]Found {len(errors)} errors:[/bold]")
        for i, error in enumerate(errors, 1):
            console.print(f"\n{i}. [red]{error['error_type']}[/red] in [blue]{error['file_path']}[/blue] at line {error['line_number']}")
            console.print(f"   Message: {error['error_message']}")

        # Ask if user wants to proceed with fixes
        if not Confirm.ask("\nWould you like to see and apply fixes for these errors?"):
            return

        # Process fixes
        for i, error in enumerate(errors, 1):
            console.print(f"\n[bold]Processing error {i} of {len(errors)}[/bold]")
            
            file_path = analyzer.find_file(error['file_path'])
            if not file_path:
                console.print(f"[red]Could not find file: {error['file_path']}[/red]")
                continue

            code_context = analyzer.get_relevant_code(
                file_path,
                int(error['line_number'])
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

if __name__ == '__main__':
    main() 
