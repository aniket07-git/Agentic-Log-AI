# Smart Log Analyzer

An AI-powered log analysis tool that helps developers quickly identify, understand, and fix errors in application logs. The tool offers two modes of analysis - a fast basic review and a comprehensive in-depth review with code fixes.

## Features

- **Dual Analysis Modes**:
  - 🚀 **Basic Review**: Quick log-only analysis with error interpretation and recommendations
  - 🔍 **In-Depth Review**: Comprehensive analysis with source code context and automated fixes

- **Smart Error Detection**:
  - Automatic error extraction from log files
  - Error classification and pattern recognition
  - Traceback analysis and interpretation

- **AI-Powered Solutions**:
  - Error cause explanation
  - Suggested fixes and troubleshooting steps
  - Code modification recommendations (in-depth mode)

- **User-Friendly Interface**:
  - Color-coded console output
  - Interactive prompts
  - Clear error visualization

## Installation

1. **Prerequisites**:
   - Python 3.8+
   - OpenAI API key (set in `.env` file)

2. **Setup**:
   ```bash
   git clone https://github.com/your-repo/log-analyzer.git
   cd log-analyzer
   pip install -r requirements.txt

Usage

Basic Command

bash
python new_log_analyzer.py
Options

Flag	Description	Default
-f, --log-file	Analyze specific log file	None
-d, --directory	Directory to search for logs	Current dir
-r, --recursive	Search for logs recursively	False
--max-depth	Max recursion depth	4
-e, --extensions	Log file extensions to look for	.log, .txt
-g, --grep	Filter logs by pattern	None
