
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


## Interactive Options

When you run the tool, you'll go through these steps:

1. **Mode Selection**:
- `1`: Get quick analysis of errors without code access
- `2`: Full analysis with code examination and fix suggestions

2. **Action Selection**:
   - `1`: Analyze all found log files
- `2`: Choose specific files from the list
- `3`: Quit the analyzer

3. **For In-Depth Mode**:
- View diffs of proposed changes
- Confirm before applying fixes
- Option to continue to next file

## Command Line Flags

| Flag | Description | Example | Default |
|------|-------------|---------|---------|
| `-f`, `--log-file` | Analyze specific log file | `-f error.log` | None |
| `-d`, `--directory` | Directory to search for logs | `-d ./logs` | Current dir |
| `-r`, `--recursive` | Search for logs recursively | `-r` | False |
| `--max-depth` | Max recursion depth | `--max-depth 3` | 4 |
| `-e`, `--extensions` | Log file extensions to look for | `-e .log -e .txt` | .log, .txt |
| `-g`, `--grep` | Filter logs by pattern | `-g "Timeout"` | None |

## Full Usage Examples

1. **Basic quick analysis** (fastest):
```bash
python long_analyzer.py -d ./logs --extensions .log .err
