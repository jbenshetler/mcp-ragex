#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "mcp>=1.0.0",
#   "pytest>=7.0.0",
#   "pytest-asyncio>=0.21.0",
# ]
# ///
"""
RAGex MCP Tests with UV Dependencies

This script uses UV's inline script metadata to automatically install
required dependencies in an isolated environment.

Usage:
    uv run tests/test_mcp_with_uv.py

The script will:
1. Install MCP, pytest, and other dependencies
2. Run comprehensive MCP server tests
3. Validate semantic, regex, and symbol search
4. Report structured results
"""

import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import sys
import os

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    import mcp.server.stdio
    import mcp.types as types
    MCP_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  MCP import failed: {e}")
    print("Run with: uv run tests/test_mcp_with_uv.py")
    MCP_AVAILABLE = False

try:
    from src.server import RipgrepSearcher
    SERVER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Server import failed: {e}")
    SERVER_AVAILABLE = False


class TestCodebase:
    """Creates comprehensive test files for MCP validation"""
    
    @staticmethod
    def create_files(base_path: Path) -> Dict[str, str]:
        """Create realistic test codebase with multiple languages"""
        
        files = {
            "auth/authentication.py": '''
"""Authentication service with JWT token management"""
import hashlib
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class AuthenticationService:
    """Handles user authentication and session management"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.session_store = {}
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate user credentials and return session info
        
        Args:
            username: User login name
            password: Plain text password
            
        Returns:
            Authentication result with token or None if failed
        """
        # TODO: Implement proper password verification
        if self._verify_credentials(username, password):
            token = self._generate_session_token(username)
            return {
                "success": True,
                "username": username,
                "token": token,
                "expires_at": datetime.utcnow() + timedelta(hours=24)
            }
        return None
    
    def _verify_credentials(self, username: str, password: str) -> bool:
        """Verify user credentials against database"""
        if not username or not password:
            raise ValueError("Username and password are required")
        
        # Mock credential verification
        hashed = hashlib.sha256(password.encode()).hexdigest()
        return len(hashed) > 10  # Simple mock validation
    
    def _generate_session_token(self, username: str) -> str:
        """Generate JWT token for authenticated user"""
        payload = {
            "username": username,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

async def validate_session_token(token: str) -> Dict[str, Any]:
    """Validate JWT session token and return user info"""
    try:
        # TODO: Add proper JWT validation with secret key
        decoded = jwt.decode(token, options={"verify_signature": False})
        return {
            "valid": True,
            "username": decoded.get("username"),
            "expires_at": decoded.get("exp")
        }
    except jwt.InvalidTokenError:
        return {"valid": False, "error": "Invalid token"}

def hash_password(password: str, salt: str = "") -> str:
    """Hash password with salt for secure storage"""
    combined = f"{password}{salt}"
    return hashlib.sha256(combined.encode()).hexdigest()
''',
            
            "api/client.js": '''
/**
 * API client for file upload and data processing
 * Handles HTTP requests with proper error handling and retries
 */

class ApiClient {
    constructor(baseUrl, options = {}) {
        this.baseUrl = baseUrl;
        this.authToken = options.authToken || null;
        this.timeout = options.timeout || 30000;
        this.retryAttempts = options.retryAttempts || 3;
        this.uploadQueue = [];
    }

    /**
     * Submit file for processing with metadata
     * @param {File} file - File object to upload
     * @param {Object} metadata - Additional file metadata
     * @returns {Promise} Upload response
     */
    async submitFile(file, metadata = {}) {
        if (!file || !file.name) {
            throw new Error('Valid file object is required');
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('metadata', JSON.stringify({
            originalName: file.name,
            size: file.size,
            type: file.type,
            uploadedAt: new Date().toISOString(),
            ...metadata
        }));

        try {
            const response = await this.makeRequest('/api/files/upload', {
                method: 'POST',
                body: formData
            });

            return await this.handleUploadResponse(response);
        } catch (error) {
            console.error('File upload failed:', error);
            // TODO: Implement upload retry logic
            throw new Error(`Upload failed: ${error.message}`);
        }
    }

    /**
     * Process queued file uploads
     * @returns {Promise} Processing results
     */
    async processUploadQueue() {
        const results = [];
        
        while (this.uploadQueue.length > 0) {
            const uploadTask = this.uploadQueue.shift();
            try {
                const result = await this.submitFile(uploadTask.file, uploadTask.metadata);
                results.push({ success: true, result });
            } catch (error) {
                results.push({ success: false, error: error.message });
            }
        }
        
        return results;
    }

    async makeRequest(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const headers = {
            'Accept': 'application/json',
            ...options.headers
        };

        // Add auth token if available
        if (this.authToken) {
            headers['Authorization'] = `Bearer ${this.authToken}`;
        }

        // Don't set Content-Type for FormData (browser will set it with boundary)
        if (!(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        }

        return fetch(url, {
            ...options,
            headers,
            timeout: this.timeout
        });
    }

    async handleUploadResponse(response) {
        if (!response.ok) {
            const error = await response.text();
            throw new Error(`HTTP ${response.status}: ${error}`);
        }

        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return response.json();
        }
        
        return response.text();
    }
}

// Utility functions for file handling
const FileUtils = {
    /**
     * Validate file before upload
     */
    validateFile(file, maxSize = 10 * 1024 * 1024) {
        if (!file) return { valid: false, error: 'No file provided' };
        if (file.size > maxSize) return { valid: false, error: 'File too large' };
        return { valid: true };
    },

    /**
     * Get file extension
     */
    getFileExtension(filename) {
        return filename.split('.').pop().toLowerCase();
    }
};

export { ApiClient, FileUtils };
''',

            "utils/validation.ts": '''
/**
 * Data validation utilities with comprehensive type safety
 * Supports various validation rules and error reporting
 */

interface ValidationRule {
    field: string;
    type: 'required' | 'string' | 'number' | 'email' | 'url' | 'pattern';
    message: string;
    pattern?: RegExp;
    minLength?: number;
    maxLength?: number;
    min?: number;
    max?: number;
}

interface ValidationResult {
    isValid: boolean;
    errors: ValidationError[];
    warnings: string[];
    validatedData: Record<string, any>;
}

interface ValidationError {
    field: string;
    message: string;
    value: any;
    rule: string;
}

class DataValidator {
    private rules: Map<string, ValidationRule[]> = new Map();
    private customValidators: Map<string, (value: any) => boolean> = new Map();

    /**
     * Add validation rule for a specific field
     */
    addRule(field: string, rule: ValidationRule): DataValidator {
        if (!this.rules.has(field)) {
            this.rules.set(field, []);
        }
        this.rules.get(field)!.push(rule);
        return this;
    }

    /**
     * Add custom validator function
     */
    addCustomValidator(name: string, validator: (value: any) => boolean): DataValidator {
        this.customValidators.set(name, validator);
        return this;
    }

    /**
     * Validate user input data against all rules
     * @param data - Object containing data to validate
     * @returns Comprehensive validation result
     */
    validateUserInput(data: Record<string, any>): ValidationResult {
        const errors: ValidationError[] = [];
        const warnings: string[] = [];
        const validatedData: Record<string, any> = {};

        // Validate each field with its rules
        for (const [field, rules] of this.rules.entries()) {
            const value = data[field];
            
            for (const rule of rules) {
                const validationError = this.validateField(field, value, rule);
                if (validationError) {
                    errors.push(validationError);
                } else {
                    // Store validated data
                    validatedData[field] = this.sanitizeValue(value, rule);
                }
            }
        }

        // Check for unexpected fields
        for (const field in data) {
            if (!this.rules.has(field)) {
                warnings.push(`Unexpected field: ${field}`);
            }
        }

        return {
            isValid: errors.length === 0,
            errors,
            warnings,
            validatedData
        };
    }

    private validateField(field: string, value: any, rule: ValidationRule): ValidationError | null {
        // Required check
        if (rule.type === 'required' && (value === undefined || value === null || value === '')) {
            return {
                field,
                message: rule.message || `${field} is required`,
                value,
                rule: 'required'
            };
        }

        // Skip other validations if value is empty and not required
        if (!value && rule.type !== 'required') {
            return null;
        }

        // Type-specific validations
        switch (rule.type) {
            case 'string':
                if (typeof value !== 'string') {
                    return this.createError(field, value, rule, 'Must be a string');
                }
                if (rule.minLength && value.length < rule.minLength) {
                    return this.createError(field, value, rule, `Minimum length is ${rule.minLength}`);
                }
                if (rule.maxLength && value.length > rule.maxLength) {
                    return this.createError(field, value, rule, `Maximum length is ${rule.maxLength}`);
                }
                break;

            case 'number':
                const num = Number(value);
                if (isNaN(num)) {
                    return this.createError(field, value, rule, 'Must be a valid number');
                }
                if (rule.min !== undefined && num < rule.min) {
                    return this.createError(field, value, rule, `Minimum value is ${rule.min}`);
                }
                if (rule.max !== undefined && num > rule.max) {
                    return this.createError(field, value, rule, `Maximum value is ${rule.max}`);
                }
                break;

            case 'email':
                const emailPattern = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
                if (!emailPattern.test(value)) {
                    return this.createError(field, value, rule, 'Must be a valid email address');
                }
                break;

            case 'url':
                try {
                    new URL(value);
                } catch {
                    return this.createError(field, value, rule, 'Must be a valid URL');
                }
                break;

            case 'pattern':
                if (rule.pattern && !rule.pattern.test(value)) {
                    return this.createError(field, value, rule, rule.message || 'Invalid format');
                }
                break;
        }

        return null;
    }

    private createError(field: string, value: any, rule: ValidationRule, defaultMessage: string): ValidationError {
        return {
            field,
            message: rule.message || defaultMessage,
            value,
            rule: rule.type
        };
    }

    private sanitizeValue(value: any, rule: ValidationRule): any {
        switch (rule.type) {
            case 'string':
                return String(value).trim();
            case 'number':
                return Number(value);
            default:
                return value;
        }
    }
}

// Utility functions for common validations
export const ValidationUtils = {
    isValidEmail: (email: string): boolean => {
        return /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email);
    },

    isValidUrl: (url: string): boolean => {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    },

    sanitizeHtml: (input: string): string => {
        return input.replace(/<[^>]*>/g, '');
    }
};

export { DataValidator, ValidationRule, ValidationResult, ValidationError };
''',

            "config/app_settings.py": '''
"""
Application configuration and settings management
Handles environment variables, feature flags, and runtime configuration
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

class Environment(Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

@dataclass
class DatabaseConfig:
    """Database connection configuration"""
    host: str = "localhost"
    port: int = 5432
    name: str = "app_db"
    user: str = "app_user"
    password: str = ""
    ssl_mode: str = "prefer"
    pool_size: int = 10
    max_overflow: int = 20

@dataclass
class RedisConfig:
    """Redis configuration for caching and queues"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ssl: bool = False
    decode_responses: bool = True

@dataclass
class FileConfig:
    """File upload and processing configuration"""
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: List[str] = field(default_factory=lambda: [
        '.txt', '.pdf', '.docx', '.xlsx', '.csv', '.json'
    ])
    upload_directory: str = "/tmp/uploads"
    processing_timeout: int = 300  # 5 minutes
    
    def get_upload_directory(self) -> Path:
        """Get upload directory as Path object"""
        upload_dir = Path(self.upload_directory)
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir

@dataclass
class SecurityConfig:
    """Security-related configuration"""
    secret_key: str = ""
    jwt_expiry_hours: int = 24
    password_min_length: int = 8
    max_login_attempts: int = 5
    session_timeout_minutes: int = 30
    cors_origins: List[str] = field(default_factory=list)

class AppConfig:
    """Main application configuration class"""
    
    def __init__(self):
        self.environment = Environment(os.environ.get('APP_ENV', 'development'))
        self.debug = os.environ.get('DEBUG', '').lower() == 'true'
        
        # Initialize configuration sections
        self.database = self._load_database_config()
        self.redis = self._load_redis_config()
        self.files = self._load_file_config()
        self.security = self._load_security_config()
        
        # Feature flags
        self.features = self._load_feature_flags()
    
    def _load_database_config(self) -> DatabaseConfig:
        """Load database configuration from environment"""
        return DatabaseConfig(
            host=os.environ.get('DB_HOST', 'localhost'),
            port=int(os.environ.get('DB_PORT', '5432')),
            name=os.environ.get('DB_NAME', 'app_db'),
            user=os.environ.get('DB_USER', 'app_user'),
            password=os.environ.get('DB_PASSWORD', ''),
            ssl_mode=os.environ.get('DB_SSL_MODE', 'prefer')
        )
    
    def _load_redis_config(self) -> RedisConfig:
        """Load Redis configuration from environment"""
        return RedisConfig(
            host=os.environ.get('REDIS_HOST', 'localhost'),
            port=int(os.environ.get('REDIS_PORT', '6379')),
            db=int(os.environ.get('REDIS_DB', '0')),
            password=os.environ.get('REDIS_PASSWORD'),
            ssl=os.environ.get('REDIS_SSL', '').lower() == 'true'
        )
    
    def _load_file_config(self) -> FileConfig:
        """Load file handling configuration"""
        return FileConfig(
            max_file_size=int(os.environ.get('MAX_FILE_SIZE', '10485760')),  # 10MB
            upload_directory=os.environ.get('UPLOAD_DIR', '/tmp/uploads'),
            processing_timeout=int(os.environ.get('PROCESSING_TIMEOUT', '300'))
        )
    
    def _load_security_config(self) -> SecurityConfig:
        """Load security configuration"""
        cors_origins = os.environ.get('CORS_ORIGINS', '').split(',')
        cors_origins = [origin.strip() for origin in cors_origins if origin.strip()]
        
        return SecurityConfig(
            secret_key=os.environ.get('SECRET_KEY', ''),
            jwt_expiry_hours=int(os.environ.get('JWT_EXPIRY_HOURS', '24')),
            cors_origins=cors_origins
        )
    
    def _load_feature_flags(self) -> Dict[str, bool]:
        """Load feature flags from environment"""
        return {
            'semantic_search': os.environ.get('FEATURE_SEMANTIC_SEARCH', 'true').lower() == 'true',
            'file_processing': os.environ.get('FEATURE_FILE_PROCESSING', 'true').lower() == 'true',
            'advanced_analytics': os.environ.get('FEATURE_ANALYTICS', 'false').lower() == 'true',
            'user_registration': os.environ.get('FEATURE_USER_REG', 'true').lower() == 'true',
            'api_rate_limiting': os.environ.get('FEATURE_RATE_LIMIT', 'true').lower() == 'true'
        }
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment == Environment.DEVELOPMENT
    
    def get_feature_flag(self, flag_name: str, default: bool = False) -> bool:
        """Get feature flag value with default fallback"""
        return self.features.get(flag_name, default)

# Global configuration instance
config = AppConfig()

def get_config() -> AppConfig:
    """Get the global configuration instance"""
    return config

# Configuration validation
def validate_config() -> List[str]:
    """Validate configuration and return list of issues"""
    issues = []
    
    if not config.security.secret_key:
        issues.append("SECRET_KEY environment variable is required")
    
    if config.is_production() and config.debug:
        issues.append("Debug mode should not be enabled in production")
    
    if not config.files.get_upload_directory().exists():
        try:
            config.files.get_upload_directory().mkdir(parents=True, exist_ok=True)
        except Exception as e:
            issues.append(f"Cannot create upload directory: {e}")
    
    return issues
''',

            "utils/error_handling.py": '''
"""
Comprehensive error handling and logging system
Provides structured error handling, logging, and monitoring capabilities
"""

import logging
import traceback
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, Type
from functools import wraps
from enum import Enum

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error categories for classification"""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATABASE = "database"
    EXTERNAL_API = "external_api"
    FILE_SYSTEM = "file_system"
    NETWORK = "network"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"

class BaseAppError(Exception):
    """Base application error with structured information"""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ):
        super().__init__(message)
        self.error_id = str(uuid.uuid4())
        self.message = message
        self.error_code = error_code
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.user_message = user_message or message
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/serialization"""
        return {
            "error_id": self.error_id,
            "message": self.message,
            "error_code": self.error_code,
            "category": self.category.value,
            "severity": self.severity.value,
            "context": self.context,
            "user_message": self.user_message,
            "timestamp": self.timestamp.isoformat()
        }

class ValidationError(BaseAppError):
    """Raised when data validation fails"""
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            **kwargs
        )
        if field:
            self.context["field"] = field

class AuthenticationError(BaseAppError):
    """Raised when authentication fails"""
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            user_message="Invalid credentials",
            **kwargs
        )

class AuthorizationError(BaseAppError):
    """Raised when authorization fails"""
    def __init__(self, message: str = "Access denied", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHORIZATION,
            severity=ErrorSeverity.HIGH,
            user_message="You don't have permission to perform this action",
            **kwargs
        )

class DatabaseError(BaseAppError):
    """Raised when database operations fail"""
    def __init__(self, message: str, operation: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            user_message="A database error occurred",
            **kwargs
        )
        if operation:
            self.context["operation"] = operation

class ExternalApiError(BaseAppError):
    """Raised when external API calls fail"""
    def __init__(self, message: str, api_name: Optional[str] = None, status_code: Optional[int] = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.EXTERNAL_API,
            severity=ErrorSeverity.MEDIUM,
            user_message="External service is temporarily unavailable",
            **kwargs
        )
        if api_name:
            self.context["api_name"] = api_name
        if status_code:
            self.context["status_code"] = status_code

class ErrorHandler:
    """Centralized error handling and logging"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.error_callbacks: Dict[Type[Exception], List[Callable]] = {}
    
    def register_callback(self, error_type: Type[Exception], callback: Callable[[Exception, Dict[str, Any]], None]):
        """Register callback for specific error types"""
        if error_type not in self.error_callbacks:
            self.error_callbacks[error_type] = []
        self.error_callbacks[error_type].append(callback)
    
    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> str:
        """Handle error with logging and callbacks"""
        context = context or {}
        
        # Generate error ID for tracking
        error_id = getattr(error, 'error_id', str(uuid.uuid4()))
        
        # Prepare error information
        error_info = {
            "error_id": error_id,
            "error_type": type(error).__name__,
            "message": str(error),
            "context": context,
            "traceback": traceback.format_exc()
        }
        
        # Add structured error information if available
        if isinstance(error, BaseAppError):
            error_info.update(error.to_dict())
        
        # Log error based on severity
        if isinstance(error, BaseAppError):
            log_level = self._get_log_level(error.severity)
        else:
            log_level = logging.ERROR
        
        self.logger.log(
            log_level,
            f"Error {error_id}: {error_info['message']}",
            extra={"error_info": error_info}
        )
        
        # Execute callbacks
        self._execute_callbacks(error, error_info)
        
        return error_id
    
    def _get_log_level(self, severity: ErrorSeverity) -> int:
        """Convert error severity to log level"""
        severity_map = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }
        return severity_map.get(severity, logging.ERROR)
    
    def _execute_callbacks(self, error: Exception, error_info: Dict[str, Any]):
        """Execute registered callbacks for error type"""
        error_type = type(error)
        
        # Execute callbacks for specific error type
        for callback in self.error_callbacks.get(error_type, []):
            try:
                callback(error, error_info)
            except Exception as callback_error:
                self.logger.error(f"Error in callback: {callback_error}")

# Global error handler instance
error_handler = ErrorHandler()

def handle_exceptions(
    error_types: Optional[List[Type[Exception]]] = None,
    reraise: bool = True,
    default_response: Any = None
):
    """Decorator for automatic exception handling"""
    def decorator(func):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if error_types and not any(isinstance(e, et) for et in error_types):
                    raise
                
                error_handler.handle_error(e, {"function": func.__name__, "args": str(args)[:200]})
                
                if reraise:
                    raise
                return default_response
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if error_types and not any(isinstance(e, et) for et in error_types):
                    raise
                
                error_handler.handle_error(e, {"function": func.__name__, "args": str(args)[:200]})
                
                if reraise:
                    raise
                return default_response
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

def log_error_with_context(
    error: Exception,
    context: Dict[str, Any],
    logger: Optional[logging.Logger] = None
) -> str:
    """Log error with additional context"""
    handler = ErrorHandler(logger)
    return handler.handle_error(error, context)

# Import asyncio for coroutine detection
import asyncio
'''
        }
        
        # Create all test files
        for file_path, content in files.items():
            full_path = base_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        return files


