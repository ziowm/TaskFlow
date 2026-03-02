import time
import random
import math
import logging
from collections import Counter
from typing import Dict, Any

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────

def _require(payload, *fields):
    for f in fields:
        if f not in payload:
            raise ValueError(f"Missing required field: '{f}'")


# ── Math ───────────────────────────────────────────────────────────────────

def execute_math_operation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """add / subtract / multiply / divide / power / sqrt / modulo"""
    _require(payload, 'operation')
    op = payload['operation']

    if op == 'sqrt':
        _require(payload, 'a')
        a = payload['a']
        if not isinstance(a, (int, float)):
            raise ValueError("'a' must be numeric")
        if a < 0:
            raise ValueError("Cannot take sqrt of a negative number")
        return {"operation": op, "a": a, "result": math.sqrt(a)}

    _require(payload, 'a', 'b')
    a, b = payload['a'], payload['b']
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise ValueError("'a' and 'b' must be numeric")

    if op == 'add':
        result = a + b
    elif op == 'subtract':
        result = a - b
    elif op == 'multiply':
        result = a * b
    elif op == 'divide':
        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        result = a / b
    elif op == 'power':
        result = a ** b
    elif op == 'modulo':
        if b == 0:
            raise ZeroDivisionError("Cannot modulo by zero")
        result = a % b
    else:
        raise ValueError(f"Unsupported operation: '{op}'. "
                         "Valid: add, subtract, multiply, divide, power, modulo, sqrt")

    logger.info(f"math: {a} {op} {b} = {result}")
    return {"operation": op, "a": a, "b": b, "result": result}


