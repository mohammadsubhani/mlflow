# This file contains utility functions for scorer functionality.

import ast
import inspect
import logging
import re
from textwrap import dedent
from typing import Any, Callable, Optional

_logger = logging.getLogger(__name__)


def _validate_function_name(func_name: str) -> bool:
    """Validate that func_name is a safe Python identifier."""
    if not func_name.isidentifier():
        return False
    # Ensure it's not a Python keyword or builtin
    import keyword
    if keyword.iskeyword(func_name) or func_name in dir(__builtins__):
        return False
    return True


def _validate_function_signature(signature: str) -> bool:
    """Validate that the signature is safe and properly formatted."""
    try:
        # Try to parse as a function signature
        test_func = f"def test_func{signature}: pass"
        ast.parse(test_func)
        return True
    except SyntaxError:
        return False


def _validate_function_source(source: str) -> bool:
    """Validate that the source code is safe Python code."""
    try:
        # Parse the source to ensure it's valid Python
        ast.parse(source)
        
        # Check for dangerous operations
        tree = ast.parse(source)
        
        class DangerousNodeVisitor(ast.NodeVisitor):
            def __init__(self):
                self.has_dangerous_nodes = False
                
            def visit_Import(self, node):
                # Allow only specific safe imports
                for alias in node.names:
                    if not alias.name.startswith(('mlflow.', 'numpy', 'pandas')):
                        self.has_dangerous_nodes = True
                self.generic_visit(node)
                
            def visit_ImportFrom(self, node):
                # Allow only mlflow imports
                if node.module and not node.module.startswith('mlflow'):
                    self.has_dangerous_nodes = True
                self.generic_visit(node)
                
            def visit_Call(self, node):
                # Check for dangerous function calls
                if isinstance(node.func, ast.Name):
                    dangerous_funcs = {'exec', 'eval', '__import__', 'compile', 'open'}
                    if node.func.id in dangerous_funcs:
                        self.has_dangerous_nodes = True
                self.generic_visit(node)
        
        visitor = DangerousNodeVisitor()
        visitor.visit(tree)
        return not visitor.has_dangerous_nodes
        
    except SyntaxError:
        return False


# FunctionBodyExtractor class is forked from https://github.com/unitycatalog/unitycatalog/blob/20dd3820be332ac04deec4e063099fb863eb3392/ai/core/src/unitycatalog/ai/core/utils/callable_utils.py
class FunctionBodyExtractor(ast.NodeVisitor):
    """
    AST NodeVisitor class to extract the body of a function.
    """

    def __init__(self, func_name: str, source_code: str):
        self.func_name = func_name
        self.source_code = source_code
        self.function_body = ""
        self.indent_unit = 4
        self.found = False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if not self.found and node.name == self.func_name:
            self.found = True
            self.extract_body(node)

    def extract_body(self, node: ast.FunctionDef):
        body = node.body
        # Skip the docstring
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]

        if not body:
            return

        start_lineno = body[0].lineno
        end_lineno = body[-1].end_lineno

        source_lines = self.source_code.splitlines(keepends=True)
        function_body_lines = source_lines[start_lineno - 1 : end_lineno]

        self.function_body = dedent("".join(function_body_lines)).rstrip("\n")

        indents = [stmt.col_offset for stmt in body if stmt.col_offset is not None]
        if indents:
            self.indent_unit = min(indents)


# extract_function_body function is forked from https://github.com/unitycatalog/unitycatalog/blob/20dd3820be332ac04deec4e063099fb863eb3392/ai/core/src/unitycatalog/ai/core/utils/callable_utils.py
def extract_function_body(func: Callable[..., Any]) -> tuple[str, int]:
    """
    Extracts the body of a function as a string without the signature or docstring,
    dedents the code, and returns the indentation unit used in the function (e.g., 2 or 4 spaces).
    """
    source_lines, _ = inspect.getsourcelines(func)
    dedented_source = dedent("".join(source_lines))
    func_name = func.__name__

    extractor = FunctionBodyExtractor(func_name, dedented_source)
    parsed_source = ast.parse(dedented_source)
    extractor.visit(parsed_source)

    return extractor.function_body, extractor.indent_unit


def recreate_function(source: str, signature: str, func_name: str) -> Optional[Callable]:
    """
    Recreate a function from its source code, signature, and name.

    Args:
        source: The function body source code.
        signature: The function signature string (e.g., "(inputs, outputs)").
        func_name: The name of the function.

    Returns:
        The recreated function or None if recreation failed.
    """
    try:
        # Validate inputs to prevent code injection
        if not _validate_function_name(func_name):
            _logger.error(f"Invalid function name: {func_name}")
            return None
            
        if not _validate_function_signature(signature):
            _logger.error(f"Invalid function signature: {signature}")
            return None
            
        if not _validate_function_source(source):
            _logger.error("Invalid or potentially dangerous function source code")
            return None

        # Parse the signature to build the function definition
        sig_match = re.match(r"\((.*?)\)", signature)
        if not sig_match:
            return None

        params_str = sig_match.group(1).strip()

        # Build the function definition
        func_def = f"def {func_name}({params_str}):\n"
        # Indent the source code
        indented_source = "\n".join(f"    {line}" for line in source.split("\n"))
        func_def += indented_source

        # Create a restricted namespace with only allowed MLflow imports
        import_namespace = {
            '__builtins__': {
                # Only allow safe builtins
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                'range': range,
                'enumerate': enumerate,
                'zip': zip,
                'isinstance': isinstance,
                'type': type,
            }
        }

        # Import commonly used MLflow classes
        try:
            from mlflow.entities import (
                Assessment,
                AssessmentError,
                AssessmentSource,
                AssessmentSourceType,
                Feedback,
            )
            from mlflow.genai.judges import CategoricalRating

            import_namespace.update(
                {
                    "Feedback": Feedback,
                    "Assessment": Assessment,
                    "AssessmentSource": AssessmentSource,
                    "AssessmentError": AssessmentError,
                    "AssessmentSourceType": AssessmentSourceType,
                    "CategoricalRating": CategoricalRating,
                }
            )
        except ImportError:
            pass  # Some imports might not be available in all contexts

        local_namespace = {}

        # Execute the function definition with MLflow imports available
        exec(func_def, import_namespace, local_namespace)

        # Return the recreated function
        return local_namespace[func_name]

    except Exception as e:
        _logger.warning(f"Failed to recreate function '{func_name}' from serialized source code: {e}")
        return None
