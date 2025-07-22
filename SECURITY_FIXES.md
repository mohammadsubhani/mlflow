# Security Vulnerabilities Fixed in MLflow Codebase

This document describes 3 critical security vulnerabilities found and fixed in the MLflow codebase.

## Bug 1: Code Injection Vulnerability in Scorer Utils

**File**: `mlflow/genai/scorers/scorer_utils.py`
**Severity**: Critical
**Type**: Code Injection

### Description
The `recreate_function()` function used `exec()` to execute dynamically constructed function definitions without proper validation. This created a critical security vulnerability where malicious code could be injected through the `source`, `signature`, or `func_name` parameters.

### Security Impact
An attacker who could control any of these parameters could execute arbitrary Python code, leading to:
- Remote code execution
- Data exfiltration  
- System compromise
- Privilege escalation

### Fix Applied
Added comprehensive input validation:
1. **Function name validation**: Ensures function names are valid Python identifiers and not reserved keywords
2. **Signature validation**: Validates function signatures using AST parsing
3. **Source code validation**: Uses AST analysis to detect dangerous operations like `exec`, `eval`, `__import__`, etc.
4. **Restricted execution namespace**: Limited the `__builtins__` to only safe functions
5. **Enhanced error logging**: Added specific error messages for validation failures

### Code Changes
- Added `_validate_function_name()`, `_validate_function_signature()`, and `_validate_function_source()` functions
- Modified `recreate_function()` to validate all inputs before execution
- Restricted the execution namespace to prevent dangerous operations

## Bug 2: SQL Injection Vulnerability in Delta Utils

**File**: `mlflow/data/spark_delta_utils.py`
**Severity**: High
**Type**: SQL Injection

### Description
The `_is_delta_table()` function constructed SQL queries using f-string formatting with user-provided `table_name` parameter without proper sanitization, creating a SQL injection vulnerability.

### Security Impact
An attacker could inject malicious SQL code through the table_name parameter, potentially:
- Accessing unauthorized data
- Modifying database contents
- Executing arbitrary SQL commands
- Performing database reconnaissance

### Fix Applied
- Used the existing `_backtick_quote()` function to properly sanitize table names
- Added proper SQL identifier quoting to prevent injection attacks
- Maintained functionality while securing the SQL query construction

### Code Changes
- Added table name sanitization using `_backtick_quote(table_name)`
- Modified the SQL query to use the sanitized table name
- Added comments explaining the security fix

## Bug 3: Unsafe YAML Loading in Requirements Updater

**File**: `dev/update_requirements.py`
**Severity**: High
**Type**: Arbitrary Code Execution

### Description
The script used `yaml.load()` without specifying a safe loader, which could lead to arbitrary code execution if the YAML file contained malicious content using YAML's object instantiation features.

### Security Impact
An attacker who could control the YAML file could execute arbitrary Python code during parsing, potentially:
- Executing system commands
- Installing malware
- Accessing sensitive files
- Compromising the development environment

### Fix Applied
- Changed `yaml.load(requirements_src)` to `yaml.safe_load(requirements_src)`
- Added explanatory comment about preventing arbitrary code execution
- Maintained all existing functionality while securing the YAML parsing

### Code Changes
- Replaced `yaml.load()` with `yaml.safe_load()`
- Added security-focused comment explaining the change

## Verification

All fixes have been applied and maintain backward compatibility while significantly improving security. The changes:

1. **Preserve functionality**: All legitimate use cases continue to work as expected
2. **Add security layers**: Multiple validation steps prevent malicious input
3. **Provide clear logging**: Security violations are logged with specific error messages
4. **Follow security best practices**: Use established patterns for input validation and safe parsing

## Recommendations

1. **Code Review**: Implement mandatory security reviews for code using `exec()`, `eval()`, or dynamic SQL
2. **Static Analysis**: Add SAST tools to detect similar vulnerabilities automatically
3. **Input Validation**: Establish standard libraries for input validation across the codebase
4. **Security Testing**: Include security test cases for functions handling user input
5. **Developer Training**: Educate developers on secure coding practices for Python and SQL

These fixes address critical security vulnerabilities that could have led to remote code execution and data compromise. The implemented solutions follow security best practices while maintaining the existing functionality of the affected components.