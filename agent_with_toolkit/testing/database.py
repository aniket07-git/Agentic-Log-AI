import json
import os
import logging
import datetime
import random
import traceback
import sys

# Configure logging with enhanced format (file path and line numbers)
LOG_FILE = "database_errors.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] [%(pathname)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class DatabaseError(Exception):
    """Custom exception for database errors"""
    pass

class Database:
    def __init__(self, db_file="database.json"):
        """Initialize database with a file path"""
        self.db_file = db_file
        self.data = {}
        self.load_data()
    
    def load_data(self):
        """Load data from the database file"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r') as f:
                    self.data = json.load(f)
            else:
                self.data = {}
                self.save_data()  # Create the file
        except json.JSONDecodeError as e:
            error_msg = f"Failed to decode JSON in database file: {str(e)}"
            logging.error(error_msg, exc_info=True)  # Include traceback
            # Simulating corrupt data error
            if random.random() < 0.2:  # 20% chance of corruption simulation
                self.data = {"_corrupted": True}
            else:
                self.data = {}
            raise DatabaseError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error loading database: {str(e)}"
            logging.error(error_msg, exc_info=True)  # Include traceback
            raise DatabaseError(error_msg)
    
    def save_data(self):
        """Save data to the database file"""
        try:
            # Simulate occasional write failure
            if random.random() < 0.1:  # 10% chance of write failure
                error_msg = "Simulated disk write failure"
                logging.error(error_msg)
                # Create an artificial exception to get a traceback
                try:
                    raise IOError(error_msg)
                except IOError as e:
                    logging.error(f"Traceback for disk write failure:", exc_info=True)
                    raise e
                
            with open(self.db_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except IOError as e:
            error_msg = f"Failed to write to database file: {str(e)}"
            logging.error(error_msg, exc_info=True)  # Include traceback
            raise DatabaseError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error saving database: {str(e)}"
            logging.error(error_msg, exc_info=True)  # Include traceback
            raise DatabaseError(error_msg)
    
    def create(self, collection, item_id, data):
        """Create an item in a collection"""
        try:
            # Validate input
            if not isinstance(collection, str) or not collection:
                error_msg = f"Invalid collection name: {collection}"
                logging.error(error_msg, exc_info=True)
                raise ValueError(error_msg)
            
            if not isinstance(item_id, str) or not item_id:
                error_msg = f"Invalid item ID: {item_id}"
                logging.error(error_msg, exc_info=True)
                raise ValueError(error_msg)
            
            # Initialize collection if it doesn't exist
            if collection not in self.data:
                self.data[collection] = {}
            
            # Check if item already exists
            if item_id in self.data[collection]:
                error_msg = f"Item with ID {item_id} already exists in {collection}"
                logging.warning(error_msg, exc_info=True)
                raise DatabaseError(error_msg)
            
            # Store data with timestamp
            self.data[collection][item_id] = {
                "data": data,
                "created_at": datetime.datetime.now().isoformat(),
                "updated_at": datetime.datetime.now().isoformat()
            }
            
            self.save_data()
            return True
        except DatabaseError:
            # Re-raise database errors
            raise
        except Exception as e:
            error_msg = f"Error creating item {item_id} in {collection}: {str(e)}"
            logging.error(error_msg, exc_info=True)  # Include traceback
            raise DatabaseError(error_msg)
    
    def read(self, collection, item_id=None):
        """Read an item or all items from a collection"""
        try:
            # Validate collection
            if collection not in self.data:
                error_msg = f"Collection not found: {collection}"
                logging.warning(error_msg, exc_info=True)
                raise DatabaseError(error_msg)
            
            # Return specific item or all items
            if item_id is not None:
                if item_id not in self.data[collection]:
                    error_msg = f"Item not found: {item_id} in {collection}"
                    logging.warning(error_msg, exc_info=True)
                    raise DatabaseError(error_msg)
                return self.data[collection][item_id]["data"]
            else:
                return {id: item["data"] for id, item in self.data[collection].items()}
        except DatabaseError:
            # Re-raise database errors
            raise
        except Exception as e:
            error_msg = f"Error reading from {collection}: {str(e)}"
            logging.error(error_msg, exc_info=True)  # Include traceback
            raise DatabaseError(error_msg)
    
    def update(self, collection, item_id, data):
        """Update an item in a collection"""
        try:
            # Validate collection and item existence
            if collection not in self.data:
                error_msg = f"Collection not found: {collection}"
                logging.warning(error_msg, exc_info=True)
                raise DatabaseError(error_msg)
            
            if item_id not in self.data[collection]:
                error_msg = f"Item not found: {item_id} in {collection}"
                logging.warning(error_msg, exc_info=True)
                raise DatabaseError(error_msg)
            
            # Simulate random connection timeout
            if random.random() < 0.15:  # 15% chance of timeout
                error_msg = f"Simulated connection timeout while updating {item_id}"
                logging.error(error_msg)
                # Create artificial exception for traceback
                try:
                    raise TimeoutError(error_msg)
                except TimeoutError as e:
                    logging.error("Traceback for connection timeout:", exc_info=True)
                    raise DatabaseError(error_msg) from e
                
            # Update the item
            self.data[collection][item_id]["data"] = data
            self.data[collection][item_id]["updated_at"] = datetime.datetime.now().isoformat()
            
            self.save_data()
            return True
        except DatabaseError:
            # Re-raise database errors
            raise
        except Exception as e:
            error_msg = f"Error updating item {item_id} in {collection}: {str(e)}"
            logging.error(error_msg, exc_info=True)  # Include traceback
            raise DatabaseError(error_msg)
    
    def delete(self, collection, item_id):
        """Delete an item from a collection"""
        try:
            # Validate collection and item existence
            if collection not in self.data:
                error_msg = f"Collection not found: {collection}"
                logging.warning(error_msg, exc_info=True)
                raise DatabaseError(error_msg)
            
            if item_id not in self.data[collection]:
                error_msg = f"Item not found: {item_id} in {collection}"
                logging.warning(error_msg, exc_info=True)
                raise DatabaseError(error_msg)
            
            # Simulate permission error
            if random.random() < 0.12:  # 12% chance of permission error
                error_msg = f"Simulated permission denied for deleting {item_id}"
                # Create artificial exception for traceback
                try:
                    raise PermissionError(error_msg)
                except PermissionError as e:
                    logging.error(error_msg, exc_info=True)
                    raise DatabaseError(error_msg) from e
            
            # Delete the item
            del self.data[collection][item_id]
            
            # If collection is empty, remove it
            if not self.data[collection]:
                del self.data[collection]
                
            self.save_data()
            return True
        except PermissionError as e:
            error_msg = f"Permission error: {str(e)}"
            logging.error(error_msg, exc_info=True)  # Include traceback
            raise DatabaseError(error_msg)
        except DatabaseError:
            # Re-raise database errors
            raise
        except Exception as e:
            error_msg = f"Error deleting item {item_id} from {collection}: {str(e)}"
            logging.error(error_msg, exc_info=True)  # Include traceback
            raise DatabaseError(error_msg)
    
    def query(self, collection, filter_func=None):
        """Query items in a collection using a filter function"""
        try:
            # Validate collection
            if collection not in self.data:
                error_msg = f"Collection not found: {collection}"
                logging.warning(error_msg, exc_info=True)
                raise DatabaseError(error_msg)
            
            # No filter, return all
            if filter_func is None:
                return {id: item["data"] for id, item in self.data[collection].items()}
            
            # Apply filter
            try:
                result = {
                    id: item["data"] 
                    for id, item in self.data[collection].items() 
                    if filter_func(item["data"])
                }
                return result
            except Exception as e:
                error_msg = f"Filter function error: {str(e)}"
                logging.error(error_msg, exc_info=True)  # Include traceback
                raise DatabaseError(error_msg)
                
        except DatabaseError:
            # Re-raise database errors
            raise
        except Exception as e:
            error_msg = f"Error querying {collection}: {str(e)}"
            logging.error(error_msg, exc_info=True)  # Include traceback
            raise DatabaseError(error_msg)