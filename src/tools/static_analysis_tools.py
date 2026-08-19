"""Static analysis tools for evaluating generated Python and Java code quality, syntax, and complexity."""

from __future__ import annotations
import ast
import re
from typing import Any


class StaticAnalysisTools:
    """Performs AST and regex-based validation, syntax checking, and code metrics extraction on Python and Java code."""

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
        """Estimates cyclomatic complexity (McCabe) by counting branching nodes in Python AST."""
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

    @staticmethod
    def validate_java_syntax(code_str: str) -> dict[str, Any]:
        """Validates Java code structure, brace balancing, class/record/interface declarations, and imports."""
        if not code_str or not code_str.strip():
            return {
                "valid_syntax": False,
                "error": "Java code is empty",
                "classes": [],
                "methods": [],
                "imports": [],
                "line_count": 0
            }

        # Check balanced braces, parentheses, and brackets
        brace_stack = []
        pairs = {')': '(', '}': '{', ']': '['}
        in_string = False
        in_char = False
        in_single_comment = False
        in_multi_comment = False
        lines = code_str.splitlines()

        for line_no, line in enumerate(lines, start=1):
            i = 0
            while i < len(line):
                char = line[i]
                next_char = line[i + 1] if i + 1 < len(line) else ''

                if in_single_comment:
                    break
                if in_multi_comment:
                    if char == '*' and next_char == '/':
                        in_multi_comment = False
                        i += 1
                    i += 1
                    continue

                if char == '/' and next_char == '/':
                    in_single_comment = True
                    break
                if char == '/' and next_char == '*':
                    in_multi_comment = True
                    i += 2
                    continue

                if char == '"' and not in_char:
                    if i == 0 or line[i - 1] != '\\':
                        in_string = not in_string
                elif char == "'" and not in_string:
                    if i == 0 or line[i - 1] != '\\':
                        in_char = not in_char
                elif not in_string and not in_char:
                    if char in '({[':
                        brace_stack.append((char, line_no))
                    elif char in ')}]':
                        expected = pairs[char]
                        if not brace_stack or brace_stack[-1][0] != expected:
                            return {
                                "valid_syntax": False,
                                "error": f"Mismatched closing bracket '{char}' at line {line_no}",
                                "classes": [],
                                "methods": [],
                                "imports": [],
                                "line_count": len(lines)
                            }
                        brace_stack.pop()
                i += 1
            in_single_comment = False

        if brace_stack:
            unclosed, line_no = brace_stack[-1]
            return {
                "valid_syntax": False,
                "error": f"Unclosed '{unclosed}' opened at line {line_no}",
                "classes": [],
                "methods": [],
                "imports": [],
                "line_count": len(lines)
            }

        # Extract declared types and methods
        class_pattern = re.compile(r'\b(?:public|protected|private|static|\s)+\s+(?:class|interface|enum|record)\s+([A-Za-z0-9_]+)')
        classes = class_pattern.findall(code_str)

        method_pattern = re.compile(r'\b(?:public|protected|private|static|\s)+\s+(?:[A-Za-z0-9_<>[\]]+)\s+([A-Za-z0-9_]+)\s*\([^)]*\)\s*(?:throws\s+[A-Za-z0-9_,\s]+)?\s*\{')
        methods = [m for m in method_pattern.findall(code_str) if m not in ('if', 'for', 'while', 'switch', 'catch')]

        import_pattern = re.compile(r'^\s*import\s+([^;]+);', re.MULTILINE)
        imports = import_pattern.findall(code_str)

        return {
            "valid_syntax": True,
            "error": None,
            "classes": classes,
            "methods": methods,
            "imports": imports,
            "line_count": len(lines)
        }

    @staticmethod
    def calculate_java_cyclomatic_complexity(code_str: str) -> int:
        """Estimates Java cyclomatic complexity by identifying branching and control flow constructs."""
        if not code_str:
            return 1
        
        # Remove comments and strings
        clean = re.sub(r'//.*', '', code_str)
        clean = re.sub(r'/\*.*?\*/', '', clean, flags=re.DOTALL)
        clean = re.sub(r'"(?:\\.|[^"\\])*"', '', clean)

        keywords = [
            r'\bif\s*\(',
            r'\belse\s+if\s*\(',
            r'\bfor\s*\(',
            r'\bwhile\s*\(',
            r'\bcase\b',
            r'\bcatch\s*\(',
            r'\bthrow\b',
            r'\bswitch\s*\(',
            r'&&',
            r'\|\|',
            r'\?'
        ]
        
        complexity = 1
        for kw in keywords:
            matches = re.findall(kw, clean)
            complexity += len(matches)
            
        return complexity

