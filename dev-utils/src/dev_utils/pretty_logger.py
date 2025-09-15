"""
Pretty Logger Module for Development Utils

This module provides beautiful, colorful logging with emojis and structured formatting
for development and production environments. It can replace boring JSON logs with
human-readable, visually appealing output.

Usage:
    from dev_utils.pretty_logger import PrettyLogger, log_success, log_error, log_info
    
    # Simple usage
    log_success("Operation completed successfully!")
    log_error("Something went wrong")
    log_info("Processing data...")
    
    # Advanced usage with context
    logger = PrettyLogger("my-service")
    logger.step("Starting synchronization", step=1, total=5)
    logger.metric("Records processed", value=1500, unit="records")
    logger.progress("Uploading", current=75, total=100)

Author: Bastian Ibañez
"""

import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
from enum import Enum


class LogLevel(Enum):
    """Log levels with associated colors and emojis"""
    DEBUG = ("DEBUG", "🐛", "\033[90m")      # Gray
    INFO = ("INFO", "ℹ️", "\033[94m")         # Blue
    SUCCESS = ("SUCCESS", "✅", "\033[92m")  # Green
    WARNING = ("WARNING", "⚠️", "\033[93m")   # Yellow
    ERROR = ("ERROR", "❌", "\033[91m")      # Red
    CRITICAL = ("CRITICAL", "🔥", "\033[95m") # Magenta


@dataclass
class LogColors:
    """ANSI color codes for terminal output"""
    # Basic colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'
    
    # Background colors
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'


