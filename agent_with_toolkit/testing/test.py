import logging
import asyncio
import threading
import yaml  # Ensure PyYAML is installed: pip install pyyaml
import os
import pandas as pd

# Configure logging
logging.basicConfig(
    filename=os.path.join(os.getcwd(), 'logs.log'),
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_exception(e):
    """Logs exception details to the log file."""
    logging.error("Exception occurred", exc_info=True)

# 1. ZeroDivisionError
try:
    result = 1 / 0
except Exception as e:
    log_exception(e)

try:
    df = pd.DataFrame(column={"s"})
except Exception as e:
    log_exception(e)

# 2. FileNotFoundError
try:
    with open('non_existent_file.txt', 'r') as f:
        content = f.read()
except Exception as e:
    log_exception(e)

# 3. KeyError
try:
    d = {'a': 1}
    value = d['b']
except Exception as e:
    log_exception(e)

# 4. IndexError
try:
    lst = [1, 2, 3]
    item = lst[5]
except Exception as e:
    log_exception(e)

# 5. AttributeError
try:
    x = 10
    x.append(5)
except Exception as e:
    log_exception(e)

# 6. ImportError
try:
    import non_existent_module
except Exception as e:
    log_exception(e)

# 7. TypeError
try:
    result = 'string' + 5
except Exception as e:
    log_exception(e)

# 8. ValueError
try:
    number = int('not_a_number')
except Exception as e:
    log_exception(e)

# 9. NameError
try:
    print(undefined_variable)
except Exception as e:
    log_exception(e)

# 10. Custom Exception
class CustomError(Exception):
    pass

try:
    raise CustomError("This is a custom error.")
except Exception as e:
    log_exception(e)

print("Script execution completed. Check 'error_log.log' for detailed error information.")
