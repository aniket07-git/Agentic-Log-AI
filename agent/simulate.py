# simulate.py
import logging
import random
import time
import sys
from datetime import datetime

# Import service classes
from services.user_service import UserService
from services.payment_service import PaymentService
from services.db_connector import DatabaseConnector
from services.network_client import NetworkClient

# --- Configuration ---
LOG_FILENAME = 'simulated_system.log'
SIMULATION_DURATION_SECONDS = 60 # Run for 60 seconds
LOG_LEVEL = logging.DEBUG # Set to INFO for less verbose logs, DEBUG for more detail
MAX_LOG_VOLUME_APPROX = 50000 # Target approx log lines (adjust duration/intensity)
INTENSITY_FACTOR = 10 # Higher number means more operations per second

# --- Logging Setup ---
def setup_logging():
    """Configures the root logger."""
    logging.basicConfig(
        level=LOG_LEVEL,
        format='%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S,%f', # Added milliseconds
        filename=LOG_FILENAME,
        filemode='w' # Overwrite log file on each run
    )
    # Optional: Add a handler to also print logs to console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL) # Or set a different level for console
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S,%f')
    console_handler.setFormatter(formatter)
    # logging.getLogger().addHandler(console_handler) # Uncomment to see logs in console too

# --- Simulation Logic ---
def run_simulation(duration_seconds, intensity):
    """Runs the system simulation."""
    setup_logging()
    logger = logging.getLogger(__name__) # Get logger for the main script
    logger.info(f"Starting simulation for {duration_seconds} seconds with intensity {intensity}...")

    # Instantiate services
    user_svc = UserService()
    payment_svc = PaymentService()
    db_conn = DatabaseConnector()
    net_client = NetworkClient()

    start_time = time.time()
    operations_count = 0

    while time.time() - start_time < duration_seconds:
        # Simulate a burst of activity based on intensity
        for _ in range(intensity):
            operation = random.choice([
                'get_user', 'update_profile', 'process_payment',
                'refund_payment', 'db_query', 'db_check', 'network_request'
            ])
            operations_count += 1

    user_svc.update_profile(random.randint(1000, 5000), {'pref': random.choice(['option1', 'option2', 'option3'])})

if __name__ == "__main__":
    # Adjust duration and intensity here if needed
    run_simulation(SIMULATION_DURATION_SECONDS, INTENSITY_FACTOR)

