"""
GraphDBInterface - Abstract base class cho mọi database adapter trong DotCode.
Cho phép hoán đổi giữa SQLite, Neo4j, Kuzu mà không ảnh hưởng đến code phía trên.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from ..models import Symbol, Edge, BlastRadiusResult, Subgraph


class GraphDBInterface(ABC):
    @abstractmethod
    def add_symbol(self, symbol: Symbol) -> None:
        """Thêm một symbol vào database."""
        pass

    @abstractmethod
    def add_edge(self, edge: Edge) -> None:
        """Thêm một edge vào database."""
        pass

    @abstractmethod
    def get_symbol(self, symbol_id: str) -> Optional[Symbol]:
        """Lấy symbol theo ID."""
        pass

    @abstractmethod
    def get_callees(self, symbol_id: str, depth: int = 1) -> List[Symbol]:
        """Lấy danh sách symbols được gọi bởi symbol_id."""
        pass

    @abstractmethod
    def get_callers(self, symbol_id: str, depth: int = 1) -> List[Symbol]:
        """Lấy danh sách symbols gọi đến symbol_id."""
        pass

    @abstractmethod
    def search(self, query: str, kind: str = None, limit: int = 10) -> List[Symbol]:
        """Tìm kiếm symbols theo tên."""
        pass

    @abstractmethod
    def get_symbols_in_file(self, file_path: str) -> List[Symbol]:
        """Lấy tất cả symbols trong một file."""
        pass

    @abstractmethod
    def count_symbols(self) -> int:
        """Đếm tổng số symbols."""
        pass

    @abstractmethod
    def get_blast_radius(self, symbol_id: str, max_depth: int = 3) -> Optional[BlastRadiusResult]:
        """Tính toán blast radius."""
        pass

    @abstractmethod
    def get_unused_symbols(self) -> List[Symbol]:
        """Phát hiện dead code."""
        pass

    @abstractmethod
    def replace_symbols(self, file_path: str, symbols: List[Symbol]) -> None:
        """Thay thế toàn bộ symbols của một file."""
        pass

    @abstractmethod
    def replace_edges(self, file_path: str, edges: List[Edge]) -> None:
        """Thay thế toàn bộ edges của một file."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Đóng kết nối database."""
        pass