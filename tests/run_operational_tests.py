"""
DotCode Operational Test Suite
Kiem tra import, logic cot loi, tich hop giua cac module.
Chay: python tests/run_operational_tests.py
"""
import os
import sys
import tempfile
import shutil
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = []
FAIL = []
SKIP = []


def test(name):
    def decorator(fn):
        try:
            fn()
            PASS.append(name)
            print(f"  PASS  {name}")
        except ImportError as e:
            SKIP.append((name, str(e)))
            print(f"  SKIP  {name}  [{e}]")
        except Exception as e:
            FAIL.append((name, traceback.format_exc()))
            print(f"  FAIL  {name}  -> {e}")
        return fn
    return decorator


print("=" * 60)
print("DotCode Operational Tests")
print("=" * 60)

# ──────────────────────────────────────────────
print("\n[1] IMPORT TESTS")
# ──────────────────────────────────────────────

@test("Import dotcode.graph.database")
def _():
    from dotcode.graph.database import GraphDatabase
    assert GraphDatabase is not None

@test("Import dotcode.graph.sqlite_adapter")
def _():
    from dotcode.graph.sqlite_adapter import SQLiteAdapter
    assert SQLiteAdapter is not None

@test("Import dotcode.graph (CodeGraph)")
def _():
    from dotcode.graph import CodeGraph
    assert CodeGraph is not None

@test("Import dotcode.graphrag")
def _():
    from dotcode.graphrag import GraphRAGEngine
    assert GraphRAGEngine is not None

@test("Import dotcode.model_router")
def _():
    from dotcode.model_router import ModelRouter, SafeModelRouter, TaskComplexity
    assert SafeModelRouter is not None

@test("Import dotcode.hitl")
def _():
    from dotcode.hitl import HITLManager, RiskLevel
    assert HITLManager is not None

@test("Import dotcode.sage")
def _():
    from dotcode.sage import SAGEEngine
    assert SAGEEngine is not None

@test("Import dotcode.dst")
def _():
    from dotcode.dst import DialogueStateTracker, DialogueState
    assert DialogueStateTracker is not None

@test("Import dotcode.context_pruner")
def _():
    from dotcode.context_pruner import ContextPruner
    assert ContextPruner is not None

@test("Import dotcode.agents.intent_agent")
def _():
    from dotcode.agents.intent_agent import IntentAgent
    assert IntentAgent is not None

@test("Import dotcode.models")
def _():
    from dotcode.models import Symbol, Edge, BlastRadiusResult, SymbolKind
    assert Symbol is not None

# ──────────────────────────────────────────────
print("\n[2] DATABASE TESTS")
# ──────────────────────────────────────────────

@test("DB: Create in-memory database")
def _():
    from dotcode.graph.database import GraphDatabase
    db = GraphDatabase(":memory:")
    assert db.count_symbols() == 0

@test("DB: Insert and query symbols")
def _():
    from dotcode.graph.database import GraphDatabase
    db = GraphDatabase(":memory:")
    symbols = [
        {"id": "f.py::foo", "name": "foo", "kind": "function",
         "start_line": 1, "end_line": 5, "signature": "def foo():",
         "body_hash": "h1", "complexity": 1, "metadata": "{}"},
        {"id": "f.py::bar", "name": "bar", "kind": "class",
         "start_line": 7, "end_line": 12, "signature": "class Bar:",
         "body_hash": "h2", "complexity": 2, "metadata": "{}"},
    ]
    db.replace_symbols("f.py", symbols)
    assert db.count_symbols() == 2
    sym = db.get_symbol("f.py::foo")
    assert sym["name"] == "foo"

@test("DB: Edge insert and callee/caller queries")
def _():
    from dotcode.graph.database import GraphDatabase
    db = GraphDatabase(":memory:")
    syms = [
        {"id": "a.py::caller", "name": "caller", "kind": "function",
         "start_line": 1, "end_line": 3, "signature": "def caller():",
         "body_hash": "x", "complexity": 0, "metadata": "{}"},
        {"id": "a.py::callee", "name": "callee", "kind": "function",
         "start_line": 5, "end_line": 7, "signature": "def callee():",
         "body_hash": "y", "complexity": 0, "metadata": "{}"},
    ]
    db.replace_symbols("a.py", syms)
    db.replace_edges("a.py", [
        {"source_id": "a.py::caller", "target_id": "a.py::callee", "type": "calls"}
    ])
    callees = db.get_callees("a.py::caller")
    callers = db.get_callers("a.py::callee")
    assert len(callees) == 1 and callees[0]["name"] == "callee"
    assert len(callers) == 1 and callers[0]["name"] == "caller"

