"""Plan drawing import -> DRAFT model -> 'Imported model review' approval -> frame analysis."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application import engineering_modules as em
from app.application import plan_import as pi
from app.application import plan_import_flow as flow
from app.application import revision_workflow as rw
from app.application.frame3d_chat_analysis import build_frame3d_payload
from app.domain.models.human_approval import ApprovalStatus

PLANS = Path(__file__).parent / "fixtures" / "plans"
SX, SY = [5.0, 4.0, 6.0], [4.5, 5.0]


def _read(name: str) -> bytes:
    return (PLANS / name).read_bytes()


class FakeApprovals:
    def __init__(self):
        self.items = []

    def create_request(self, project_id, **kw):
        item = SimpleNamespace(id=uuid4(), project_id=project_id, status=ApprovalStatus.PENDING,
                               created_at=datetime.now(UTC), **kw)
        self.items.append(item)
        return item

    def list_requests(self, project_id, status=None):
        return [i for i in self.items if status is None or i.status == status]

    def cancel_request(self, project_id, request_id, actor, reason=None):
        next(i for i in self.items if i.id == request_id).status = ApprovalStatus.CANCELLED

    def approve(self, item):
        item.status = ApprovalStatus.APPROVED


@pytest.mark.parametrize("name,prompt,tol", [("sample_plan.dxf", "", 0.01), ("sample_plan.pdf", "", 0.05),
                                             ("sample_plan.png", "first bay 5 m", 0.05)])
def test_extract_grid_spacings_and_columns(name, prompt, tol):
    d = pi.extract(_read(name), name, prompt + ", 4 storeys, storey height 3.2")
    assert d["labels_x"] == ["1", "2", "3", "4"] and d["labels_y"] == ["A", "B", "C"]
    assert d["spans_x_m"] == pytest.approx(SX, abs=tol) and d["spans_y_m"] == pytest.approx(SY, abs=tol)
    assert len(d["columns"]) == 11 and [2, 1] not in d["columns"]  # one intersection has no column
    assert d["storeys"] == 4 and d["storey_height_m"] == 3.2
    assert 0 < d["confidence"]["overall"] <= 1


def test_image_without_dimensions_is_low_confidence_and_edits_fix_it():
    d = pi.extract(_read("sample_plan.png"), "sample_plan.png", "")
    assert d["confidence"]["spacing"] < 0.5 and any("ASSUMED" in n for n in d["notes"])
    d2, done = pi.apply_edits(d, "first bay 5 m")
    assert d2["spans_x_m"][0] == 5.0 and d2["confidence"]["spacing"] >= 0.9 and not any("ASSUMED" in n for n in d2["notes"])
    d3, done = pi.apply_edits(d2, "فاصله محور ۲ تا ۳ = ۴.۵ متر، ۵ طبقه، ارتفاع طبقه ۳.۴، حذف ستون A-1")
    assert d3["spans_x_m"][1] == 4.5 and d3["storeys"] == 5 and d3["storey_height_m"] == 3.4 and [0, 0] not in d3["columns"]
    assert pi.is_edit("spacing axis A-B = 6m") and not pi.is_edit("what is the drift limit?")


def test_preview_png_and_markdown():
    d = pi.extract(_read("sample_plan.pdf"), "sample_plan.pdf", "3 storeys")
    png = pi.preview_png(d)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 5000
    md = pi.markdown(pi.payload(d))
    assert "Imported model review" in md and "1–2: 5 m" in md


def test_adapter_reject_revises_and_frame_runs_unequal_spans():
    approvals, pid = FakeApprovals(), uuid4()
    p = pi.payload(pi.extract(_read("sample_plan.dxf"), "sample_plan.dxf", "2 storeys"))
    a1 = rw.create_run_approval(approvals, pid, "u1", p)
    assert a1.metadata["module_label"] == "Imported model review" and a1.metadata["module_kind"] == "plan_import"
    out = rw.handle_rejection(approvals, pid, a1, "spacing axis 3-4 = 5.5 m", "u1")
    assert out["outcome"] == "revised" and out["approval"].metadata["revision"] == 2
    assert out["approval"].metadata["inputs"]["draft"]["spans_x_m"][2] == 5.5
    assert any(c["key"] == "draft.spans_x_m" for c in out["changes"])
    assert rw.handle_rejection(approvals, pid, a1, "looks odd", "u1")["outcome"] == "clarify"
    frame = build_frame3d_payload("", manual_inputs=pi.frame_inputs(out["approval"].metadata["inputs"]["draft"]))
    assert frame["status"] == "completed" and em.adapter_for("plan_import") is not None


def test_chat_flow_import_edit_gate_and_analyze():
    approvals, pid, cid = FakeApprovals(), uuid4(), uuid4()
    att = [SimpleNamespace(file_id=uuid4(), filename="sample_plan.pdf")]
    kw = dict(project_id=pid, conversation_id=cid, actor="u1", approval_service=approvals,
              read_file=lambda _id: _read("sample_plan.pdf"))
    assert flow.handle_chat(text="what is in this file?", attachments=att, **kw) is None  # not an import request
    md, meta = flow.handle_chat(text="مدل را از این پلان بساز، ۲ طبقه", attachments=att, **kw)
    assert meta["engineering_results"]["kind"] == "plan_import" and meta["engineering_results"]["preview_png"].startswith("data:image/png")
    assert approvals.items[0].status == ApprovalStatus.PENDING and approvals.items[0].metadata["inputs"]["draft"]["storeys"] == 2

    md, meta = flow.handle_chat(text="analyze the imported model", attachments=[], **kw)
    assert meta.get("blocked")  # gated until approved

    md, meta = flow.handle_chat(text="spacing axis 1-2 = 5.5m", attachments=[], **kw)
    assert "revision 2" in md and approvals.items[0].status == ApprovalStatus.CANCELLED
    rev2 = approvals.items[1]
    assert rev2.metadata["revision"] == 2 and rev2.metadata["parent_approval_id"] == str(approvals.items[0].id)

    approvals.approve(rev2)
    assert "analyze the imported model" in flow.approved_message(rev2)
    md, meta = flow.handle_chat(text="مدل وارد شده را تحلیل کن", attachments=[], **kw)
    fr = meta["engineering_results"]
    assert fr["kind"] == "frame3d_analysis" and fr["status"] == "completed"
    assert fr["inputs"]["spans_x_m"] == [5.5, 4.0, 6.0]
