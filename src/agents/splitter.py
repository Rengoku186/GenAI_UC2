import os
import re
from typing import List, Any
from src.schemas import Chunk

def create_chunk_from_node_data(node_id: Any, node_data: dict) -> Chunk:
    str_id = str(node_data.get("id", node_id))
    name = node_data.get("name")
    if not name:
        name = str_id.split("::")[-1]
    return Chunk(
        id=str_id,
        file_path=node_data.get("file_path", ""),
        scope=node_data.get("scope"),
        name=name,
        code=node_data.get("code", ""),
        start_line=node_data.get("start_line", 1),
        end_line=node_data.get("end_line", 1),
        depends_on=node_data.get("depends_on", []),
        is_cycle_group=node_data.get("is_cycle_group", False)
    )

def _split_at_next_boundary(chunk: Chunk) -> List[Chunk]:
    """
    Subdivides an oversized non-cyclic chunk at logical statement boundaries.
    """
    lines = chunk.code.splitlines()
    total_lines = len(lines)
    midpoint = total_lines // 2
    
    split_idx = midpoint
    for i in range(midpoint, min(midpoint + 50, total_lines)):
        if not lines[i].strip() or lines[i].strip().endswith('.') or lines[i].strip().endswith(';'):
            split_idx = i + 1
            break
            
    if split_idx <= 0 or split_idx >= total_lines:
        split_idx = max(1, midpoint)
            
    part1_code = "\n".join(lines[:split_idx])
    part2_code = "\n".join(lines[split_idx:])
    
    c1 = Chunk(
        id=f"{chunk.id}::part1",
        file_path=chunk.file_path,
        scope=chunk.scope,
        name=f"{chunk.name}_part1",
        code=part1_code,
        start_line=chunk.start_line,
        end_line=chunk.start_line + split_idx - 1,
        depends_on=chunk.depends_on,
        is_cycle_group=False
    )
    
    c2 = Chunk(
        id=f"{chunk.id}::part2",
        file_path=chunk.file_path,
        scope=chunk.scope,
        name=f"{chunk.name}_part2",
        code=part2_code,
        start_line=chunk.start_line + split_idx,
        end_line=chunk.end_line,
        depends_on=[],
        is_cycle_group=False
    )
    
    return [c1, c2]

def split_chunk_if_oversized(chunk: Chunk, max_lines: int = 800) -> List[Chunk]:
    line_count = chunk.end_line - chunk.start_line + 1
    if line_count <= max_lines or chunk.is_cycle_group:
        return [chunk]
        
    sub_chunks = _split_at_next_boundary(chunk)
    result = []
    for sc in sub_chunks:
        result.extend(split_chunk_if_oversized(sc, max_lines))
    return result
