#!/usr/bin/env python3
"""
Advanced Logging System for IBKR Premarket Trader

🎯 Features:
- Structured logging with class/method context
- Dynamic log level configuration
- Separate log files by component
- IBKR message logging
- Performance metrics
- Error tracking with stack traces
- JSON structured logs for analysis

🔧 Log Levels:
- TRACE: Ultra-detailed (method entry/exit, variables)
- DEBUG: Development debugging
- INFO: General information
- WARNING: Potential issues
- ERROR: Errors that don't stop execution
- CRITICAL: Fatal errors that stop execution

📂 Log Structure:
logs/
├── main/
│   ├── trading_YYYY-MM-DD.log
│   ├── trading_YYYY-MM-DD.json
├── ibkr/
│   ├── messages_YYYY-MM-DD.log
│   ├── orders_YYYY-MM-DD.log
├── performance/
│   ├── metrics_YYYY-MM-DD.log
└── errors/
    ├── errors_YYYY-MM-DD.log
"""

import logging
import logging.config
import json
import os
import sys
import traceback
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
from functools import wraps
from pathlib import Path
import time

class ContextualLogger:
    """Logger with automatic class/method context"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._context_stack = threading.local()
    
    def _get_caller_info(self, depth: int = 3):
        """Extract caller class and method information"""
        try:
            frame = sys._getframe(depth)
            filename = os.path.basename(frame.f_code.co_filename)
            method_name = frame.f_code.co_name
            line_number = frame.f_lineno
            
            # Try to get class name from frame locals
            class_name = None
            if 'self' in frame.f_locals:
                class_name = frame.f_locals['self'].__class__.__name__
            elif 'cls' in frame.f_locals:
                class_name = frame.f_locals['cls'].__name__
            
            context = f"{filename}"
            if class_name:
                context += f":{class_name}"
            context += f":{method_name}:{line_number}"
            
            return context
        except:
            return "unknown_context"
    
    def _log_with_context(self, level: int, msg: str, *args, **kwargs):
        """Log with automatic context"""
        context = self._get_caller_info()
        extra = kwargs.get('extra', {})
        extra.update({
            'context': context,
            'custom_thread_info': threading.current_thread().name,
            'timestamp_ms': int(time.time() * 1000)
        })
        kwargs['extra'] = extra
        self.logger.log(level, msg, *args, **kwargs)
    
    def trace(self, msg: str, *args, **kwargs):
        """Ultra-detailed logging"""
        self._log_with_context(5, f"TRACE: {msg}", *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        """Debug level logging"""
        self._log_with_context(logging.DEBUG, f"DEBUG: {msg}", *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        """Info level logging"""
        self._log_with_context(logging.INFO, f"INFO: {msg}", *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        """Warning level logging"""
        self._log_with_context(logging.WARNING, f"WARN: {msg}", *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        """Error level logging"""
        self._log_with_context(logging.ERROR, f"ERROR: {msg}", *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        """Critical level logging"""
        self._log_with_context(logging.CRITICAL, f"CRITICAL: {msg}", *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        """Log exception with stack trace"""
        exc_info = sys.exc_info()
        if exc_info[0] is not None:
            stack_trace = ''.join(traceback.format_exception(*exc_info))
            kwargs['extra'] = kwargs.get('extra', {})
            kwargs['extra']['stack_trace'] = stack_trace
        self.error(f"EXCEPTION: {msg}", *args, **kwargs)

class IBKRMessageLogger:
    """Specialized logger for IBKR messages and events"""
    
    def __init__(self):
        self.logger = ContextualLogger('ibkr.messages')
        self.order_logger = ContextualLogger('ibkr.orders')
        self.connection_logger = ContextualLogger('ibkr.connection')
    
    def log_message(self, msg_type: str, msg_data: Any, direction: str = "received"):
        """Log IBKR API message"""
        self.logger.info(f"IBKR {direction.upper()}: {msg_type}", extra={
            'msg_type': msg_type,
            'msg_data': str(msg_data),
            'direction': direction
        })
    
    def log_order_event(self, order_id: int, event: str, details: Dict):
        """Log order-specific events"""
        self.order_logger.info(f"ORDER {event}: #{order_id}", extra={
            'order_id': order_id,
            'event': event,
            'details': details
        })
    
    def log_connection_event(self, event: str, details: Dict):
        """Log connection events"""
        self.connection_logger.info(f"CONNECTION {event}", extra={
            'event': event,
            'details': details
        })
    
    def log_market_data(self, symbol: str, data: Dict):
        """Log market data updates"""
        self.logger.debug(f"MARKET_DATA {symbol}", extra={
            'symbol': symbol,
            'market_data': data
        })

class PerformanceLogger:
    """Performance metrics logging"""
    
    def __init__(self):
        self.logger = ContextualLogger('performance')
        self._timers = {}
    
    def start_timer(self, operation: str) -> str:
        """Start performance timer"""
        timer_id = f"{operation}_{int(time.time() * 1000)}"
        self._timers[timer_id] = {
            'operation': operation,
            'start_time': time.time(),
            'start_timestamp': datetime.now().isoformat()
        }
        return timer_id
    
    def end_timer(self, timer_id: str, details: Optional[Dict] = None):
        """End performance timer and log duration"""
        if timer_id in self._timers:
            timer_data = self._timers[timer_id]
            duration = time.time() - timer_data['start_time']
            
            self.logger.info(f"PERFORMANCE: {timer_data['operation']} completed in {duration:.3f}s", extra={
                'operation': timer_data['operation'],
                'duration_seconds': duration,
                'duration_ms': int(duration * 1000),
                'details': details or {}
            })
            
            del self._timers[timer_id]

class BackwardCompatibleFormatter(logging.Formatter):
    """Formatter that handles both contextual and regular log records"""
    
    def format(self, record):
        # Add context field if it doesn't exist
        if not hasattr(record, 'context'):
            record.context = f"{record.filename}:{record.funcName}:{record.lineno}"
        
        return super().format(record)

class StructuredJsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def _make_json_safe(self, obj):
        """Recursively make an object JSON serializable"""
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        elif isinstance(obj, dict):
            return {k: self._make_json_safe(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_json_safe(item) for item in obj]
        else:
            # Convert non-serializable objects to string
            return str(obj)
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'logger': record.name
        }
        
        # Add context information
        if hasattr(record, 'context'):
            log_data['context'] = record.context
        else:
            log_data['context'] = f"{record.filename}:{record.funcName}:{record.lineno}"
            
        if hasattr(record, 'custom_thread_info'):
            log_data['thread_info'] = record.custom_thread_info
        if hasattr(record, 'timestamp_ms'):
            log_data['timestamp_ms'] = record.timestamp_ms
        
        # Add any extra fields (make them JSON safe)
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'context', 'timestamp_ms', 'custom_thread_info']:
                try:
                    log_data[key] = self._make_json_safe(value)
                except Exception as e:
                    log_data[key] = f"<serialization-error: {str(e)}>"
        
        try:
            return json.dumps(log_data)
        except Exception as e:
            # Fallback to simple format if JSON fails
            return f"{log_data['timestamp']} | {log_data['level']} | {log_data['context']} | {log_data['message']}"

class AdvancedLogger:
    """Main logger configuration and management"""
    
    def __init__(self, base_dir: str = "logs"):
        self.base_dir = Path(base_dir)
        self.current_level = logging.INFO
        self._setup_directories()
        self._setup_logging()
        
        # Specialized loggers
        self.ibkr = IBKRMessageLogger()
        self.performance = PerformanceLogger()
    
    def _setup_directories(self):
        """Create logging directory structure"""
        directories = [
            self.base_dir / "main",
            self.base_dir / "ibkr", 
            self.base_dir / "performance",
            self.base_dir / "errors"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _setup_logging(self):
        """Setup comprehensive logging configuration"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Custom log level for TRACE
        logging.addLevelName(5, "TRACE")
        
        config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'detailed': {
                    '()': BackwardCompatibleFormatter,
                    'format': '%(asctime)s | %(levelname)-8s | %(context)-40s | %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                'simple': {
                    'format': '%(asctime)s | %(levelname)-8s | %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                'json': {
                    '()': StructuredJsonFormatter
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'level': 'WARNING',
                    'formatter': 'simple',
                    'stream': 'ext://sys.stdout'
                },
                'main_file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'INFO',
                    'formatter': 'detailed',
                    'filename': str(self.base_dir / "main" / f"trading_{today}.log"),
                    'maxBytes': 10485760,  # 10MB
                    'backupCount': 5
                },
                'main_json': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'DEBUG',
                    'formatter': 'json',
                    'filename': str(self.base_dir / "main" / f"trading_{today}.json"),
                    'maxBytes': 10485760,  # 10MB
                    'backupCount': 5
                },
                'ibkr_messages': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'DEBUG',
                    'formatter': 'detailed',
                    'filename': str(self.base_dir / "ibkr" / f"messages_{today}.log"),
                    'maxBytes': 10485760,
                    'backupCount': 5
                },
                'ibkr_orders': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'DEBUG',
                    'formatter': 'detailed', 
                    'filename': str(self.base_dir / "ibkr" / f"orders_{today}.log"),
                    'maxBytes': 10485760,
                    'backupCount': 5
                },
                'performance': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'INFO',
                    'formatter': 'detailed',
                    'filename': str(self.base_dir / "performance" / f"metrics_{today}.log"),
                    'maxBytes': 10485760,
                    'backupCount': 5
                },
                'errors': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'ERROR',
                    'formatter': 'detailed',
                    'filename': str(self.base_dir / "errors" / f"errors_{today}.log"),
                    'maxBytes': 10485760,
                    'backupCount': 5
                }
            },
            'loggers': {
                '': {  # Root logger
                    'handlers': ['console', 'main_file', 'main_json', 'errors'],
                    'level': 'DEBUG',
                    'propagate': False
                },
                'ibkr.messages': {
                    'handlers': ['ibkr_messages', 'main_json'],
                    'level': 'DEBUG',
                    'propagate': False
                },
                'ibkr.orders': {
                    'handlers': ['ibkr_orders', 'main_json'],
                    'level': 'DEBUG',
                    'propagate': False
                },
                'ibkr.connection': {
                    'handlers': ['ibkr_messages', 'main_json'],
                    'level': 'DEBUG', 
                    'propagate': False
                },
                'performance': {
                    'handlers': ['performance', 'main_json'],
                    'level': 'DEBUG',
                    'propagate': False
                }
            }
        }
        
        logging.config.dictConfig(config)
    
    def set_level(self, level: Union[str, int]):
        """Dynamically change log level"""
        if isinstance(level, str):
            level = getattr(logging, level.upper())
        
        self.current_level = level
        
        # Update all handlers
        for handler in logging.root.handlers:
            if handler.name != 'console':  # Keep console at WARNING
                handler.setLevel(level)
        
        print(f"📊 Log level changed to: {logging.getLevelName(level)}")
    
    def get_logger(self, name: str) -> ContextualLogger:
        """Get contextual logger for a specific component"""
        return ContextualLogger(name)

