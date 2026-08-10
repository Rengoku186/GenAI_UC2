from pydantic import BaseModel, Field
from typing import List, Optional

class Chunk(BaseModel):
    id: str                    # fully-qualified: "file_path::scope::name"
    file_path: str
    scope: Optional[str] = None # enclosing class / program, if any
    name: str
    code: str
    start_line: int
    end_line: int
    depends_on: List[str] = Field(default_factory=list) # qualified ids of chunks this one calls
    is_cycle_group: bool = False

class ChunkDoc(BaseModel):
    chunk_id: str
    summary: str
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    business_logic: str
    dependencies_used: List[str] = Field(default_factory=list)

class EvalResult(BaseModel):
    chunk_id: str
    overall_score: float       # 0-100, see compute_confidence_score
    issues: List[str] = Field(default_factory=list)
    needs_refinement: bool

class TestResult(BaseModel):
    chunk_id: str
    passed: bool
    stdout: str = ""
    stderr: str = ""
    failing_tests: List[str] = Field(default_factory=list)
