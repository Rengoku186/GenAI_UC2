"""State schema definitions for the Legacy Code Modernization LangGraph pipeline."""

from __future__ import annotations
from typing import TypedDict, Annotated, Any
from pydantic import BaseModel, Field
import operator


class ChunkMetadata(BaseModel):
    """Metadata describing a discrete logical chunk of legacy source code."""
    chunk_id: str = Field(description="Unique identifier for the chunk, e.g. 'LOANCALC_INIT'")
    source_file: str = Field(description="Path or filename of the original source file")
    language: str = Field(description="Legacy programming language (cobol, vb, java)")
    line_start: int = Field(description="Starting line number in source file (1-indexed)")
    line_end: int = Field(description="Ending line number in source file (inclusive)")
    name: str = Field(description="Symbol name (paragraph, function, class, or method name)")
    chunk_type: str = Field(default="procedure", description="Type: paragraph, procedure, function, class, data_division, etc.")
    raw_code: str = Field(description="Raw source code lines for this chunk")
    signature: str | None = Field(default=None, description="Function/Method signature or section header")


class DependencyEdge(BaseModel):
    """Represents a directed dependency relationship between chunks or external resources."""
    source_chunk: str = Field(description="ID of chunk that initiates call or uses data")
    target_chunk: str = Field(description="ID of chunk or external symbol being targeted")
    edge_type: str = Field(description="Type: 'calls', 'shared_data', 'copybook', 'file_io', 'db_io'")
    symbol: str | None = Field(default=None, description="Specific variable, procedure, copybook, or table name")
    description: str | None = Field(default=None, description="Brief description of the coupling")


class DocSection(BaseModel):
    """Structured documentation generated for a code chunk."""
    chunk_id: str = Field(description="Target chunk ID")
    purpose: str = Field(description="High-level purpose and business intent of the chunk")
    inputs: list[str] = Field(default_factory=list, description="Input parameters, shared variables read, or file inputs")
    outputs: list[str] = Field(default_factory=list, description="Output return values, mutated variables, or file/report writes")
    business_rules: list[str] = Field(default_factory=list, description="Explicit algorithmic rules, formulas, and conditions")
    control_flow: str = Field(description="Summary of branching, loops, error conditions, and sequence")
    version: int = Field(default=1, description="Refinement version number (starts at 1)")


class GeneratedCode(BaseModel):
    """Generated target Python service code for a chunk."""
    chunk_id: str = Field(description="Target chunk ID")
    target_code: str = Field(description="Modern, idiomatic, fully runnable Python code")
    module_name: str = Field(default="", description="Suggested Python module filename or class name")
    imports: list[str] = Field(default_factory=list, description="Required Python import statements")
    version: int = Field(default=1, description="Refinement version number (starts at 1)")


class TestResult(BaseModel):
    """Unit test code and execution outcomes for a chunk."""
    chunk_id: str = Field(description="Target chunk ID")
    test_code: str = Field(description="Pytest test suite code targeting the generated Python code")
    pass_count: int = Field(default=0, description="Number of passing test cases")
    fail_count: int = Field(default=0, description="Number of failing test cases")
    coverage_pct: float = Field(default=0.0, description="Code line coverage percentage (0.0 - 100.0)")
    execution_output: str = Field(default="", description="Captured stdout/stderr or traceback from pytest")
    all_passed: bool = Field(default=False, description="True if pass_count > 0 and fail_count == 0")


class EvalResult(BaseModel):
    """Evaluation result for any stage of a chunk or whole pipeline."""
    target_id: str = Field(description="Chunk ID or 'pipeline' / 'global'")
    stage: str = Field(description="Stage name: 'chunk_evaluation', 'dependency_evaluation', 'doc_evaluation', 'code_evaluation', 'test_execution'")
    score: float = Field(description="Normalized confidence/quality score between 0.0 and 1.0")
    passed: bool = Field(description="Whether the evaluation passed configured thresholds")
    issues: list[str] = Field(default_factory=list, description="List of identified discrepancies, gaps, or errors")
    suggestions: list[str] = Field(default_factory=list, description="Actionable recommendations for refinement")
    needs_human_review: bool = Field(default=False, description="Flagged if score is below threshold after retry cap")
    version_evaluated: int = Field(default=1, description="Version of doc or code that was evaluated")


# Reducer helpers for TypedDict state
def merge_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Merges two dictionaries, allowing updates."""
    merged = left.copy() if left else {}
    if right:
        merged.update(right)
    return merged


def append_list(left: list[Any], right: list[Any]) -> list[Any]:
    """Appends elements to an append-only list."""
    if left is None:
        left = []
    if right is None:
        return left
    return list(left) + list(right)


class PipelineState(TypedDict):
    """Shared state for the entire modernization LangGraph pipeline."""
    source_files: list[str]
    chunks: list[ChunkMetadata]
    dependency_graph: list[DependencyEdge]
    docs: Annotated[dict[str, DocSection], merge_dicts]
    generated_code: Annotated[dict[str, GeneratedCode], merge_dicts]
    tests: Annotated[dict[str, TestResult], merge_dicts]
    eval_history: Annotated[list[EvalResult], append_list]
    retry_counts: Annotated[dict[str, int], merge_dicts]
    current_chunk_id: str | None
    stage: str
    flagged_for_review: Annotated[list[str], append_list]
    metadata: Annotated[dict[str, Any], merge_dicts]
