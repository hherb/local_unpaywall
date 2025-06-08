#!/usr/bin/env python3
"""
Test Runner for Local Unpaywall Project
=======================================

This script runs all tests in the test package and provides a summary.

Usage:
    python -m test.run_all_tests
    
    # Or from the project root:
    python test/run_all_tests.py
"""

import sys
import os
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_all_tests():
    """Run all tests in the test package."""
    print("=" * 60)
    print("LOCAL UNPAYWALL PROJECT - TEST SUITE")
    print("=" * 60)
    
    # Discover and run all tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(
        verbosity=2,
        stream=sys.stdout,
        descriptions=True,
        failfast=False
    )
    
    print(f"\nRunning tests from: {start_dir}")
    print("-" * 60)
    
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped) if hasattr(result, 'skipped') else 0
    
    print(f"Total tests run: {total_tests}")
    print(f"Successes: {total_tests - failures - errors - skipped}")
    print(f"Failures: {failures}")
    print(f"Errors: {errors}")
    print(f"Skipped: {skipped}")
    
    if result.wasSuccessful():
        print("\n✓ ALL TESTS PASSED!")
        return True
    else:
        print(f"\n✗ TESTS FAILED ({failures} failures, {errors} errors)")
        
        if result.failures:
            print("\nFAILURES:")
            for test, traceback in result.failures:
                print(f"  - {test}")
        
        if result.errors:
            print("\nERRORS:")
            for test, traceback in result.errors:
                print(f"  - {test}")
        
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
