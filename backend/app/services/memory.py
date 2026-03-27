"""
MemoryManager — persistent, compounding memory for QuantNeuralEdge.

Stores observations about each user as semantic embeddings in ChromaDB.
Retrieves relevant memories before each analysis session.
Extracts learning moments after each session.

Architecture follows the Version A spec:
  - ChromaDB for vector storage (semantic retrieval by meaning)
  - OpenAI text-embedding-3-small for embeddings (~€0 at this scale)
  - Claude for memory extraction (what's worth remembering?)
  - 7 memory types: BEHAVIOURAL, PERFORMANCE, PSYCHOLOGICAL,
    ACCOUNT_STATE, PREFERENCE, LEARNING, SESSION_CONTEXT
"""
import json
import hashlib
from datetime import datetime, timezone
from typing import Any
import structlog

log = structlog.get_logger()

# ── Lazy imports to avoid startup crash if deps missing ──────────────────────
_chroma_client = None
_collection = None
_openai_client = None


def _get_chroma():
    """Lazy-init ChromaDB persistent client."""
    global _chroma_client, _collection
    if _collection is not None:
        return _collection
    try:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path="./memory_store")
        _collection = _chroma_client.get_or_create_collection(
            name="user_memories",
            metadata={"hnsw:space": "cosine"},
        )
        log.info("memory_chroma_init", status="ok")
        return _collection
    except Exception as exc:
        log.error("memory_chroma_init_failed", error=str(exc))
        return None


def _get_openai():
    """Lazy-init OpenAI client (for embeddings only)."""
    global _openai_client
    if _openai_client is not None:
        return _openai_client
    try:
        from openai import OpenAI
        _openai_client = OpenAI()  # reads OPENAI_API_KEY from env
        return _openai_client
    except Exception as exc:
        log.error("memory_openai_init_failed", error=str(exc))
        return None


