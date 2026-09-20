"""
Fraud Investigation Workflow Orchestrator.
Delegates case execution to the LangGraph-based FraudInvestigationGraph,
providing unified interface, metrics collection, and explainability tracing.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.tools import GraphTools
from rag.vector_store import FraudVectorStore
from memory.case_memory import CaseMemory
from agent.graph import FraudInvestigationGraph

class FraudInvestigationWorkflow:
    def __init__(
        self,
        tools: Optional[GraphTools] = None,
        memory: Optional[CaseMemory] = None,
        vector_store: Optional[FraudVectorStore] = None
    ):
        self.tools = tools or GraphTools()
        self.vector_store = vector_store or (self.tools.vector_store if hasattr(self.tools, "vector_store") else FraudVectorStore())
        self.memory = memory or CaseMemory()
        self.agent_graph = FraudInvestigationGraph(
            tools=self.tools,
            vector_store=self.vector_store,
            memory=self.memory
        )

    def run_investigation(
        self,
        case_row: Dict[str, Any],
        submitted_evidence: Optional[Dict[str, Any]] = None,
        resume_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes complete end-to-end investigation via LangGraph StateGraph:
        - Multi-hop Graph Traversal (TigerGraph)
        - GraphRAG Policy & Precedent Retrieval (ChromaDB)
        - Dynamic Cardholder Simulation & Step-Up Authentication / External Evidence
        - Calibrated Risk Scoring & Bank Policy Action Routing (R1-R10)
        - FinCEN SAR 5 Ws and H Narrative Synthesis
        - Live TigerGraph Graph Persistence & Cross-Case Working Memory Update
        """
        return self.agent_graph.run(case_row, submitted_evidence=submitted_evidence, resume_state=resume_state)
