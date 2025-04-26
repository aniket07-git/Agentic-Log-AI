# LogAnalytics Dashboard

An AI-powered log analytics dashboard built with Streamlit that provides intelligent error analysis and resolution suggestions.

## Features

- Real-time log monitoring with Loki integration
- Manual log file upload support
- AI-powered error analysis and resolution suggestions
- Interactive dashboard with metrics and visualizations
- Error pattern detection and root cause analysis

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure Loki (optional):
- Set LOKI_URL environment variable or configure through the UI
- Optional authentication with LOKI_USERNAME and LOKI_PASSWORD

3. Run the application:
```bash
streamlit run agent/streamlit_app.py
```

## Usage

1. **Dashboard**: View real-time metrics, error analysis, and resolution suggestions
2. **Log Explorer**: Search and filter through log entries
3. **Error Analysis**: Detailed analysis of error patterns and trends
4. **Sources**: Configure Loki connection and upload log files
5. **Settings**: Customize dashboard preferences

## Log File Format

The dashboard supports the following log file formats:

1. JSON format:
```json
[
  {
    "timestamp": "2024-02-20 10:30:00",
    "level": "ERROR",
    "message": "Error message here",
    "service": "auth-service"
  }
]
```

2. Text format (one log per line):
```
[2024-02-20 10:30:00] ERROR services.auth-service: Error message here
```

## Contributing

Feel free to submit issues and enhancement requests!