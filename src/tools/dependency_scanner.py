import os
import re
import networkx as nx
from typing import List, Dict, Tuple, Set

CALL_PATTERNS = {
    "cobol": re.compile(r"\b(CALL|PERFORM)\s+['\"]?([\w-]+)['\"]?", re.IGNORECASE),
    "vb":    re.compile(r"\b(Call|GoSub)\s+(\w+)", re.IGNORECASE),
    "java":  re.compile(r"\b([a-zA-Z_]\w*)\s*\(", re.IGNORECASE),
}

DEF_PATTERNS = {
    "cobol": re.compile(r"^\s*([\w-]+)\.\s*$", re.MULTILINE),
    "vb":    re.compile(r"^\s*(?:Public|Private|Friend|Static)?\s*(?:Sub|Function)\s+(\w+)", re.MULTILINE | re.IGNORECASE),
    "java":  re.compile(r"(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)\s*\{", re.MULTILINE),
}

def detect_language(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.cbl', '.cob', '.cobol']:
        return 'cobol'
    elif ext in ['.bas', '.cls', '.vb', '.vbs']:
        return 'vb'
    elif ext in ['.java']:
        return 'java'
    return 'unknown'

def parse_file_chunks(file_path: str) -> List[Tuple[str, str, str, str, int, int]]:
    """
    Returns list of tuples: (qualified_id, scope, name, code_snippet, start_line, end_line)
    """
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    lines = content.splitlines()
    lang = detect_language(file_path)
    file_basename = os.path.basename(file_path)
    chunks = []

    if lang == 'cobol':
        program_match = re.search(r"PROGRAM-ID\.\s*([\w-]+)", content, re.IGNORECASE)
        scope = program_match.group(1) if program_match else file_basename

        proc_div_idx = 0
        for i, line in enumerate(lines):
            if "PROCEDURE DIVISION" in line.upper():
                proc_div_idx = i
                break

        para_matches = []
        for i in range(proc_div_idx, len(lines)):
            m = re.match(r"^\s*([\w-]+)\.\s*$", lines[i])
            if m:
                pname = m.group(1).upper()
                if pname not in ['PROCEDURE', 'DIVISION', 'DATA', 'WORKING-STORAGE']:
                    para_matches.append((pname, i + 1))

        for idx, (pname, start_l) in enumerate(para_matches):
            end_l = para_matches[idx + 1][1] - 1 if idx + 1 < len(para_matches) else len(lines)
            chunk_code = "\n".join(lines[start_l - 1:end_l])
            qid = f"{file_path}::{pname}"
            chunks.append((qid, scope, pname, chunk_code, start_l, end_l))

    elif lang == 'vb':
        attr_match = re.search(r'Attribute VB_Name = "([^"]+)"', content)
        scope = attr_match.group(1) if attr_match else file_basename

        matches = list(re.finditer(r"^\s*(?:Public|Private|Friend|Static)?\s*(?:Sub|Function)\s+(\w+)", content, re.MULTILINE | re.IGNORECASE))
        for idx, m in enumerate(matches):
            fname = m.group(1)
            start_l = content[:m.start()].count('\n') + 1
            end_l = content[:matches[idx + 1].start()].count('\n') if idx + 1 < len(matches) else len(lines)
            chunk_code = "\n".join(lines[start_l - 1:end_l])
            qid = f"{file_path}::{scope}::{fname}"
            chunks.append((qid, scope, fname, chunk_code, start_l, end_l))

    elif lang == 'java':
        class_match = re.search(r"(?:class|interface|enum)\s+(\w+)", content)
        scope = class_match.group(1) if class_match else file_basename

        matches = list(re.finditer(r"(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)\s*\{", content))
        for idx, m in enumerate(matches):
            mname = m.group(1)
            if mname in ['if', 'while', 'for', 'switch']:
                continue
            start_l = content[:m.start()].count('\n') + 1
            end_l = content[:matches[idx + 1].start()].count('\n') if idx + 1 < len(matches) else len(lines)
            chunk_code = "\n".join(lines[start_l - 1:end_l])
            qid = f"{file_path}::{scope}::{mname}"
            chunks.append((qid, scope, mname, chunk_code, start_l, end_l))

    if not chunks:
        qid = f"{file_path}::MAIN"
        chunks.append((qid, file_basename, "MAIN", content, 1, len(lines)))

    return chunks

def scan_project(file_paths: List[str]) -> nx.DiGraph:
    graph = nx.DiGraph()
    chunk_registry: Dict[str, str] = {}
    all_chunks_info = []

    # Pass 1: register every chunk as a node (qualified id)
    for path in file_paths:
        lang = detect_language(path)  # computed once per file
        parsed_chunks = parse_file_chunks(path)
        for qid, scope, name, code, s_line, e_line in parsed_chunks:
            graph.add_node(
                qid,
                file_path=path,
                scope=scope,
                name=name,
                code=code,
                language=lang,          # NEW
                start_line=s_line,
                end_line=e_line,
                unresolved=[]
            )
            chunk_registry[name.upper()] = qid
            chunk_registry[f"{scope}::{name}".upper()] = qid
            chunk_registry[qid.upper()] = qid
            all_chunks_info.append((qid, path, lang, code, name))  # reuse lang

    # Pass 2: regex-match calls per file/chunk, add directed edges
    keywords_ignore = {'IF', 'THEN', 'ELSE', 'END-IF', 'STOP', 'RUN', 'MOVE', 'TO', 'COMPUTE', 'DISPLAY', 'PUBLIC', 'PRIVATE', 'VOID', 'RETURN', 'CLASS', 'SYSTEM', 'OUT', 'PRINTLN'}

    for qid, path, lang, code, current_name in all_chunks_info:
        pattern = CALL_PATTERNS.get(lang)
        if not pattern:
            continue

        matches = pattern.findall(code)
        unresolved_list = []

        for m in matches:
            called_name = m[1] if isinstance(m, tuple) else m
            called_upper = called_name.upper()

            if called_upper in keywords_ignore or called_upper == current_name.upper():
                continue

            target_qid = None
            if called_upper in chunk_registry:
                target_qid = chunk_registry[called_upper]
            else:
                prefix_qid = f"{path}::{called_name}".upper()
                for key in chunk_registry:
                    if key.endswith(prefix_qid) or prefix_qid.endswith(key):
                        target_qid = chunk_registry[key]
                        break

            if target_qid and target_qid != qid:
                graph.add_edge(qid, target_qid)
            elif called_upper not in keywords_ignore and len(called_name) > 1:
                unresolved_list.append(called_name)

        graph.nodes[qid]['unresolved'] = list(set(unresolved_list))

    return graph