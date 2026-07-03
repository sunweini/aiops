"""Tests for RRF fusion and reranker."""
import pytest


class TestRRFKeyCollision:
    def test_no_collision_with_different_service_id_splits(self):
        """service_ids ['svc_a', 'bc'] and ['svc_ab', 'c'] must not collide."""
        from app.reranker.reranker import reciprocal_rank_fusion

        list_a = [{"service_ids": ["svc_a", "bc"], "doc_type": "sop", "title": "t", "content": ""}]
        list_b = [{"service_ids": ["svc_ab", "c"], "doc_type": "sop", "title": "t", "content": ""}]

        result = reciprocal_rank_fusion([list_a, list_b])
        assert len(result) == 2, "Different service_id splits should not collide"

    def test_same_doc_deduplicates(self):
        """Identical items from different engines are deduplicated."""
        from app.reranker.reranker import reciprocal_rank_fusion

        item = {"service_ids": ["svc_es"], "doc_type": "sop", "title": "9200 SOP", "content": ""}
        result = reciprocal_rank_fusion([[item], [item]])
        assert len(result) == 1

    def test_empty_lists(self):
        from app.reranker.reranker import reciprocal_rank_fusion
        assert reciprocal_rank_fusion([]) == []
        assert reciprocal_rank_fusion([[]]) == []

    def test_rank_ordering(self):
        """Higher-ranked items should get higher RRF scores."""
        from app.reranker.reranker import reciprocal_rank_fusion

        item_high = {"service_ids": ["svc_a"], "doc_type": "sop", "title": "high", "content": ""}
        item_low = {"service_ids": ["svc_b"], "doc_type": "sop", "title": "low", "content": ""}
        result = reciprocal_rank_fusion([[item_high, item_low]])
        assert result[0]["title"] == "high"