class MemoryManager:
    """
    Manages persistent memory for QuantNeuralEdge users.
    Stores observations as semantic embeddings.
    Retrieves relevant memories before each analysis session.
    """

    def embed(self, text: str) -> list[float] | None:
        """Convert text to semantic embedding vector."""
        client = _get_openai()
        if not client:
            return None
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return response.data[0].embedding
        except Exception as exc:
            log.error("memory_embed_failed", error=str(exc))
            return None

    def store_memory(
        self,
        user_id: str,
        memory: str,
        memory_type: str,
        importance: str = "MEDIUM",
    ) -> str | None:
        """
        Store a single memory for a user.

        importance: HIGH | MEDIUM | LOW
        memory_type: BEHAVIOURAL | PERFORMANCE | PSYCHOLOGICAL |
                     ACCOUNT_STATE | PREFERENCE | LEARNING | SESSION_CONTEXT
        """
        collection = _get_chroma()
        if not collection:
            return None

        memory_id = hashlib.sha256(
            f"{user_id}{memory}{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]

        embedding = self.embed(memory)
        if not embedding:
            return None

        try:
            collection.add(
                ids=[memory_id],
                embeddings=[embedding],
                documents=[memory],
                metadatas=[{
                    "user_id": user_id,
                    "memory_type": memory_type,
                    "importance": importance,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "times_retrieved": 0,
                }],
            )
            log.info("memory_stored", user_id=user_id[:8], type=memory_type,
                     importance=importance)
            return memory_id
        except Exception as exc:
            log.error("memory_store_failed", error=str(exc))
            return None

    def retrieve_memories(
        self,
        user_id: str,
        context: str,
        n_results: int = 8,
    ) -> list[dict]:
        """
        Retrieve the most relevant memories for this user
        given the current analysis context.
        """
        collection = _get_chroma()
        if not collection:
            return []

        context_embedding = self.embed(context)
        if not context_embedding:
            return []

        try:
            results = collection.query(
                query_embeddings=[context_embedding],
                n_results=n_results,
                where={"user_id": user_id},
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            log.error("memory_retrieve_failed", error=str(exc))
            return []

        memories = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # Only return memories above relevance threshold
            # cosine distance: lower = more similar
            if dist < 0.4:
                memories.append({
                    "memory": doc,
                    "type": meta["memory_type"],
                    "importance": meta["importance"],
                    "created_at": meta["created_at"],
                    "relevance_score": round(1 - dist, 3),
                })

        # Sort: HIGH importance first, then by relevance
        memories.sort(key=lambda x: (
            0 if x["importance"] == "HIGH" else
            1 if x["importance"] == "MEDIUM" else 2,
            -x["relevance_score"],
        ))
        return memories

    async def extract_memories_from_session(
        self,
        user_id: str,
        session_data: dict[str, Any],
    ) -> list[str]:
        """
        After each analysis session, extract what is worth remembering.
        Calls Claude to identify meaningful observations.

        session_data contains: instrument, analysis_output, user_action,
                               signal_id, session_timestamp, direction,
                               probability_score, conviction_tier, etc.
        """
        import anthropic

        extraction_prompt = f"""You are extracting memorable observations about a specific trader from one analysis session. Output a JSON array of observations worth storing.

SESSION DATA:
{json.dumps(session_data, indent=2, default=str)}

Extract observations that would meaningfully change future analysis for this specific user. Focus on:
- Patterns in what setups they act on vs ignore
- Their emotional/behavioural state (overtrading, hesitation)
- Account status changes (drawdown, profit target progress)
- Preferences (instruments, strategies, session timing)
- Performance trends (which setups work for them vs not)

Return JSON array only. Each item: {{"memory": str, "type": str, "importance": str}}
Types: BEHAVIOURAL | PERFORMANCE | PSYCHOLOGICAL | ACCOUNT_STATE | PREFERENCE | LEARNING
Importance: HIGH | MEDIUM | LOW

Only include observations that would CHANGE future analysis.
Do not include generic observations that apply to all traders.
If nothing meaningful occurred, return an empty array []."""

        try:
            client = anthropic.AsyncAnthropic()
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",  # lightweight tier for extraction
                max_tokens=1000,
                messages=[{"role": "user", "content": extraction_prompt}],
            )

            observations = json.loads(response.content[0].text)
            stored = []
            for obs in observations:
                mid = self.store_memory(
                    user_id=user_id,
                    memory=obs["memory"],
                    memory_type=obs["type"],
                    importance=obs["importance"],
                )
                if mid:
                    stored.append(obs["memory"])
            log.info("memory_extracted", user_id=user_id[:8],
                     count=len(stored))
            return stored
        except Exception as exc:
            log.error("memory_extraction_failed", error=str(exc))
            return []  # silent fail — memory is enhancement, not core

    async def generate_agent_corrections(
        self,
        signal_data: dict[str, Any],
    ) -> list[dict]:
        """
        Compare each agent's prediction against the actual outcome.
        Generate correction lessons for agents that got it wrong.

        Returns list of correction dicts ready for DB insertion.
        """
        outcome = signal_data.get("outcome")
        if not outcome or outcome == "EXPIRED":
            return []

        agent_votes = signal_data.get("agent_votes", {})
        actual_direction = "LONG" if outcome == "WIN" else "SHORT"
        # If the signal was SHORT and it won, the correct direction was SHORT
        if signal_data.get("direction") == "SHORT":
            actual_direction = "SHORT" if outcome == "WIN" else "LONG"

        corrections = []
        for agent_name, vote in agent_votes.items():
            if not isinstance(vote, dict):
                continue
            agent_dir = vote.get("direction")
            if not agent_dir or agent_dir == "NEUTRAL":
                continue

            # Check if agent was wrong
            was_wrong = (
                (agent_dir == "LONG" and actual_direction == "SHORT") or
                (agent_dir == "SHORT" and actual_direction == "LONG")
            )
            if not was_wrong:
                continue

            confidence = vote.get("confidence", 50)
            correction_type = "OVERCONFIDENT" if confidence > 70 else "WRONG_DIRECTION"

            lesson = (
                f"{agent_name.replace('_', ' ').title()} predicted {agent_dir} "
                f"with {confidence}% confidence on {signal_data.get('ticker', '?')} "
                f"({signal_data.get('timeframe', '?')}), but the outcome was "
                f"{outcome}. "
            )
            if signal_data.get("pnl_pct"):
                lesson += f"PnL: {signal_data['pnl_pct']:+.1f}%. "

            conditions_hash = hashlib.sha256(
                f"{agent_name}{signal_data.get('ticker')}{signal_data.get('timeframe')}{outcome}".encode()
            ).hexdigest()[:32]

            corrections.append({
                "agent_name": agent_name,
                "signal_id": signal_data.get("signal_id"),
                "correction_type": correction_type,
                "lesson": lesson,
                "ticker": signal_data.get("ticker"),
                "conditions_hash": conditions_hash,
            })

        return corrections

    def build_memory_context(self, user_id: str, current_context: str) -> str:
        """
        Build the memory context block injected into the
        Trader Agent prompt before each analysis.
        """
        memories = self.retrieve_memories(user_id, current_context)

        if not memories:
            return ""  # No memories yet — first-time user

        high = [m for m in memories if m["importance"] == "HIGH"]
        medium = [m for m in memories if m["importance"] == "MEDIUM"]

        lines = []
        lines.append("PERSISTENT USER CONTEXT:")
        lines.append("=" * 50)
        lines.append("The following is what is known about this "
                      "specific user from prior sessions. "
                      "Use this to personalise the analysis.")
        lines.append("")

        if high:
            lines.append("HIGH PRIORITY CONTEXT:")
            for m in high[:3]:  # Max 3 high-priority memories
                lines.append(f"  - {m['memory']}")
            lines.append("")

        if medium:
            lines.append("SUPPORTING CONTEXT:")
            for m in medium[:5]:  # Max 5 medium-priority memories
                lines.append(f"  - {m['memory']}")
            lines.append("")

        lines.append("=" * 50)
        lines.append("")

        return "\n".join(lines)

    def build_agent_correction_context(
        self,
        agent_name: str,
        ticker: str,
        corrections: list[dict],
    ) -> str:
        """
        Build correction context for a specific agent from past mistakes.
        Injected into the agent's prompt so it can self-correct.
        """
        relevant = [
            c for c in corrections
            if c.get("agent_name") == agent_name
        ]
        if not relevant:
            return ""

        lines = [f"SELF-CORRECTION NOTES (from past {agent_name} predictions):"]
        for c in relevant[:3]:  # Max 3 corrections
            lines.append(f"  - {c['lesson']}")
        lines.append("")
        return "\n".join(lines)

    def get_user_memory_count(self, user_id: str) -> int:
        """Get total stored memories for a user."""
        collection = _get_chroma()
        if not collection:
            return 0
        try:
            results = collection.get(
                where={"user_id": user_id},
                include=[],
            )
            return len(results["ids"])
        except Exception:
            return 0

    def get_user_memories(self, user_id: str, limit: int = 50) -> list[dict]:
        """Get all memories for a user (for the memory dashboard)."""
        collection = _get_chroma()
        if not collection:
            return []
        try:
            results = collection.get(
                where={"user_id": user_id},
                include=["documents", "metadatas"],
                limit=limit,
            )
            memories = []
            for doc, meta in zip(results["documents"], results["metadatas"]):
                memories.append({
                    "memory": doc,
                    "type": meta.get("memory_type"),
                    "importance": meta.get("importance"),
                    "created_at": meta.get("created_at"),
                })
            return memories
        except Exception:
            return []

    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """Delete a specific memory (essential for user trust)."""
        collection = _get_chroma()
        if not collection:
            return False
        try:
            # Verify ownership before deletion
            result = collection.get(ids=[memory_id], include=["metadatas"])
            if result["metadatas"] and result["metadatas"][0].get("user_id") == user_id:
                collection.delete(ids=[memory_id])
                return True
            return False
        except Exception:
            return False


# ── Singleton ────────────────────────────────────────────────────────────────
memory_manager = MemoryManager()
