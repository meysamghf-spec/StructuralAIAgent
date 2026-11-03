"""Per-project chat memory: recall across conversations of one project, strict isolation between projects / General."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.application import project_chat_memory as pcm
from app.domain.models.project_memory import MemoryType, ProjectMemory

T0 = datetime(2026, 11, 1, tzinfo=UTC)


class FakeRepo:
    def __init__(self):
        self.convs, self.msgs, self.n = [], {}, 0

    def conv(self, account, project_id, title="chat"):
        c = SimpleNamespace(id=uuid4(), account_id=account, project_id=project_id, title=title)
        self.convs.append(c)
        self.msgs[c.id] = []
        return c

    def say(self, conv, role, content):
        self.n += 1
        self.msgs[conv.id].append(SimpleNamespace(role=role, content=content, created_at=T0 + timedelta(seconds=self.n)))

    def list_for_account(self, account_id, *, limit=100, project_id=None, unassigned=False):
        out = [c for c in self.convs if c.account_id == account_id]
        if project_id is not None:
            out = [c for c in out if c.project_id == project_id]
        return out[:limit]

    def list_messages(self, conversation_id, *, limit=500):
        return self.msgs[conversation_id][:limit]


class FakeMemory:
    def __init__(self):
        self.items: list[ProjectMemory] = []

    def create_memory(self, project_id, memory_type, content, *, source_type=None, metadata=None, created_by=None, **_):
        m = ProjectMemory(id=uuid4(), project_id=project_id, memory_type=memory_type, content=content,
                          source_type=source_type, metadata=metadata or {}, created_by=created_by)
        self.items.append(m)
        return m

    def list_memories(self, project_id):
        return [m for m in self.items if m.project_id == project_id]

    def retrieve_memories(self, project_id, *, source_type=None, **_):
        return [m for m in self.list_memories(project_id) if source_type is None or m.source_type == source_type]

    def delete_memory(self, project_id, memory_id):
        self.items = [m for m in self.items if not (m.project_id == project_id and m.id == memory_id)]
        return True


def _setup():
    repo, mem = FakeRepo(), FakeMemory()
    p1, p2 = uuid4(), uuid4()
    a = repo.conv("acct", p1, "A")
    repo.say(a, "user", "ستون‌ها بتن C30 و ارتفاع طبقه 3.2 متر است")
    repo.say(a, "assistant", "ثبت شد.")
    b = repo.conv("acct", p1, "B")
    other = repo.conv("acct", p2, "X")
    repo.say(other, "user", "the secret word is PINEAPPLE")
    general = repo.conv("acct", None, "G")
    repo.say(general, "user", "general chat fact ZEBRA")
    return repo, mem, p1, p2, a, b, other, general


def test_fact_from_conversation_a_is_recalled_in_conversation_b_of_same_project():
    repo, mem, p1, _p2, _a, b, *_ = _setup()
    out = pcm.build_project_memory(repo, mem, "acct", p1, current_conversation_id=b.id, project_name="P1")
    assert "C30" in out["text"] and "3.2" in out["text"]
    assert out["stats"]["conversations"] == 1


def test_other_project_and_general_never_leak():
    repo, mem, p1, p2, _a, b, other, _g = _setup()
    t1 = pcm.build_project_memory(repo, mem, "acct", p1, current_conversation_id=b.id)["text"]
    assert "PINEAPPLE" not in t1 and "ZEBRA" not in t1
    t2 = pcm.build_project_memory(repo, mem, "acct", p2, current_conversation_id=uuid4())["text"]
    assert "PINEAPPLE" in t2 and "C30" not in t2 and "ZEBRA" not in t2


def test_other_account_conversations_are_not_read():
    repo, mem, p1, *_ = _setup()
    intruder = repo.conv("someone-else", p1, "Z")
    repo.say(intruder, "user", "intruder text KIWI")
    assert "KIWI" not in pcm.build_project_memory(repo, mem, "acct", p1)["text"]


def test_current_conversation_window_is_not_duplicated():
    repo, mem, p1, _p2, a, *_ = _setup()
    assert pcm.build_project_memory(repo, mem, "acct", p1, current_conversation_id=a.id)["text"] == ""


def test_key_facts_come_from_project_memory_only():
    repo, mem, p1, p2, _a, b, *_ = _setup()
    mem.create_memory(p1, MemoryType.DECISION, "frame: 3 storeys, 2 bays x, 5 m")
    mem.create_memory(p2, MemoryType.DECISION, "other project decision MANGO")
    t = pcm.build_project_memory(repo, mem, "acct", p1, current_conversation_id=b.id)["text"]
    assert "3 storeys" in t and "MANGO" not in t


def test_long_history_uses_persisted_incremental_summary_and_budget(monkeypatch):
    monkeypatch.setattr(pcm, "RECENT_BUDGET", 2000)
    repo, mem, p1, _p2, a, b, *_ = _setup()
    for i in range(200):
        repo.say(a, "user", f"note {i} " + "x" * 100)
    out = pcm.build_project_memory(repo, mem, "acct", p1, current_conversation_id=b.id)
    assert out["stats"]["summarized"] > 0 and len(out["text"]) <= pcm.TOTAL_BUDGET
    summaries = mem.retrieve_memories(p1, source_type=pcm.SUMMARY_SOURCE)
    assert len(summaries) == 1
    covered = summaries[0].metadata["covered_until"]
    repo.say(a, "user", "late note LATEST")
    for i in range(30):
        repo.say(a, "user", "y" * 100)
    pcm.build_project_memory(repo, mem, "acct", p1, current_conversation_id=b.id)
    summaries = mem.retrieve_memories(p1, source_type=pcm.SUMMARY_SOURCE)
    assert len(summaries) == 1 and summaries[0].metadata["covered_until"] > covered
    assert sum(len(x) + 1 for x in summaries[0].content.splitlines()) <= pcm.SUMMARY_BUDGET + 1
    assert all(isinstance(m.project_id, UUID) and m.project_id == p1 for m in summaries)


def test_general_chat_service_path_has_no_project_memory():
    from app.application.conversation_service import ConversationService

    svc = object.__new__(ConversationService)
    conv = SimpleNamespace(id=uuid4(), project_id=None)
    assert svc._project_memory_text(conv, SimpleNamespace(account_id="acct")) == ""


def test_service_injects_project_memory_into_helper_context_and_isolates():
    from app.application.conversation_service import ConversationService

    repo, mem, p1, p2, _a, b, other, _g = _setup()
    svc = object.__new__(ConversationService)
    svc._repo, svc._project_memory = repo, mem
    acct = SimpleNamespace(account_id="acct")
    assert "C30" in svc._project_memory_text(b, acct)
    assert "C30" not in svc._project_memory_text(other, acct)


def test_orchestrator_prompt_state_carries_project_memory():
    from app.application.orchestrator import engine

    port = SimpleNamespace(project={"name": "P1"}, usage_snapshot=lambda: "", project_memory=lambda: "MEM-C30")
    ctx = SimpleNamespace(port=port, fa=True, current_model=lambda: None)
    assert engine._state_for_prompt(ctx)["project_chat_memory"] == "MEM-C30"
