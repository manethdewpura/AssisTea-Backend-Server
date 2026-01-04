"""Script to run all tests."""
import pytest
import sys

if __name__ == '__main__':
    # Run pytest with verbose output
    exit_code = pytest.main([
        '-v',           # Verbose
        '--tb=short',   # Short traceback format
        'tests/'        # Test directory
    ])
    sys.exit(exit_code)

