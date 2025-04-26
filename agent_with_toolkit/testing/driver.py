
import time
import random
import os
from datetime import datetime

# Create logs directory if it doesn't exist
if not os.path.exists("logs"):
    os.makedirs("logs")

# Create or append to driver log file
with open("driver.log", "a") as log_file:
    log_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} INFO Driver simulation started\n")
    
    # Simulate some log entries
    for i in range(30):
        time.sleep(0.1)  # Small delay between entries
        log_type = random.choice(["INFO", "WARNING", "ERROR"])
        message = ""
        
        if log_type == "INFO":
            message = random.choice([
                "Connection established",
                "Data processed successfully",
                "User authenticated",
                "Config loaded",
                "Background task completed"
            ])
        elif log_type == "WARNING":
            message = random.choice([
                "High memory usage detected",
                "Response time exceeded threshold",
                "Rate limit approaching",
                "Deprecated API call detected",
                "Low disk space warning"
            ])
        else:  # ERROR
            message = random.choice([
                "Database connection failed",
                "Authentication error",
                "API request timeout",
                "Invalid input parameters",
                "Memory allocation failed"
            ])
            
            # Write serious errors to a separate error log
            if random.random() < 0.3:
                with open("database_errors.log", "a") as error_log:
                    error_log.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CRITICAL {message}\n")
        
        log_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {log_type} {message}\n")
        log_file.flush()  # Ensure it's written immediately
        
    log_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} INFO Driver simulation completed\n")

print("Driver simulation completed. Check driver.log and database_errors.log for details.")
