"""Document indexing with Chinese-aware chunking + vector embedding.

Chunking strategy:
- SOP docs: parent-child (section→child chunks), tables/code blocks preserved
- Tech/incident docs: hierarchical heading-based → paragraph grouping → char fallback
"""

import asyncio
import re
from pathlib import Path

import yaml
from elasticsearch import Elasticsearch
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.retrievers.es_retriever import INDEX_NAME
from app.retrievers.vector_retriever import embed_batch, EMBEDDING_DIM

# ── SOP chunker ─────────────────────────────────────────────────────
CHILD_SIZE = 300
CHILD_OVERLAP = 50
_CHILD_CHUNKER = RecursiveCharacterTextSplitter(
    chunk_size=CHILD_SIZE,
    chunk_overlap=CHILD_OVERLAP,
    separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""],
)

# ── Hierarchical chunker (tech/incident) ────────────────────────────
_TARGET_CHUNK_CHARS = 800
_MAX_PARAGRAPHS_PER_CHUNK = 5
_PARAGRAPH_RE = re.compile(r"\n{2,}")
_FALLBACK_CHUNKER = RecursiveCharacterTextSplitter(
    chunk_size=700,
    chunk_overlap=80,
    separators=["\n\n", "\n", "。", "！", "？", "；", ". ", "? ", "! ", " ", ""],
)

# ── Shared ──────────────────────────────────────────────────────────
_HEADER_RE = re.compile(r"^(#{2,4})\s+(.+)", re.MULTILINE)
PLACEHOLDER_PATTERNS = [
    re.compile(r"（[^）]*待[填写确认补充]+[^）]*）"),
    re.compile(r"\{[a-z_]+\}"),
]


# ── Section splitting ───────────────────────────────────────────────

def _split_sections(body: str) -> list[dict]:
    """Split markdown body into sections by ##/###/#### headers.
    Returns [{heading, level, content}, ...]."""
    matches = list(_HEADER_RE.finditer(body))
    if not matches:
        return [{"heading": "", "level": 0, "content": body.strip()}]

    sections = []
    for i, m in enumerate(matches):
        start = m.end() + 1
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections.append({
            "heading": m.group(2).strip(),
            "level": len(m.group(1)),
            "content": body[start:end].strip(),
        })
    return sections


def _has_placeholder(text: str) -> bool:
    """Check if text is mostly template placeholder."""
    count = sum(len(pat.findall(text)) for pat in PLACEHOLDER_PATTERNS)
    return count > max(1, len(text) / 100)


# ── Chunk dict builder ──────────────────────────────────────────────

def _make_chunk(content: str, idx, total, ctype: str, parent_id: str | None,
                path: list[str], title: str, doc_id: str, metadata: dict) -> dict:
    path_str = " > ".join(path) if len(path) > 1 else title
    if not content.startswith("#"):
        content = f"## {title}\n\n{content}"
    return {
        "title": title, "content": content,
        "chunk_index": idx, "chunk_total": total,
        "chunk_type": ctype, "parent_id": parent_id,
        "chunk_path": path_str,
        "doc_id": doc_id, "doc_type": metadata.get("doc_type", "tech"),
        "service_ids": metadata.get("service_ids", []),
        "service_name": metadata.get("service_name", ""),
        "tags": metadata.get("tags", []),
        "host_ids": metadata.get("related_hosts", []),
        "updated_at": metadata.get("updated_at", ""),
    }


# ── SOP: parent-child chunking ──────────────────────────────────────