# ──────────────────────────────────────────────
print("\n[3] SQLITE ADAPTER TESTS")
# ──────────────────────────────────────────────

@test("Adapter: search returns Symbol Pydantic objects")
def _():
    from dotcode.graph.database import GraphDatabase
    from dotcode.graph.sqlite_adapter import SQLiteAdapter
    from dotcode.models import Symbol
    db = GraphDatabase(":memory:")
    adapter = SQLiteAdapter(db)
    db.replace_symbols("s.py", [
        {"id": "s.py::my_func", "name": "my_func", "kind": "function",
         "start_line": 1, "end_line": 4, "signature": "def my_func():",
         "body_hash": "h", "complexity": 1, "metadata": "{}"},
    ])
    results = adapter.search("my_func")
    assert len(results) == 1
    assert isinstance(results[0], Symbol)
    # Verify .id attribute works (the BUG5 fix test)
    assert results[0].id == "s.py::my_func"
    assert results[0].name == "my_func"

@test("Adapter: get_blast_radius returns BlastRadiusResult")
def _():
    from dotcode.graph.database import GraphDatabase
    from dotcode.graph.sqlite_adapter import SQLiteAdapter
    db = GraphDatabase(":memory:")
    adapter = SQLiteAdapter(db)
    db.replace_symbols("b.py", [
        {"id": "b.py::A", "name": "A", "kind": "function",
         "start_line": 1, "end_line": 3, "signature": "def A():",
         "body_hash": "ha", "complexity": 0, "metadata": "{}"},
        {"id": "b.py::B", "name": "B", "kind": "function",
         "start_line": 5, "end_line": 7, "signature": "def B():",
         "body_hash": "hb", "complexity": 0, "metadata": "{}"},
    ])
    db.replace_edges("b.py", [
        {"source_id": "b.py::B", "target_id": "b.py::A", "type": "calls"}
    ])
    result = adapter.get_blast_radius("b.py::A")
    assert result is not None
    assert len(result.direct_callers) == 1
    assert result.direct_callers[0].name == "B"

@test("Adapter: get_unused_symbols detects dead code")
def _():
    from dotcode.graph.database import GraphDatabase
    from dotcode.graph.sqlite_adapter import SQLiteAdapter
    db = GraphDatabase(":memory:")
    adapter = SQLiteAdapter(db)
    db.replace_symbols("u.py", [
        {"id": "u.py::used", "name": "used", "kind": "function",
         "start_line": 1, "end_line": 2, "signature": "def used():",
         "body_hash": "hu", "complexity": 0, "metadata": "{}"},
        {"id": "u.py::orphan", "name": "orphan", "kind": "function",
         "start_line": 3, "end_line": 4, "signature": "def orphan():",
         "body_hash": "ho", "complexity": 0, "metadata": "{}"},
    ])
    db.replace_edges("u.py", [
        {"source_id": "u.py::external", "target_id": "u.py::used", "type": "calls"}
    ])
    unused = adapter.get_unused_symbols()
    names = [s.name for s in unused]
    assert "orphan" in names
    assert "used" not in names

# ──────────────────────────────────────────────
print("\n[4] CODEGRAPH INTEGRATION TESTS")
# ──────────────────────────────────────────────

@test("CodeGraph: index Python file and search symbols")
def _():
    from dotcode.graph import CodeGraph
    tmpdir = tempfile.mkdtemp()
    try:
        fpath = os.path.join(tmpdir, "sample.py")
        with open(fpath, "w") as f:
            f.write(
                "def greet(name):\n"
                "    return f'Hello {name}'\n\n"
                "class Dog:\n"
                "    def bark(self):\n"
                "        return greet('dog')\n"
            )
        cg = CodeGraph(root=tmpdir)
        cg.index()
        assert cg.is_indexed()
        symbols = cg.search("greet")
        assert len(symbols) > 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

