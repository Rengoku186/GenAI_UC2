"""Static analysis tools for evaluating generated Python code quality and syntax."""

from __future__ import annotations
import ast
from typing import Any


class StaticAnalysisTools:
    """Performs AST validation, syntax checking, and code metrics extraction on Python code."""

    @staticmethod
    def validate_python_syntax(code_str: str) -> dict[str, Any]:
        """Validates Python syntax and extracts top-level symbols using the standard AST library."""
        try:
            tree = ast.parse(code_str)
            
            # Extract classes and functions
            classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            async_functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)]
            
            # Extract imports
            imports: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for alias in node.names:
                        imports.append(f"{mod}.{alias.name}")

            return {
                "valid_syntax": True,
                "error": None,
                "classes": classes,
                "functions": functions + async_functions,
                "imports": imports,
                "line_count": len(code_str.splitlines())
            }
        except SyntaxError as e:
            return {
                "valid_syntax": False,
                "error": f"SyntaxError at line {e.lineno}, col {e.offset}: {e.msg}",
                "classes": [],
                "functions": [],
                "imports": [],
                "line_count": len(code_str.splitlines())
            }
        except Exception as e:
            return {
                "valid_syntax": False,
                "error": f"Parse Error: {str(e)}",
                "classes": [],
                "functions": [],
                "imports": [],
                "line_count": len(code_str.splitlines())
            }

    @staticmethod
    def calculate_cyclomatic_complexity(code_str: str) -> int:
        """Estimates cyclomatic complexity (McCabe) by counting branching nodes in AST."""
        try:
            tree = ast.parse(code_str)
            complexity = 1
            branch_types = (
                ast.If, ast.While, ast.For, ast.AsyncFor,
                ast.ExceptHandler, ast.With, ast.AsyncWith,
                ast.Assert, ast.comprehension
            )
            for node in ast.walk(tree):
                if isinstance(node, branch_types):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
            return complexity
        except Exception:
            return 1
