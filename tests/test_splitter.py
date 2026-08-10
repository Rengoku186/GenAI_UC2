import pytest
from src.schemas import Chunk
from src.agents.splitter import split_chunk_if_oversized

def test_lossless_reconstitution():
    original_code = "LINE 1\nLINE 2\nLINE 3\nLINE 4\nLINE 5"
    c = Chunk(
        id="test::file::chunk1",
        file_path="test.txt",
        name="chunk1",
        code=original_code,
        start_line=1,
        end_line=5
    )
    chunks = split_chunk_if_oversized(c, max_lines=10)
    assert len(chunks) == 1
    reconstituted = "\n".join([c.code for c in chunks])
    assert reconstituted == original_code

def test_oversized_chunk_resplit():
    lines = [f"STATEMENT_{i};" for i in range(1, 2001)]
    oversized_code = "\n".join(lines)
    c = Chunk(
        id="test::file::oversized",
        file_path="test.txt",
        name="oversized",
        code=oversized_code,
        start_line=1,
        end_line=2000
    )
    
    chunks = split_chunk_if_oversized(c, max_lines=800)
    assert len(chunks) > 1
    for sub in chunks:
        assert (sub.end_line - sub.start_line + 1) <= 800
