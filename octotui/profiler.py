"""Profiling utilities for octotui performance analysis.

This module provides function-level profiling with file-based logging.
Enable profiling by setting the environment variable OCTOTUI_PROFILE=1

Usage:
    from octotui.profiler import profile, get_profiler
    
    @profile
    def slow_function():
        ...
    
    # Or manually:
    profiler = get_profiler()
    with profiler.measure("operation_name"):
        do_stuff()

The profiler will write to ~/.octotui_profile.log by default.
Set OCTOTUI_PROFILE_LOG to customize the log file path.
"""

import atexit
import functools
import os
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class ProfileStats:
    """Statistics for a single profiled function/operation."""
    
    call_count: int = 0
    total_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    recent_times: List[float] = field(default_factory=list)
    
    def record(self, elapsed: float) -> None:
        """Record a timing measurement."""
        self.call_count += 1
        self.total_time += elapsed
        self.min_time = min(self.min_time, elapsed)
        self.max_time = max(self.max_time, elapsed)
        # Keep last 100 measurements for recent analysis
        self.recent_times.append(elapsed)
        if len(self.recent_times) > 100:
            self.recent_times.pop(0)
    
    @property
    def avg_time(self) -> float:
        """Average time per call."""
        return self.total_time / self.call_count if self.call_count > 0 else 0.0
    
    @property
    def recent_avg(self) -> float:
        """Average of recent measurements."""
        if not self.recent_times:
            return 0.0
        return sum(self.recent_times) / len(self.recent_times)


class Profiler:
    """Profile manager that tracks timing stats and logs to file."""
    
    def __init__(self, log_path: Optional[Path] = None, enabled: bool = True):
        self.enabled = enabled
        self.log_path = log_path or Path.home() / ".octotui_profile.log"
        self.stats: Dict[str, ProfileStats] = defaultdict(ProfileStats)
        self._lock = Lock()
        self._log_file = None
        self._start_time = time.time()
        self._call_log: List[tuple] = []  # (timestamp, name, elapsed)
        
        if self.enabled:
            self._open_log()
            atexit.register(self._cleanup)
    
    def _open_log(self) -> None:
        """Open log file for writing."""
        try:
            self._log_file = open(self.log_path, "a")
            self._write_header()
        except Exception as e:
            print(f"Warning: Could not open profile log {self.log_path}: {e}")
            self._log_file = None
    
    def _write_header(self) -> None:
        """Write session header to log."""
        if self._log_file:
            timestamp = datetime.now().isoformat()
            self._log_file.write("\n" + "=" * 80 + "\n")
            self._log_file.write(f"OCTOTUI PROFILE SESSION: {timestamp}\n")
            self._log_file.write("=" * 80 + "\n")
            self._log_file.flush()
    
    def _log(self, name: str, elapsed: float, extra: str = "") -> None:
        """Log a timing entry."""
        if self._log_file:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            extra_str = f" | {extra}" if extra else ""
            self._log_file.write(
                f"[{timestamp}] {name:50} {elapsed*1000:10.2f}ms{extra_str}\n"
            )
            # Flush every 10 entries to avoid buffering issues
            if self.stats[name].call_count % 10 == 0:
                self._log_file.flush()
    
    def record(self, name: str, elapsed: float, extra: str = "") -> None:
        """Record a timing measurement."""
        if not self.enabled:
            return
        
        with self._lock:
            self.stats[name].record(elapsed)
            self._call_log.append((time.time(), name, elapsed))
            self._log(name, elapsed, extra)
    
    @contextmanager
    def measure(self, name: str, extra: str = ""):
        """Context manager for measuring a block of code."""
        if not self.enabled:
            yield
            return
        
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self.record(name, elapsed, extra)
    
    def get_summary(self) -> str:
        """Generate a summary report of all profiled operations."""
        lines = [
            "\n" + "=" * 80,
            "PROFILE SUMMARY",
            "=" * 80,
            "",
            f"{'Function/Operation':<50} {'Calls':>8} {'Total(ms)':>12} {'Avg(ms)':>10} {'Min(ms)':>10} {'Max(ms)':>10}",
            "-" * 100,
        ]
        
        # Sort by total time descending (slowest first)
        sorted_stats = sorted(
            self.stats.items(),
            key=lambda x: x[1].total_time,
            reverse=True
        )
        
        for name, stat in sorted_stats:
            lines.append(
                f"{name:<50} {stat.call_count:>8} {stat.total_time*1000:>12.2f} "
                f"{stat.avg_time*1000:>10.2f} {stat.min_time*1000:>10.2f} {stat.max_time*1000:>10.2f}"
            )
        
        total_time = time.time() - self._start_time
        lines.extend([
            "-" * 100,
            f"Session duration: {total_time:.2f}s",
            "=" * 80,
        ])
        
        return "\n".join(lines)
    
    def get_hotspots(self, top_n: int = 10) -> List[tuple]:
        """Get top N functions by total time."""
        sorted_stats = sorted(
            self.stats.items(),
            key=lambda x: x[1].total_time,
            reverse=True
        )
        return sorted_stats[:top_n]
    
    def _cleanup(self) -> None:
        """Write summary and close log file."""
        if self._log_file:
            self._log_file.write(self.get_summary())
            self._log_file.write("\n")
            self._log_file.close()
            self._log_file = None


# Global profiler instance
_profiler: Optional[Profiler] = None


def get_profiler() -> Profiler:
    """Get the global profiler instance.
    
    Creates the profiler on first call, checking environment variables:
    - OCTOTUI_PROFILE: Set to '1' or 'true' to enable profiling
    - OCTOTUI_PROFILE_LOG: Custom path for the log file
    """
    global _profiler
    
    if _profiler is None:
        enabled = os.environ.get("OCTOTUI_PROFILE", "").lower() in ("1", "true", "yes")
        log_path = os.environ.get("OCTOTUI_PROFILE_LOG")
        if log_path:
            log_path = Path(log_path)
        
        _profiler = Profiler(log_path=log_path, enabled=enabled)
    
    return _profiler


def profile(func: F) -> F:
    """Decorator to profile a function.
    
    Usage:
        @profile
        def my_function():
            ...
    
    The function name will be used as the profile entry name.
    For methods, it will include the class name if available.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        profiler = get_profiler()
        
        if not profiler.enabled:
            return func(*args, **kwargs)
        
        # Build a descriptive name
        name = func.__qualname__  # Includes class name for methods
        
        # Add extra context if first arg is self and has meaningful repr
        extra = ""
        if args and hasattr(args[0], "__class__"):
            # Check for specific context we care about (e.g., file paths)
            if len(args) > 1 and isinstance(args[1], str):
                extra = f"arg={args[1][:50]}"  # Truncate long args
        
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            profiler.record(name, elapsed, extra)
    
    return wrapper  # type: ignore


def profile_method(name: Optional[str] = None):
    """Decorator factory for profiling with a custom name.
    
    Usage:
        @profile_method("CustomName")
        def my_function():
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            profiler = get_profiler()
            
            if not profiler.enabled:
                return func(*args, **kwargs)
            
            entry_name = name or func.__qualname__
            
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                profiler.record(entry_name, elapsed)
        
        return wrapper  # type: ignore
    
    return decorator


# Convenience function for one-off measurements
def profile_block(name: str, extra: str = ""):
    """Context manager for profiling a block of code.
    
    Usage:
        with profile_block("loading_data"):
            data = load_stuff()
    """
    return get_profiler().measure(name, extra)