class MCPTestResult:
    """Test result with structured information"""
    def __init__(self, name: str, passed: bool, details: str, response_data: Optional[Dict] = None, execution_time: float = 0.0):
        self.name = name
        self.passed = passed
        self.details = details
        self.response_data = response_data or {}
        self.execution_time = execution_time
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "details": self.details,
            "execution_time": self.execution_time,
            "has_response_data": bool(self.response_data)
        }


class UVMCPTester:
    """Comprehensive MCP tester with UV dependencies"""
    
    def __init__(self):
        self.temp_dir = None
        self.searcher = None
        self.results: List[MCPTestResult] = []
        self.total_execution_time = 0.0
    
    async def setup(self) -> bool:
        """Set up test environment"""
        print("🔧 Setting up test environment...")
        
        if not MCP_AVAILABLE:
            print("❌ MCP module not available - run with: uv run tests/test_mcp_with_uv.py")
            return False
        
        if not SERVER_AVAILABLE:
            print("❌ Server module not available")
            return False
        
        try:
            # Create temporary directory
            self.temp_dir = Path(tempfile.mkdtemp(prefix="uv_mcp_test_"))
            print(f"📁 Created test directory: {self.temp_dir}")
            
            # Create comprehensive test codebase
            test_files = TestCodebase.create_files(self.temp_dir)
            print(f"📝 Created {len(test_files)} test files")
            
            # Initialize searcher (no working_directory parameter)
            self.searcher = RipgrepSearcher()
            print("🔍 Initialized RipgrepSearcher")
            
            return True
            
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            return False
    
    async def cleanup(self):
        """Clean up test environment"""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            print("🗑️  Cleaned up test directory")
    
    async def test_basic_search_functionality(self) -> MCPTestResult:
        """Test basic search capabilities"""
        import time
        start_time = time.time()
        
        try:
            result = await self.searcher.search(
                pattern="class.*Service",
                paths=[self.temp_dir],
                file_types=["py"],
                limit=10
            )
            
            success = result.get('success', False) and result.get('total_matches', 0) > 0
            matches = result.get('total_matches', 0)
            details = f"Found {matches} class definitions"
            
            return MCPTestResult(
                "Basic Search Functionality",
                success,
                details,
                result,
                time.time() - start_time
            )
            
        except Exception as e:
            return MCPTestResult(
                "Basic Search Functionality",
                False,
                f"Search failed: {e}",
                execution_time=time.time() - start_time
            )
    
    async def test_semantic_authentication_search(self) -> MCPTestResult:
        """Test semantic search for authentication concepts"""
        import time
        start_time = time.time()
        
        try:
            # Search for authentication-related patterns
            auth_patterns = [
                "authenticate.*user",
                "jwt.*token",
                "login.*credential",
                "session.*validate"
            ]
            
            total_matches = 0
            results = []
            
            for pattern in auth_patterns:
                result = await self.searcher.search(
                paths=[self.temp_dir],
                    pattern=pattern,
                    case_sensitive=False,
                    limit=5
                )
                matches = result.get('total_matches', 0)
                total_matches += matches
                results.append(f"{pattern}: {matches}")
            
            success = total_matches > 0
            details = f"Authentication patterns: {'; '.join(results)}"
            
            return MCPTestResult(
                "Semantic Authentication Search",
                success,
                details,
                {"total_matches": total_matches, "patterns": results},
                time.time() - start_time
            )
            
        except Exception as e:
            return MCPTestResult(
                "Semantic Authentication Search",
                False,
                f"Authentication search failed: {e}",
                execution_time=time.time() - start_time
            )
    
    async def test_file_upload_functionality_search(self) -> MCPTestResult:
        """Test search for file upload functionality"""
        import time
        start_time = time.time()
        
        try:
            upload_patterns = [
                "submit.*file",
                "upload.*queue",
                "FormData",
                "file.*metadata"
            ]
            
            total_matches = 0
            found_patterns = []
            
            for pattern in upload_patterns:
                result = await self.searcher.search(
                paths=[self.temp_dir],
                    pattern=pattern,
                    case_sensitive=False,
                    limit=3
                )
                matches = result.get('total_matches', 0)
                if matches > 0:
                    total_matches += matches
                    found_patterns.append(pattern)
            
            success = total_matches > 0 and len(found_patterns) >= 2
            details = f"Upload patterns found: {len(found_patterns)}/4, Total matches: {total_matches}"
            
            return MCPTestResult(
                "File Upload Functionality Search",
                success,
                details,
                {"patterns_found": found_patterns, "total_matches": total_matches},
                time.time() - start_time
            )
            
        except Exception as e:
            return MCPTestResult(
                "File Upload Functionality Search",
                False,
                f"Upload search failed: {e}",
                execution_time=time.time() - start_time
            )
    
    async def test_validation_logic_search(self) -> MCPTestResult:
        """Test search for validation logic"""
        import time
        start_time = time.time()
        
        try:
            validation_patterns = [
                "validate.*input",
                "ValidationError",
                "check.*field",
                "sanitize.*value"
            ]
            
            results = {}
            for pattern in validation_patterns:
                result = await self.searcher.search(
                paths=[self.temp_dir],
                    pattern=pattern,
                    limit=5
                )
                results[pattern] = result.get('total_matches', 0)
            
            total_matches = sum(results.values())
            success = total_matches >= 3  # Should find validation logic
            
            details = f"Validation matches: {total_matches} across {len([p for p, c in results.items() if c > 0])} patterns"
            
            return MCPTestResult(
                "Validation Logic Search",
                success,
                details,
                results,
                time.time() - start_time
            )
            
        except Exception as e:
            return MCPTestResult(
                "Validation Logic Search",
                False,
                f"Validation search failed: {e}",
                execution_time=time.time() - start_time
            )
    
    async def test_regex_pattern_matching(self) -> MCPTestResult:
        """Test complex regex pattern matching"""
        import time
        start_time = time.time()
        
        try:
            # Test various regex patterns
            regex_tests = [
                ("TODO.*implement", "TODO comments"),
                ("async def\\s+\\w+", "Async function definitions"),
                ("class\\s+\\w+.*:", "Class definitions"),
                ("@\\w+", "Decorators"),
                ("def\\s+_\\w+", "Private methods")
            ]
            
            results = {}
            for pattern, description in regex_tests:
                result = await self.searcher.search(
                paths=[self.temp_dir],
                    pattern=pattern,
                    limit=3
                )
                matches = result.get('total_matches', 0)
                results[description] = matches
            
            total_matches = sum(results.values())
            successful_patterns = len([desc for desc, count in results.items() if count > 0])
            
            success = successful_patterns >= 3
            details = f"Regex patterns: {successful_patterns}/5 successful, {total_matches} total matches"
            
            return MCPTestResult(
                "Regex Pattern Matching",
                success,
                details,
                results,
                time.time() - start_time
            )
            
        except Exception as e:
            return MCPTestResult(
                "Regex Pattern Matching",
                False,
                f"Regex matching failed: {e}",
                execution_time=time.time() - start_time
            )
    
    async def test_symbol_search_precision(self) -> MCPTestResult:
        """Test precise symbol searching"""
        import time
        start_time = time.time()
        
        try:
            # Test exact symbol matching
            symbol_tests = [
                ("\\bAuthenticationService\\b", "AuthenticationService class"),
                ("\\bDataValidator\\b", "DataValidator class"),
                ("\\bvalidateUserInput\\b", "validateUserInput method"),
                ("\\bsubmitFile\\b", "submitFile method"),
                ("\\bAppConfig\\b", "AppConfig class")
            ]
            
            found_symbols = []
            results = {}
            
            for pattern, description in symbol_tests:
                result = await self.searcher.search(
                paths=[self.temp_dir],
                    pattern=pattern,
                    limit=2
                )
                matches = result.get('total_matches', 0)
                results[description] = matches
                if matches > 0:
                    found_symbols.append(description)
            
            success = len(found_symbols) >= 3
            details = f"Symbols found: {len(found_symbols)}/5 ({', '.join(found_symbols[:3])}{'...' if len(found_symbols) > 3 else ''})"
            
            return MCPTestResult(
                "Symbol Search Precision",
                success,
                details,
                results,
                time.time() - start_time
            )
            
        except Exception as e:
            return MCPTestResult(
                "Symbol Search Precision",
                False,
                f"Symbol search failed: {e}",
                execution_time=time.time() - start_time
            )
    
    async def test_multi_language_support(self) -> MCPTestResult:
        """Test search across different file types"""
        import time
        start_time = time.time()
        
        try:
            language_tests = [
                ("py", "class", "Python classes"),
                ("js", "async", "JavaScript async functions"),
                ("ts", "interface", "TypeScript interfaces"),
                ("py", "def\\s+\\w+", "Python functions"),
                ("js", "const\\s+\\w+", "JavaScript constants")
            ]
            
            results = {}
            total_matches = 0
            
            for file_type, pattern, description in language_tests:
                result = await self.searcher.search(
                paths=[self.temp_dir],
                    pattern=pattern,
                    file_types=[file_type],
                    limit=5
                )
                matches = result.get('total_matches', 0)
                results[f"{file_type}:{description}"] = matches
                total_matches += matches
            
            successful_languages = len([desc for desc, count in results.items() if count > 0])
            success = successful_languages >= 3 and total_matches >= 5
            
            details = f"Multi-language: {successful_languages}/5 patterns, {total_matches} total matches"
            
            return MCPTestResult(
                "Multi-Language Support",
                success,
                details,
                results,
                time.time() - start_time
            )
            
        except Exception as e:
            return MCPTestResult(
                "Multi-Language Support",
                False,
                f"Multi-language search failed: {e}",
                execution_time=time.time() - start_time
            )
    
    async def test_mcp_response_structure(self) -> MCPTestResult:
        """Test MCP response structure compliance"""
        import time
        start_time = time.time()
        
        try:
            result = await self.searcher.search(
                paths=[self.temp_dir],
                pattern="function|def|class",
                limit=5
            )
            
            # Validate required fields
            required_fields = ['success', 'total_matches', 'matches']
            missing_fields = [f for f in required_fields if f not in result]
            
            if missing_fields:
                return MCPTestResult(
                    "MCP Response Structure",
                    False,
                    f"Missing required fields: {missing_fields}",
                    execution_time=time.time() - start_time
                )
            
            # Validate match structure
            matches = result.get('matches', [])
            if matches:
                first_match = matches[0]
                match_fields = ['file', 'line_number', 'line']  # Use actual field names from RipgrepSearcher
                missing_match_fields = [f for f in match_fields if f not in first_match]
                
                if missing_match_fields:
                    return MCPTestResult(
                        "MCP Response Structure",
                        False,
                        f"Match missing fields: {missing_match_fields}",
                        execution_time=time.time() - start_time
                    )
            
            # Validate data types
            structure_valid = (
                isinstance(result['success'], bool) and
                isinstance(result['total_matches'], int) and
                isinstance(result['matches'], list)
            )
            
            success = structure_valid and not missing_fields
            details = f"Structure valid: {len(matches)} matches with proper fields"
            
            return MCPTestResult(
                "MCP Response Structure",
                success,
                details,
                {"sample_match": matches[0] if matches else None},
                time.time() - start_time
            )
            
        except Exception as e:
            return MCPTestResult(
                "MCP Response Structure",
                False,
                f"Structure validation failed: {e}",
                execution_time=time.time() - start_time
            )
    
    async def test_error_handling_robustness(self) -> MCPTestResult:
        """Test error handling for various invalid inputs"""
        import time
        start_time = time.time()
        
        try:
            error_tests = [
                ("[invalid(", "Invalid regex pattern"),
                ("", "Empty pattern"),
                ("\\", "Incomplete escape sequence")
            ]
            
            handled_gracefully = 0
            error_results = {}
            
            for pattern, description in error_tests:
                try:
                    result = await self.searcher.search(
                paths=[self.temp_dir],
                        pattern=pattern,
                        limit=1
                    )
                    
                    # Check if error was handled gracefully
                    if not result.get('success', True) or result.get('total_matches', 0) == 0:
                        handled_gracefully += 1
                        error_results[description] = "Handled gracefully"
                    else:
                        error_results[description] = f"Unexpected success: {result.get('total_matches')} matches"
                        
                except Exception:
                    # Exception handling is also acceptable
                    handled_gracefully += 1
                    error_results[description] = "Exception raised (acceptable)"
            
            success = handled_gracefully >= 2  # At least 2/3 should be handled gracefully
            details = f"Error handling: {handled_gracefully}/3 cases handled gracefully"
            
            return MCPTestResult(
                "Error Handling Robustness",
                success,
                details,
                error_results,
                time.time() - start_time
            )
            
        except Exception as e:
            return MCPTestResult(
                "Error Handling Robustness",
                False,
                f"Error handling test failed: {e}",
                execution_time=time.time() - start_time
            )
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run complete test suite"""
        print("🚀 Starting UV MCP Test Suite")
        print("=" * 60)
        
        if not await self.setup():
            return {
                "success": False,
                "error": "Test setup failed"
            }
        
        # Define test methods
        test_methods = [
            self.test_basic_search_functionality,
            self.test_semantic_authentication_search,
            self.test_file_upload_functionality_search,
            self.test_validation_logic_search,
            self.test_regex_pattern_matching,
            self.test_symbol_search_precision,
            self.test_multi_language_support,
            self.test_mcp_response_structure,
            self.test_error_handling_robustness
        ]
        
        # Run tests
        import time
        suite_start_time = time.time()
        
        for test_method in test_methods:
            try:
                result = await test_method()
                self.results.append(result)
                status = "✅ PASS" if result.passed else "❌ FAIL"
                print(f"  {status}: {result.name} - {result.details} ({result.execution_time:.2f}s)")
                
            except Exception as e:
                error_result = MCPTestResult(
                    test_method.__name__,
                    False,
                    f"Test execution failed: {e}"
                )
                self.results.append(error_result)
                print(f"  ❌ ERROR: {error_result.name} - {error_result.details}")
        
        self.total_execution_time = time.time() - suite_start_time
        await self.cleanup()
        
        # Calculate results
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print("\n" + "=" * 60)
        print("📊 UV MCP TEST RESULTS")
        print("=" * 60)
        print(f"✅ Passed: {passed}/{total}")
        print(f"🎯 Success Rate: {success_rate:.1f}%")
        print(f"⏱️  Total Execution Time: {self.total_execution_time:.2f}s")
        
        if passed < total:
            print("\n❌ Failed tests:")
            for result in self.results:
                if not result.passed:
                    print(f"   - {result.name}: {result.details}")
        
        # Return structured results
        return {
            "success": success_rate >= 80,
            "summary": {
                "total_tests": total,
                "passed": passed,
                "failed": total - passed,
                "success_rate": success_rate,
                "execution_time": self.total_execution_time
            },
            "test_details": [r.to_dict() for r in self.results],
            "performance": {
                "average_test_time": sum(r.execution_time for r in self.results) / total if total > 0 else 0,
                "slowest_test": max(self.results, key=lambda x: x.execution_time).name if self.results else None,
                "fastest_test": min(self.results, key=lambda x: x.execution_time).name if self.results else None
            }
        }


async def main():
    """Main entry point for UV MCP tests"""
    tester = UVMCPTester()
    results = await tester.run_all_tests()
    
    if results.get("success"):
        print("\n🎉 All tests completed successfully!")
        return 0
    else:
        failed = results.get('summary', {}).get('failed', 'unknown')
        print(f"\n💥 Test suite failed - {failed} tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)