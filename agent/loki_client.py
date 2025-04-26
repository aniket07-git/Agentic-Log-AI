import requests
import json
from datetime import datetime, timedelta
import os
import time
from typing import List, Dict, Optional, Union
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class LokiClient:
    """Client for interacting with Grafana Loki log aggregation system."""
    
    def __init__(self, base_url: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize the Loki client.
        
        Args:
            base_url (str, optional): Loki server URL. Defaults to env var LOKI_URL
            username (str, optional): Authentication username. Defaults to env var LOKI_USERNAME
            password (str, optional): Authentication password. Defaults to env var LOKI_PASSWORD
        """
        self.base_url = base_url or os.getenv('LOKI_URL', 'http://localhost:3100')
        self.username = username or os.getenv('LOKI_USERNAME')
        self.password = password or os.getenv('LOKI_PASSWORD')
        
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Validate configuration
        if not self.base_url:
            raise ValueError("Loki URL must be provided either through constructor or LOKI_URL environment variable")
        
        # Set up session with authentication if provided
        self.session = requests.Session()
        if self.username and self.password:
            self.session.auth = (self.username, self.password)

    def query_range(self, 
                   query: str,
                   start: Union[datetime, str],
                   end: Union[datetime, str] = None,
                   limit: int = 100,
                   direction: str = "backward") -> Dict:
        """
        Execute a LogQL range query.
        
        Args:
            query (str): LogQL query string
            start (Union[datetime, str]): Start time
            end (Union[datetime, str], optional): End time. Defaults to now
            limit (int, optional): Maximum number of entries. Defaults to 100
            direction (str, optional): Query direction. Defaults to "backward"
            
        Returns:
            Dict: Query results
        """
        # Convert datetime objects to RFC3339 strings
        if isinstance(start, datetime):
            start = start.isoformat() + "Z"
        if isinstance(end, datetime):
            end = end.isoformat() + "Z"
        elif end is None:
            end = datetime.utcnow().isoformat() + "Z"
            
        params = {
            "query": query,
            "start": start,
            "end": end,
            "limit": limit,
            "direction": direction
        }
        
        try:
            response = self.session.get(
                f"{self.base_url}/loki/api/v1/query_range",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error executing range query: {e}")
            raise

    def instant_query(self, query: str, time: Union[datetime, str] = None) -> Dict:
        """
        Execute a LogQL instant query.
        
        Args:
            query (str): LogQL query string
            time (Union[datetime, str], optional): Evaluation timestamp. Defaults to now
            
        Returns:
            Dict: Query results
        """
        if isinstance(time, datetime):
            time = time.isoformat() + "Z"
        elif time is None:
            time = datetime.utcnow().isoformat() + "Z"
            
        params = {
            "query": query,
            "time": time
        }
        
        try:
            response = self.session.get(
                f"{self.base_url}/loki/api/v1/query",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error executing instant query: {e}")
            raise

    def get_label_names(self) -> List[str]:
        """
        Get all label names.
        
        Returns:
            List[str]: List of label names
        """
        try:
            response = self.session.get(f"{self.base_url}/loki/api/v1/labels")
            response.raise_for_status()
            return response.json()["data"]
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error getting label names: {e}")
            raise

    def get_label_values(self, label: str) -> List[str]:
        """
        Get values for a specific label.
        
        Args:
            label (str): Label name
            
        Returns:
            List[str]: List of label values
        """
        try:
            response = self.session.get(
                f"{self.base_url}/loki/api/v1/label/{label}/values"
            )
            response.raise_for_status()
            return response.json()["data"]
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error getting label values: {e}")
            raise

    def get_series(self, 
                  match: List[str],
                  start: Union[datetime, str],
                  end: Union[datetime, str] = None) -> List[Dict]:
        """
        Get series matching a label selector.
        
        Args:
            match (List[str]): List of series selectors
            start (Union[datetime, str]): Start time
            end (Union[datetime, str], optional): End time. Defaults to now
            
        Returns:
            List[Dict]: List of series
        """
        if isinstance(start, datetime):
            start = start.isoformat() + "Z"
        if isinstance(end, datetime):
            end = end.isoformat() + "Z"
        elif end is None:
            end = datetime.utcnow().isoformat() + "Z"
            
        params = {
            "match[]": match,
            "start": start,
            "end": end
        }
        
        try:
            response = self.session.get(
                f"{self.base_url}/loki/api/v1/series",
                params=params
            )
            response.raise_for_status()
            return response.json()["data"]
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error getting series: {e}")
            raise

    def push_logs(self, streams: List[Dict]) -> None:
        """
        Push log entries to Loki.
        
        Args:
            streams (List[Dict]): List of streams to push
                Each stream should have format:
                {
                    "stream": {"label": "value"},
                    "values": [["unix_nano_timestamp", "log line"]]
                }
        """
        try:
            response = self.session.post(
                f"{self.base_url}/loki/api/v1/push",
                json={"streams": streams},
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error pushing logs: {e}")
            raise

    def get_metrics(self, 
                   start: Union[datetime, str],
                   end: Union[datetime, str] = None,
                   step: str = "1h") -> Dict:
        """
        Get metrics about log volume and patterns.
        
        Args:
            start (Union[datetime, str]): Start time
            end (Union[datetime, str], optional): End time. Defaults to now
            step (str, optional): Step interval. Defaults to "1h"
            
        Returns:
            Dict: Metrics data including:
                - Total log volume
                - Error rate
                - Top error types
                - Response time patterns
        """
        metrics = {
            "log_volume": {},
            "error_rate": {},
            "top_errors": [],
            "response_times": {}
        }
        
        # Get total log volume
        volume_query = 'sum(count_over_time({job=~".+"}[1h]))'
        volume_data = self.query_range(volume_query, start, end, direction="forward")
        if "data" in volume_data and "result" in volume_data["data"]:
            metrics["log_volume"] = volume_data["data"]["result"]
            
        # Get error rate
        error_query = 'sum(count_over_time({level="error"}[1h])) / sum(count_over_time({job=~".+"}[1h]))'
        error_data = self.query_range(error_query, start, end, direction="forward")
        if "data" in error_data and "result" in error_data["data"]:
            metrics["error_rate"] = error_data["data"]["result"]
            
        # Get top errors
        top_errors_query = 'topk(10, sum by (error) (count_over_time({level="error"}[1h])))'
        top_errors_data = self.instant_query(top_errors_query)
        if "data" in top_errors_data and "result" in top_errors_data["data"]:
            metrics["top_errors"] = top_errors_data["data"]["result"]
            
        # Get response time patterns
        response_query = 'avg_over_time({response_time=~".+"}[1h])'
        response_data = self.query_range(response_query, start, end, direction="forward")
        if "data" in response_data and "result" in response_data["data"]:
            metrics["response_times"] = response_data["data"]["result"]
            
        return metrics

    def tail_logs(self, query: str, delay_seconds: int = 1) -> None:
        """
        Tail logs in real-time.
        
        Args:
            query (str): LogQL query string
            delay_seconds (int, optional): Delay between polls. Defaults to 1
        """
        last_timestamp = datetime.utcnow()
        
        while True:
            try:
                # Query for new logs since last timestamp
                results = self.query_range(
                    query,
                    start=last_timestamp,
                    limit=100,
                    direction="forward"
                )
                
                # Process and print new logs
                if "data" in results and "result" in results["data"]:
                    for stream in results["data"]["result"]:
                        for timestamp, line in stream.get("values", []):
                            print(f"{datetime.fromtimestamp(float(timestamp))} - {line}")
                            last_timestamp = datetime.fromtimestamp(float(timestamp))
                
                # Wait before next poll
                time.sleep(delay_seconds)
                
            except KeyboardInterrupt:
                print("\nStopping log tail...")
                break
            except Exception as e:
                self.logger.error(f"Error in tail_logs: {e}")
                break

def main():
    """Example usage of LokiClient."""
    # Initialize client
    client = LokiClient()
    
    # Example queries
    start_time = datetime.utcnow() - timedelta(hours=1)
    
    # Get recent error logs
    error_logs = client.query_range(
        query='{level="error"}',
        start=start_time,
        limit=10
    )
    print("Recent Errors:", json.dumps(error_logs, indent=2))
    
    # Get label names
    labels = client.get_label_names()
    print("Available Labels:", labels)
    
    # Get metrics
    metrics = client.get_metrics(start=start_time)
    print("Metrics:", json.dumps(metrics, indent=2))

if __name__ == "__main__":
    main() 