def _chunk_sop(body: str, doc_id: str, metadata: dict, filepath: str) -> list[dict]:
    results = []
    sections = _split_sections(body)
    title = metadata.get("title", Path(filepath).stem)
    parent_idx = 0

    for sec in sections:
        sec_content = sec["content"]
        if not sec_content.strip():
            continue

        heading_line = f"{'#' * sec['level']} {sec['heading']}"
        parent_content = f"## {title}\n\n{heading_line}\n\n{sec_content}"
        parent_id = f"{doc_id}_chunks{parent_idx}"

        results.append(_make_chunk(
            content=parent_content, idx=f"s{parent_idx}", total=0,
            ctype="parent", parent_id=None,
            path=[title, sec['heading']], title=title, doc_id=doc_id, metadata=metadata,
        ))

        if _has_placeholder(sec_content):
            parent_idx += 1
            continue

        child_chunks = _CHILD_CHUNKER.split_text(sec_content)
        for i, child in enumerate(child_chunks):
            child = child.strip()
            if not child or _has_placeholder(child):
                continue
            child_with_ctx = f"## {title}\n\n{heading_line}\n\n{child}"
            results.append(_make_chunk(
                content=child_with_ctx, idx=f"s{parent_idx}_c{i}",
                total=len(child_chunks),
                ctype="child", parent_id=parent_id,
                path=[title, sec['heading']], title=title, doc_id=doc_id, metadata=metadata,
            ))
        parent_idx += 1

    return results


# ── Hierarchical chunking (tech/incident) ───────────────────────────

def _chunk_hierarchical(body: str, doc_id: str, metadata: dict, filepath: str) -> list[dict]:
    """1) Split by H2/H3/H4 headers → sections
    2) Section too long? Recurse into sub-headers (forms parent-child hierarchy)
    3) No sub-headers? Merge paragraphs 3-5 per chunk
    4) Single paragraph too long? Fallback to char split at sentence boundaries
    5) No structure at all? Fixed-length with 10% overlap"""
    results = []
    title = metadata.get("title", Path(filepath).stem)
    sections = _split_sections(body)

    for sec in sections:
        sec_content = sec["content"].strip()
        if not sec_content or _has_placeholder(sec_content):
            continue
        _recurse_h(
            sec_content, sec["heading"],
            [title], title, doc_id, metadata, results,
        )

    if not results:
        chunks = _FALLBACK_CHUNKER.split_text(body)
        for i, chunk in enumerate(chunks):
            chunk = chunk.strip()
            if not chunk or _has_placeholder(chunk):
                continue
            results.append(_make_chunk(
                content=chunk, idx=i, total=len(chunks),
                ctype="flat", parent_id=None,
                path=[title], title=title, doc_id=doc_id, metadata=metadata,
            ))

    return results


def _recurse_h(content: str, heading: str, path: list[str],
               title: str, doc_id: str, metadata: dict, results: list):
    """Recurse: sub-headers → paragraph groups → char fallback."""
    cur_path = path + [heading] if heading else path

    # 1. Try sub-headers
    subs = _split_sections(content)
    if len(subs) > 1:
        for sub in subs:
            sc = sub["content"].strip()
            if not sc or _has_placeholder(sc):
                continue
            _recurse_h(sc, sub["heading"], cur_path, title, doc_id, metadata, results)
        return

    # 2. Fits in one chunk
    if len(content) <= _TARGET_CHUNK_CHARS:
        results.append(_make_chunk(
            content=content, idx=len(results), total=1,
            ctype="section", parent_id=None,
            path=cur_path, title=title, doc_id=doc_id, metadata=metadata,
        ))
        return

    # 3. Split by paragraphs
    paragraphs = [p.strip() for p in _PARAGRAPH_RE.split(content)
                  if p.strip() and not _has_placeholder(p)]

    if len(paragraphs) <= 1:
        # 4. Single huge paragraph — char fallback
        for i, chunk in enumerate(_FALLBACK_CHUNKER.split_text(content)):
            chunk = chunk.strip()
            if not chunk or _has_placeholder(chunk):
                continue
            results.append(_make_chunk(
                content=chunk, idx=i, total=0,
                ctype="flat", parent_id=None,
                path=cur_path, title=title, doc_id=doc_id, metadata=metadata,
            ))
        return

    # 3. Merge paragraphs into 3-5 groups
    groups = []
    i = 0
    while i < len(paragraphs):
        g, g_len = [], 0
        while i < len(paragraphs) and len(g) < _MAX_PARAGRAPHS_PER_CHUNK:
            p = paragraphs[i]
            if g_len + len(p) > int(_TARGET_CHUNK_CHARS * 1.5) and g:
                break
            g.append(p)
            g_len += len(p)
            i += 1
        groups.append("\n\n".join(g))

    for j, chunk in enumerate(groups):
        results.append(_make_chunk(
            content=chunk, idx=j, total=len(groups),
            ctype="section", parent_id=None,
            path=cur_path, title=title, doc_id=doc_id, metadata=metadata,
        ))


