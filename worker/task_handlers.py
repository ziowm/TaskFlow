"""
Example task handlers demonstrating payload processing and error handling patterns.

This module provides sample task execution functions that can be used as templates
for implementing custom task logic in the distributed task scheduler.
"""

import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def execute_math_operation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example task handler: Perform mathematical operations
    
    Demonstrates:
    - Payload validation
    - Result generation
    - Error handling for invalid inputs
    
    Args:
        payload: Task data containing:
            - operation: str (add, subtract, multiply, divide)
            - a: number
            - b: number
            
    Returns:
        Result dictionary with operation result
        
    Raises:
        ValueError: If payload is invalid or operation is unsupported
        ZeroDivisionError: If attempting to divide by zero
        
    Example payload:
        {
            "operation": "add",
            "a": 10,
            "b": 5
        }
    """
    # Validate required fields
    if 'operation' not in payload:
        raise ValueError("Missing required field: 'operation'")
    if 'a' not in payload or 'b' not in payload:
        raise ValueError("Missing required fields: 'a' and 'b'")
    
    operation = payload['operation']
    a = payload['a']
    b = payload['b']
    
    # Validate numeric types
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise ValueError("Fields 'a' and 'b' must be numeric")
    
    # Perform operation
    if operation == 'add':
        result = a + b
    elif operation == 'subtract':
        result = a - b
    elif operation == 'multiply':
        result = a * b
    elif operation == 'divide':
        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        result = a / b
    else:
        raise ValueError(f"Unsupported operation: {operation}")
    
    logger.info(f"Executed {operation}: {a} {operation} {b} = {result}")
    
    return {
        "operation": operation,
        "a": a,
        "b": b,
        "result": result
    }


def execute_data_processing(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example task handler: Process data with simulated work
    
    Demonstrates:
    - Processing lists of data
    - Simulating longer-running tasks
    - Generating summary statistics
    
    Args:
        payload: Task data containing:
            - data: list of numbers
            - operation: str (sum, average, max, min)
            
    Returns:
        Result dictionary with processed data
        
    Raises:
        ValueError: If payload is invalid
        
    Example payload:
        {
            "data": [1, 2, 3, 4, 5],
            "operation": "average"
        }
    """
    # Validate required fields
    if 'data' not in payload:
        raise ValueError("Missing required field: 'data'")
    if 'operation' not in payload:
        raise ValueError("Missing required field: 'operation'")
    
    data = payload['data']
    operation = payload['operation']
    
    # Validate data is a list
    if not isinstance(data, list):
        raise ValueError("Field 'data' must be a list")
    
    if not data:
        raise ValueError("Field 'data' cannot be empty")
    
    # Validate all elements are numeric
    if not all(isinstance(x, (int, float)) for x in data):
        raise ValueError("All elements in 'data' must be numeric")
    
    # Simulate processing time (proportional to data size)
    processing_time = min(len(data) * 0.01, 2.0)  # Cap at 2 seconds
    time.sleep(processing_time)
    
    # Perform operation
    if operation == 'sum':
        result = sum(data)
    elif operation == 'average':
        result = sum(data) / len(data)
    elif operation == 'max':
        result = max(data)
    elif operation == 'min':
        result = min(data)
    else:
        raise ValueError(f"Unsupported operation: {operation}")
    
    logger.info(f"Processed {len(data)} items with operation '{operation}': result={result}")
    
    return {
        "operation": operation,
        "count": len(data),
        "result": result,
        "processing_time_seconds": processing_time
    }


def execute_text_processing(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example task handler: Process text data
    
    Demonstrates:
    - String manipulation
    - Multiple result fields
    - Handling different data types
    
    Args:
        payload: Task data containing:
            - text: str
            - operation: str (uppercase, lowercase, word_count, reverse)
            
    Returns:
        Result dictionary with processed text
        
    Raises:
        ValueError: If payload is invalid
        
    Example payload:
        {
            "text": "Hello World",
            "operation": "uppercase"
        }
    """
    # Validate required fields
    if 'text' not in payload:
        raise ValueError("Missing required field: 'text'")
    if 'operation' not in payload:
        raise ValueError("Missing required field: 'operation'")
    
    text = payload['text']
    operation = payload['operation']
    
    # Validate text is a string
    if not isinstance(text, str):
        raise ValueError("Field 'text' must be a string")
    
    # Perform operation
    if operation == 'uppercase':
        result = text.upper()
    elif operation == 'lowercase':
        result = text.lower()
    elif operation == 'word_count':
        result = len(text.split())
    elif operation == 'reverse':
        result = text[::-1]
    else:
        raise ValueError(f"Unsupported operation: {operation}")
    
    logger.info(f"Processed text with operation '{operation}'")
    
    return {
        "operation": operation,
        "original_length": len(text),
        "result": result
    }


def execute_task_with_error_demo(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example task handler: Demonstrate error handling
    
    This handler intentionally raises errors based on payload to demonstrate
    how the worker handles task failures.
    
    Args:
        payload: Task data containing:
            - error_type: str (none, value_error, runtime_error, timeout)
            
    Returns:
        Result dictionary if no error requested
        
    Raises:
        ValueError: If error_type is 'value_error'
        RuntimeError: If error_type is 'runtime_error'
        
    Example payload:
        {
            "error_type": "none"
        }
    """
    error_type = payload.get('error_type', 'none')
    
    if error_type == 'value_error':
        raise ValueError("Intentional ValueError for testing error handling")
    elif error_type == 'runtime_error':
        raise RuntimeError("Intentional RuntimeError for testing error handling")
    elif error_type == 'timeout':
        # Simulate a long-running task that might timeout
        logger.warning("Simulating long-running task (60 seconds)")
        time.sleep(60)
    elif error_type == 'none':
        return {
            "status": "success",
            "message": "Task completed without errors"
        }
    else:
        raise ValueError(f"Unknown error_type: {error_type}")
