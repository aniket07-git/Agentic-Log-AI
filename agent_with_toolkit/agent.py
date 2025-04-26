from langchain.chat_models import ChatOpenAI
import json
import time
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from dotenv import load_dotenv

# Import all necessary tools from the modularized codebase_QA module
from ToolKit import (
    create_enhanced_tools,
    save_analysis_to_json,
)

load_dotenv()

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2  # Lower temperature for more deterministic outputs
)

# Enhanced prompt with more context requirements
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert Python error resolver. Your task is to analyze log files for errors and provide comprehensive solutions.

    WORKFLOW:
    1. Use find_log_files to locate all log files in the current directory using path="."
    2. Read each log file with read_file
    3. For each error found:
       a. Use find_files_by_content to locate relevant code files containing error-related information
       b. Use read_file to examine the related code files
       c. Analyze both the error context and the code that caused it
    4. For each error, create a detailed JSON object with these EXACT fields:
        {{
          "log_level": string,        // MUST be one of: "INFO", "ERROR", "DEBUG", "WARNING", or "UNKNOWN"
          "error_type": string,       // MUST be a valid Python error class name (e.g., "ZeroDivisionError")
          "error_message": string,    // MUST be the exact error message from logs without modification
          "file_location": string,    // MUST be the full file path (e.g., "src/utils/parser.py")
          "line_number": integer,     // MUST be a positive number (>0)
          "error_explanation": string, // MUST explain the root cause in 1-2 sentences
          "related_code": string,     // MUST contain ONLY the code snippet without any explanation
          "fixes": array,             // MUST be a list of specific code-focused solutions
          "code_suggestion": string,  // MUST contain ONLY the corrected code without any explanation
          "confidence": string         // MUST be a HIGH, MEDIUM, or LOW confidence level based on the analysis
        }}
    5. Group results by log file
    6. Use save_analysis to save your final analysis as JSON

    IMPORTANT RULES:
    - Never invent or fabricate error information
    - Use null for any field where information cannot be determined
    - Extract only what is explicitly present in the logs or code
    - Provide code snippets and suggestions WITHOUT explanatory text
    
    YOUR FINAL RESPONSE MUST BE VALID JSON.
    """),
    # MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# Create agent with enhanced workflow
def create_agent():
    # Use the modularized tools from codebase_QA.py
    tools = create_enhanced_tools()

    # memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    
    agent = create_openai_tools_agent(
        llm=llm,
        tools=tools,
        prompt=prompt
    )
    
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        # memory=memory,
        return_intermediate_steps=True
    )

# Enhanced analysis function
def analyze_logs(query="Find all log files and analyze them in detail for errors"):
    agent_executor = create_agent()
    result = agent_executor.invoke({"input": query})
    
    # Save the result automatically with timestamp
    if "output" in result:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"error_analysis_{timestamp}.json"
        res = save_analysis_to_json(result["output"], filename)
        print(f"Analysis saved to {filename}")
    
    return res

# Example usage
if __name__ == "__main__":
    print("Log Analysis System v2.0")
    print("Analyzing logs and related code for detailed error context...")
    result = analyze_logs()
    print("\nFinal Analysis Summary:")
    
    # Try to parse and show a summary
    try:
        analysis = json.loads(result["json_object"])
        error_count = sum(len(errors) for log_file, errors in analysis.items())
        print(f"\nFound {error_count} errors across {len(analysis)} log files.")
        print("\nError types found:")
        error_types = {}
        for log_file, errors in analysis.items():
            for error in errors:
                error_type = error.get("error_type", "Unknown")
                error_types[error_type] = error_types.get(error_type, 0) + 1
        
        for error_type, count in error_types.items():
            print(f"  - {error_type}: {count} occurrence(s)")
    except:
        # Fallback to showing raw output
        print(result["output"])