# ── Main parse entry ──────────────────────────────────────────────

def parse_markdown(filepath: str) -> list[dict]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if not match:
        return []

    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        print(f"YAML error in {filepath}: {e}")
        return []

    body = match.group(2).strip()
    if not isinstance(metadata, dict):
        return []

    from app.schema import validate_frontmatter
    fm_errors = validate_frontmatter(metadata)
    if fm_errors:
        print(f"Frontmatter 校验失败 [{filepath}]:")
        for e in fm_errors:
            print(f"  - {e}")
        return []

    service_ids = metadata.get("service_ids", [])
    if not service_ids:
        return []
    doc_id_str = f"{service_ids[0]}_{Path(filepath).stem}"
    doc_type = metadata.get("doc_type", "tech")

    if doc_type == "sop":
        return _chunk_sop(body, doc_id_str, metadata, filepath)
    return _chunk_hierarchical(body, doc_id_str, metadata, filepath)


# ── Indexing helpers ──────────────────────────────────────────────

_BATCH_SIZE = 64  # ES bulk batch size


async def _embed_chunks_batch(chunks: list[dict]) -> list[dict]:
    """Embed chunks in sub-batches per EMBEDDING_BATCH_SIZE, attach content_vector in-place.
    Returns chunks with vectors; logs errors but doesn't fail."""
    texts = [c.get("content", "") for c in chunks]
    flat_texts = [t for t in texts if t]
    if not flat_texts:
        return chunks

    batch_size = settings.embedding_batch_size
    all_vectors: list[list[float]] = []
    errors = 0

    for i in range(0, len(flat_texts), batch_size):
        sub = flat_texts[i:i + batch_size]
        vecs = await embed_batch(sub)
        if vecs:
            all_vectors.extend(vecs)
        else:
            errors += 1
            print(f"  Embedding sub-batch {i // batch_size} failed ({len(sub)} chunks)")
            all_vectors.extend([[] for _ in sub])

    if all_vectors:
        idx = 0
        for c in chunks:
            if c.get("content"):
                c["content_vector"] = all_vectors[idx]
                idx += 1

    if errors:
        print(f"  {errors}/{max(1, (len(flat_texts) + batch_size - 1) // batch_size)} embedding sub-batches failed")
    return chunks


def _es_id(doc: dict) -> str:
    return doc.get("doc_id", "") + f"_chunk{doc.get('chunk_index', 0)}"


async def index_chunk(es: Elasticsearch, doc: dict) -> str | None:
    """Index a single chunk (vector must be pre-attached).
    Fallback for single-file index path."""
    if not doc:
        return None
    es_id_val = _es_id(doc)
    try:
        resp = es.index(index=INDEX_NAME, id=es_id_val, document=doc, refresh="wait_for")
        return resp["_id"]
    except Exception as e:
        print(f"ES index error: {e}")
        return None


async def _index_chunk_bulk(es: Elasticsearch, chunks: list[dict]) -> tuple[int, int]:
    """Bulk index chunks using ES bulk API. Returns (success, failed)."""
    if not chunks:
        return 0, 0

    from elasticsearch.helpers import bulk

    actions = []
    for c in chunks:
        actions.append({
            "_index": INDEX_NAME,
            "_id": _es_id(c),
            "_source": c,
        })

    success = 0
    failed = 0
    try:
        # Split into sub-batches to avoid huge payloads
        for i in range(0, len(actions), _BATCH_SIZE):
            batch = actions[i:i + _BATCH_SIZE]
            ok, fail_count = bulk(es, batch, raise_on_error=False, refresh=True, stats_only=True)
            success += ok
            failed += fail_count
    except Exception as e:
        print(f"ES bulk index error: {e}")
        failed = len(actions)

    return success, failed


