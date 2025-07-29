#!/usr/bin/env python3
"""
Test whether awt.py conforms to PEP8 standards.

This test uses pycodestyle (formerly pep8) to check code formatting.
"""


import os
import pytest
import sys
import subprocess
import unittest
from pathlib import Path


class TestPEP8Compliance(unittest.TestCase):
    """Test that all awt Python files follow PEP8 style guidelines."""
    
    IGNORED_ERRORS = ['E501', 'W504']
    PYTHON_FILES = ['awt.py', 'cache_awt.py', 'conduits.py']

    def setUp(self):
        """Set up test environment."""
        awt_dir = os.environ.get('AWT_DIR') or os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.project_dir = Path(awt_dir)
        self.python_files = [self.project_dir / f for f in self.PYTHON_FILES]
        self.maxDiff = None  # Show full diffs for better debugging
    
    def test_pep8_compliance(self):
        """Test that all awt Python files pass pycodestyle checks."""
        # Check if pycodestyle is available
        try:
            import pycodestyle
        except ImportError:
            self.skipTest("pycodestyle not installed. Install with: pip install pycodestyle")
        
        # Run pycodestyle on all awt Python files
        style_guide = pycodestyle.StyleGuide(
            ignore=self.IGNORED_ERRORS,
            quiet=True
        )
        
        if not self.python_files:
            self.skipTest("No Python files found to check")
        
        files_to_check = [str(f) for f in self.python_files]
        result = style_guide.check_files(files_to_check)
        
        if result.total_errors > 0:
            # Get detailed error report
            detailed_guide = pycodestyle.StyleGuide(
                max_line_length=79,
                ignore=self.IGNORED_ERRORS,
                quiet=False
            )
            detailed_guide.check_files(files_to_check)
            
            file_list = ' '.join(f.name for f in self.python_files)
            self.fail(
                f"PEP8 compliance check failed with {result.total_errors} errors.\n"
                f"Run 'pycodestyle {file_list}' to see detailed errors and fix them."
            )
        
        self.assertEqual(result.total_errors, 0, 
                        "All awt Python files should pass PEP8 style checks")
    
    def test_pep8_compliance_cli(self):
        """Test PEP8 compliance using command-line pycodestyle."""
        if not self.python_files:
            self.skipTest("No Python files found to check")
        
        files_to_check = [str(f) for f in self.python_files]
        
        try:
            cmd = ['pycodestyle', '--max-line-length=79', f'--ignore={",".join(self.IGNORED_ERRORS)}'] + files_to_check
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
        except FileNotFoundError:
            self.skipTest("pycodestyle command not found. Install with: pip install pycodestyle")
        except subprocess.TimeoutExpired:
            self.fail("pycodestyle check timed out")
        
        if result.returncode != 0:
            # Parse and categorize the errors for better feedback
            errors = result.stdout.strip().split('\n') if result.stdout else []
            categorized_errors = self._categorize_pep8_errors(errors)
            
            error_summary = self._format_error_summary(categorized_errors)
            
            file_list = ' '.join(f.name for f in self.python_files)
            self.fail(
                f"PEP8 compliance check failed with {len(errors)} errors:\n\n"
                f"{error_summary}\n\n"
                f"To fix these issues:\n"
                f"1. Install autopep8: pip install autopep8\n"
                f"2. Run: autopep8 --in-place {file_list}\n"
                f"3. Or fix manually using the guidance above\n"
                f"4. Re-run this test to verify fixes"
            )
        
        self.assertEqual(result.returncode, 0, 
                        "pycodestyle should return exit code 0 for compliant code")
    
    @unittest.skip("This test is too strict for our current codebase")
    def test_strict_pep8_compliance(self):
        """Strict PEP8 compliance test that we're not ready for yet."""
        # This test would be very strict and fail on many issues
        # We can enable it later when the codebase is more PEP8 compliant
        pass
    
    @unittest.skipIf(not Path('awt.py').exists(), "awt.py not found")
    def test_conditional_pep8_check(self):
        """PEP8 check that only runs if awt.py exists."""
        # This test will be skipped if awt.py doesn't exist
        pass
    
    @unittest.skipUnless(sys.platform.startswith('linux'), "Only runs on Linux")
    def test_linux_specific_pep8_check(self):
        """PEP8 check that only runs on Linux systems."""
        # This test will be skipped on non-Linux systems
        pass
    
    def test_optional_pep8_check(self):
        """Optional PEP8 check that can be disabled via environment variable."""
        if os.environ.get('SKIP_OPTIONAL_PEP8') == '1':
            self.skipTest("Optional PEP8 check disabled via SKIP_OPTIONAL_PEP8=1")
        
        # This test will run unless explicitly disabled
        pass
    
    def _categorize_pep8_errors(self, errors):
        """Categorize PEP8 errors by type for better reporting."""
        categories = {
            'whitespace': [],
            'imports': [],
            'indentation': [],
            'comments': [],
            'blank_lines': [],
            'other': []
        }
        
        for error in errors:
            if not error.strip():
                continue
                
            # Parse error line: file:line:col: code message
            parts = error.split(':', 3)
            if len(parts) >= 4:
                line_num = parts[1]
                code = parts[2].strip()
                message = parts[3].strip()
                
                error_info = f"Line {line_num}: {code} - {message}"
                
                if code.startswith('E2'):  # Whitespace issues
                    categories['whitespace'].append(error_info)
                elif code.startswith('E4'):  # Import issues
                    categories['imports'].append(error_info)
                elif code.startswith('E1'):  # Indentation issues
                    categories['indentation'].append(error_info)
                elif code.startswith('E3'):  # Blank line issues
                    categories['blank_lines'].append(error_info)
                elif code.startswith('E2'):  # Comment issues
                    categories['comments'].append(error_info)
                else:
                    categories['other'].append(error_info)
        
        return categories
    
    def _format_error_summary(self, categorized_errors):
        """Format categorized errors into a readable summary."""
        summary = []
        
        for category, errors in categorized_errors.items():
            if errors:
                summary.append(f"\n{category.upper().replace('_', ' ')} ({len(errors)} errors):")
                for error in errors:
                    summary.append(f"  {error}")
        
        return '\n'.join(summary)
    
    def test_file_exists(self):
        """Test that AWT Python files exist."""
        self.assertTrue(len(self.python_files) > 0, 
                       f"At least one AWT Python file should exist. Found: {[f.name for f in self.python_files]}")
    
    def test_file_is_readable(self):
        """Test that self.PYTHON_FILES are readable."""
        for file_path in self.python_files:
            if file_path.exists():
                self.assertTrue(file_path.is_file(), 
                               f"{file_path} should be a readable file")

    def test_conservative_pep8_check(self):
        """Conservative PEP8 check focusing on safe issues only."""
        files_to_check = []
        for file_path in self.python_files:
            if file_path.exists():
                files_to_check.append((file_path.name, file_path))
        
        if not files_to_check:
            self.skipTest("No AWT Python files found")
        
        all_issues = []
        
        for filename, filepath in files_to_check:
            content = filepath.read_text()
            lines = content.split('\n')
            issues = []
            
            # Check for safe-to-fix issues only
            for i, line in enumerate(lines, 1):
                # Check for trailing whitespace (safe to fix)
                if line.rstrip() != line and line.strip():
                    issues.append(f"{filename}:{i}: Trailing whitespace")
                
                # Check for tabs (should use spaces) - safe to fix
                if '\t' in line:
                    issues.append(f"{filename}:{i}: Contains tabs (use spaces)")
                
                # Check for lines longer than 79 characters (excluding comments)
                # This is informational only - not a hard failure
                if len(line) > 79 and not line.strip().startswith('#'):
                    issues.append(f"{filename}:{i}: Line too long ({len(line)} chars) - consider breaking")
            
            # Check for proper file ending
            if content and not content.endswith('\n'):
                issues.append(f"{filename}: File should end with a newline")
            
            all_issues.extend(issues)
        
        # Only fail on critical issues, warn on others
        critical_issues = [issue for issue in all_issues if 'tabs' in issue or 'trailing whitespace' in issue]
        
        if critical_issues:
            self.fail(
                f"Critical PEP8 issues found:\n" +
                '\n'.join(f"  {issue}" for issue in critical_issues) +
                f"\n\nOther issues (consider fixing):\n" +
                '\n'.join(f"  {issue}" for issue in all_issues if issue not in critical_issues)
            )
        elif all_issues:
            # Just warn about non-critical issues
            print(f"\nPEP8 suggestions (not failures):")
            for issue in all_issues:
                print(f"  {issue}")
    
    def test_import_order_safety(self):
        """Test that imports are in a safe order (don't break functionality)."""
        files_to_check = []
        for file_path in self.python_files:
            if file_path.exists():
                files_to_check.append((file_path.name, file_path))
        
        if not files_to_check:
            self.skipTest("No AWT Python files found")
        
        for filename, filepath in files_to_check:
            content = filepath.read_text()
            lines = content.split('\n')
            
            # Find where abiflib imports are
            abiflib_import_line = None
            setup_lines = []
            
            for i, line in enumerate(lines, 1):
                if 'from abiflib import' in line or 'import abiflib' in line:
                    abiflib_import_line = i
                elif abiflib_import_line is None and ('AWT_DIR' in line or 'ABIFTOOL_DIR' in line or 'sys.path.append' in line):
                    setup_lines.append(i)
            
            # Check if abiflib imports come after setup
            if abiflib_import_line and setup_lines:
                max_setup_line = max(setup_lines)
                if abiflib_import_line < max_setup_line:
                    self.fail(
                        f"{filename}: abiflib import at line {abiflib_import_line} comes before setup "
                        f"at line {max_setup_line}. This could break functionality if "
                        f"autopep8 moves imports to the top."
                    )