class PrettyLogger:
    """
    Beautiful logging class with colors, emojis, and structured formatting
    """
    
    def __init__(self, service_name: str = __name__, enable_colors: bool = True,
                 enable_timestamps: bool = True, min_level: LogLevel = LogLevel.INFO):
        self.service_name = service_name
        self.enable_colors = enable_colors and self._supports_color()
        self.enable_timestamps = enable_timestamps
        self.min_level = min_level
        self.start_time = time.time()

        # Track progress and context
        self._current_step = 0
        self._total_steps = 0
        self._context = {}
        # Progress line management
        self._active_progress_id: Optional[str] = None
        self._progress_text_by_id: Dict[str, str] = {}
    
    def _supports_color(self) -> bool:
        """Check if terminal supports color output"""
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    
    def _format_timestamp(self) -> str:
        """Format current timestamp"""
        if not self.enable_timestamps:
            return ""
        return datetime.now().strftime("%H:%M:%S")
    
    def _format_duration(self, start_time: float = None) -> str:
        """Format elapsed time since start or given time"""
        elapsed = time.time() - (start_time or self.start_time)
        if elapsed < 60:
            return f"{elapsed:.1f}s"
        elif elapsed < 3600:
            return f"{elapsed/60:.1f}m"
        else:
            return f"{elapsed/3600:.1f}h"
    
    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled"""
        if not self.enable_colors:
            return text
        return f"{color}{text}{LogColors.RESET}"
    
    def _should_log(self, level: LogLevel) -> bool:
        """Check if message should be logged based on min_level"""
        levels_order = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.SUCCESS, 
                       LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL]
        return levels_order.index(level) >= levels_order.index(self.min_level)
    
    def _log(self, level: LogLevel, message: str, **kwargs):
        """Core logging method"""
        if not self._should_log(level):
            return
        
        # If a progress bar is active, clear it temporarily
        if self._active_progress_id is not None and self._supports_color():
            # Move to line start and clear line
            print("\r\033[2K", end="", flush=True)

        level_name, emoji, color = level.value
        timestamp = self._format_timestamp()
        
        # Build log line
        parts = []
        
        if timestamp:
            parts.append(self._colorize(timestamp, LogColors.DIM))
        
        # Service name with color
        service = self._colorize(f"[{self.service_name}]", LogColors.CYAN)
        parts.append(service)
        
        # Level with emoji and color
        level_str = f"{emoji} {level_name}"
        if self.enable_colors:
            level_str = self._colorize(level_str, color)
        parts.append(level_str)
        
        # Main message
        if self.enable_colors and level in [LogLevel.SUCCESS, LogLevel.ERROR, LogLevel.WARNING]:
            message = self._colorize(message, color)
        parts.append(message)
        
        # Add context if provided
        if kwargs:
            context_parts = []
            for key, value in kwargs.items():
                if key.startswith('_'):  # Skip internal keys
                    continue
                context_parts.append(f"{key}={value}")
            if context_parts:
                context = self._colorize(f"({', '.join(context_parts)})", LogColors.DIM)
                parts.append(context)
        
        # Print the formatted line
        print(" ".join(parts))

        # Re-render the active progress bar at the bottom
        if self._active_progress_id is not None and self._supports_color():
            text = self._progress_text_by_id.get(self._active_progress_id)
            if text:
                print(f"\r{text}", end="", flush=True)
    
    # Basic logging methods
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log(LogLevel.INFO, message, **kwargs)
    
    def success(self, message: str, **kwargs):
        """Log success message"""
        self._log(LogLevel.SUCCESS, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self._log(LogLevel.CRITICAL, message, **kwargs)
    
    # Special formatting methods
    def header(self, title: str, char: str = "=", width: int = 60):
        """Print a formatted header"""
        border = char * width
        title_line = f" {title} ".center(width, char)
        
        print()
        print(self._colorize(border, LogColors.BRIGHT_BLUE))
        print(self._colorize(title_line, LogColors.BRIGHT_BLUE + LogColors.BOLD))
        print(self._colorize(border, LogColors.BRIGHT_BLUE))
        print()
    
    def step(self, message: str, step: int = None, total: int = None, **kwargs):
        """Log a step in a process"""
        if step is not None:
            self._current_step = step
        if total is not None:
            self._total_steps = total
        
        if self._total_steps > 0:
            progress = f"[{self._current_step}/{self._total_steps}]"
            progress = self._colorize(progress, LogColors.BRIGHT_CYAN)
            message = f"{progress} {message}"
        
        self._log(LogLevel.INFO, f"🚀 {message}", **kwargs)
    
    def metric(self, name: str, value: Union[int, float], unit: str = "", **kwargs):
        """Log a metric with formatting"""
        if isinstance(value, float):
            value_str = f"{value:,.2f}"
        else:
            value_str = f"{value:,}"
        
        if unit:
            value_str += f" {unit}"
        
        metric_text = f"{name}: {self._colorize(value_str, LogColors.BRIGHT_GREEN)}"
        self._log(LogLevel.INFO, f"📊 {metric_text}", **kwargs)
    
    def progress(self, name: str, current: int, total: int, progress_id: Optional[str] = None, **kwargs):
        """Render or update a single persistent progress bar for this logger.

        - If a progress bar with the same progress_id is active, update it in place.
        - If a different bar is active, finalize it and start a new one.
        - If not a TTY/ANSI environment, fallback to regular log lines.
        """
        # Compute text
        safe_total = max(total, 1)
        percentage = (current / safe_total) * 100
        bar_width = 20
        filled = int(bar_width * current / safe_total)
        bar = "█" * filled + "░" * (bar_width - filled)
        pid = progress_id or name
        progress_text = f"⏳ {name}: {self._colorize(bar, LogColors.BRIGHT_GREEN)} {percentage:.1f}% ({current:,}/{total:,})"

        # Non-TTY: just print as a normal line
        if not self._supports_color():
            self._log(LogLevel.INFO, progress_text, **kwargs)
            return

        # If another bar is active and it's different, finalize previous with newline
        if self._active_progress_id is not None and self._active_progress_id != pid:
            # Clear previous active line and print its last state ended with newline
            prev_text = self._progress_text_by_id.get(self._active_progress_id)
            if prev_text:
                print("\r\033[2K" + prev_text)
            self._active_progress_id = None

        # Mark this bar as active and render in place
        self._active_progress_id = pid
        self._progress_text_by_id[pid] = progress_text

        # Clear current line and print without newline so it can be updated
        print(f"\r\033[2K{progress_text}", end="", flush=True)

        # If finished, add newline and deactivate
        if current >= total:
            print()  # newline to finalize the bar
            self._active_progress_id = None
    
    def duration(self, message: str, start_time: float = None, **kwargs):
        """Log a message with duration"""
        duration = self._format_duration(start_time)
        duration_colored = self._colorize(f"({duration})", LogColors.DIM)
        self._log(LogLevel.INFO, f"⏱️  {message} {duration_colored}", **kwargs)
    
    def separator(self, char: str = "-", width: int = 60):
        """Print a separator line"""
        line = char * width
        print(self._colorize(line, LogColors.DIM))
    
    def table(self, data: Dict[str, Any], title: str = None):
        """Print data in a simple table format"""
        if title:
            self.info(f"📋 {title}")
        
        max_key_len = max(len(str(k)) for k in data.keys()) if data else 0
        
        for key, value in data.items():
            key_colored = self._colorize(f"{key:<{max_key_len}}", LogColors.CYAN)
            if isinstance(value, (int, float)):
                value_colored = self._colorize(str(value), LogColors.BRIGHT_GREEN)
            else:
                value_colored = str(value)
            
            print(f"  {key_colored} : {value_colored}")
    
    def json_pretty(self, data: Dict[str, Any], title: str = None):
        """Print JSON data in a pretty format (fallback for when data is complex)"""
        if title:
            self.info(f"📋 {title}")
        
        import json
        try:
            formatted = json.dumps(data, indent=2, default=str)
            for line in formatted.split('\n'):
                print(f"  {self._colorize(line, LogColors.DIM)}")
        except Exception:
            self.table(data, title)
    
    def loading(self, message: str, duration: float = 0.5):
        """Show a loading animation"""
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        
        for _ in range(int(duration * 10)):
            for frame in frames:
                print(f"\r{self._colorize(frame, LogColors.BRIGHT_CYAN)} {message}", end="", flush=True)
                time.sleep(0.1)
        print(f"\r{self._colorize('✅', LogColors.BRIGHT_GREEN)} {message}")


# Global convenience functions
_default_logger = PrettyLogger(__name__)

def set_default_service(service_name: str):
    """Set the default service name for convenience functions"""
    global _default_logger
    _default_logger = PrettyLogger(service_name)

def log_debug(message: str, **kwargs):
    """Log debug message using default logger"""
    _default_logger.debug(message, **kwargs)

def log_info(message: str, **kwargs):
    """Log info message using default logger"""
    _default_logger.info(message, **kwargs)

def log_success(message: str, **kwargs):
    """Log success message using default logger"""
    _default_logger.success(message, **kwargs)

def log_warning(message: str, **kwargs):
    """Log warning message using default logger"""
    _default_logger.warning(message, **kwargs)

def log_error(message: str, **kwargs):
    """Log error message using default logger"""
    _default_logger.error(message, **kwargs)

def log_critical(message: str, **kwargs):
    """Log critical message using default logger"""
    _default_logger.critical(message, **kwargs)

def log_step(message: str, step: int = None, total: int = None, **kwargs):
    """Log step using default logger"""
    _default_logger.step(message, step, total, **kwargs)

def log_metric(name: str, value: Union[int, float], unit: str = "", **kwargs):
    """Log metric using default logger"""
    _default_logger.metric(name, value, unit, **kwargs)

def log_progress(name: str, current: int, total: int, **kwargs):
    """Log progress using default logger"""
    _default_logger.progress(name, current, total, **kwargs)

def log_header(title: str, char: str = "=", width: int = 60):
    """Print header using default logger"""
    _default_logger.header(title, char, width)

def log_table(data: Dict[str, Any], title: str = None):
    """Print table using default logger"""
    _default_logger.table(data, title)


# Context manager for timing operations
class timer:
    """Context manager for timing operations with pretty logging"""
    
    def __init__(self, message: str, logger: PrettyLogger = None):
        self.message = message
        self.logger = logger or _default_logger
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(f"🏁 Starting {self.message}...")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.logger.duration(f"Completed {self.message}", self.start_time)
        else:
            self.logger.error(f"Failed {self.message}", error=str(exc_val))


# Demo function
def demo():
    """Demonstrate the pretty logger capabilities"""
    logger = PrettyLogger(__name__)
    
    logger.header("Pretty Logger Demo")
    
    logger.step("Initializing system", 1, 4)
    time.sleep(0.5)
    
    logger.step("Loading configuration", 2, 4)
    logger.info("Configuration loaded successfully")
    
    logger.step("Connecting to database", 3, 4)
    logger.success("Database connection established", host="localhost", port=5432)
    
    logger.step("Starting sync process", 4, 4)
    
    logger.metric("Records processed", 1500, "records")
    logger.metric("Processing speed", 250.5, "records/sec")
    
    logger.progress("Uploading data", 75, 100)
    logger.progress("Uploading data", 100, 100)
    
    logger.table({
        "Total Records": 1500,
        "Success Rate": "99.8%",
        "Duration": "6.2s",
        "Errors": 3
    }, "Sync Summary")
    
    logger.warning("Some records had validation warnings", count=3)
    logger.success("Synchronization completed successfully!")
    
    logger.separator()
    logger.info("Demo completed")


if __name__ == "__main__":
    demo() 