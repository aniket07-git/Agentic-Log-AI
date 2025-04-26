# services/network_client.py
import logging
import random
import time

logger = logging.getLogger(__name__)

class NetworkClient:
    def request(self, url):
        """Simulates making an external network request."""
        start_time = time.time()
        logger.debug(f"Making request to {url}")
        base_delay = random.uniform(0.02, 0.1)
        time.sleep(base_delay) # Simulate network latency

        # Simulate occasional timeouts
        if random.random() < 0.025: # 2.5% chance of timeout
            try:
                raise TimeoutError(f"Request to {url} timed out after {base_delay + 0.5:.2f}s")
            except TimeoutError as e:
                logger.error(f"TimeoutError making request to {url}", exc_info=True)
                return None
        # Simulate high latency warnings (statistical anomaly)
        elif random.random() < 0.08: # 8% chance of high latency
            extra_delay = random.uniform(0.2, 0.5)
            time.sleep(extra_delay)
            total_time = (time.time() - start_time) * 1000
            logger.warning(f"High latency detected for request to {url}. Response time: {total_time:.2f} ms")
            return {'status': 200, 'data': 'Success (but slow)'}


        response_time = (time.time() - start_time) * 1000 # in ms
        logger.info(f"Request to {url} completed successfully. Response time: {response_time:.2f} ms")
        return {'status': 200, 'data': 'Success'}