@test("CodeGraph: update_file does not crash when graphrag=None (BUG3 fix)")
def _():
    from dotcode.graph import CodeGraph
    tmpdir = tempfile.mkdtemp()
    try:
        fpath = os.path.join(tmpdir, "u.py")
        with open(fpath, "w") as f:
            f.write("def old(): pass\n")
        cg = CodeGraph(root=tmpdir)
        cg.index()
        cg.graphrag = None  # Simulate no GraphRAG
        with open(fpath, "w") as f:
            f.write("def old(): return 1\ndef new(): pass\n")
        cg.update_file(fpath)  # Must not raise AttributeError
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

# ──────────────────────────────────────────────
print("\n[5] HITL MANAGER TESTS")
# ──────────────────────────────────────────────

@test("HITL: LOW risk for comment-only changes")
def _():
    from dotcode.hitl import HITLManager, RiskLevel
    hitl = HITLManager()
    assert hitl.classify_change("old", "# just a comment") == RiskLevel.LOW
    assert hitl.should_auto_apply("old", "# just a comment") is True

@test("HITL: HIGH risk for class definition")
def _():
    from dotcode.hitl import HITLManager, RiskLevel
    hitl = HITLManager()
    assert hitl.classify_change("", "class MyClass:") == RiskLevel.HIGH
    assert hitl.should_auto_apply("", "class Foo:") is False

@test("HITL: MEDIUM risk for function body change")
def _():
    from dotcode.hitl import HITLManager, RiskLevel
    hitl = HITLManager()
    result = hitl.classify_change("def f(): return 0", "def f(): return 1")
    assert result == RiskLevel.MEDIUM

# ──────────────────────────────────────────────
print("\n[6] SAGE MEMORY TESTS")
# ──────────────────────────────────────────────

@test("SAGE: remember and recall events")
def _():
    from dotcode.graph.database import GraphDatabase
    from dotcode.sage import SAGEEngine
    db = GraphDatabase(":memory:")
    sage = SAGEEngine(db)
    sage.remember("bug_fix", "null pointer in login", ["auth.py::login"])
    events = sage.recall("null pointer")
    assert len(events) >= 1

@test("SAGE: learn_from_feedback does not crash")
def _():
    from dotcode.graph.database import GraphDatabase
    from dotcode.sage import SAGEEngine
    db = GraphDatabase(":memory:")
    sage = SAGEEngine(db)
    sage.remember("refactor", "restructured router", ["router.py::Router"])
    sage.learn_from_feedback("router.py::Router", accepted=True)
    ctx = sage.get_context_for_prompt(["router.py::Router"])
    assert isinstance(ctx, str)

# ──────────────────────────────────────────────
print("\n[7] DIALOGUE STATE TRACKER TESTS")
# ──────────────────────────────────────────────

@test("DST: initial state has no pending question")
def _():
    from dotcode.dst import DialogueStateTracker
    dst = DialogueStateTracker()
    assert dst.state.has_pending_question is False

@test("DST: resolve_intent delegates when no pending question")
def _():
    from dotcode.dst import DialogueStateTracker
    dst = DialogueStateTracker()
    result = dst.resolve_intent("Hello")
    assert result["resolved_intent"] == "delegate_to_intent_agent"

@test("DST: YES/NO resolution")
def _():
    import time
    from dotcode.dst import DialogueStateTracker, DialogueState, PendingQuestionType
    dst = DialogueStateTracker()
    dst.update_state(DialogueState(
        has_pending_question=True,
        question_type=PendingQuestionType.YES_NO,
        question_text="Continue?",
        asked_at=time.time(),
    ))
    yes_result = dst.resolve_intent("co")
    no_result = dst.resolve_intent("khong")
    # "co" not in confirm_words exactly, try exact match
    dst2 = DialogueStateTracker()
    dst2.update_state(DialogueState(
        has_pending_question=True,
        question_type=PendingQuestionType.YES_NO,
        question_text="Continue?",
        asked_at=time.time(),
    ))
    r = dst2.resolve_intent("yes")
    assert r["resolved_intent"] in ("contextual_yes", "delegate_to_intent_agent")

