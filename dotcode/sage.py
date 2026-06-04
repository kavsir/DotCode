import hashlib
import json
from datetime import datetime


class SAGEEngine:
    def __init__(self, db):
        self.db = db

    def remember(
        self, event_type: str, description: str, symbol_ids: list = None, metadata: dict = None
    ):
        event_id = hashlib.md5(f"{event_type}:{description}:{datetime.now()}".encode()).hexdigest()
        self.db.conn.execute(
            """INSERT OR REPLACE INTO events (id, event_type, description, metadata)
            VALUES (?, ?, ?, ?)""",
            (event_id, event_type, description, json.dumps(metadata or {})),
        )
        if symbol_ids:
            for sym_id in symbol_ids:
                self.db.conn.execute(
                    """INSERT OR REPLACE INTO event_symbols (event_id, symbol_id, relevance)
                    VALUES (?, ?, 1.0)""",
                    (event_id, sym_id),
                )
        self.db.conn.commit()
        return event_id

    def recall(self, query: str, limit: int = 5):
        cur = self.db.conn.execute(
            """SELECT * FROM events WHERE description LIKE ? 
            ORDER BY timestamp DESC LIMIT ?""",
            (f"%{query}%", limit),
        )
        return [dict(row) for row in cur.fetchall()]

    def get_events_for_symbol(self, symbol_id: str):
        cur = self.db.conn.execute(
            """SELECT e.*, es.relevance FROM events e
            JOIN event_symbols es ON e.id = es.event_id
            WHERE es.symbol_id = ?
            ORDER BY e.timestamp DESC""",
            (symbol_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    def learn_from_feedback(self, symbol_id: str, accepted: bool):
        if accepted:
            self.db.conn.execute(
                "UPDATE event_symbols SET relevance = relevance * 1.5 WHERE symbol_id = ?",
                (symbol_id,),
            )
        else:
            self.db.conn.execute(
                "UPDATE event_symbols SET relevance = relevance * 0.5 WHERE symbol_id = ?",
                (symbol_id,),
            )
        self.db.conn.commit()

    def get_context_for_prompt(self, symbol_ids: list, max_tokens: int = 500):
        events = []
        for sym_id in symbol_ids[:10]:
            sym_events = self.get_events_for_symbol(sym_id)
            events.extend(sym_events[:3])
        if not events:
            return ""
        lines = ["# Recent relevant events:"]
        for event in events[:10]:
            lines.append(f"- [{event['event_type']}] {event['description'][:100]}")
        context = "\n".join(lines)
        return context[: max_tokens * 4]
