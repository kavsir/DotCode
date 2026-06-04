"""
DotCode Data Models - Pydantic models cho Symbol, Edge, Subgraph.
Đảm bảo tính nhất quán dữ liệu xuyên suốt hệ thống.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SymbolKind(str, Enum):
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    MODULE = "module"
    VARIABLE = "variable"


class EdgeType(str, Enum):
    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    REFERENCES = "references"
    CONTAINS = "contains"


class Symbol(BaseModel):
    id: str = Field(..., description="Unique identifier, e.g., 'file.py::function_name'")
    name: str = Field(..., description="Symbol name")
    kind: SymbolKind = Field(..., description="Kind of symbol")
    file_path: str = Field(..., description="Relative file path")
    start_line: int = Field(..., description="Start line number")
    end_line: int = Field(..., description="End line number")
    signature: Optional[str] = Field(None, description="Function/class signature")
    docstring: Optional[str] = Field(None, description="Docstring if available")
    body_hash: Optional[str] = Field(None, description="MD5 hash of body for change detection")
    complexity: int = Field(0, description="Cyclomatic complexity")
    pagerank: float = Field(0.0, description="PageRank score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class Edge(BaseModel):
    source_id: str = Field(..., description="Source symbol ID")
    target_id: str = Field(..., description="Target symbol ID")
    type: EdgeType = Field(..., description="Type of relationship")
    weight: float = Field(1.0, description="Edge weight (for PageRank)")


class Subgraph(BaseModel):
    nodes: List[Symbol] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Subgraph-level metadata (e.g., community info)"
    )


class BlastRadiusResult(BaseModel):
    symbol: Symbol
    direct_callers: List[Symbol] = Field(default_factory=list)
    indirect_callers: List[Dict[str, Any]] = Field(
        default_factory=list
    )  # {symbol: Symbol, depth: int}
    callees: List[Symbol] = Field(default_factory=list)
    subclasses: List[Symbol] = Field(default_factory=list)
    total_impact: int = 0
