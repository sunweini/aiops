"""ServiceResolver — multi-recall pre-check for IP and service name matching.

Provides fast-path resolution:
- Path A: IP → host → service → SOP (exact match, no LLM)
- Path B: jieba tokenize → alias match → service → SOP (no LLM)

Used by routes.py before falling back to the full LLM pipeline (Path C).
"""

import re
import time

from app.retrievers.graph_retriever import (
    get_service_alias_map,
    get_service_sops,
    resolve_host_by_ip,
    get_host_services,
)
from app.retrievers.es_retriever import get_docs_by_ids

# IP regex pattern
IP_PATTERN = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b')


class ServiceResolver:
    """Resolves services via IP or name aliases, returns associated SOPs."""

    def __init__(self, driver, es_client):
        self.driver = driver
        self.es = es_client
        self._alias_map: dict | None = None
        self._map_loaded_at: float = 0
        self.CACHE_TTL: float = 300  # 5 minutes

    @staticmethod
    def extract_ips(query: str) -> list[str]:
        """Extract valid IPs from query text. Filters out-of-range octets."""
        raw = IP_PATTERN.findall(query)
        valid = []
        for ip in raw:
            parts = ip.split(".")
            if all(0 <= int(p) <= 255 for p in parts):
                valid.append(ip)
        return list(dict.fromkeys(valid))  # dedupe preserving order

    def get_alias_map(self) -> dict:
        """Load service alias map from Neo4j with TTL cache.
        Returns {service_id: {"name": str, "aliases": list[str]}}."""
        now = time.time()
        if self._alias_map is not None and (now - self._map_loaded_at) < self.CACHE_TTL:
            return self._alias_map
        self._alias_map = get_service_alias_map(self.driver)
        self._map_loaded_at = now
        return self._alias_map

    def resolve_by_ip(self, ip: str) -> list[str]:
        """IP → host → service_ids. Returns list of service_ids on that host."""
        host = resolve_host_by_ip(self.driver, ip)
        if not host:
            return []
        host_id = host.get("host_id", "")
        if not host_id:
            return []
        services = get_host_services(self.driver, host_id)
        return [s["id"] for s in services if s.get("id")]

    def resolve_by_name(self, query: str) -> list[tuple[str, float]]:
        """jieba tokenize query → match against service aliases.
        Returns [(service_id, score), ...] sorted by score descending."""
        import jieba
        alias_map = self.get_alias_map()
        if not alias_map:
            return []

        tokens = set(jieba.cut(query))
        tokens = {t.strip() for t in tokens if t.strip() and len(t.strip()) >= 2}

        matches: dict[str, float] = {}
        for service_id, info in alias_map.items():
            name = info.get("name", "")
            aliases = info.get("aliases", [])
            all_names = [name] + aliases if name else aliases

            best_score = 0.0
            for token in tokens:
                for candidate in all_names:
                    if not candidate:
                        continue
                    candidate_lower = candidate.lower()
                    token_lower = token.lower()
                    if token_lower == candidate_lower:
                        best_score = max(best_score, 1.0)
                    elif token_lower in candidate_lower or candidate_lower in token_lower:
                        best_score = max(best_score, 0.8)

            if best_score >= 0.8:
                matches[service_id] = best_score

        return sorted(matches.items(), key=lambda x: x[1], reverse=True)

    def get_service_sops_with_tags(self, service_ids: list[str]) -> list[dict]:
        """Fetch SOP docs for services, with tags from ES for sorting.
        Returns [{doc_id, title, doc_type, tags, content, service_ids}]."""
        # Get SOP doc_ids from Neo4j
        neo4j_sops = []
        for sid in service_ids:
            sops = get_service_sops(self.driver, sid)
            neo4j_sops.extend(sops)

        if not neo4j_sops:
            return []

        # Deduplicate by doc_id
        seen = set()
        unique_doc_ids = []
        for sop in neo4j_sops:
            did = sop["doc_id"]
            if did not in seen:
                seen.add(did)
                unique_doc_ids.append(did)

        # Fetch full content + tags from ES
        es_docs = get_docs_by_ids(self.es, unique_doc_ids, top_k=len(unique_doc_ids))

        # Filter to parent/flat/section chunks only (skip child chunks)
        valid_chunks = [d for d in es_docs if d.get("chunk_type", "flat") != "child"]

        # Deduplicate by doc_id (keep first chunk per doc)
        doc_map: dict[str, dict] = {}
        for doc in valid_chunks:
            did = doc.get("doc_id", "")
            if did and did not in doc_map:
                doc_map[did] = doc

        return list(doc_map.values())

    @staticmethod
    def tag_sort(query_tokens: set, sops: list[dict]) -> list[dict]:
        """Sort SOPs by tag intersection score with query tokens.
        Higher intersection → higher rank. Mutates nothing."""
        scored = []
        for sop in sops:
            sop_tags = set(sop.get("tags", []))
            common = query_tokens & sop_tags
            tag_score = len(common) / len(query_tokens) if query_tokens else 0
            scored.append((sop, tag_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored]

    def try_path_a(self, query: str, top_k: int = 5) -> dict | None:
        """Try Path A: IP → host → service → SOP.
        Returns {answer, sources, matched_by} or None."""
        ips = self.extract_ips(query)
        if not ips:
            return None

        all_service_ids = []
        for ip in ips:
            sids = self.resolve_by_ip(ip)
            all_service_ids.extend(sids)

        if not all_service_ids:
            return None

        # Deduplicate
        all_service_ids = list(dict.fromkeys(all_service_ids))

        # Get SOPs
        sops = self.get_service_sops_with_tags(all_service_ids)
        if not sops:
            return None

        # Tags sort
        import jieba
        query_tokens = set(jieba.cut(query))
        query_tokens = {t.strip() for t in query_tokens if t.strip() and len(t.strip()) >= 2}
        sops = self.tag_sort(query_tokens, sops)

        # Build response
        sources = self._build_sources(sops[:top_k], engine="es", source_path="ip_resolve")
        answer = self._build_answer(sops[:top_k])

        return {
            "answer": answer,
            "sources": sources,
            "matched_by": "ip",
        }

    def try_path_b(self, query: str, top_k: int = 5) -> dict | None:
        """Try Path B: jieba tokenize → alias match → SOP.
        Returns {answer, sources, matched_by} or None."""
        matches = self.resolve_by_name(query)
        if not matches:
            return None

        # Filter to score >= 0.8
        good_matches = [(sid, score) for sid, score in matches if score >= 0.8]
        if not good_matches:
            return None

        service_ids = [sid for sid, _ in good_matches]

        # Get SOPs
        sops = self.get_service_sops_with_tags(service_ids)
        if not sops:
            return None

        # Tags sort
        import jieba
        query_tokens = set(jieba.cut(query))
        query_tokens = {t.strip() for t in query_tokens if t.strip() and len(t.strip()) >= 2}
        sops = self.tag_sort(query_tokens, sops)

        # Build response
        sources = self._build_sources(sops[:top_k], engine="es", source_path="service_resolve")
        answer = self._build_answer(sops[:top_k])

        return {
            "answer": answer,
            "sources": sources,
            "matched_by": "service_name",
        }

    def _build_sources(self, sops: list[dict], engine: str = "es", source_path: str = "direct") -> list:
        """Build SourceItem list from SOP docs."""
        from app.models.query import SourceItem
        sources = []
        for sop in sops:
            sources.append(SourceItem(
                title=sop.get("title", ""),
                score=1.0,
                engine=engine,
                snippet=sop.get("content", "")[:100],
                confidence="★★★",
                source_path=source_path,
            ))
        return sources

    def _build_answer(self, sops: list[dict]) -> str:
        """Build answer text from SOP docs."""
        if not sops:
            return ""
        parts = []
        for i, sop in enumerate(sops):
            title = sop.get("title", "")
            content = sop.get("content", "")
            parts.append(f"## [文档{i+1}] {title}\n{content}")
        return "\n\n---\n\n".join(parts)
