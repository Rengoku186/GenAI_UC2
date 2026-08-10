import os
import pytest
from src.tools.dependency_scanner import scan_project

def test_scan_cobol_sample(tmp_path):
    cobol_file = tmp_path / "BILL100.cbl"
    cobol_file.write_text("""
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM VALIDATE-INPUT
           PERFORM CALC-INTEREST
           STOP RUN.

       VALIDATE-INPUT.
           IF ACCT-BAL < 0
               PERFORM RAISE-ERROR
           END-IF.

       CALC-INTEREST.
           COMPUTE INTEREST-VAL = 100.0 * 0.05.

       RAISE-ERROR.
           DISPLAY "ERROR".
""", encoding="utf-8")

    graph = scan_project([str(cobol_file)])
    
    # Check nodes
    assert len(graph.nodes) >= 4
    main_node = [n for n in graph.nodes if n.endswith("::MAIN-PARA")][0]
    val_node = [n for n in graph.nodes if n.endswith("::VALIDATE-INPUT")][0]
    calc_node = [n for n in graph.nodes if n.endswith("::CALC-INTEREST")][0]
    err_node = [n for n in graph.nodes if n.endswith("::RAISE-ERROR")][0]

    # Check edges
    assert graph.has_edge(main_node, val_node)
    assert graph.has_edge(main_node, calc_node)
    assert graph.has_edge(val_node, err_node)

def test_same_name_subroutines_different_files(tmp_path):
    f1 = tmp_path / "file1.cbl"
    f1.write_text("PROCEDURE DIVISION.\nCOMMON-SUB.\n    DISPLAY '1'.", encoding="utf-8")
    
    f2 = tmp_path / "file2.cbl"
    f2.write_text("PROCEDURE DIVISION.\nCOMMON-SUB.\n    DISPLAY '2'.", encoding="utf-8")
    
    graph = scan_project([str(f1), str(f2)])
    
    nodes = list(graph.nodes)
    assert len(nodes) == 2
    assert nodes[0] != nodes[1]
    assert str(f1) in nodes[0] or str(f1) in nodes[1]
    assert str(f2) in nodes[0] or str(f2) in nodes[1]
