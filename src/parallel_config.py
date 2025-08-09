#!/usr/bin/env python3
"""
Configuration management for parallel symbol extraction
Provides auto-detection and tuning of parallelism parameters
"""

import logging
import multiprocessing as mp
import os
import psutil
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("parallel-config")

@dataclass
class ParallelConfig:
    """Configuration for parallel symbol extraction"""
    max_workers: int
    min_batch_size: int
    max_batch_size: int
    target_batch_time: float
    memory_limit_mb: int
    cpu_threshold: float
    
    # Advanced settings
    enable_shared_parsers: bool = True
    worker_memory_limit_mb: int = 512
    process_timeout_seconds: int = 300
    
    def __post_init__(self):
        """Validate configuration values"""
        self.max_workers = max(1, min(self.max_workers, 16))  # Reasonable bounds
        self.min_batch_size = max(1, self.min_batch_size)
        self.max_batch_size = max(self.min_batch_size, self.max_batch_size)
        self.target_batch_time = max(0.1, self.target_batch_time)
        self.memory_limit_mb = max(256, self.memory_limit_mb)
        self.cpu_threshold = max(0.1, min(1.0, self.cpu_threshold))

class ParallelConfigManager:
    """Manages configuration for parallel symbol extraction with auto-detection"""
    
    def __init__(self):
        self._cached_config = None
        self._system_info = self._detect_system_capabilities()
    
    def _detect_system_capabilities(self) -> dict:
        """Detect system capabilities for optimal configuration"""
        try:
            # CPU information
            cpu_count = mp.cpu_count()
            cpu_freq = psutil.cpu_freq()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory information  
            memory = psutil.virtual_memory()
            available_memory_mb = memory.available // (1024 * 1024)
            total_memory_mb = memory.total // (1024 * 1024)
            
            # Disk information (for the current working directory)
            disk = psutil.disk_usage('.')
            disk_free_mb = disk.free // (1024 * 1024)
            
            system_info = {
                'cpu_count': cpu_count,
                'cpu_freq_mhz': cpu_freq.current if cpu_freq else 0,
                'cpu_usage_percent': cpu_percent,
                'available_memory_mb': available_memory_mb,
                'total_memory_mb': total_memory_mb,
                'disk_free_mb': disk_free_mb,
                'is_containerized': self._detect_containerization(),
            }
            
            logger.debug(f"System capabilities: {system_info}")
            return system_info
            
        except Exception as e:
            logger.warning(f"Failed to detect system capabilities: {e}")
            return {
                'cpu_count': mp.cpu_count(),
                'cpu_freq_mhz': 0,
                'cpu_usage_percent': 0,
                'available_memory_mb': 1024,  # Conservative default
                'total_memory_mb': 2048,
                'disk_free_mb': 1024,
                'is_containerized': False,
            }
    
    def _detect_containerization(self) -> bool:
        """Detect if running in a container environment"""
        # Check common container indicators
        container_indicators = [
            os.path.exists('/.dockerenv'),
            os.path.exists('/run/.containerenv'),
            'container' in os.environ.get('container', ''),
            'docker' in os.environ.get('HOME', ''),
            os.environ.get('DOCKER_CONTAINER') == 'true',
        ]
        
        return any(container_indicators)
    
    def get_optimal_config(self, file_count: Optional[int] = None) -> ParallelConfig:
        """
        Generate optimal configuration based on system capabilities and workload
        
        Args:
            file_count: Estimated number of files to process (for optimization)
        """
        if self._cached_config and not file_count:
            return self._cached_config
        
        info = self._system_info
        
        # Calculate optimal worker count
        max_workers = self._calculate_optimal_workers(info, file_count)
        
        # Calculate batch sizes based on memory and CPU
        min_batch, max_batch = self._calculate_batch_sizes(info, max_workers)
        
        # Calculate target batch time based on CPU speed
        target_batch_time = self._calculate_target_batch_time(info)
        
        # Memory limits
        memory_limit_mb = min(
            info['available_memory_mb'] // 2,  # Use half of available memory
            2048  # Cap at 2GB
        )
        
        worker_memory_limit_mb = min(
            memory_limit_mb // max_workers,
            512  # Cap per worker at 512MB
        )
        
        # CPU threshold for load balancing
        cpu_threshold = 0.8 if info['cpu_usage_percent'] < 50 else 0.9
        
        config = ParallelConfig(
            max_workers=max_workers,
            min_batch_size=min_batch,
            max_batch_size=max_batch,
            target_batch_time=target_batch_time,
            memory_limit_mb=memory_limit_mb,
            cpu_threshold=cpu_threshold,
            worker_memory_limit_mb=worker_memory_limit_mb,
            enable_shared_parsers=True,  # Always enable for performance
        )
        
        if not file_count:
            self._cached_config = config
            
        logger.info(f"Optimal config: {max_workers} workers, batch size {min_batch}-{max_batch}, "
                   f"target time {target_batch_time}s, memory limit {memory_limit_mb}MB")
        
        return config
    
    def _calculate_optimal_workers(self, info: dict, file_count: Optional[int] = None) -> int:
        """Calculate optimal number of worker processes"""
        cpu_count = info['cpu_count']
        available_memory_mb = info['available_memory_mb']
        is_containerized = info['is_containerized']
        
        # Base calculation: use most cores but leave some for system
        if cpu_count <= 2:
            base_workers = cpu_count
        elif cpu_count <= 4:
            base_workers = cpu_count - 1
        else:
            base_workers = max(2, cpu_count - 2)
        
        # Adjust for containerized environments
        if is_containerized:
            base_workers = min(base_workers, 4)  # Conservative in containers
        
        # Memory-based limits (assume ~200MB per worker)
        memory_workers = max(1, available_memory_mb // 200)
        
        # File count optimization
        if file_count:
            # Don't use more workers than files
            optimal_workers = min(base_workers, file_count)
            # For small file counts, use fewer workers to reduce overhead
            if file_count < 10:
                optimal_workers = min(optimal_workers, 2)
            elif file_count < 50:
                optimal_workers = min(optimal_workers, 4)
        else:
            optimal_workers = base_workers
        
        # Apply memory limit
        final_workers = min(optimal_workers, memory_workers)
        
        # Ensure minimum of 1 worker
        return max(1, final_workers)
    
    def _calculate_batch_sizes(self, info: dict, max_workers: int) -> tuple[int, int]:
        """Calculate optimal batch sizes"""
        cpu_count = info['cpu_count']
        available_memory_mb = info['available_memory_mb']
        
        # Base batch sizes
        if cpu_count <= 2:
            min_batch = 1
            max_batch = 5
        elif cpu_count <= 4:
            min_batch = 2
            max_batch = 8
        else:
            min_batch = 2
            max_batch = 12
        
        # Adjust for memory constraints
        if available_memory_mb < 1024:  # Less than 1GB
            max_batch = min(max_batch, 5)
        elif available_memory_mb < 2048:  # Less than 2GB
            max_batch = min(max_batch, 8)
        
        # Adjust for worker count
        if max_workers <= 2:
            max_batch = min(max_batch, 6)
        
        return min_batch, max_batch
    
    def _calculate_target_batch_time(self, info: dict) -> float:
        """Calculate target processing time per batch"""
        cpu_freq = info['cpu_freq_mhz']
        cpu_usage = info['cpu_usage_percent']
        
        # Base target time
        base_time = 1.0  # 1 second
        
        # Adjust for CPU frequency (higher frequency = can handle more per batch)
        if cpu_freq > 3000:  # High-frequency CPU
            base_time *= 1.5
        elif cpu_freq > 2000:  # Mid-range CPU
            base_time *= 1.2
        elif cpu_freq > 0 and cpu_freq < 1500:  # Low-frequency CPU
            base_time *= 0.8
        
        # Adjust for current CPU usage (higher usage = smaller batches)
        if cpu_usage > 80:
            base_time *= 0.7
        elif cpu_usage > 60:
            base_time *= 0.85
        elif cpu_usage < 20:
            base_time *= 1.3
        
        return max(0.5, min(3.0, base_time))  # Clamp between 0.5 and 3.0 seconds
    
    def get_config_from_env(self) -> Optional[ParallelConfig]:
        """Load configuration from environment variables"""
        try:
            config = ParallelConfig(
                max_workers=int(os.environ.get('RAGEX_MAX_WORKERS', 0)),
                min_batch_size=int(os.environ.get('RAGEX_MIN_BATCH_SIZE', 1)),
                max_batch_size=int(os.environ.get('RAGEX_MAX_BATCH_SIZE', 10)),
                target_batch_time=float(os.environ.get('RAGEX_TARGET_BATCH_TIME', 1.0)),
                memory_limit_mb=int(os.environ.get('RAGEX_MEMORY_LIMIT_MB', 1024)),
                cpu_threshold=float(os.environ.get('RAGEX_CPU_THRESHOLD', 0.8)),
                enable_shared_parsers=os.environ.get('RAGEX_ENABLE_SHARED_PARSERS', 'true').lower() == 'true',
                worker_memory_limit_mb=int(os.environ.get('RAGEX_WORKER_MEMORY_LIMIT_MB', 512)),
            )
            
            # If max_workers is 0, use auto-detection
            if config.max_workers == 0:
                auto_config = self.get_optimal_config()
                config.max_workers = auto_config.max_workers
            
            logger.info("Loaded parallel configuration from environment variables")
            return config
            
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to load config from environment: {e}")
            return None
    
    def get_config(self, file_count: Optional[int] = None) -> ParallelConfig:
        """
        Get the best available configuration
        
        Priority: environment variables > optimal detection > defaults
        """
        # Try environment variables first
        env_config = self.get_config_from_env()
        if env_config:
            return env_config
        
        # Fall back to optimal detection
        return self.get_optimal_config(file_count)

# Global configuration manager
_config_manager = None

def get_config_manager() -> ParallelConfigManager:
    """Get the global configuration manager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ParallelConfigManager()
    return _config_manager

def get_optimal_config(file_count: Optional[int] = None) -> ParallelConfig:
    """Get optimal configuration for parallel processing"""
    return get_config_manager().get_config(file_count)