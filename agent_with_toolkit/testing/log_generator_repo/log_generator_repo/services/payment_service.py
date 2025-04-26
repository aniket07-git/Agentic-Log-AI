# services/payment_service.py
import logging
import random
import time

logger = logging.getLogger(__name__)

class PaymentService:
    def process_payment(self, amount, user_id):
        """Simulates processing a payment."""
        start_time = time.time()
        logger.debug(f"Attempting payment of {amount} for user {user_id}")
        time.sleep(random.uniform(0.05, 0.15)) # Simulate work

        # Simulate occasional critical errors
        if random.random() < 0.03: # 3% chance of critical failure
            try:
                # Simulate a critical failure like NullPointerException
                config = None
                _ = config['api_key'] # Raises TypeError
            except Exception as e:
                logger.error(f"Critical failure during payment processing for user {user_id}", exc_info=True)
                return False
        # Simulate statistical anomaly (response time spike)
        elif random.random() < 0.05: # 5% chance of unusual delay
             time.sleep(random.uniform(0.5, 1.5)) # Add significant delay
             logger.warning(f"Unusual delay detected processing payment for user {user_id}")


        response_time = (time.time() - start_time) * 1000 # in ms
        logger.info(f"Payment of {amount} for user {user_id} processed successfully. Response time: {response_time:.2f} ms")
        return True

    def refund_payment(self, transaction_id):
        """Simulates refunding a payment."""
        logger.debug(f"Attempting refund for transaction {transaction_id}")
        time.sleep(random.uniform(0.03, 0.1)) # Simulate work
        logger.info(f"Refund for transaction {transaction_id} processed.")
        return True