def execute_fibonacci(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return the first n Fibonacci numbers."""
    _require(payload, 'n')
    n = payload['n']
    if not isinstance(n, int) or n < 1:
        raise ValueError("'n' must be a positive integer")
    if n > 500:
        raise ValueError("'n' must be <= 500")

    seq = [0, 1]
    for _ in range(n - 2):
        seq.append(seq[-1] + seq[-2])
    seq = seq[:n]

    return {"n": n, "sequence": seq, "nth_value": seq[-1]}


def execute_prime_check(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Check if a number is prime and return factors if not."""
    _require(payload, 'n')
    n = payload['n']
    if not isinstance(n, int) or n < 2:
        raise ValueError("'n' must be an integer >= 2")
    if n > 10_000_000:
        raise ValueError("'n' must be <= 10,000,000")

    def is_prime(num):
        if num < 2:
            return False
        if num == 2:
            return True
        if num % 2 == 0:
            return False
        for i in range(3, int(math.sqrt(num)) + 1, 2):
            if num % i == 0:
                return False
        return True

    def factors(num):
        f = []
        for i in range(2, int(math.sqrt(num)) + 1):
            while num % i == 0:
                f.append(i)
                num //= i
        if num > 1:
            f.append(num)
        return f

    prime = is_prime(n)
    return {
        "n": n,
        "is_prime": prime,
        "prime_factors": [] if prime else factors(n),
    }


def execute_matrix_multiply(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Multiply two matrices A and B."""
    _require(payload, 'a', 'b')
    A, B = payload['a'], payload['b']

    if not (isinstance(A, list) and isinstance(B, list)):
        raise ValueError("'a' and 'b' must be 2D arrays (lists of lists)")

    rows_a = len(A)
    if rows_a == 0:
        raise ValueError("Matrix 'a' cannot be empty")
    cols_a = len(A[0])
    rows_b = len(B)
    if rows_b == 0:
        raise ValueError("Matrix 'b' cannot be empty")
    cols_b = len(B[0])

    if cols_a != rows_b:
        raise ValueError(f"Shape mismatch: A is {rows_a}x{cols_a}, B is {rows_b}x{cols_b}")
    if rows_a > 20 or cols_b > 20:
        raise ValueError("Matrices must be at most 20x20")

    result = [[sum(A[i][k] * B[k][j] for k in range(cols_a))
               for j in range(cols_b)]
              for i in range(rows_a)]

    return {
        "shape_a": [rows_a, cols_a],
        "shape_b": [rows_b, cols_b],
        "result_shape": [rows_a, cols_b],
        "result": result,
    }


# ── Data processing ────────────────────────────────────────────────────────

def execute_data_processing(payload: Dict[str, Any]) -> Dict[str, Any]:
    """sum / average / max / min / median / std / range — on a list of numbers."""
    _require(payload, 'data', 'operation')
    data = payload['data']
    op   = payload['operation']

    if not isinstance(data, list) or not data:
        raise ValueError("'data' must be a non-empty list")
    if not all(isinstance(x, (int, float)) for x in data):
        raise ValueError("All elements in 'data' must be numeric")
    if len(data) > 10_000:
        raise ValueError("'data' length must be <= 10,000")

    time.sleep(min(len(data) * 0.0001, 0.5))

    sorted_data = sorted(data)
    n = len(data)

    if op == 'sum':
        result = sum(data)
    elif op == 'average':
        result = sum(data) / n
    elif op == 'max':
        result = max(data)
    elif op == 'min':
        result = min(data)
    elif op == 'median':
        mid = n // 2
        result = sorted_data[mid] if n % 2 else (sorted_data[mid-1] + sorted_data[mid]) / 2
    elif op == 'std':
        mean = sum(data) / n
        result = math.sqrt(sum((x - mean) ** 2 for x in data) / n)
    elif op == 'range':
        result = max(data) - min(data)
    else:
        raise ValueError(f"Unsupported operation: '{op}'. "
                         "Valid: sum, average, max, min, median, std, range")

    return {"operation": op, "count": n, "result": round(result, 6)}


def execute_sort(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sort a list using bubble / merge / quick sort and report comparisons."""
    _require(payload, 'data', 'algorithm')
    data = list(payload['data'])
    alg  = payload['algorithm']

    if not isinstance(data, list) or not data:
        raise ValueError("'data' must be a non-empty list")
    if len(data) > 1000:
        raise ValueError("'data' length must be <= 1000 for sorting demo")

    comparisons = [0]

    def bubble(arr):
        a = arr[:]
        n = len(a)
        for i in range(n):
            for j in range(n - i - 1):
                comparisons[0] += 1
                if a[j] > a[j+1]:
                    a[j], a[j+1] = a[j+1], a[j]
        return a

    def merge(arr):
        if len(arr) <= 1:
            return arr
        mid = len(arr) // 2
        left  = merge(arr[:mid])
        right = merge(arr[mid:])
        result = []
        i = j = 0
        while i < len(left) and j < len(right):
            comparisons[0] += 1
            if left[i] <= right[j]:
                result.append(left[i]); i += 1
            else:
                result.append(right[j]); j += 1
        result.extend(left[i:])
        result.extend(right[j:])
        return result

    def quick(arr):
        if len(arr) <= 1:
            return arr
        pivot = arr[len(arr) // 2]
        left  = [x for x in arr if (comparisons.__setitem__(0, comparisons[0]+1) or True) and x < pivot]
        mid   = [x for x in arr if x == pivot]
        right = [x for x in arr if (comparisons.__setitem__(0, comparisons[0]+1) or True) and x > pivot]
        return quick(left) + mid + quick(right)

    start = time.time()
    if alg == 'bubble':
        sorted_data = bubble(data)
    elif alg == 'merge':
        sorted_data = merge(data)
    elif alg == 'quick':
        sorted_data = quick(data)
    else:
        raise ValueError(f"Unknown algorithm: '{alg}'. Valid: bubble, merge, quick")
    elapsed = round(time.time() - start, 4)

    return {
        "algorithm": alg,
        "input_length": len(data),
        "comparisons": comparisons[0],
        "elapsed_seconds": elapsed,
        "sorted": sorted_data,
    }


# ── Text ───────────────────────────────────────────────────────────────────

def execute_text_processing(payload: Dict[str, Any]) -> Dict[str, Any]:
    """uppercase / lowercase / word_count / reverse / palindrome_check / caesar_cipher / word_frequency"""
    _require(payload, 'text', 'operation')
    text = payload['text']
    op   = payload['operation']

    if not isinstance(text, str):
        raise ValueError("'text' must be a string")
    if len(text) > 50_000:
        raise ValueError("'text' must be <= 50,000 characters")

    if op == 'uppercase':
        result = text.upper()
    elif op == 'lowercase':
        result = text.lower()
    elif op == 'word_count':
        words = text.split()
        return {"operation": op, "word_count": len(words), "char_count": len(text),
                "sentence_count": text.count('.') + text.count('!') + text.count('?')}
    elif op == 'reverse':
        result = text[::-1]
    elif op == 'palindrome_check':
        clean = ''.join(c.lower() for c in text if c.isalnum())
        is_palindrome = clean == clean[::-1]
        return {"operation": op, "text": text, "is_palindrome": is_palindrome, "cleaned": clean}
    elif op == 'caesar_cipher':
        shift = int(payload.get('shift', 13))
        result = ''
        for c in text:
            if c.isalpha():
                base = ord('A') if c.isupper() else ord('a')
                result += chr((ord(c) - base + shift) % 26 + base)
            else:
                result += c
        return {"operation": op, "shift": shift, "input": text, "result": result}
    elif op == 'word_frequency':
        words = [w.strip('.,!?;:"\'').lower() for w in text.split() if w.strip('.,!?;:"\'')]
        freq  = dict(Counter(words).most_common(20))
        return {"operation": op, "total_words": len(words),
                "unique_words": len(freq), "top_20": freq}
    else:
        raise ValueError(f"Unsupported operation: '{op}'. "
                         "Valid: uppercase, lowercase, word_count, reverse, "
                         "palindrome_check, caesar_cipher, word_frequency")

    return {"operation": op, "original_length": len(text), "result": result}


# ── Simulated real-world ───────────────────────────────────────────────────

def execute_send_email(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate sending an email (no actual email is sent)."""
    _require(payload, 'to', 'subject', 'body')
    to      = payload['to']
    subject = payload['subject']
    body    = payload['body']

    if not isinstance(to, str) or '@' not in to:
        raise ValueError("'to' must be a valid email address")
    if not subject or not body:
        raise ValueError("'subject' and 'body' cannot be empty")

    time.sleep(0.3)  # simulate SMTP handshake

    return {
        "status": "sent",
        "to": to,
        "subject": subject,
        "body_length": len(body),
        "message_id": f"msg_{random.randint(100000, 999999)}@taskflow.dev",
        "note": "simulated — no real email was sent",
    }


def execute_resize_image(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate resizing an image (no actual image processing)."""
    _require(payload, 'filename', 'width', 'height')
    filename = payload['filename']
    width    = payload['width']
    height   = payload['height']

    if not isinstance(width, int) or not isinstance(height, int):
        raise ValueError("'width' and 'height' must be integers")
    if width <= 0 or height <= 0:
        raise ValueError("Dimensions must be positive")
    if width > 8000 or height > 8000:
        raise ValueError("Max dimension is 8000px")

    format_ = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
    if format_ not in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
        raise ValueError(f"Unsupported format: '{format_}'")

    original_w = random.randint(800, 4000)
    original_h = random.randint(600, 3000)
    compression = {'jpg': 0.85, 'jpeg': 0.85, 'png': 1.0, 'webp': 0.75, 'gif': 0.5}
    fake_size_kb = round(width * height * 3 * compression.get(format_, 0.85) / 1024, 1)

    time.sleep(0.4)  # simulate encode time

    return {
        "status": "resized",
        "filename": filename,
        "original_dimensions": [original_w, original_h],
        "new_dimensions": [width, height],
        "format": format_,
        "estimated_size_kb": fake_size_kb,
        "note": "simulated — no real image was processed",
    }


def execute_generate_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate generating a business report from fake data."""
    _require(payload, 'report_type')
    report_type = payload['report_type']
    period      = payload.get('period', 'monthly')

    valid_types = ('sales', 'traffic', 'performance', 'inventory')
    if report_type not in valid_types:
        raise ValueError(f"Unknown report type: '{report_type}'. Valid: {', '.join(valid_types)}")

    time.sleep(0.5)  # simulate aggregation

    base = random.randint(800, 1200)
    data = [round(base * random.uniform(0.8, 1.2), 2) for _ in range(12)]
    total = round(sum(data), 2)
    avg   = round(total / len(data), 2)
    trend = round((data[-1] - data[0]) / data[0] * 100, 1)

    return {
        "report_type": report_type,
        "period": period,
        "generated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        "summary": {
            "total": total,
            "average": avg,
            "peak": max(data),
            "trough": min(data),
            "trend_pct": trend,
        },
        "monthly_data": data,
        "note": "simulated data for demo purposes",
    }


# ── Chaos / stress testing ─────────────────────────────────────────────────

def execute_random_fail(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Fails randomly based on a configurable failure rate. Great for demoing DLQ."""
    fail_rate = float(payload.get('fail_rate', 0.5))
    if not 0.0 <= fail_rate <= 1.0:
        raise ValueError("'fail_rate' must be between 0.0 and 1.0")

    time.sleep(random.uniform(0.1, 0.5))

    if random.random() < fail_rate:
        raise RuntimeError(f"Random failure triggered (rate={fail_rate:.0%})")

    return {
        "status": "survived",
        "fail_rate": fail_rate,
        "message": f"Got lucky — passed with {fail_rate:.0%} failure rate",
    }


def execute_slow_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sleeps for a configurable number of seconds. Good for demoing timeout monitor."""
    duration = float(payload.get('duration_seconds', 5))
    if duration < 0:
        raise ValueError("'duration_seconds' must be >= 0")
    if duration > 400:
        raise ValueError("'duration_seconds' must be <= 400")

    start = time.time()
    time.sleep(duration)
    actual = round(time.time() - start, 3)

    return {
        "requested_seconds": duration,
        "actual_seconds": actual,
        "status": "completed",
    }


def execute_error_demo(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Intentionally raise specific error types for testing."""
    error_type = payload.get('error_type', 'none')

    if error_type == 'none':
        return {"status": "success", "message": "No error triggered"}
    elif error_type == 'value_error':
        raise ValueError("Intentional ValueError")
    elif error_type == 'runtime_error':
        raise RuntimeError("Intentional RuntimeError")
    elif error_type == 'timeout':
        time.sleep(400)
    elif error_type == 'division_by_zero':
        return {"result": 1 / 0}
    elif error_type == 'memory':
        _ = [0] * (10 ** 8)
    else:
        raise ValueError(f"Unknown error_type: '{error_type}'. "
                         "Valid: none, value_error, runtime_error, timeout, division_by_zero, memory")
