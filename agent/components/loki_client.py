import requests
from datetime import datetime, timedelta
import os
from typing import List, Dict
import re
from urllib.parse import urljoin

class LokiClient:
    def __init__(self):
        self.base_url = os.getenv('LOKI_URL', 'http://localhost:3100')
        self.username = os.getenv('LOKI_USERNAME')
        self.password = os.getenv('LOKI_PASSWORD')
        self.verify_ssl = os.getenv('LOKI_VERIFY_SSL', 'true').lower() == 'true'
        
    def get_auth(self):
        """Get authentication tuple if credentials are provided."""
        if self.username and self.password:
            return (self.username, self.password)
        return None
    
    def get_headers(self):
        """Get request headers."""
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
    
    def query_range(self, query: str, start_time: datetime, end_time: datetime, limit: int = 1000) -> List[Dict]:
        """Query Loki for logs within a time range."""
        url = urljoin(self.base_url, "/loki/api/v1/query_range")
        
        params = {
            'query': query,
            'start': start_time.isoformat() + 'Z',
            'end': end_time.isoformat() + 'Z',
            'limit': limit
        }
        
        try:
            response = requests.get(
                url,
                params=params,
                headers=self.get_headers(),
                auth=self.get_auth(),
                verify=self.verify_ssl
            )
            response.raise_for_status()
            data = response.json()
            
            logs = []
            for stream in data.get('data', {}).get('result', []):
                labels = stream.get('stream', {})
                for value in stream.get('values', []):
                    timestamp = datetime.fromtimestamp(float(value[0])/1e9)
                    message = value[1]
                    
                    # Extract log level and service from message
                    level_match = re.search(r'(ERROR|WARNING|INFO|DEBUG|CRITICAL)', message)
                    service_match = re.search(r'services\.(\w+)', message)
                    
                    log_entry = {
                        'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        'message': message,
                        'level': level_match.group(1).lower() if level_match else 'info',
                        'service': service_match.group(1) if service_match else labels.get('service', 'unknown'),
                        'labels': labels
                    }
                    logs.append(log_entry)
            
            return logs
        except requests.exceptions.RequestException as e:
            if isinstance(e, requests.exceptions.ConnectionError):
                raise Exception(f"Failed to connect to Loki at {self.base_url}. Please check if Loki is running and accessible.")
            elif isinstance(e, requests.exceptions.HTTPError):
                if e.response.status_code == 401:
                    raise Exception("Authentication failed. Please check your Loki credentials.")
                else:
                    raise Exception(f"HTTP error occurred: {str(e)}")
            else:
                raise Exception(f"An error occurred while querying Loki: {str(e)}")
    
    def test_connection(self) -> bool:
        """Test the connection to Loki."""
        try:
            url = urljoin(self.base_url, "/loki/api/v1/labels")
            response = requests.get(
                url,
                headers=self.get_headers(),
                auth=self.get_auth(),
                verify=self.verify_ssl
            )
            response.raise_for_status()
            return True
        except:
            return False

    def fetch_logs(self, time_range: str, query: str = '{job="application"}') -> List[Dict]:
        """Fetch logs from Loki based on time range."""
        end_time = datetime.utcnow()
        
        if time_range == 'Last 24 hours':
            start_time = end_time - timedelta(hours=24)
        elif time_range == 'Last 7 days':
            start_time = end_time - timedelta(days=7)
        elif time_range == 'Last 30 days':
            start_time = end_time - timedelta(days=30)
        else:  # Default to last hour
            start_time = end_time - timedelta(hours=1)
        
        return self.query_range(query, start_time, end_time) 