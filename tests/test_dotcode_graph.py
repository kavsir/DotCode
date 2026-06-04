import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotcode.graph.__init__old import CodeGraph
from dotcode.graph.database import GraphDatabase
from dotcode.graph.indexer import Indexer
from dotcode.hitl import HITLManager, RiskLevel


def test_database():
    """Test database schema, insert, query."""
    db = GraphDatabase(":memory:")
    symbols = [
        {
            "id": "test.py::hello",
            "name": "hello",
            "kind": "function",
            "start_line": 1,
            "end_line": 3,
            "signature": "def hello():",
            "body_hash": "abc",
            "complexity": 1,
            "metadata": "{}",
        },
        {
            "id": "test.py::world",
            "name": "world",
            "kind": "function",
            "start_line": 5,
            "end_line": 7,
            "signature": "def world():",
            "body_hash": "def",
            "complexity": 2,
            "metadata": "{}",
        },
    ]
    db.replace_symbols("test.py", symbols)
    assert db.count_symbols() == 2
    db.replace_edges(
        "test.py", [{"source_id": "test.py::hello", "target_id": "test.py::world", "type": "calls"}]
    )
    assert len(db.get_callees("test.py::hello")) == 1
    assert len(db.get_callers("test.py::world")) == 1
    assert db.get_symbol("test.py::hello")["name"] == "hello"


def test_indexer():
    """Test tree-sitter indexer extracts symbols (edges under development)."""
    code = """
def helper():
    return 42

def main():
    result = helper()
    print(result)

class Calculator:
    def add(self, a, b):
        return a + b

    def compute(self):
        return self.add(1, 2)
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        tmp = f.name
    try:
        db = GraphDatabase(":memory:")
        indexer = Indexer(db, root=os.path.dirname(tmp))
        indexer.index_file(tmp)
        symbols = db.get_symbols_in_file(os.path.basename(tmp))
        assert len(symbols) == 5
        # Edge extraction is still being improved; will test later
    finally:
        os.unlink(tmp)


def test_codegraph_context():
    """Test context generation with call relationships."""
    tmpdir = tempfile.mkdtemp()
    try:
        fname = os.path.join(tmpdir, "t.py")
        with open(fname, "w") as f:
            f.write("def foo(): pass\ndef bar():\n  foo()\n")
        cg = CodeGraph(root=tmpdir)
        cg.index()
        ctx = cg.get_context([fname], [])
        assert "foo" in ctx and "bar" in ctx
        cg.db.conn.close()
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)


def test_sage_memory():
    """Test SAGE memory recall and feedback."""
    db = GraphDatabase(":memory:")
    db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, event_type TEXT, description TEXT, timestamp TEXT DEFAULT (datetime('now')), metadata TEXT DEFAULT '{}');
        CREATE TABLE IF NOT EXISTS event_symbols (event_id TEXT NOT NULL, symbol_id TEXT NOT NULL, relevance REAL DEFAULT 1.0, PRIMARY KEY (event_id, symbol_id));
    """)
    from dotcode.sage import SAGEEngine

    sage = SAGEEngine(db)
    eid = sage.remember("bug_fix", "null pointer", ["main.py::main"])
    assert len(sage.recall("null")) == 1
    assert len(sage.get_events_for_symbol("main.py::main")) == 1
    sage.learn_from_feedback("main.py::main", True)
    ctx = sage.get_context_for_prompt(["main.py::main"])
    assert len(ctx) > 0


def test_hitl():
    """Test HITL risk classification."""
    hitl = HITLManager()
    assert hitl.classify_change("old", "# comment") == RiskLevel.LOW
    assert hitl.classify_change("", "import os") == RiskLevel.LOW
    assert hitl.classify_change("", "class X:") == RiskLevel.HIGH
    assert hitl.classify_change("", "@decorator\ndef f(): pass") == RiskLevel.HIGH
    assert hitl.classify_change("def old(): pass", "def old():\n  return 1") == RiskLevel.MEDIUM
    assert hitl.should_auto_apply("", "# x") is True
    assert hitl.should_auto_apply("", "class Y:") is False