async def index_single_file(es: Elasticsearch, filepath: str) -> tuple[int, int]:
    """Index a single .md file. Deletes old chunks by doc_id first, then re-indexes.
    Uses batch embedding + bulk ES index.
    Returns (success_count, failed_count)."""
    chunks = parse_markdown(filepath)
    if not chunks:
        return 0, 1

    doc_id = chunks[0].get("doc_id", "")
    if doc_id:
        try:
            es.delete_by_query(
                index=INDEX_NAME,
                body={"query": {"prefix": {"doc_id": doc_id}}},
                refresh=True,
            )
        except Exception as e:
            print(f"Delete old chunks error [{doc_id}]: {e}")

    # Batch embed all chunks
    await _embed_chunks_batch(chunks)

    # Bulk index
    success, failed = await _index_chunk_bulk(es, chunks)

    # Sync Neo4j once per document
    if success > 0:
        try:
            from app.retrievers.graph_retriever import get_driver, sync_document_node
            driver = get_driver()
            result = sync_document_node(driver, chunks[0])
            if result["status"] == "error":
                print(f"Neo4j sync error [{doc_id}]: {result['detail']}")
        except Exception as e:
            print(f"Neo4j sync driver error [{doc_id}]: {e}")

    return success, failed


async def _index_one_file(es: Elasticsearch, fp: Path,
                           sem: asyncio.Semaphore,
                           synced_docs: set,
                           counters: dict) -> None:
    """Index one file with concurrency control."""
    async with sem:
        chunks = parse_markdown(str(fp))
        if not chunks:
            counters["failed"] += 1
            return

        doc_id = chunks[0].get("doc_id", "")
        if not doc_id:
            counters["failed"] += 1
            return

        # Batch embed all chunks
        try:
            await _embed_chunks_batch(chunks)
        except Exception as e:
            print(f"Embedding error [{doc_id}]: {e}")
            # Continue without vectors

        # Bulk index
        ok, err = await _index_chunk_bulk(es, chunks)
        counters["success"] += ok
        counters["failed"] += err

        if ok > 0 and doc_id not in synced_docs:
            synced_docs.add(doc_id)
            try:
                from app.retrievers.graph_retriever import get_driver, sync_document_node
                driver = get_driver()
                result = sync_document_node(driver, chunks[0])
                if result["status"] == "error":
                    counters["sync_errors"] += 1
                    print(f"Neo4j sync error [{doc_id}]: {result['detail']}")
                elif result["status"] == "partial_success":
                    counters["sync_errors"] += 1
                    print(f"Neo4j sync partial [{doc_id}]: {result['detail']}")
            except Exception as e:
                counters["sync_errors"] += 1
                print(f"Neo4j sync driver error [{doc_id}]: {e}")


async def index_directory(es: Elasticsearch, dir_path: str, clean: bool = False) -> tuple[int, int]:
    md_files = list(Path(dir_path).rglob("*.md"))
    print(f"Indexing {len(md_files)} files (concurrency={settings.embedding_concurrency}, batch_size={settings.embedding_batch_size})")

    if clean:
        try:
            es.indices.delete(index=INDEX_NAME, ignore_unavailable=True)
            from app.retrievers.es_retriever import init_index
            init_index(es)
            print("Index cleared and recreated")
        except Exception as e:
            print(f"Index cleanup error: {e}")

    sem = asyncio.Semaphore(settings.embedding_concurrency)
    synced_docs: set = set()
    counters = {"success": 0, "failed": 0, "sync_errors": 0}

    tasks = [_index_one_file(es, fp, sem, synced_docs, counters) for fp in md_files]
    await asyncio.gather(*tasks)

    if counters["sync_errors"]:
        print(f"Neo4j sync errors: {counters['sync_errors']}/{len(synced_docs)} documents")

    return counters["success"], counters["failed"]
