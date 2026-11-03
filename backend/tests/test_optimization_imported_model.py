"""Regression: 'Start optimization' on an imported ETABS model failed with KeyError 'beams' (steel default pool)."""

import copy
import json
from pathlib import Path

import pytest

from app.application.optimization_full import jobs
from app.application.optimization_full.engine import (OptimizationInputError, friendly_error, optimize_model,
                                                      prepare_model)

FIX = Path(__file__).parent / "fixtures" / "model_import" / "portal_e2k_reviewed.json"
FAST = {"time_budget_s": 20, "max_evals": 20}


def _portal():
    return json.loads(FIX.read_text(encoding="utf-8"))


def test_imported_e2k_with_steel_members_and_no_lists():
    r = optimize_model(_portal(), {}, FAST)  # used to raise KeyError('beams')
    assert r["status"] == "done" and r["cost"] > 0
    secs = {g["section"] for g in r["groups"]}
    assert any(s.startswith("IPE") for s in secs)  # steel beam got the default IPE pool
    assert any(s.startswith("2UNP") for s in secs)  # steel brace got the default brace pool
    assert any(g["type"] == "beam" and "فولادی" in g["label"] for g in r["groups"])


def test_imported_model_without_beams():
    m = _portal()
    m["members"] = [x for x in m["members"] if x["type"] != "beam"]
    r = optimize_model(m, {}, FAST)
    assert r["status"] == "done" and all(g["type"] != "beam" for g in r["groups"])


def test_irregular_model_and_unknown_member_types():
    m = _portal()
    m["nodes"]["2@Story2"]["z"] = 7.1  # irregular storey height
    for x in m["members"]:
        if x["type"] == "beam":
            x["type"] = "Girder"  # alias, any case
    extra = copy.deepcopy(m["members"][0]); extra.update(id="W1", type="wall")
    m["members"].append(extra)
    r = optimize_model(m, {}, FAST)
    assert r["status"] == "done"
    assert any(g["type"] == "beam" for g in r["groups"])
    assert "W1" not in r["assignment"]  # unknown types stay as modelled


def test_bad_models_give_persian_errors():
    m = _portal(); m["members"][0]["j"] = "nope"
    with pytest.raises(OptimizationInputError, match="گره"):
        prepare_model(m)
    m = _portal(); m["members"] = []
    with pytest.raises(OptimizationInputError, match="عضو"):
        prepare_model(m)
    m = _portal(); m["members"][4]["section"] = ""
    with pytest.raises(OptimizationInputError, match="مقطع"):
        prepare_model(m)
    for exc in (KeyError("beams"), ValueError("Resolve the blocking review items before analysis."), RuntimeError("x")):
        msg = friendly_error(exc)
        assert "beams" not in msg and "Resolve" not in msg and any("\u0600" <= ch <= "\u06ff" for ch in msg)


def test_job_error_is_persian(tmp_path, monkeypatch):
    import time

    monkeypatch.setattr(jobs, "_dir", lambda: tmp_path)

    def work(progress, cancelled):
        raise KeyError("beams")

    j = jobs.start("u1", {}, work)
    for _ in range(100):
        st = jobs.get(j["id"])
        if st and st["status"] == "error":
            break
        time.sleep(0.05)
    pub = jobs.public(st)
    assert pub["status"] == "error" and "beams" not in pub["error"] and "KeyError" in pub["error_detail"]


@pytest.mark.parametrize("name", ["portal_kgf_cm.e2k", "saia_export_3storey.e2k"])
def test_parsed_e2k_files_optimize(name):
    from app.application.model_import import parse_model_file
    from app.application.model_import.analyze import apply_review, review_summary

    path = FIX.parent / name
    m = parse_model_file(name, path.read_bytes())
    rev = review_summary(m)
    m = apply_review(m, {"confirmed": rev["requires_confirmation"]})
    if not review_summary(m)["can_analyze"]:
        pytest.skip("sample needs manual section edits")
    r = optimize_model(m, {}, FAST)
    assert r["status"] == "done" and r["groups"]
