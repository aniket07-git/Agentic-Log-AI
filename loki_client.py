import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class LokiClient:
    def __init__(self):
        self.url = os.getenv('LOKI_URL', 'http://localhost:3100')
        self.username = os.getenv('LOKI_USERNAME')
        self.password = os.getenv('LOKI_PASSWORD')
        
        # Basic auth if credentials are provided
        self.auth = None
        if self.username and self.password:
            self.auth = (self.username, self.password)

    def query_range(self, 
                   query: str,
                   start: datetime,
                   end: datetime,
                   limit: int = 1000,
                   direction: str = "backward") -> List[Dict]:
        """
        Query Loki for logs within a time range.
        
        Args:
            query: LogQL query string
            start: Start time
            end: End time
            limit: Maximum number of entries to return
            direction: Query direction ("forward" or "backward")
            
        Returns:
            List of log entries
        """
        try:
            params = {
                "query": query,
                "start": int(start.timestamp() * 1e9),
                "end": int(end.timestamp() * 1e9),
                "limit": limit,
                "direction": direction
            }
            
            response = requests.get(
                f"{self.url}/loki/api/v1/query_range",
                params=params,
                auth=self.auth
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Process and format the results
            results = []
            for stream in data.get("data", {}).get("result", []):
                labels = stream.get("stream", {})
                for value in stream.get("values", []):
                    timestamp, log_line = value
                    results.append({
                        "timestamp": datetime.fromtimestamp(int(timestamp) / 1e9),
                        "log": log_line,
                        "labels": labels
                    })
            
            return results
            
        except requests.exceptions.RequestException as e:
            print(f"Error querying Loki: {str(e)}")
            return []

    def instant_query(self, query: str) -> List[Dict]:
        """
        Perform an instant query at the current time.
        
        Args:
            query: LogQL query string
            
        Returns:
            List of log entries
        """
        try:
            params = {
                "query": query,
                "time": int(datetime.now().timestamp() * 1e9)
            }
            
            response = requests.get(
                f"{self.url}/loki/api/v1/query",
                params=params,
                auth=self.auth
            )
            response.raise_for_status()
            
            data = response.json()
            
            results = []
            for stream in data.get("data", {}).get("result", []):
                labels = stream.get("stream", {})
                value = stream.get("value", [])
                if value:
                    timestamp, log_line = value
                    results.append({
                        "timestamp": datetime.fromtimestamp(int(timestamp) / 1e9),
                        "log": log_line,
                        "labels": labels
                    })
            
            return results
            
        except requests.exceptions.RequestException as e:
            print(f"Error querying Loki: {str(e)}")
            return []

    def get_label_values(self, label: str) -> List[str]:
        """
        Get all values for a specific label.
        
        Args:
            label: Label name
            
        Returns:
            List of label values
        """
        try:
            response = requests.get(
                f"{self.url}/loki/api/v1/label/{label}/values",
                auth=self.auth
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("data", [])
            
        except requests.exceptions.RequestException as e:
            print(f"Error getting label values: {str(e)}")
            return []

    def get_metrics(self, 
                   start: datetime,
                   end: datetime,
                   interval: str = "5m") -> Dict[str, List]:
        """
        Get log metrics for the dashboard.
        
        Args:
            start: Start time
            end: End time
            interval: Time interval for aggregation
            
        Returns:
            Dictionary containing metrics data
        """
        metrics = {
            "errors": [],
            "warnings": [],
            "info": []
        }
        
        try:
            # Query for each log level
            for level in metrics.keys():
                query = f'count_over_time({{level="{level.upper()}"}}[{interval}])'
                
                params = {
                    "query": query,
                    "start": int(start.timestamp() * 1e9),
                    "end": int(end.timestamp() * 1e9),
                }
                
                response = requests.get(
                    f"{self.url}/loki/api/v1/query_range",
                    params=params,
                    auth=self.auth
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Extract values
                for result in data.get("data", {}).get("result", []):
                    values = result.get("values", [])
                    metrics[level] = [(datetime.fromtimestamp(int(ts) / 1e9), float(val)) 
                                    for ts, val in values]
            
            return metrics
            
        except requests.exceptions.RequestException as e:
            print(f"Error getting metrics: {str(e)}")
            return metrics

    def push_logs(self, logs: List[Dict]) -> bool:
        """
        Push logs to Loki.
        
        Args:
            logs: List of log entries with timestamp and labels
            
        Returns:
            Boolean indicating success
        """
        try:
            streams = []
            
            # Group logs by their label sets
            grouped_logs = {}
            for log in logs:
                labels = frozenset(log.get("labels", {}).items())
                if labels not in grouped_logs:
                    grouped_logs[labels] = []
                grouped_logs[labels].append([
                    str(int(log["timestamp"].timestamp() * 1e9)),
                    log["log"]
                ])
            
            # Format for Loki push API
            for labels, values in grouped_logs.items():
                stream = {
                    "stream": dict(labels),
                    "values": values
                }
                streams.append(stream)
            
            payload = {"streams": streams}
            
            response = requests.post(
                f"{self.url}/loki/api/v1/push",
                json=payload,
                auth=self.auth
            )
            response.raise_for_status()
            
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error pushing logs: {str(e)}")
            return False 