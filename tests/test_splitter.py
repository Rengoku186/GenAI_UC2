import pytest
from src.schemas import Chunk
from src.agents.splitter import (
    create_chunk_from_node_data,
    split_chunk_if_oversized,
)


def test_lossless_reconstitution():
    original_code = "LINE 1\nLINE 2\nLINE 3\nLINE 4\nLINE 5"
    c = Chunk(
        id="test::file::chunk1",
        file_path="test.txt",
        name="chunk1",
        code=original_code,
        start_line=1,
        end_line=5,
    )
    chunks = split_chunk_if_oversized(c, max_lines=10)
    assert len(chunks) == 1
    reconstituted = "\n".join([c.code for c in chunks])
    assert reconstituted == original_code


def test_oversized_monolith_5000_lines():
    # Simulate a massive legacy monolithic file with 5000 statements
    lines = [f"    MOVE {i} TO VAR-{i}." for i in range(1, 5001)]
    code = "\n".join(lines)
    c = Chunk(
        id="BILLING::MONOLITH",
        file_path="BILLING.cbl",
        name="MONOLITH",
        code=code,
        language="cobol",
        start_line=1,
        end_line=5000,
        depends_on=["COMMON::LOGGER", "DB::CONNECT"],
    )

    max_lines = 400
    sub_chunks = split_chunk_if_oversized(c, max_lines=max_lines)

    assert len(sub_chunks) >= 12
    for sc in sub_chunks:
        line_count = sc.end_line - sc.start_line + 1
        assert line_count <= max_lines
        assert sc.file_path == "BILLING.cbl"
        assert sc.language == "cobol"

    # Line continuity invariant
    for i in range(len(sub_chunks) - 1):
        assert sub_chunks[i].end_line + 1 == sub_chunks[i + 1].start_line

    # Lossless guarantee
    reconstituted = "\n".join([sc.code for sc in sub_chunks])
    assert reconstituted == code


def test_cobol_semantic_boundary_selection():
    # Build COBOL code with paragraphs embedded
    lines = []
    for i in range(1, 60):
        lines.append(f"    COMPUTE VAL-{i} = {i} * 2.")
    lines.append("CALC-TAX-PARA.")  # Natural high-score boundary
    for i in range(61, 120):
        lines.append(f"    MOVE VAL-{i} TO DB-FIELD-{i}.")

    code = "\n".join(lines)
    c = Chunk(
        id="PROG::PROCESS",
        file_path="PROG.cbl",
        name="PROCESS",
        code=code,
        language="cobol",
        start_line=10,
        end_line=10 + len(lines) - 1,
    )

    sub_chunks = split_chunk_if_oversized(c, max_lines=65, min_lines=20)
    assert len(sub_chunks) == 2

    # Verify that the split cleanly aligned near CALC-TAX-PARA
    assert "CALC-TAX-PARA." in sub_chunks[1].code.splitlines()[0]
    reconstituted = "\n".join(sc.code for sc in sub_chunks)
    assert reconstituted == code


def test_java_semantic_boundary_selection():
    lines = ["public class BigService {"]
    for i in range(1, 40):
        lines.append(f"    public void method{i}() {{ doWork({i}); }}")
    lines.append("}")

    code = "\n".join(lines)
    c = Chunk(
        id="BigService.java::BigService",
        file_path="BigService.java",
        name="BigService",
        code=code,
        language="java",
        start_line=1,
        end_line=len(lines),
    )

    sub_chunks = split_chunk_if_oversized(c, max_lines=20, min_lines=10)
    assert len(sub_chunks) > 1

    # Verify line numbers are sequential
    assert sub_chunks[0].start_line == 1
    assert sub_chunks[-1].end_line == len(lines)

    reconstituted = "\n".join(sc.code for sc in sub_chunks)
    assert reconstituted == code


def test_cycle_group_component_boundary_splitting():
    # Composite cycle group chunk created by cycle_detector
    comp1 = "// --- Component: FILE1.cbl::PROG1::SUB_A ---\n" + "\n".join([f"    PERFORM SUB_B_{i}." for i in range(30)])
    comp2 = "// --- Component: FILE2.cbl::PROG2::SUB_B ---\n" + "\n".join([f"    PERFORM SUB_A_{i}." for i in range(30)])

    code = comp1 + "\n\n" + comp2
    c = Chunk(
        id="SCC_0",
        file_path="FILE1.cbl",
        name="SCC_0",
        code=code,
        language="cobol",
        start_line=1,
        end_line=len(code.splitlines()),
        is_cycle_group=True,
    )

    sub_chunks = split_chunk_if_oversized(c, max_lines=35, min_lines=15)
    assert len(sub_chunks) >= 2
    for sc in sub_chunks:
        assert sc.is_cycle_group is True

    reconstituted = "\n".join(sc.code for sc in sub_chunks)
    assert reconstituted == code


def test_char_limit_splitting():
    # Short line count (10 lines), but massive 4000-character single line
    long_line = "X" * 4000
    lines = [f"VAR_{i} = '{long_line}'" for i in range(10)]
    code = "\n".join(lines)

    c = Chunk(
        id="test::long_chars",
        file_path="test.py",
        name="long_chars",
        code=code,
        start_line=1,
        end_line=10,
    )

    # Max chars 10000 should trigger split
    sub_chunks = split_chunk_if_oversized(c, max_lines=100, max_chars=10000, min_lines=2)
    assert len(sub_chunks) > 1

    reconstituted = "\n".join(sc.code for sc in sub_chunks)
    assert reconstituted == code


def test_dependency_filtering():
    code_part1 = "Call DatabaseConnect\nMsgBox \"Connected\""
    code_part2 = "Call EmailReceipt\nMsgBox \"Done\""
    full_code = f"{code_part1}\n\n{code_part2}"

    c = Chunk(
        id="OrderModule::Process",
        file_path="OrderModule.bas",
        name="Process",
        code=full_code,
        language="vb",
        start_line=1,
        end_line=len(full_code.splitlines()),
        depends_on=["DB::DatabaseConnect", "EmailService::EmailReceipt", "Unused::Module"],
    )

    sub_chunks = split_chunk_if_oversized(c, max_lines=3, min_lines=2)
    assert len(sub_chunks) >= 2

    # Part 1 should contain DatabaseConnect
    assert "DB::DatabaseConnect" in sub_chunks[0].depends_on
    # Part 2 should contain EmailReceipt
    assert "EmailService::EmailReceipt" in sub_chunks[-1].depends_on


def test_create_chunk_from_node_data():
    node_data = {
        "id": "app.java::com.example::Billing",
        "file_path": "app.java",
        "scope": "com.example",
        "name": "Billing",
        "code": "public class Billing {}",
        "language": "java",
        "start_line": 10,
        "end_line": 20,
        "depends_on": ["dep1"],
        "is_cycle_group": False,
    }

    chunk = create_chunk_from_node_data("fallback_id", node_data)
    assert chunk.id == "app.java::com.example::Billing"
    assert chunk.name == "Billing"
    assert chunk.language == "java"
    assert chunk.start_line == 10
    assert chunk.end_line == 20
    assert chunk.depends_on == ["dep1"]