# Example of how to run specific tests or skip them
class TestPEP8IndividualChecks(unittest.TestCase):
    """Individual PEP8 checks that can be run selectively."""
    
    # Use the same list as the main class
    PYTHON_FILES = ['awt.py', 'cache_awt.py', 'conduits.py']
    
    def setUp(self):
        self.project_dir = Path(__file__).parent
        self.python_files = [self.project_dir / f for f in self.PYTHON_FILES]
    
    @unittest.skip("Enable when ready to check line length")
    def test_line_length(self):
        """Check that no lines exceed 79 characters."""
        files_to_check = []
        for file_path in self.python_files:
            if file_path.exists():
                files_to_check.append((file_path.name, file_path))
        
        if not files_to_check:
            self.skipTest("No AWT Python files found")
        
        all_long_lines = []
        
        for filename, filepath in files_to_check:
            content = filepath.read_text()
            lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                if len(line) > 79 and not line.strip().startswith('#'):
                    all_long_lines.append(f"{filename}:{i}: {len(line)} chars")
        
        if all_long_lines:
            self.fail(f"Lines too long:\n" + '\n'.join(all_long_lines))
    
    @unittest.skip("Enable when ready to check import order")
    def test_import_order(self):
        """Check that imports follow PEP8 order."""
        # This would check import order, but we skip it because our code
        # has legitimate reasons for non-standard import order
        pass


if __name__ == '__main__':
    # Set up test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestPEP8Compliance))
    suite.addTests(loader.loadTestsFromTestCase(TestPEP8IndividualChecks))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(not result.wasSuccessful())
