"""PolyglotIndexer -- orchestrates the extractors into ConceptStore.

Build order (§3): authorities first (VocabularyExtractor seeds concepts + a
value->concept resolution table), then the code/JSON extractors collect raw sites
which are resolved to concept ids and inserted. Per-file content hashes are recorded
so a later incremental reindex can re-extract only changed files.

Phase 1 = full build. Incremental reindex(paths) re-extracts a subset (used by the
`reindex` MCP tool; symbol/DB layers land in later phases).
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Dict, List, Optional

from .store import ConceptStore
from .extractors import VocabularyExtractor, JsonContentExtractor, PyExtractor
from .extractors.vocabulary import load_vocab
from .extractors.schema import SchemaExtractor
from .extractors.ml_vocab import MlVocabExtractor
from .extractors.csharp import CsExtractor
from .extractors.contract import ContractExtractor


class PolyglotIndexer:
    def __init__(self, repo_root: str, scan_root: str):
        self.repo_root = repo_root
        self.scan_root = scan_root
        self.vocab_extractor = VocabularyExtractor()
        self.json_extractor = JsonContentExtractor()
        self.py_extractor = PyExtractor()
        self.schema_extractor = SchemaExtractor()
        self.ml_extractor = MlVocabExtractor()
        self.cs_extractor = CsExtractor()
        self.contract_extractor = ContractExtractor()

    # ── full build ────────────────────────────────────────────────
    def build(self, store: ConceptStore, verbose: bool = False) -> Dict[str, int]:
        t0 = time.time()
        self._wipe(store)
        vocab = self.vocab_extractor.run(store, self.repo_root, self.scan_root)
        if verbose:
            print(f"[vocab] {len(vocab.values)} values, {len(vocab.categories)} categories")

        raw = []
        raw += self.json_extractor.collect(self.repo_root, self.scan_root, vocab)
        if verbose:
            print(f"[json]  {len(raw)} content sites")
        py_sites = self.py_extractor.collect(self.repo_root, self.scan_root, vocab)
        if verbose:
            print(f"[py]    {len(py_sites)} code sites")
        raw += py_sites
        ml_sites = self.ml_extractor.collect(self.repo_root)
        if verbose:
            print(f"[ml]    {len(ml_sites)} ml-label sites")
        raw += ml_sites
        cs_sites = self.cs_extractor.collect(self.repo_root, vocab)
        if verbose:
            print(f"[cs]    {len(cs_sites)} csharp-mirror sites")
        raw += cs_sites

        self.schema_extractor.run(store, self.repo_root)  # db_junction shared sites
        self.contract_extractor.run(store, self.repo_root, self.scan_root)  # output_contract sites
        self._insert_sites(store, raw)
        self._record_hashes(store, raw)
        from .seeds import apply_seed_edges
        apply_seed_edges(store)
        from .drift import run_coverage_check
        cov = run_coverage_check(store, self.repo_root)
        if verbose and cov:
            for w in cov:
                print(f"[coverage] {w}")
        store.set_meta("repo_head_sha", self._head_sha())
        store.set_meta("built_at", str(time.time()))
        store.commit()

        stats = store.stats()
        stats["elapsed_ms"] = int((time.time() - t0) * 1000)
        stats["coverage_warnings"] = len(cov)
        return stats

    # ── incremental ───────────────────────────────────────────────
    def reindex(self, store: ConceptStore, paths: List[str]) -> Dict[str, int]:
        """Re-extract a specific set of files (source-only; §5).

        Authorities are cheap so any authority change -> full rebuild is safer; here
        we handle code/JSON files. Deletes each file's sites, re-collects, re-inserts.
        """
        if store.stats()["concepts"] == 0:
            return self.build(store)
        # Reconstruct the gate from existing concepts -- do NOT re-run authority
        # extraction (it would re-append definition sites/edges and duplicate them).
        vocab = load_vocab(store)
        abspaths, touched = [], 0
        for p in paths:
            ap = p if os.path.isabs(p) else os.path.join(self.repo_root, p)
            if os.path.exists(ap):
                abspaths.append(ap)
        json_files = [p for p in abspaths if p.lower().endswith(".json")]
        py_files = [p for p in abspaths if p.lower().endswith(".py")]

        raw = []
        if json_files:
            raw += self.json_extractor.collect(self.repo_root, self.scan_root, vocab, files=json_files)
        if py_files:
            raw += self.py_extractor.collect(self.repo_root, self.scan_root, vocab, files=py_files)

        # per-file idempotency: drop old rows for the touched files first
        from .util import rel
        for ap in abspaths:
            store.delete_sites_for_file(rel(ap, self.repo_root))
            touched += 1
        self._insert_sites(store, raw)
        self._record_hashes(store, raw)
        store.set_meta("repo_head_sha", self._head_sha())
        store.commit()
        return {"reindexed_files": touched, "sites_updated": len(raw)}

    # ── internals ─────────────────────────────────────────────────
    def _wipe(self, store: ConceptStore) -> None:
        c = store.connection
        for tbl in ("binding_sites", "concept_edges", "concepts", "file_index"):
            c.execute(f"DELETE FROM {tbl}")
        c.commit()

    def _insert_sites(self, store: ConceptStore, raw: List[Dict]) -> None:
        cache: Dict[tuple, str] = {}
        for s in raw:
            cid = self._resolve(store, s["value"], s.get("kind_hint", "tag_value"),
                                s.get("preferred_taxonomy"), cache)
            store.add_binding_site(
                cid, s["site_kind"], s["language"], s["file"], s["line"],
                s["coupling_type"], s["role"],
                silent_failure=s.get("silent_failure"),
                mirror_group=s.get("mirror_group"),
                pinned_by_test=s.get("pinned_by_test"),
                editable=s.get("editable", 1),
                locator_extra=s.get("locator_extra"),
                content_hash=s.get("content_hash"))
            gov = s.get("governance")
            if gov:
                store.connection.execute(
                    "UPDATE concepts SET governance = ? WHERE id = ? AND governance IS NULL",
                    (gov, cid))
        store.commit()

    def _resolve(self, store, value, kind_hint, preferred_tax, cache) -> str:
        key = (value, kind_hint, preferred_tax)
        if key in cache:
            return cache[key]
        matches = store.find_concepts_by_value(value)
        cid = None
        if matches:
            if preferred_tax:
                for m in matches:
                    if m["taxonomy"] == preferred_tax:
                        cid = m["id"]
                        break
            if cid is None:
                for m in matches:
                    if m["concept_kind"] == kind_hint:
                        cid = m["id"]
                        break
            if cid is None:
                cid = matches[0]["id"]
        else:
            # used-but-undefined -> a lightweight concept so drift is visible (§5)
            cid = store.upsert_concept(
                kind_hint or "tag_value", value, "undefined",
                summary="used in code/content but not defined in any authority")
        cache[key] = cid
        return cid

    def _record_hashes(self, store: ConceptStore, raw: List[Dict]) -> None:
        seen: Dict[str, str] = {}
        for s in raw:
            if s.get("content_hash"):
                seen[s["file"]] = s["content_hash"]
        for f, h in seen.items():
            store.set_file_hash(f, h)
        store.commit()

    def _head_sha(self) -> str:
        try:
            out = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=self.repo_root,
                capture_output=True, text=True, timeout=5)
            return out.stdout.strip() if out.returncode == 0 else ""
        except Exception:  # noqa: BLE001
            return ""
