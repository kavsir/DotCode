"""
DotCode Harness Framework Package.
"""
from dotcode.harness.retrieval_harness import (
    DotCodeRetrievalHarness,
    RetrievalTask,
    RetrievalResult,
)
from dotcode.harness.provider_harness import (
    DotCodeProviderHarness,
    ProviderTask,
    ProviderResult,
)
from dotcode.harness.mcp_harness import (
    DotCodeMCPHarness,
    MCPTask,
    MCPResult,
)
from dotcode.harness.coding_harness import (
    DotCodeCodingHarness,
    CodingPatchTask,
    CodingPatchResult,
)

__all__ = [
    "DotCodeRetrievalHarness",
    "RetrievalTask",
    "RetrievalResult",
    "DotCodeProviderHarness",
    "ProviderTask",
    "ProviderResult",
    "DotCodeMCPHarness",
    "MCPTask",
    "MCPResult",
    "DotCodeCodingHarness",
    "CodingPatchTask",
    "CodingPatchResult",
]