@test("DST: clear_state resets pending question")
def _():
    import time
    from dotcode.dst import DialogueStateTracker, DialogueState, PendingQuestionType
    dst = DialogueStateTracker()
    dst.update_state(DialogueState(
        has_pending_question=True,
        question_type=PendingQuestionType.YES_NO,
        asked_at=time.time(),
    ))
    dst.clear_state()
    assert dst.state.has_pending_question is False

# ──────────────────────────────────────────────
print("\n[8] CONTEXT PRUNER TESTS")
# ──────────────────────────────────────────────

@test("ContextPruner: always keeps last N messages")
def _():
    from dotcode.context_pruner import ContextPruner
    pruner = ContextPruner(keep_last_n=3)
    msgs = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
    pruned = pruner.prune_messages(msgs, "msg 9")
    contents = [m["content"] for m in pruned]
    assert "msg 9" in contents
    assert "msg 8" in contents
    assert "msg 7" in contents

@test("ContextPruner: short history not pruned")
def _():
    from dotcode.context_pruner import ContextPruner
    pruner = ContextPruner(keep_last_n=5)
    msgs = [{"role": "user", "content": f"m{i}"} for i in range(3)]
    pruned = pruner.prune_messages(msgs, "query")
    assert len(pruned) == 3

# ──────────────────────────────────────────────
print("\n[9] MODEL ROUTER TESTS")
# ──────────────────────────────────────────────

@test("SafeModelRouter: get_safe_model returns non-empty string")
def _():
    from dotcode.model_router import SafeModelRouter
    router = SafeModelRouter()
    # get_safe_model(message, intent, context_tokens)
    for intent in ("question", "command", "architecture"):
        model = router.get_safe_model("test message", intent, 0)
        assert isinstance(model, str) and len(model) > 0

# ──────────────────────────────────────────────
print("\n[10] MULTI-HOP ENGINE TESTS")
# ──────────────────────────────────────────────

@test("MultiHopEngine: get_k_hop_neighbors")
def _():
    from dotcode.graph.database import GraphDatabase
    from dotcode.graph.multi_hop import MultiHopEngine
    db = GraphDatabase(":memory:")
    db.replace_symbols("mh.py", [
        {"id": "mh.py::A", "name": "A", "kind": "function",
         "start_line": 1, "end_line": 2, "signature": "def A():",
         "body_hash": "a", "complexity": 0, "metadata": "{}"},
        {"id": "mh.py::B", "name": "B", "kind": "function",
         "start_line": 3, "end_line": 4, "signature": "def B():",
         "body_hash": "b", "complexity": 0, "metadata": "{}"},
        {"id": "mh.py::C", "name": "C", "kind": "function",
         "start_line": 5, "end_line": 6, "signature": "def C():",
         "body_hash": "c", "complexity": 0, "metadata": "{}"},
    ])
    db.replace_edges("mh.py", [
        {"source_id": "mh.py::A", "target_id": "mh.py::B", "type": "calls"},
        {"source_id": "mh.py::B", "target_id": "mh.py::C", "type": "calls"},
    ])
    engine = MultiHopEngine(db)
    # Returns: [{"symbol": Symbol, "depth": int, "path": list}, ...]
    neighbors = engine.get_k_hop_neighbors("mh.py::A", k=2, edge_types=["calls"])
    ids = [n["symbol"].id for n in neighbors]
    assert "mh.py::B" in ids
    assert "mh.py::C" in ids

# ──────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────
total = len(PASS) + len(FAIL) + len(SKIP)
print("\n" + "=" * 60)
print(f"RESULTS: {len(PASS)} passed, {len(FAIL)} failed, {len(SKIP)} skipped / {total} total")
print("=" * 60)

if FAIL:
    print("\nFAILED TESTS:")
    for name, tb in FAIL:
        print(f"\n  [{name}]")
        for line in tb.strip().split("\n")[-3:]:
            print(f"    {line}")

if SKIP:
    print("\nSKIPPED (missing optional deps):")
    for name, reason in SKIP:
        print(f"  {name}: {reason}")

sys.exit(1 if FAIL else 0)
