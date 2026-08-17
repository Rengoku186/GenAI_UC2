from typing import TypedDict, List, Dict, Optional, Any

class PipelineState(TypedDict, total=False):
    file_paths: List[str]
    raw_graph_edges: List[tuple]
    unresolved_deps: Dict[str, List[str]]
    chunks: List[Dict[str, Any]]
    docs: Dict[str, Dict[str, Any]]
    eval_scores: Dict[str, float]
    eval_issues: Dict[str, List[str]]          # NEW
    refine_count: Dict[str, int]
    current_chunk: Optional[str]
    processing_order: List[str]
    app_layers: List[List[str]]
    generated_code: Dict[str, str]
    tests_code: Dict[str, str]
    test_results: Dict[str, Dict[str, Any]]
    flagged_items: List[Dict[str, Any]]
    target_language: str
    intermediate_merged_app: Dict[str, str]
    validator_retry_count: int
    validation_passed: bool