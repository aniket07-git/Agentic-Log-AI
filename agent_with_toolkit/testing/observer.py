import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class SimpleLogFileHandler(FileSystemEventHandler):
    """Simple handler for log file creation and modification events"""
    
    def __init__(self, callback=None):
        self.callback = callback
    
    def on_created(self, event):
        """Called when a file is created"""
        if not event.is_directory and self._is_log_file(event.src_path):
            print(f"Log file created: {event.src_path}")
            if self.callback:
                self.callback('created', event.src_path)
    
    def on_modified(self, event):
        """Called when a file is modified"""
        if not event.is_directory and self._is_log_file(event.src_path):
            print(f"Log file modified: {event.src_path}")
            if self.callback:
                self.callback('modified', event.src_path)
    
    def _is_log_file(self, path):
        """Check if the file is a log file based on extension"""
        log_extensions = ['.log', '.txt', '.out']
        _, ext = os.path.splitext(path)
        return ext.lower() in log_extensions

class SimpleLogObserver:
    """Class to observe log file creation and modification"""
    
    def __init__(self, paths=None, callback=None):
        self.paths = paths or ['.']
        self.observer = Observer()
        self.handler = SimpleLogFileHandler(callback=callback)
        self.running = False
    
    def start(self):
        """Start monitoring the specified directories"""
        if self.running:
            return
            
        for path in self.paths:
            if os.path.exists(path):
                self.observer.schedule(self.handler, path, recursive=True)
            else:
                print(f"Warning: Path {path} does not exist")
        
        self.observer.start()
        self.running = True
        print(f"Log observer started. Monitoring directories: {', '.join(self.paths)}")
    
    def stop(self):
        """Stop monitoring"""
        if self.running:
            self.observer.stop()
            self.observer.join()
            self.running = False
            print("Log observer stopped")

# Example usage
if __name__ == "__main__":
    def log_callback(event_type, file_path):
        print(f"{event_type.capitalize()} log file: {file_path}")
    
    # Create observer to monitor the current directory
    observer = SimpleLogObserver(paths=['.'], callback=log_callback)
    
    try:
        observer.start()
        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    finally:
        observer.stop()