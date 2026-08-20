"""Static analysis tools for evaluating generated Python and Java code quality, syntax, and complexity."""

from __future__ import annotations
import ast
import re
from typing import Any


class StaticAnalysisTools:
    """Performs AST and regex-based validation, syntax checking, and code metrics extraction on Java code."""

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