def log_method_calls(logger: ContextualLogger):
    """Decorator to automatically log method entry/exit"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            method_name = func.__name__
            class_name = ""
            if args and hasattr(args[0], '__class__'):
                class_name = f"{args[0].__class__.__name__}."
            
            logger.trace(f"→ ENTER {class_name}{method_name}")
            
            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.trace(f"← EXIT {class_name}{method_name} ({duration:.3f}s)")
                return result
            except Exception as e:
                logger.exception(f"✗ EXCEPTION in {class_name}{method_name}: {e}")
                raise
        
        return wrapper
    return decorator

# Global logger instance
_advanced_logger = None

def get_logger(name: str = None) -> ContextualLogger:
    """Get global logger instance"""
    global _advanced_logger
    if _advanced_logger is None:
        _advanced_logger = AdvancedLogger()
    
    if name:
        return _advanced_logger.get_logger(name)
    else:
        return _advanced_logger.get_logger('main')

def set_log_level(level: Union[str, int]):
    """Set global log level"""
    global _advanced_logger
    if _advanced_logger is None:
        _advanced_logger = AdvancedLogger()
    
    _advanced_logger.set_level(level)

def get_ibkr_logger() -> IBKRMessageLogger:
    """Get IBKR specialized logger"""
    global _advanced_logger
    if _advanced_logger is None:
        _advanced_logger = AdvancedLogger()
    
    return _advanced_logger.ibkr

def get_performance_logger() -> PerformanceLogger:
    """Get performance logger"""
    global _advanced_logger
    if _advanced_logger is None:
        _advanced_logger = AdvancedLogger()
    
    return _advanced_logger.performance

# Example usage
if __name__ == "__main__":
    # Demo the logging system
    logger = get_logger("demo")
    ibkr_logger = get_ibkr_logger()
    perf_logger = get_performance_logger()
    
    logger.info("Advanced logging system initialized")
    logger.debug("This is a debug message")
    logger.warning("This is a warning")
    
    # Test IBKR logging
    ibkr_logger.log_message("orderStatus", {"orderId": 123, "status": "Filled"})
    ibkr_logger.log_order_event(123, "FILLED", {"price": 10.50, "quantity": 100})
    
    # Test performance logging
    timer_id = perf_logger.start_timer("test_operation")
    time.sleep(0.1)
    perf_logger.end_timer(timer_id, {"result": "success"})
    
    # Test level changes
    set_log_level("DEBUG")
    logger.debug("Now you can see debug messages!")
    
    set_log_level("TRACE")
    logger.trace("Ultra detailed trace message")
    
    print("✅ Advanced logging demo completed!")
    print("📂 Check logs/ directory for output files")