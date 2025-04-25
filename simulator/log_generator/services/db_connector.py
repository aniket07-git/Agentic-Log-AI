# services/db_connector.py
import logging
import random
import time

logger = logging.getLogger(__name__)

class DatabaseConnector:
    def __init__(self):
        self._connection_healthy = True

    def query(self, sql):
        """Simulates executing a database query."""
        logger.debug(f"Executing query: {sql[:50]}...") # Log truncated query
        time.sleep(random.uniform(0.01, 0.06)) # Simulate work

        # Simulate pattern anomaly (burst of connection errors)
        if not self._connection_healthy:
             if random.random() < 0.8: # High chance of error if connection unhealthy
                 logger.error("Database connection error during query execution.")
                 return None
             else: # Chance to recover
                 self._connection_healthy = True
                 logger.info("Database connection restored.")

        # Simulate occasional random connection issues
        if random.random() < 0.015: # 1.5% chance of connection error
            logger.error("Lost database connection unexpectedly.")
            self._connection_healthy = False # Trigger potential burst
            return None

        logger.info("Query executed successfully.")
        return [{'result_col': random.randint(1, 100)}]

    def check_connection(self):
        """Simulates checking the DB connection status."""
        if not self._connection_healthy and random.random() < 0.3: # 30% chance to recover if unhealthy
            self._connection_healthy = True
            logger.info("Database connection check successful: Connection restored.")
            return True
        elif self._connection_healthy:
             logger.debug("Database connection check successful: Connection healthy.")
             return True
        else:
             logger.warning("Database connection check failed: Still unhealthy.")
             return False
