# services/user_service.py
import logging
import random
import time

logger = logging.getLogger(__name__)

class UserService:
    def get_user(self, user_id):
        """Simulates fetching user data."""
        start_time = time.time()
        logger.debug(f"Attempting to fetch user {user_id}")
        time.sleep(random.uniform(0.01, 0.05)) # Simulate work

        # Simulate occasional errors
        if random.random() < 0.02: # 2% chance of failure
            try:
                # Simulate a potential error source
                data = {'id': user_id, 'name': None}
                _ = data['name'].upper() # This will cause AttributeError if name is None
            except Exception as e:
                logger.error(f"Failed to process data for user {user_id}", exc_info=True)
                return None

        response_time = (time.time() - start_time) * 1000 # in ms
        logger.info(f"User {user_id} fetched successfully. Response time: {response_time:.2f} ms")
        return {'id': user_id, 'name': f'User_{user_id}'}

    def update_profile(self, user_id, data):
        """Simulates updating a user profile."""
        logger.debug(f"Attempting to update profile for user {user_id} with data: {data}")
        time.sleep(random.uniform(0.02, 0.08)) # Simulate work

        if random.random() < 0.01: # 1% chance of warning
            logger.warning(f"Profile update for user {user_id} took longer than expected.")

        logger.info(f"Profile for user {user_id} updated successfully.")
        return True

