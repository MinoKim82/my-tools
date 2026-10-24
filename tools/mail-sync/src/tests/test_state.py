import os
import tempfile
import pytest
from core.state import StateManager

def test_state_manager_dedup():
    with tempfile.TemporaryDirectory() as tmp_dir:
        sm = StateManager(tmp_dir)
        msg_id = "test-msg-123"

        assert not sm.is_processed(msg_id)

        sm.mark_processed(msg_id, "finance", {"amount": 50000})

        assert sm.is_processed(msg_id)
        assert sm.get_last_sync_time("finance") is not None

        # Re-load from disk
        sm2 = StateManager(tmp_dir)
        assert sm2.is_processed(msg_id)
