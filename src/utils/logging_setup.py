"""
Logging configuration for MCP RAGex server.

Provides environment-aware logging that:
- Uses stderr exclusively to avoid MCP protocol conflicts
- Outputs JSON in Docker environments
- Provides human-readable output for local development
- Supports log rotation for file-based logging
"""

import sys
import logging
import json
import os
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any


class DockerFormatter(logging.Formatter):
    """JSON formatter optimized for container logs"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON for container environments"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'component': record.name,
            'message': record.getMessage(),
            'pid': os.getpid(),
        }
        
        # Add any extra fields
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
            
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)


def configure_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_rotation: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    quiet_libraries: bool = True,
) -> None:
    """
    Configure logging based on environment.
    
    Args:
        log_level: Override log level (defaults to LOG_LEVEL env var or INFO)
        log_file: Path to log file (only used in non-Docker environments)
        enable_rotation: Enable log rotation for file handler
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        quiet_libraries: Suppress verbose third-party library logs
    """
    # Determine log level (RAGEX_LOG_LEVEL takes precedence over LOG_LEVEL)
    level = log_level or os.environ.get('RAGEX_LOG_LEVEL') or os.environ.get('LOG_LEVEL', 'WARN')
    
    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers = []
    
    # Detect Docker environment
    in_docker = (
        os.path.exists('/.dockerenv') or 
        os.environ.get('DOCKER_CONTAINER', '').lower() == 'true'
    )
    
    # Create appropriate handler
    if in_docker or os.environ.get('LOG_TO_STDERR', '').lower() == 'true':
        # Always use stderr in Docker or when explicitly requested
        handler = logging.StreamHandler(sys.stderr)
        
        if in_docker:
            # JSON format for container environments
            handler.setFormatter(DockerFormatter())
        else:
            # Human-readable format
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
    else:
        # File-based logging for local development
        if log_file:
            log_path = Path(log_file)
        else:
            # Default log location
            log_dir = Path.home() / '.mcp-ragex' / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / 'server.log'
        
        # Create handler with rotation if enabled
        if enable_rotation:
            handler = RotatingFileHandler(
                str(log_path),
                maxBytes=max_bytes,
                backupCount=backup_count
            )
        else:
            handler = logging.FileHandler(str(log_path))
            
        # Human-readable format for files
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        
        # Also add console handler for immediate feedback
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(logging.Formatter(
            '%(levelname)s: %(message)s'
        ))
        console_handler.setLevel(logging.WARNING)  # Only warnings and above to console
        root_logger.addHandler(console_handler)
    
    # Configure root logger
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    
    # Quiet noisy libraries if requested
    if quiet_libraries:
        noisy_libs = [
            'sentence_transformers',
            'chromadb',
            'urllib3',
            'httpx',
            'transformers',
            'torch',
            'tqdm',
            'filelock',
        ]
        for lib in noisy_libs:
            logging.getLogger(lib).setLevel(logging.WARNING)
    
    # Log startup information
    logger = logging.getLogger('mcp-ragex')
    logger.info(f"Logging configured - Level: {level}, Docker: {in_docker}")
    

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **context: Any
) -> None:
    """
    Log a message with additional context fields.
    
    Args:
        logger: Logger instance
        level: Log level (e.g., logging.INFO)
        message: Log message
        **context: Additional fields to include in structured logs
    """
    extra = {'extra': context} if context else {}
    logger.log(level, message, extra=extra)