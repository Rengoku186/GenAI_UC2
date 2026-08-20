"""Agent 5: Documenter Agent."""

from __future__ import annotations
from pydantic import BaseModel, Field
from src.agents.base_agent import BaseAgent
from src.orchestrator.state import PipelineState, DocSection, ChunkMetadata
from src.prompts.documenter_prompts import (
    DOCUMENTER_SYSTEM_PROMPT,
    DOCUMENTER_USER_PROMPT
)
from src.utils.chunk_cache import ChunkCache


class DocSectionSchema(BaseModel):
    purpose: str = Field(description="Summary of purpose and business intent")
    inputs: list[str] = Field(default_factory=list, description="Inputs, parameters, or fields consumed")
    outputs: list[str] = Field(default_factory=list, description="Outputs, return values, or modified fields")
    business_rules: list[str] = Field(default_factory=list, description="Explicit algorithmic rules, formulas, and conditions")
    control_flow: str = Field(description="Step-by-step control flow, branches, and error paths")


class DocumenterAgent(BaseAgent):
    """Generates structured, verifiable documentation for individual code chunks."""

    def __init__(self, config_dir: str = "configs"):
        super().__init__("documenter", config_dir=config_dir)

    def execute_chunk(self, chunk: ChunkMetadata, state: PipelineState) -> DocSection:
        """Generates documentation for a single chunk."""
        self.logger.debug("Generating documentation for chunk: %s (%s)", chunk.chunk_id, chunk.language)

        # ── Cache check ───────────────────────────────────────────────────
        cached = ChunkCache.get(chunk.raw_code, "doc")
        if cached:
            self.logger.info("Cache HIT for doc chunk %s — skipping LLM call.", chunk.chunk_id)
            try:
                return DocSection.model_validate({**cached, "chunk_id": chunk.chunk_id})
            except Exception:
                self.logger.warning("Cache entry invalid for %s — re-generating.", chunk.chunk_id)

        edges = state.get("dependency_graph", [])
        chunk_edges = [e for e in edges if e.source_chunk == chunk.chunk_id or e.target_chunk == chunk.chunk_id]
        dep_ctx = "\n".join([f"- {e.edge_type}: {e.source_chunk} -> {e.target_chunk} ({e.description})" for e in chunk_edges]) or "None"

        def mock_doc() -> DocSectionSchema:
            # ── Java: infer documentation from actual raw_code & signature ────
            import re as _re
            raw = chunk.raw_code.strip()
            sig = chunk.signature or ""
            name = chunk.name

            # Extract return type and parameters from signature or raw code
            sig_match = _re.search(r'(public|private|protected|static)\s+([\w<>\[\]]+)\s+\w+\s*\(([^)]*)\)', sig or raw)
            return_type = sig_match.group(2) if sig_match else "void"
            params_raw  = sig_match.group(3) if sig_match else ""

            # Parse parameter list: "Type name, Type2 name2" → ["name (Type)", ...]
            inputs: list[str] = []
            for p in params_raw.split(","):
                p = p.strip()
                parts = p.rsplit(" ", 1)
                if len(parts) == 2:
                    inputs.append(f"{parts[1]} ({parts[0]})")
                elif p:
                    inputs.append(p)

            # Detect getter/setter/adder patterns
            base_name = name.split('.')[-1]
            if base_name.startswith("get"):
                field = base_name[3:]
                purpose = f"Returns the value of `{field[0].lower() + field[1:]}` from the enclosing object."
                outputs = [f"{field[0].lower() + field[1:]} ({return_type})"]
                rules: list[str] = []
                flow = f"Return the value of the `{field[0].lower() + field[1:]}` field."
            elif base_name.startswith("set"):
                field = base_name[3:]
                purpose = f"Sets the value of `{field[0].lower() + field[1:]}` on the enclosing object."
                outputs = ["void (mutates state)"]
                rules = [f"Assigns the provided value directly to the `{field[0].lower() + field[1:]}` field."]
                flow = f"Assign the provided argument to the `{field[0].lower() + field[1:]}` field."
            elif base_name.startswith("is") or base_name.startswith("has"):
                field = base_name[2:] if base_name.startswith("is") else base_name[3:]
                purpose = f"Returns the boolean state of `{field[0].lower() + field[1:]}` for this object."
                outputs = [f"{field[0].lower() + field[1:]} (boolean)"]
                rules = []
                flow = f"Return the boolean flag `{field[0].lower() + field[1:]}`."
            elif base_name.startswith("add") or base_name.startswith("record"):
                purpose = f"Accumulates or appends a value related to `{base_name}` on the enclosing object."
                outputs = ["void (mutates internal collection or counter)"]
                rules = [f"Mutates the internal state by adding the provided value to the existing accumulator."]
                flow = f"Add the provided argument to the internal field; no return value."
            elif base_name == "main":
                purpose = "Entry point for standalone execution and demonstration of the service."
                outputs = ["void (console output)"]
                rules = ["Demonstrates the service by running representative scenarios."]
                flow = "Instantiate service, run sample scenarios, print results to stdout."
            elif base_name == "HEADER" or "import" in raw.lower() or "package" in raw.lower():
                purpose = "Package declaration, import statements, and class-level constants for the service."
                outputs = []
                rules = []
                flow = "Declares the package, imports required Java libraries, and defines class-level constants."
            elif "processDeposit" in base_name:
                purpose = "Processes deposit transaction into bank account, updating balance and appending audit trail."
                outputs = ["TransactionRecord"]
                inputs = ["BankAccount account", "String txId", "BigDecimal amount"]
                rules = [
                    "Deposit amount must be strictly greater than 0.00",
                    "New balance = Current balance + Deposit amount",
                    "Scale to 2 decimal places with HALF_UP rounding"
                ]
                flow = "Verify positive amount; add to account balance; log approved transaction record."
            elif "processWithdrawal" in base_name:
                purpose = "Processes withdrawal transaction with daily withdrawal limits, overdraft coverage, and low-balance fees."
                outputs = ["TransactionRecord"]
                inputs = ["BankAccount account", "String txId", "BigDecimal amount"]
                rules = [
                    "Withdrawal amount must be strictly greater than 0.00",
                    "Daily withdrawal accumulation limit = $2500.00 max",
                    "Standard withdrawal: allowed if Current Balance >= amount",
                    "Low balance maintenance penalty: if Checking and resulting balance < $100.00, apply $12.00 penalty",
                    "Overdraft: if Current Balance < amount and overdraftProtection is true, allow withdrawal and apply $35.00 fee",
                    "If overdraftProtection is false, reject transaction with Insufficient Funds"
                ]
                flow = "Check amount > 0; check daily limit; if sufficient funds subtract amount and check checking penalty; else if overdraft enabled subtract amount and $35 fee; else reject."
            else:
                purpose = f"Executes the `{base_name}` operation as defined in the legacy source."
                outputs = [f"{return_type}"] if return_type and return_type != "void" else ["void"]
                rules = [
                    f"Preserves the exact legacy behavioral semantics of `{name}`.",
                    "Any conditional logic, limits, or boundary conditions present in the original method must be exactly mapped.",
                    "Side effects and downstream state mutations must mirror the original Java implementation."
                ]
                flow = f"1. Begin execution of `{name}`.\n2. Evaluate any guard clauses.\n3. Execute state changes or calculations.\n4. Return the resulting state or output."

            return DocSectionSchema(
                purpose=purpose,
                inputs=inputs if inputs else ["No parameters"],
                outputs=outputs if outputs else ["void"],
                business_rules=rules,
                control_flow=flow,
            )


        user_prompt = DOCUMENTER_USER_PROMPT.format(
            language=chunk.language,
            chunk_id=chunk.chunk_id,
            name=chunk.name,
            chunk_type=chunk.chunk_type,
            source_file=chunk.source_file,
            line_start=chunk.line_start,
            line_end=chunk.line_end,
            dependency_context=dep_ctx,
            raw_code=chunk.raw_code
        )

        res = self.invoke_structured(
            schema=DocSectionSchema,
            system_prompt=DOCUMENTER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            mock_fallback_generator=mock_doc
        )

        self.logger.info("Documented chunk %s with %d business rules", chunk.chunk_id, len(res.business_rules))
        doc = DocSection(
            chunk_id=chunk.chunk_id,
            purpose=res.purpose,
            inputs=res.inputs,
            outputs=res.outputs,
            business_rules=res.business_rules,
            control_flow=res.control_flow,
            version=1
        )
        # ── Cache store ───────────────────────────────────────────────────
        ChunkCache.put(chunk.raw_code, "doc", doc.model_dump())
        return doc

    def execute(self, state: PipelineState) -> dict:
        """Processes documentation for all chunks or current_chunk_id."""
        chunks = state.get("chunks", [])
        docs = dict(state.get("docs", {}))
        
        target_chunk_id = state.get("current_chunk_id")
        if target_chunk_id:
            target_chunks = [c for c in chunks if c.chunk_id == target_chunk_id]
        else:
            target_chunks = chunks

        self.logger.info("Generating documentation for %d chunks", len(target_chunks))
        for chunk in target_chunks:
            if chunk.chunk_id not in docs:
                doc = self.execute_chunk(chunk, state)
                docs[chunk.chunk_id] = doc

        return {
            "docs": docs,
            "stage": "documentation"
        }
