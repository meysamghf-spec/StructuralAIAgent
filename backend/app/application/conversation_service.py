"""Conversation and chat orchestration service."""

from __future__ import annotations
import logging

from queue import Queue
from threading import Event, Thread
from typing import Any, Iterator
from uuid import UUID

from app.application.frame3d_chat_analysis import frame3d_memory_summary
from app.application.agent_run_events import (
    EVENT_APPROVAL_REQUIRED,
    EVENT_COMPLETED,
    EVENT_FAILED,
    EVENT_STARTED,
    EVENT_STEP,
    EVENT_TOKEN,
    AgentRunProgressSink,
    emit_progress,
    safe_stream_error,
)
from app.application.agent_run_view import build_agent_run_view, chat_mode_to_agent_type
from app.application.agent_runtime_service import AgentRuntimeService
from app.application.ai_gateway_service import AIGatewayService
from app.application.chat_attachment_context_service import (
    ChatAttachmentContextBundle,
    ChatAttachmentContextService,
    enrich_user_request_with_attachments,
)
from app.application.exceptions import (
    ConversationForbiddenError,
    ConversationNotFoundError,
    ProjectAuthorizationError,
)
from app.application.file_ingestion_service import FileIngestionService
from app.application.file_registry_service import FileRegistryService
from app.application.project_access_service import ProjectAccessService
from app.application.project_memory_service import ProjectMemoryService
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import (
    AgentExecutionRecord,
    AgentExecutionRequest,
    AgentExecutionStatus,
    is_awaiting_human_approval,
)
from app.domain.models.engineering_task import EngineeringTaskStatus
from app.domain.models.agent_runtime_view import build_agent_execution_user_view
from app.domain.models.ai_gateway import AIMessage, AIMessageRole, AICompletionRequest
from app.domain.models.conversation import (
    AttachmentStatus,
    Conversation,
    ConversationMessage,
    MessageAttachment,
    MessageRole,
)
from app.domain.models.file_artifact import ExtractionStatus, ParsingStatus, ProjectFile
from app.domain.models.project_memory import MemoryType
from app.domain.models.user import AuthenticatedAccount
from app.infrastructure.repositories.postgres_conversation_repository import (
    PostgresConversationRepository,
)

_CHAT_MODEL = "stub-engineering-chat"
_MAX_HISTORY_MESSAGES = 20

_AGENT_WORKSPACE_LINKS: dict[EngineeringAgentType, str] = {
    EngineeringAgentType.STRUCTURAL_MODELING_AGENT: "/workspace/model",
    EngineeringAgentType.LOAD_ASSESSMENT_AGENT: "/workspace/model",
    EngineeringAgentType.ANALYSIS_AGENT: "/workspace/analysis",
    EngineeringAgentType.CONCRETE_DESIGN_AGENT: "/workspace/design",
    EngineeringAgentType.STEEL_DESIGN_AGENT: "/workspace/design",
    EngineeringAgentType.SEISMIC_AGENT: "/workspace/analysis",
    EngineeringAgentType.VALIDATION_AGENT: "/workspace/validation",
    EngineeringAgentType.CAD_AGENT: "/workspace/cad",
    EngineeringAgentType.REPORTING_AGENT: "/workspace/reports",
    EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT: "/workspace/files",
    EngineeringAgentType.PROMPT_GENERATION_AGENT: "/workspace/agents",
    EngineeringAgentType.STRUCTURAL_ENGINEERING_AGENT: "/workspace/agents",
}

from app.application import assistant_chat as _assistant_chat  # noqa: E402

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(
        self,
        *,
        repository: PostgresConversationRepository,
        project_access: ProjectAccessService,
        agent_runtime: AgentRuntimeService,
        ai_gateway: AIGatewayService,
        file_ingestion: FileIngestionService,
        file_registry: FileRegistryService,
        project_memory: ProjectMemoryService,
        attachment_context: ChatAttachmentContextService,
    ) -> None:
        self._repo = repository
        self._project_access = project_access
        self._agent_runtime = agent_runtime
        self._ai_gateway = ai_gateway
        self._file_ingestion = file_ingestion
        self._file_registry = file_registry
        self._project_memory = project_memory
        self._attachment_context = attachment_context

    def create_conversation(
        self,
        account: AuthenticatedAccount,
        *,
        title: str = "New conversation",
        project_id: UUID | None = None,
    ) -> Conversation:
        if project_id is not None:
            self._project_access.require_project(project_id, account)
        return self._repo.create(
            account_id=account.account_id,
            title=title.strip() or "New conversation",
            project_id=project_id,
        )

    def list_conversations(
        self,
        account: AuthenticatedAccount,
        *,
        limit: int = 100,
    ) -> list[Conversation]:
        return self._repo.list_for_account(account.account_id, limit=limit)

    def list_project_chat_runs(self, account: AuthenticatedAccount, project_id: UUID) -> list[dict]:
        """Engineering runs from this account's chats in one project, newest first."""
        from app.application.chat_runs import extract_runs

        runs: list[dict] = []
        for conv in self._repo.list_for_account(account.account_id, limit=500):
            if conv.project_id != project_id:
                continue
            runs.extend(extract_runs(conv, self._repo.list_messages(conv.id)))
        runs.sort(key=lambda r: r["created_at"], reverse=True)
        return runs

    def get_conversation(
        self,
        conversation_id: UUID,
        account: AuthenticatedAccount,
    ) -> Conversation:
        return self._require_conversation(conversation_id, account)

    def delete_conversation(
        self,
        conversation_id: UUID,
        account: AuthenticatedAccount,
    ) -> None:
        conversation = self._require_conversation(conversation_id, account)
        self._repo.delete(conversation.id)

    def rename_conversation(self, conversation_id: UUID, account: AuthenticatedAccount, title: str) -> Conversation:
        conversation = self._require_conversation(conversation_id, account)
        clean = " ".join((title or "").split())[:120]
        if not clean:
            raise ValueError("Title must not be empty")
        updated = self._repo.update_title(conversation.id, clean)
        return updated or conversation

    def list_messages(
        self,
        conversation_id: UUID,
        account: AuthenticatedAccount,
    ) -> list[ConversationMessage]:
        conversation = self._require_conversation(conversation_id, account)
        messages = self._repo.list_messages(conversation.id)
        return [message for message in messages if message.role != MessageRole.SYSTEM]

    def upload_attachment(
        self,
        conversation_id: UUID,
        account: AuthenticatedAccount,
        *,
        filename: str,
        content: bytes,
        content_type: str | None,
        project_id: UUID | None = None,
    ) -> MessageAttachment:
        conversation = self._require_conversation(conversation_id, account)
        resolved_project_id = conversation.project_id or project_id
        if resolved_project_id is None:
            raise ConversationForbiddenError(
                "Select or create a project before uploading engineering files."
            )
        self._project_access.require_project(resolved_project_id, account)
        if conversation.project_id is None:
            updated = self._repo.set_project(conversation.id, resolved_project_id)
            if updated is not None:
                conversation = updated

        record = self._file_ingestion.ingest_upload(
            resolved_project_id,
            filename=filename,
            content=content,
            content_type=content_type,
            created_by=account.account_id,
        )
        return _attachment_from_file(record)

    def assign_project(
        self,
        conversation_id: UUID,
        project_id: UUID,
        account: AuthenticatedAccount,
    ) -> Conversation:
        conversation = self._require_conversation(conversation_id, account)
        self._project_access.require_project(project_id, account)
        updated = self._repo.set_project(conversation.id, project_id)
        if updated is None:
            raise ConversationNotFoundError(conversation_id)
        return updated

    def send_message(
        self,
        conversation_id: UUID,
        account: AuthenticatedAccount,
        *,
        content: str,
        attachment_file_ids: list[UUID] | None = None,
        actor_id: str,
        mode: str = "auto",
        assistant: str | None = None,
        progress_sink: AgentRunProgressSink | None = None,
    ) -> tuple[ConversationMessage, ConversationMessage]:
        conversation = self._require_conversation(conversation_id, account)
        trimmed = content.strip()
        file_ids = attachment_file_ids or []

        attachments: list[MessageAttachment] = []
        if file_ids:
            if conversation.project_id is None:
                raise ConversationForbiddenError(
                    "A project is required when sending messages with file attachments."
                )
            self._project_access.require_project(conversation.project_id, account)
            for file_id in file_ids:
                record = self._file_registry.get_project_file(conversation.project_id, file_id)
                attachments.append(_attachment_from_file(record))

        if not trimmed and not attachments:
            raise ConversationForbiddenError("Enter a message or attach a file.")

        if not trimmed and attachments:
            trimmed = "Please review the attached file(s) and explain what they contain."

        attachment_context_bundle: ChatAttachmentContextBundle | None = None
        if file_ids and conversation.project_id is not None:
            attachment_context_bundle = self._attachment_context.build(
                conversation.project_id,
                file_ids,
                created_by=account.account_id,
            )

        user_message_metadata = (
            attachment_context_bundle.to_metadata() if attachment_context_bundle else None
        )
        user_message = self._repo.create_message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=trimmed,
            attachments=attachments,
            metadata=user_message_metadata,
        )
        self._repo.touch_updated_at(conversation.id)
        self._maybe_update_title(conversation, trimmed)
        emit_progress(
            progress_sink,
            EVENT_STARTED,
            {
                "conversation_id": str(conversation.id),
                "user_message": _message_payload(user_message),
                "selected_mode": mode or "auto",
            },
        )
        emit_progress(
            progress_sink,
            EVENT_STEP,
            {
                "conversation_id": str(conversation.id),
                "step_id": "understand",
                "name": "Understanding request",
                "status": "current",
            },
        )
        emit_progress(
            progress_sink,
            EVENT_STEP,
            {
                "conversation_id": str(conversation.id),
                "step_id": "understand",
                "name": "Understanding request",
                "status": "complete",
            },
        )

        assistant_content, assistant_metadata = self._generate_assistant_response(
            conversation=conversation,
            account=account,
            user_content=trimmed,
            attachments=attachments,
            attachment_context=attachment_context_bundle,
            actor_id=actor_id,
            mode=mode,
            assistant=assistant,
            progress_sink=progress_sink,
        )

        assistant_message = self._repo.create_message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=assistant_content,
            metadata=assistant_metadata,
        )
        self._repo.touch_updated_at(conversation.id)

        if conversation.project_id is not None:
            self._persist_conversation_memory(
                project_id=conversation.project_id,
                user_content=trimmed,
                assistant_content=assistant_content,
                account_id=account.account_id,
                conversation_id=conversation.id,
            )

        _emit_terminal_chat_event(
            progress_sink,
            conversation_id=conversation.id,
            user_message=user_message,
            assistant_message=assistant_message,
        )
        return user_message, assistant_message

    def iter_send_events(
        self,
        conversation_id: UUID,
        account: AuthenticatedAccount,
        *,
        content: str,
        attachment_file_ids: list[UUID] | None = None,
        actor_id: str,
        mode: str = "auto",
        assistant: str | None = None,
        cancelled: Event | None = None,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        events: Queue[tuple[str, dict[str, Any]] | None] = Queue()
        stop = cancelled or Event()

        class _QueueSink:
            def emit(self, event_type: str, payload: dict[str, Any]) -> None:
                if stop.is_set():
                    return
                events.put((event_type, payload))

        def worker() -> None:
            try:
                self.send_message(
                    conversation_id,
                    account,
                    content=content,
                    attachment_file_ids=attachment_file_ids,
                    actor_id=actor_id,
                    mode=mode,
                    assistant=assistant,
                    progress_sink=_QueueSink(),
                )
            except Exception as exc:
                from app.application.exceptions import ApplicationError

                if isinstance(exc, ApplicationError):
                    reason = exc.message
                else:
                    reason = "The agent could not complete this engineering step."
                emit_progress(
                    _QueueSink(),
                    EVENT_FAILED,
                    {
                        "conversation_id": str(conversation_id),
                        "error": safe_stream_error(title="Engineering workflow failed", reason=reason),
                    },
                )
            finally:
                events.put(None)

        thread = Thread(target=worker, daemon=True)
        thread.start()
        try:
            while True:
                item = events.get()
                if item is None:
                    break
                yield item
        finally:
            stop.set()
            thread.join(timeout=60)

    def append_execution_follow_up(
        self,
        execution: AgentExecutionRecord,
        *,
        reason: str = "approval_resolved",
    ) -> ConversationMessage | None:
        return append_execution_follow_up(execution, reason=reason)

    def _require_conversation(
        self,
        conversation_id: UUID,
        account: AuthenticatedAccount,
    ) -> Conversation:
        conversation = self._repo.get_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        if conversation.account_id != account.account_id:
            raise ConversationForbiddenError("You do not have access to this conversation.")
        if conversation.project_id is not None:
            try:
                self._project_access.require_project(conversation.project_id, account)
            except ProjectAuthorizationError as exc:
                raise ConversationForbiddenError(str(exc.message)) from exc
        return conversation

    def _maybe_update_title(self, conversation: Conversation, content: str) -> None:
        if conversation.title != "New conversation":
            return
        title = content.strip().splitlines()[0][:120]
        if title:
            self._repo.update_title(conversation.id, title)

    def _generate_assistant_response(
        self,
        *,
        conversation: Conversation,
        account: AuthenticatedAccount,
        user_content: str,
        attachments: list[MessageAttachment],
        attachment_context: ChatAttachmentContextBundle | None,
        actor_id: str,
        mode: str = "auto",
        assistant: str | None = None,
        progress_sink: AgentRunProgressSink | None = None,
    ) -> tuple[str, dict]:
        if not attachments:
            acted = self._maybe_chat_action(conversation, account, user_content)
            if acted is not None:
                acted[1]["selected_mode"] = mode or "auto"
                return acted
        agent_type = _assistant_chat.normalize_assistant(assistant)
        if agent_type is not None:
            reply = self._assistant_reply(conversation, account, agent_type, user_content, attachments)
            if reply is not None:
                reply[1]["selected_mode"] = mode or "auto"
                return reply
        cad = self._maybe_run_autocad(conversation, account, user_content, attachments)
        if cad is not None:
            cad[1]["selected_mode"] = mode or "auto"
            return cad
        history = self._repo.list_messages(conversation.id, limit=_MAX_HISTORY_MESSAGES)
        helper_reply = self._helper_reply(conversation, account, user_content, history, attachments, progress_sink)
        if helper_reply is not None:
            helper_reply[1]["selected_mode"] = mode or "auto"
            return helper_reply
        enriched_request = enrich_user_request_with_attachments(
            user_content,
            attachments,
            attachment_context,
        )

        from app.application import frame_optimizer as _fopt

        if _fopt.is_optimize_request(user_content):
            from app.application.billing import service as _billing

            try:
                _billing.require_feature(account.account_id, "optimization")
            except _billing.QuotaExceededError as exc:
                fa = any("\u0600" <= ch <= "\u06ff" for ch in user_content)
                msg = ("بهینه‌سازی قاب در پلن فعلی شما فعال نیست. برای استفاده، از صفحه Upgrades به پلن Pro یا بالاتر ارتقا دهید."
                       if fa else exc.message)
                return msg, {"mode": "rule_based", "intent": "frame_optimization", "quota_exceeded": exc.details}
        if conversation.project_id is not None:
            from app.application.agent_intent_routing import frame_context

            with frame_context(self._latest_frame_inputs(conversation, account) is not None):
                return self._run_project_orchestration(
                    conversation=conversation,
                    account=account,
                    user_request=enriched_request,
                    attachments=attachments,
                    attachment_context=attachment_context,
                    actor_id=actor_id,
                    mode=mode,
                    progress_sink=progress_sink,
                )

        content, metadata = self._run_general_chat(enriched_request, history, account=account, progress_sink=progress_sink,
                                                   conversation=conversation)
        metadata["selected_mode"] = mode or "auto"
        return content, metadata

    def _latest_frame_inputs(self, conversation, account) -> dict | None:
        from app.application.chat_runs import extract_runs

        runs = extract_runs(conversation, self._repo.list_messages(conversation.id))
        if conversation.project_id is not None:
            runs += self.list_project_chat_runs(account, conversation.project_id)
        runs.sort(key=lambda r: r["created_at"], reverse=True)
        return next((r["inputs"] for r in runs if r.get("kind") == "frame3d_analysis" and r.get("inputs")), None)

    @staticmethod
    def _plan_exports(account) -> Any:
        """The account plan's "exports" allowance (None when billing is not enforced)."""
        try:
            from app.application.billing import service as billing

            if not billing.enforcement_enabled() or not getattr(account, "account_id", None):
                return None
            return billing.current_plan(account.account_id)["limits"].get("exports")
        except Exception:  # noqa: BLE001 - never block a download answer on a billing lookup
            return None

    def _maybe_chat_action(self, conversation, account: AuthenticatedAccount, text: str) -> tuple[str, dict] | None:
        """Chat-first commands for what the UI can do besides engineering edits: downloads, projects, assistants, approvals."""
        from app.application import chat_actions as ca

        try:
            fa = ca.is_fa(text)
            # "how do I export to ETABS?" / «چطور دانلود کنم؟» is a question for the helper (explanation + offer), not a command.
            from app.platform_helper.intents import is_platform_explain_question

            if is_platform_explain_question(text):
                return None
            spec = ca.parse_download(text)
            if spec is not None:
                inputs = self._latest_frame_inputs(conversation, account)
                assumed: list[str] = []
                if inputs is None:
                    inputs, assumed = ca.default_frame_inputs(fa)
                if fa:
                    inputs = {**inputs, "lang": "fa"}
                spec, withheld = ca.apply_plan(spec, self._plan_exports(account), fa)
                return ca.downloads_reply(spec, inputs, fa=fa, assumed=assumed, withheld=withheld,
                                          project_id=str(conversation.project_id) if conversation.project_id else None)
            cmd = ca.parse_project_command(text)
            if cmd is not None:
                return self._run_project_command(conversation, account, cmd, fa)
            agent = ca.parse_assistant_switch(text)
            if agent is not None:
                title = _assistant_chat.assistant_title(agent, fa)
                starters = _assistant_chat.starters(agent, fa)
                body = (f"دستیار فعال شد: **{title}**. هر چه می‌خواهید همین‌جا بنویسید." if fa
                        else f"Switched to **{title}**. Just tell it what you need here in the chat.")
                return body, {"mode": "rule_based", "intent": "switch_assistant", "switch_assistant": agent, "starters": starters}
            appr = ca.parse_approval_command(text)
            if appr is not None:
                return ca.run_approval(appr, project_id=conversation.project_id, account_id=account.account_id, fa=fa)
        except Exception:  # noqa: BLE001 - a chat command must never break the conversation; fall through to the engines
            logger.exception("chat action failed")
        return None

    def _run_project_command(self, conversation, account: AuthenticatedAccount, cmd: dict, fa: bool) -> tuple[str, dict]:
        from app.application.service_factory import build_project_service

        projects = self._project_access.list_accessible_projects(account)
        meta: dict = {"mode": "rule_based", "intent": "projects"}
        if cmd["kind"] == "list":
            lines = ["پروژه‌های شما:" if fa else "Your projects:", ""] + [f"- {p.name}" for p in projects] if projects else []
            if not projects:
                lines = ["هنوز پروژه‌ای ندارید. بنویسید «یک پروژه جدید به نام … بساز»." if fa else "You have no projects yet. Say “create a new project called …”."]
            return "\n".join(lines), meta
        if cmd["kind"] == "open":
            q = cmd["name"].strip().lower()
            hit = next((p for p in projects if p.name.strip().lower() == q), None) or next(
                (p for p in projects if q in p.name.lower()), None)
            if hit is None:
                names = "، ".join(p.name for p in projects[:8]) or ("—" )
                return (f"پروژه‌ای با نام «{cmd['name']}» پیدا نشد. پروژه‌های شما: {names}" if fa else
                        f"No project matches “{cmd['name']}”. Your projects: {names}"), meta
            self._repo.set_project(conversation.id, hit.id)
            meta["project_switch"] = {"id": str(hit.id), "name": hit.name}
            return (f"پروژه «{hit.name}» باز شد؛ از این به بعد گفتگو در این پروژه انجام می‌شود." if fa else
                    f"Opened project “{hit.name}”. This chat now works inside it."), meta
        # create
        from app.application.billing import service as billing

        name = cmd["name"] or ("پروژه جدید" if fa else "New project")
        owned = sum(1 for p in projects if str(getattr(p, "owner_account_id", "")) == str(account.account_id))
        try:
            billing.require_count(account.account_id, "projects", owned)
        except billing.QuotaExceededError as exc:
            return (("سقف تعداد پروژه در پلن فعلی پر شده است؛ از صفحه Upgrades ارتقا دهید." if fa else exc.message),
                    {**meta, "quota_exceeded": exc.details})
        result = build_project_service().create_project(name=name, description=None, created_by=account.account_id,
                                                        owner_account_id=account.account_id)
        self._repo.set_project(conversation.id, result.project.id)
        meta["project_switch"] = {"id": str(result.project.id), "name": result.project.name}
        note = "" if cmd["name"] else (" (نام را ننوشته بودید، «پروژه جدید» گذاشتم؛ بعداً می‌توانید بگویید «نام پروژه را … کن».)" if fa else
                                      " (you gave no name, so I called it “New project”.)")
        return (f"پروژه «{name}» ساخته و باز شد.{note}" if fa else f"Created and opened project “{name}”.{note}"), meta

    def _helper_context(self, conversation, account: AuthenticatedAccount | None) -> dict[str, str]:
        """Live per-user facts for the assistant prompt: plan + limits, selected project, whether a model exists."""
        from app.application.platform_knowledge import user_context

        project_name: str | None = None
        has_model: bool | None = None
        try:
            if conversation is not None and conversation.project_id is not None and account is not None:
                project_name = next((p.name for p in self._project_access.list_accessible_projects(account)
                                     if str(p.id) == str(conversation.project_id)), "selected")
            if conversation is not None and account is not None:
                has_model = self._latest_frame_inputs(conversation, account) is not None
        except Exception:  # noqa: BLE001 - context is best effort
            logger.debug("helper context lookup failed", exc_info=True)
        return user_context(getattr(account, "account_id", None), project=project_name, has_model=has_model)

    def _helper_reply(self, conversation, account: AuthenticatedAccount, user_content: str, history,
                      attachments, progress_sink) -> tuple[str, dict] | None:
        """Platform helper: greetings, 'how do I...' questions, bug reports and issue status. Engineering stays with the engines."""
        if attachments:
            return None
        try:
            from app.application.platform_helper_factory import get_helper_service

            svc = get_helper_service()
            if not svc.classify(user_content).handled_by_helper:
                return None
            pairs = [("user" if m.role == MessageRole.USER else "assistant", m.content)
                     for m in history if m.role in (MessageRole.USER, MessageRole.ASSISTANT)]
            if pairs and pairs[-1] == ("user", user_content):
                pairs = pairs[:-1]
            reply = svc.handle(
                user_content, pairs, account_id=account.account_id,
                project_id=str(conversation.project_id or ""), conversation_id=str(conversation.id),
                context=self._helper_context(conversation, account),
                on_token=(lambda d: emit_progress(progress_sink, EVENT_TOKEN, {"delta": d})) if progress_sink else None)
            if reply is None:
                return None
            return reply.text, reply.to_metadata()
        except Exception:  # noqa: BLE001 - the helper must never break the chat
            logger.exception("platform helper failed")
            return None

    def _maybe_run_autocad(self, conversation, account: AuthenticatedAccount, user_content: str,
                           attachments: list[MessageAttachment]) -> tuple[str, dict] | None:
        """PDF/photo -> DXF and prompt -> drawing run right here in the chat (AutoCAD v1)."""
        from app.application.autocad.chat_intent import run_chat_autocad

        pid = conversation.project_id

        def _reader(file_id):
            return lambda: self._file_ingestion.get_file_content(pid, file_id)[1]

        def _save(filename: str, content: bytes) -> str | None:
            record = self._file_ingestion.ingest_upload(pid, filename=filename, content=content,
                                                        content_type="application/dxf", created_by=account.account_id)
            return str(record.id)

        from app.application.autocad import structural_set as _ss

        if not attachments and _ss.wants_structural_set(user_content):
            try:
                return self._run_structural_set(conversation, account, user_content, _save if pid else None)
            except Exception:  # noqa: BLE001
                logger.exception("structural drawing set failed")
        try:
            from app.application.architecture import service as arch

            pending = None
            for m in reversed(self._repo.list_messages(conversation.id, limit=6)):
                if m.role == MessageRole.ASSISTANT:
                    pending = (m.metadata or {}).get("arch_interview")
                    break
            if not attachments:
                def _save_any(filename: str, content: bytes, ctype: str) -> str | None:
                    record = self._file_ingestion.ingest_upload(pid, filename=filename, content=content,
                                                                content_type=ctype, created_by=account.account_id)
                    return str(record.id)

                res = arch.chat_turn(user_content, owner=str(account.account_id), project_id=str(pid) if pid else None,
                                     pending=pending, save_project_file=_save_any if pid else None)
                if res is not None:
                    return res
        except Exception:  # noqa: BLE001
            logger.exception("architecture chat failed")
        try:
            return run_chat_autocad(
                user_content, [(a.filename, _reader(a.file_id)) for a in attachments],
                owner=str(account.account_id), project_id=str(pid) if pid else None,
                save_project_file=_save if pid else None)
        except Exception:  # noqa: BLE001
            logger.exception("autocad chat failed")
            return None

    def _run_structural_set(self, conversation, account: AuthenticatedAccount, text: str, save) -> tuple[str, dict]:
        """«نقشه‌های اجرایی سازه را بده» -> S-sheet set from the latest 3D frame analysis in this chat / project."""
        from app.application.autocad import structural_set as ss
        from app.application.chat_runs import extract_runs

        fa = any("\u0600" <= ch <= "\u06ff" for ch in text)
        pid = conversation.project_id
        runs = extract_runs(conversation, self._repo.list_messages(conversation.id))
        if pid is not None:
            runs += self.list_project_chat_runs(account, pid)
        runs.sort(key=lambda r: r["created_at"], reverse=True)
        inputs = next((r["inputs"] for r in runs if r.get("kind") == "frame3d_analysis" and r.get("inputs")), None)
        if not inputs:
            msg = ("برای نقشه‌های اجرایی سازه ابتدا باید قاب سه‌بعدی تحلیل و طراحی شود. مثلاً بنویسید: «۳ دهانه ۵ متری در جهت x و ۲ دهانه ۴ متری در جهت y، ۴ طبقه با ارتفاع ۳.۲ متر»."
                   if fa else "To produce the structural drawings I first need a 3D frame analysis. For example: "
                   "\"3 bays of 5 m in x, 2 bays of 4 m in y, 4 storeys of 3.2 m\".")
            return msg, {"mode": "rule_based", "intent": "structural_drawings", "needs": "frame3d_analysis"}

        def _save3(name, data, ctype):
            return save(name, data) if save and ctype == "application/dxf" else (
                str(self._file_ingestion.ingest_upload(pid, filename=name, content=data, content_type=ctype,
                                                       created_by=account.account_id).id) if save else None)

        meta = ss.generate_and_store(inputs, owner=str(account.account_id), project_id=str(pid) if pid else None,
                                     save_project_file=_save3 if save else None)
        head = "**نقشه‌های اجرایی سازه (مبحث ۹)**" if fa else "**Structural drawing set (Mabhas 9)**"
        lines = [head, ""]
        for it in meta["sheets"]:
            lines.append(f"- {it['sheet_no']} — {it['title_fa'] if fa else it['title']} ({it['scale']})")
        for n in meta["notes"]:
            lines.append(f"- ⚠ {n}")
        lines.append("")
        lines.append("هر برگ یک فایل DXF جدا است و یک PDF ترکیبی هم ساخته شد؛ همه در صفحه CAD و فایل‌های پروژه هستند." if fa
                     else "Each sheet is its own DXF plus one combined PDF; all are on the CAD page and in project Files.")
        return "\n".join(lines), {"mode": "rule_based", "intent": "structural_drawings",
                                  "structural_set": {"id": meta["id"], "sheets": meta["sheets"], "pdf": meta["pdf"],
                                                     "pdf_file_id": meta["pdf_file_id"], "notes": meta["notes"]}}

    def _assistant_reply(self, conversation, account, agent_type: str, text: str, attachments):
        """Answer from the selected assistant's summariser, or None to let the regular engines run."""
        try:
            history = self._repo.list_messages(conversation.id, limit=_MAX_HISTORY_MESSAGES)
            prior = [m.content for m in reversed(history) if m.role == MessageRole.USER]
            if _assistant_chat.wants_engine(text, has_attachments=bool(attachments), prior_user_texts=prior):
                return None
            payload = _assistant_chat.latest_payload_from_messages(self._repo.list_messages(conversation.id))
            if payload is None and conversation.project_id is not None:
                payload = self._project_frame_payload(account, conversation.project_id)
            content, meta = _assistant_chat.assistant_reply(agent_type, text, payload)
            if payload is not None and agent_type in ("ANALYSIS_AGENT", "LOAD_ASSESSMENT_AGENT", "SEISMIC_AGENT",
                                                       "CONCRETE_DESIGN_AGENT", "VALIDATION_AGENT", "STRUCTURAL_MODELING_AGENT"):
                pass  # summaries are text only; the full result card stays on the run that produced it
            return content, meta
        except Exception:  # noqa: BLE001 - never block the chat on a summariser problem
            logger.exception("assistant summariser failed")
            return None

    def _project_frame_payload(self, account, project_id):
        """Rebuild the newest frame3d payload of this project from its stored run inputs (deterministic)."""
        from app.application.frame3d_chat_analysis import build_frame3d_payload, frame3d_spec, inputs_from_dict

        for run in self.list_project_chat_runs(account, project_id):
            if run.get("kind") == "frame3d_analysis" and isinstance(run.get("inputs"), dict):
                return build_frame3d_payload(frame3d_spec(inputs_from_dict(run["inputs"])))
        return None

    def _run_project_orchestration(
        self,
        *,
        conversation: Conversation,
        account: AuthenticatedAccount,
        user_request: str,
        attachments: list[MessageAttachment],
        attachment_context: ChatAttachmentContextBundle | None,
        actor_id: str,
        mode: str = "auto",
        progress_sink: AgentRunProgressSink | None = None,
    ) -> tuple[str, dict]:
        assert conversation.project_id is not None
        history = self._repo.list_messages(conversation.id, limit=_MAX_HISTORY_MESSAGES)
        resume_context = _find_resumable_workflow_context(history)
        from app.application import frame3d_followup as _fu

        prior_user_texts = [m.content for m in reversed(history) if m.role == MessageRole.USER]
        merged_request = _fu.merge_with_pending(user_request, prior_user_texts)
        if merged_request == user_request:
            # «پیش‌فرض‌ها را فرض کن» right after the optimization checklist -> run the default-frame optimization.
            from app.application import frame_optimizer as _fopt

            last_assistant = next((m.content for m in reversed(history) if m.role == MessageRole.ASSISTANT), None)
            merged_request = _fopt.merge_assume_with_checklist(user_request, prior_user_texts, last_assistant)
        resumed_optimization = merged_request != user_request and _fopt_is_optimize(merged_request)
        user_request = merged_request
        parameters: dict = {
            "conversation_id": str(conversation.id),
            "attachment_file_ids": [str(item.file_id) for item in attachments],
            "selected_mode": mode or "auto",
        }
        if resume_context is not None:
            parameters["resume_execution_id"] = resume_context["execution_id"]
        if attachment_context is not None:
            parameters["attachment_context"] = attachment_context.to_dict()
        hinted_type = chat_mode_to_agent_type(mode)
        if hinted_type is None and resumed_optimization:
            # keyword scoring would send e.g. «قاب … بهینه» to the Analysis agent, away from the pending optimization step
            hinted_type = EngineeringAgentType.OPTIMIZATION_AGENT
        record = self._agent_runtime.execute(
            AgentExecutionRequest(
                project_id=conversation.project_id,
                user_request=user_request,
                parameters=parameters,
                requested_by=account.account_id,
                agent_type=hinted_type,
            ),
            actor_id=actor_id,
            account_id=account.account_id,
            progress_sink=progress_sink,
        )
        assistant_content, assistant_metadata = _format_execution_response(record)
        assistant_metadata["selected_mode"] = mode or "auto"
        if resume_context is not None:
            assistant_metadata["resumed_from_execution_id"] = resume_context["execution_id"]
        if attachment_context is not None:
            assistant_metadata["attachment_context"] = attachment_context.to_dict()
            assistant_metadata["attachment_file_ids"] = attachment_context.file_ids
        self._maybe_persist_demo_memory(conversation, account, assistant_metadata)
        self._maybe_persist_frame3d_memory(conversation, account, assistant_metadata)
        self._maybe_persist_aci_beam_memory(conversation, account, assistant_metadata)
        self._maybe_create_run_approval(conversation, account, assistant_metadata)
        return assistant_content, assistant_metadata

    def _maybe_create_run_approval(self, conversation, account: AuthenticatedAccount, assistant_metadata: dict) -> None:
        """Every completed engineering run (any registered module kind) gets a pending approval item (revision 1)."""
        if conversation.project_id is None:
            return
        payload = assistant_metadata.get("engineering_results")
        if not isinstance(payload, dict):
            return
        try:
            from app.application import revision_workflow
            from app.application.service_factory import build_human_approval_service

            approval = revision_workflow.create_run_approval(
                build_human_approval_service(), conversation.project_id, account.account_id, payload,
                conversation_id=str(conversation.id))
        except Exception:  # noqa: BLE001 - the chat answer must not fail because of the approval item
            logger.exception("run approval creation failed")
            return
        if approval is not None:
            assistant_metadata["run_approval_id"] = str(approval.id)

    def _run_general_chat(
        self,
        user_content: str,
        history: list[ConversationMessage],
        *,
        account: AuthenticatedAccount | None = None,
        progress_sink: AgentRunProgressSink | None = None,
        conversation=None,
    ) -> tuple[str, dict]:
        messages = [
            AIMessage(
                role=AIMessageRole.SYSTEM,
                content=(
                    "You are a structural engineering assistant. Answer clearly and safely. "
                    "For project-specific engineering workflows, ask the user to select a project."
                ),
            ),
        ]
        for message in history[-_MAX_HISTORY_MESSAGES:]:
            if message.role == MessageRole.USER:
                messages.append(AIMessage(role=AIMessageRole.USER, content=message.content))
            elif message.role == MessageRole.ASSISTANT:
                messages.append(AIMessage(role=AIMessageRole.ASSISTANT, content=message.content))
        messages.append(AIMessage(role=AIMessageRole.USER, content=user_content))

        from app.application import general_beam_engine as gbe
        from app.application.frame3d_chat_analysis import build_frame3d_payload, frame3d_markdown, is_frame3d_request

        from app.application import frame_optimizer as fopt

        opt_text = fopt.pending_optimize_text(user_content, [m.content for m in reversed(history) if m.role == MessageRole.USER])
        if opt_text is not None:
            try:
                prior = fopt.prior_spec_from_texts(
                    [m.content for m in reversed(history) if m.role == MessageRole.USER]
                )
                res = fopt.build_optimization_from_chat(opt_text, prior, {"time_budget_s": 35})
                if res is not None:
                    lang = "fa" if any("\u0600" <= ch <= "\u06ff" for ch in user_content) else "en"
                    return fopt.optimization_markdown(res, lang), {"mode": "rule_based", "intent": "frame_optimization", "engineering_results": res}
                return fopt.missing_frame_checklist(opt_text), {"mode": "rule_based", "intent": "frame_optimization", "checklist": True}
            except Exception:  # noqa: BLE001
                logger.exception("frame optimizer failed")

        try:
            from app.application import frame3d_followup as _fu

            merged = _fu.merge_with_pending(user_content, [m.content for m in reversed(history) if m.role == MessageRole.USER])
            if is_frame3d_request(merged) or _fu.is_frame_followup(merged):
                payload = build_frame3d_payload(merged, fopt.prior_spec_from_texts(
                    [m.content for m in reversed(history) if m.role == MessageRole.USER]))
                if payload is not None:
                    return frame3d_markdown(payload), {"mode": "rule_based", "engineering_results": payload}
            beam = gbe.analyze_beam_prompt(user_content)
            if beam is not None:
                return beam["markdown"], {"mode": "rule_based", "engineering_results": beam["payload"]}
        except Exception:  # noqa: BLE001 - fall back to the chat model / help text
            logger.exception("rule-based chat engine failed")

        small_talk = gbe.small_talk_reply(user_content)
        if small_talk is not None:
            # Greetings / small talk: instant deterministic reply (works with no LLM, never invents numbers).
            return small_talk, {"mode": "small_talk", "provider": "none"}

        try:
            from app.application.platform_helper_factory import get_helper_service

            svc = get_helper_service()
            if svc.llm.configured or svc.faq_provider is not None:
                pairs = [("user" if m.role == MessageRole.USER else "assistant", m.content)
                         for m in history[-_MAX_HISTORY_MESSAGES:] if m.role in (MessageRole.USER, MessageRole.ASSISTANT)]
                if pairs and pairs[-1] == ("user", user_content):
                    pairs = pairs[:-1]
                reply = svc.converse(
                    user_content, pairs, intent="general_chat", context=self._helper_context(conversation, account),
                    on_token=(lambda d: emit_progress(progress_sink, EVENT_TOKEN, {"delta": d})) if progress_sink else None)
                if reply.provider != "stub" and reply.text.strip():
                    return reply.text, reply.to_metadata()
        except Exception:  # noqa: BLE001
            logger.exception("platform helper chat failed")
        try:
            response = self._ai_gateway.complete(
                AICompletionRequest(model=_CHAT_MODEL, messages=messages)
            )
        except Exception:  # noqa: BLE001
            logger.exception("chat model failed")
            return gbe.capabilities_message(user_content), {"mode": "capabilities", "provider": "none"}
        content = (response.content or "").strip()
        if "stub" in str(response.provider).lower() or content.startswith("{") or "task_acknowledged" in content:
            return gbe.capabilities_message(user_content), {"mode": "capabilities", "provider": str(response.provider)}
        return response.content, {"mode": "general_chat", "provider": response.provider}

    def _persist_conversation_memory(
        self,
        *,
        project_id: UUID,
        user_content: str,
        assistant_content: str,
        account_id: str,
        conversation_id: UUID,
    ) -> None:
        self._project_memory.create_memory(
            project_id,
            MemoryType.CONVERSATION,
            f"User: {user_content}\nAssistant: {assistant_content}",
            source_type="conversation",
            metadata={"conversation_id": str(conversation_id)},
            created_by=account_id,
        )

    def _maybe_persist_demo_memory(
        self,
        conversation,
        account: AuthenticatedAccount,
        assistant_metadata: dict,
    ) -> None:
        if conversation.project_id is None:
            return
        demo = assistant_metadata.get("engineering_results")
        if not isinstance(demo, dict) or demo.get("kind") != "demo_rc_beam":
            return
        inputs = demo.get("inputs") if isinstance(demo.get("inputs"), dict) else {}
        results = demo.get("results") if isinstance(demo.get("results"), dict) else {}
        content = (
            "Demo RC beam analysis assumptions: simply supported, "
            f"span {inputs.get('span_m')} m, "
            f"uniform load {inputs.get('uniform_load_kn_m')} kN/m, "
            f"fc={inputs.get('fc_mpa')} MPa, fy={inputs.get('fy_mpa')} MPa. "
            f"Mmax={results.get('max_moment_kn_m')} kN·m, "
            f"Vmax={results.get('max_shear_kn')} kN."
        )
        self._project_memory.create_memory(
            conversation.project_id,
            MemoryType.ASSUMPTION,
            content,
            source_type="demo_rc_beam",
            metadata={"kind": "demo_rc_beam", "conversation_id": str(conversation.id)},
            created_by=account.account_id,
        )

    def _maybe_persist_frame3d_memory(
        self,
        conversation,
        account: AuthenticatedAccount,
        assistant_metadata: dict,
    ) -> None:
        if conversation.project_id is None:
            return
        payload = assistant_metadata.get("engineering_results")
        if not isinstance(payload, dict) or payload.get("kind") != "frame3d_analysis":
            return
        if payload.get("status") != "completed":
            return
        self._project_memory.create_memory(
            conversation.project_id,
            MemoryType.ASSUMPTION,
            frame3d_memory_summary(payload),
            source_type="frame3d_analysis",
            metadata={
                "kind": "frame3d_analysis",
                "conversation_id": str(conversation.id),
                "inputs": payload.get("inputs"),
                "results": payload.get("results"),
            },
            created_by=account.account_id,
        )

    def _maybe_persist_aci_beam_memory(
        self,
        conversation,
        account: AuthenticatedAccount,
        assistant_metadata: dict,
    ) -> None:
        if conversation.project_id is None:
            return
        payload = assistant_metadata.get("engineering_results")
        if not isinstance(payload, dict) or payload.get("kind") != "aci_rc_beam":
            return
        if payload.get("status") not in {"PASS", "FAIL"}:
            return
        inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
        results = payload.get("results") if isinstance(payload.get("results"), dict) else {}
        content = (
            f"ACI 318 RC beam check ({payload.get('status')}): "
            f"b={inputs.get('width_mm')} mm, h={inputs.get('height_mm')} mm, "
            f"d={inputs.get('effective_depth_mm')} mm, As={inputs.get('as_mm2')} mm², "
            f"fc={inputs.get('fc_mpa')} MPa, fy={inputs.get('fy_mpa')} MPa. "
            f"φMn={results.get('phi_mn_kn_m')} kN·m, φVc={results.get('phi_vc_kn')} kN."
        )
        self._project_memory.create_memory(
            conversation.project_id,
            MemoryType.ASSUMPTION,
            content,
            source_type="aci_rc_beam",
            metadata={"kind": "aci_rc_beam", "conversation_id": str(conversation.id)},
            created_by=account.account_id,
        )


_RESUMABLE_TASK_STATUSES = frozenset(
    {
        EngineeringTaskStatus.WAITING_FOR_INPUT.value,
        EngineeringTaskStatus.PARTIALLY_COMPLETED.value,
        EngineeringTaskStatus.READY.value,
    }
)


def _fopt_is_optimize(text: str) -> bool:
    from app.application import frame_optimizer as _fopt

    return _fopt.is_optimize_request(text)


def _find_resumable_workflow_context(
    messages: list[ConversationMessage],
) -> dict[str, str] | None:
    for message in reversed(messages):
        if message.role != MessageRole.ASSISTANT:
            continue
        metadata = message.metadata or {}
        execution_id = metadata.get("execution_id")
        if not isinstance(execution_id, str) or not execution_id.strip():
            continue

        engineering_task = metadata.get("engineering_task")
        if not isinstance(engineering_task, dict):
            continue

        task_status = engineering_task.get("status")
        if task_status in {
            EngineeringTaskStatus.WAITING_FOR_APPROVAL.value,
            EngineeringTaskStatus.COMPLETED.value,
            EngineeringTaskStatus.FAILED.value,
        }:
            continue

        execution_status = metadata.get("execution_status")
        if execution_status in {
            AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL.value,
            "awaiting_approval",
        }:
            continue

        if task_status in _RESUMABLE_TASK_STATUSES or execution_status == AgentExecutionStatus.BLOCKED.value:
            return {
                "execution_id": execution_id,
                "task_id": str(engineering_task.get("id") or ""),
                "task_status": str(task_status or ""),
            }
    return None


def _attachment_from_file(record: ProjectFile) -> MessageAttachment:
    status = AttachmentStatus.READY
    if record.parsing_status in {ParsingStatus.PENDING, ParsingStatus.IN_PROGRESS}:
        status = AttachmentStatus.PROCESSING
    elif record.parsing_status == ParsingStatus.FAILED or record.extraction_status == ExtractionStatus.FAILED:
        status = AttachmentStatus.FAILED
    elif record.parsing_status == ParsingStatus.SKIPPED:
        status = AttachmentStatus.READY
    return MessageAttachment(
        file_id=record.id,
        filename=record.filename,
        file_type=record.file_type.value,
        content_type=record.content_type,
        status=status,
        parsing_status=record.parsing_status.value,
        extraction_status=record.extraction_status.value,
    )


def _message_payload(message: ConversationMessage) -> dict[str, Any]:
    return {
        "id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "role": message.role.value,
        "content": message.content,
        "attachments": [
            {
                "file_id": str(item.file_id),
                "filename": item.filename,
                "file_type": item.file_type,
                "content_type": item.content_type,
                "status": item.status.value,
                "parsing_status": item.parsing_status,
                "extraction_status": item.extraction_status,
            }
            for item in message.attachments
        ],
        "metadata": message.metadata or {},
        "created_at": message.created_at.isoformat(),
    }


def _emit_terminal_chat_event(
    sink: AgentRunProgressSink | None,
    *,
    conversation_id: UUID,
    user_message: ConversationMessage,
    assistant_message: ConversationMessage,
) -> None:
    metadata = assistant_message.metadata or {}
    payload = {
        "conversation_id": str(conversation_id),
        "run_id": metadata.get("execution_id"),
        "user_message": _message_payload(user_message),
        "assistant_message": _message_payload(assistant_message),
        "agent_run": metadata.get("agent_run"),
    }
    progress = metadata.get("progress")
    if metadata.get("requires_approval") or progress == "awaiting_approval":
        payload["approval_request_id"] = metadata.get("approval_request_id")
        emit_progress(sink, EVENT_APPROVAL_REQUIRED, payload)
        return
    if progress in {"failed", "rejected", "cancelled", "blocked"}:
        error = None
        agent_run = metadata.get("agent_run")
        if isinstance(agent_run, dict) and isinstance(agent_run.get("error"), dict):
            error = agent_run.get("error")
        payload["error"] = error or safe_stream_error(
            title="Engineering workflow failed",
            reason="The agent could not complete this engineering step.",
        )
        emit_progress(sink, EVENT_FAILED, payload)
        return
    emit_progress(sink, EVENT_COMPLETED, payload)


def _format_execution_response(record) -> tuple[str, dict]:
    view = build_agent_execution_user_view(record)
    sections: list[str] = []

    status_label = _execution_status_label(record.execution_status, view.progress)
    sections.append(f"**Status:** {status_label}")

    if view.summary:
        sections.append(f"### Request\n{view.summary}")

    if view.final_result:
        sections.append(f"### Result\n{view.final_result}")

    if record.agent_result and record.agent_result.recommendations:
        rec_lines = "\n".join(f"- {item}" for item in record.agent_result.recommendations[:5])
        sections.append(f"### Recommendations\n{rec_lines}")

    demo_results = _extract_engineering_results(record)
    if demo_results:
        markdown = None
        if record.agent_result and isinstance(record.agent_result.structured_output, dict):
            markdown = record.agent_result.structured_output.get("status_message")
        if isinstance(markdown, str) and markdown.strip():
            sections.append(markdown)
        else:
            sections.append("### Structural analysis (Demo)\nDeterministic simply-supported beam results are available.")

    _so = record.agent_result.structured_output if record.agent_result else None
    if isinstance(_so, dict) and _so.get("checklist") and isinstance(_so.get("status_message"), str):
        sections = [_so["status_message"]]  # prerequisites checklist replaces the generic "Completed" report

    if record.agent_result and record.agent_result.validation_information:
        warnings = record.agent_result.validation_information.get("warnings")
        if isinstance(warnings, list) and warnings:
            warn_lines = "\n".join(f"- {item}" for item in warnings[:5])
            sections.append(f"### Warnings\n{warn_lines}")

    actions = _build_workspace_actions(record)
    artifacts = _extract_artifacts(record)
    agent_run = build_agent_run_view(record)
    status_events = _build_status_events(record, view.progress, agent_run)
    selected_capability = _extract_selected_capability(record) or agent_run.get("selected_capability")

    metadata = {
        "mode": "agent_execution",
        "execution_id": str(record.id),
        "execution_status": record.execution_status.value,
        "progress": view.progress,
        "requires_approval": view.requires_approval,
        "approval_request_id": str(record.approval_request_id) if record.approval_request_id else None,
        "selected_capability": selected_capability,
        "actions": actions,
        "artifacts": artifacts,
        "status_events": status_events,
        "engineering_results": demo_results,
        "agent_run": agent_run,
    }
    engineering_task = None
    if isinstance(record.traceability_metadata, dict):
        engineering_task = record.traceability_metadata.get("engineering_task")
    if isinstance(engineering_task, dict):
        metadata["engineering_task"] = engineering_task
        _req = record.input_request.get("user_request") if isinstance(record.input_request, dict) else None
        workflow_section = _format_engineering_task_section(
            engineering_task, "fa" if _is_persian(str(_req or "")) else "en" if _req else None)
        if workflow_section:
            sections.insert(1, workflow_section)
    if isinstance(record.traceability_metadata, dict) and record.traceability_metadata.get("report_id"):
        metadata["report_id"] = str(record.traceability_metadata["report_id"])

    return "\n\n".join(sections), metadata


def _execution_status_label(status: AgentExecutionStatus, progress: str) -> str:
    mapping = {
        "queued": "Queued",
        "in_progress": "Processing",
        "awaiting_approval": "Requires human approval",
        "blocked": "Blocked — additional input required",
        "completed": "Completed",
        "failed": "Failed",
        "rejected": "Rejected",
        "cancelled": "Cancelled",
    }
    return mapping.get(progress, status.value.replace("_", " ").title())


def _conversation_id_from_execution(record: AgentExecutionRecord) -> UUID | None:
    parameters = record.input_request.get("parameters") if isinstance(record.input_request, dict) else None
    raw = None
    if isinstance(parameters, dict):
        raw = parameters.get("conversation_id")
    if not raw and isinstance(record.traceability_metadata, dict):
        engineering_task = record.traceability_metadata.get("engineering_task")
        if isinstance(engineering_task, dict):
            raw = engineering_task.get("conversation_id")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        return None


def append_execution_follow_up(
    execution: AgentExecutionRecord,
    *,
    reason: str = "approval_resolved",
) -> ConversationMessage | None:
    conversation_id = _conversation_id_from_execution(execution)
    if conversation_id is None:
        return None
    repo = PostgresConversationRepository()
    if repo.get_by_id(conversation_id) is None:
        return None
    content, metadata = _format_execution_response(execution)
    metadata = {**metadata, "follow_up_reason": reason}
    message = repo.create_message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=content,
        metadata=metadata,
    )
    repo.touch_updated_at(conversation_id)
    return message


def _build_workspace_actions(record) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    agent_type_raw = None
    if record.prompt_generation and isinstance(record.prompt_generation, dict):
        agent_type_raw = record.prompt_generation.get("selected_agent_type")
    if agent_type_raw is None and record.input_request:
        agent_type_raw = record.input_request.get("agent_type")

    if (
        record.approval_request_id is not None
        and record.project_id is not None
        and is_awaiting_human_approval(record.execution_status)
    ):
        actions.append(
            {
                "label": "Review approval",
                "href": (
                    f"/workspace/approvals?project={record.project_id}"
                    f"&review={record.approval_request_id}"
                ),
            }
        )

    if agent_type_raw:
        try:
            agent_type = EngineeringAgentType(str(agent_type_raw))
            href = _AGENT_WORKSPACE_LINKS.get(agent_type)
            if href:
                actions.append({"label": f"Open {agent_type.value.replace('_', ' ').title()}", "href": href})
        except ValueError:
            pass

    actions.append({"label": "View Assistants", "href": "/workspace/agents"})
    if record.project_id:
        actions.append({"label": "View Results", "href": "/workspace/results"})
        report_id = None
        if isinstance(record.traceability_metadata, dict):
            report_id = record.traceability_metadata.get("report_id")
        if report_id:
            actions.append(
                {
                    "label": "View Reports",
                    "href": f"/workspace/reports?project={record.project_id}",
                }
            )
            actions.append(
                {
                    "label": "View Memory",
                    "href": f"/workspace/memory?project={record.project_id}",
                }
            )
            actions.append(
                {
                    "label": "View Traceability",
                    "href": f"/workspace/traceability?project={record.project_id}",
                }
            )
    return actions


def _extract_selected_capability(record) -> str | None:
    if record.prompt_generation and isinstance(record.prompt_generation, dict):
        agent_type = record.prompt_generation.get("selected_agent_type")
        if isinstance(agent_type, str) and agent_type.strip():
            return agent_type.replace("_", " ").title()
    return None


def _build_status_events(record, progress: str, agent_run: dict | None = None) -> list[str]:
    events: list[str] = ["Building engineering context"]
    if progress in {"in_progress", "queued"}:
        events.append("Running engineering workflow")
    elif progress == "awaiting_approval":
        events.append("Awaiting human approval")
    elif progress == "completed":
        events.extend(["Running engineering workflow", "Validating results"])
    elif progress == "failed":
        events.append("Workflow failed")
    elif progress == "blocked":
        events.append("Additional input required")
    if isinstance(agent_run, dict):
        for step in agent_run.get("steps") or []:
            if not isinstance(step, dict):
                continue
            if step.get("state") in {"complete", "current", "error"} and step.get("label"):
                label = str(step["label"])
                if label not in events:
                    events.append(label)
    return events


_WF_FA_TITLES = {
    "Understand engineer goal": "درک هدف مهندسی",
    "Validate required inputs": "بررسی ورودی‌های لازم",
    "Execute specialist assistant work": "اجرای کار دستیار تخصصی",
    "Validate and record results": "اعتبارسنجی و ثبت نتایج",
    "Review attached or project files": "بررسی فایل‌های پیوست یا پروژه",
}
_WF_FA_STATUS = {
    "COMPLETED": "تکمیل شد",
    "PARTIALLY_COMPLETED": "نیمه‌کاره",
    "WAITING_FOR_INPUT": "در انتظار ورودی",
    "WAITING_FOR_APPROVAL": "در انتظار تأیید",
    "RUNNING": "در حال اجرا",
    "READY": "آماده",
    "FAILED": "ناموفق",
}
_WF_FA_MISSING = {"Structural model (required inputs)": "مدل سازه (ورودی‌های لازم)"}
_WF_FA_FIELDS = {
    "Design code": "آیین‌نامه طراحی", "Unit system": "سیستم واحدها", "Number of stories": "تعداد طبقات",
    "Plan dimensions": "ابعاد پلان", "Primary structural material": "مصالح اصلی سازه",
}
_WF_FA_SOURCE = {
    "PROJECT_CONFIGURED": "تنظیم پروژه", "USER_PROVIDED": "ورودی شما", "ENGINEER_ASSUMED": "فرض مهندس",
    "SOFTWARE_DEFAULT": "پیش‌فرض نرم‌افزار",
}
_WF_FA_UNITS = {"SI_METRIC": "SI (kN، m، MPa)", "US_CUSTOMARY": "آمریکایی (kip، ft، ksi)"}
_WF_EN_UNITS = {"SI_METRIC": "SI (kN, m, MPa)", "US_CUSTOMARY": "US customary (kip, ft, ksi)"}


def _is_persian(text: str | None) -> bool:
    t = (text or "").replace("\u061b", " ")
    return any("\u0600" <= ch <= "\u06ff" for ch in t)


def _format_engineering_task_section(engineering_task: dict, lang: str | None = None) -> str | None:
    """Honest step checklist: only EXECUTED steps are listed as completed; blocked / pending steps say why.

    ``lang`` is "fa"/"en" (the language of the user's message); defaults to the task's original request.
    """
    if not engineering_task:
        return None
    if lang not in ("fa", "en"):
        lang = "fa" if _is_persian(str(engineering_task.get("original_request") or "")) else "en"
    fa = lang == "fa"

    def title_of(raw: str) -> str:
        return _WF_FA_TITLES.get(raw, raw) if fa else raw

    lines = ["### گردش‌کار مهندسی" if fa else "### Engineering workflow"]
    status = engineering_task.get("status")
    if status:
        status_s = str(status)
        label = _WF_FA_STATUS.get(status_s, status_s) if fa else status_s.replace("_", " ").title()
        lines.append(f"{'وضعیت کار' if fa else 'Task status'}: {label}")

    objective = engineering_task.get("normalized_objective")
    if objective and (not fa or _is_persian(str(objective))):
        lines.append(f"{'هدف' if fa else 'Objective'}: {objective}")

    steps = engineering_task.get("steps") or []
    task_status = str(engineering_task.get("status"))
    completed: list[str] = []
    in_progress: list[str] = []
    pending: list[str] = []
    waiting_approval: list[str] = []
    blocked: list[str] = []
    unsupported: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        title = title_of(str(step.get("title", "Step")))
        step_status = str(step.get("status", "PLANNED")).upper()
        if step_status == "EXECUTED":
            completed.append(title)
        elif step_status in {"EXECUTABLE", "PLANNED"} and task_status == "RUNNING":
            in_progress.append(title)
        elif step_status == "EXECUTABLE" and task_status == "WAITING_FOR_APPROVAL":
            waiting_approval.append(title)
        elif step_status == "BLOCKED":
            reasons = [
                (_WF_FA_MISSING.get(str(m), str(m)) if fa else str(m)) for m in (step.get("missing_inputs") or [])
            ]
            if reasons:
                title = f"{title} — " + ("در انتظار: " if fa else "waiting for: ") + (("، " if fa else ", ").join(reasons))
            blocked.append(title)
        elif step_status == "UNSUPPORTED":
            unsupported.append(title)
        elif step_status == "EXECUTABLE":
            in_progress.append(title)
        elif step_status == "PLANNED":
            pending.append(title)

    def block(en_head: str, fa_head: str, items: list[str], limit: int) -> None:
        if items:
            lines.append(f"{fa_head if fa else en_head}:\n" + "\n".join(f"- {item}" for item in items[:limit]))

    block("Completed", "انجام‌شده", completed, 10)
    block("In progress", "در حال انجام", in_progress, 6)
    if waiting_approval or task_status == "WAITING_FOR_APPROVAL":
        approval_items = waiting_approval or (["کار برای تأیید انسانی متوقف شده است"] if fa else ["Workflow paused for human approval"])
        block("Waiting for approval", "در انتظار تأیید", approval_items, 6)
    block("Blocked", "مسدود", blocked, 8)
    block("Pending", "در انتظار اجرا", pending, 8)
    block("Unsupported", "پشتیبانی‌نشده", unsupported, 8)

    assumptions = engineering_task.get("assumptions") or []
    if assumptions:
        assumption_lines = []
        for assumption in assumptions[:8]:
            if not isinstance(assumption, dict):
                continue
            field_name = str(assumption.get("field_name", "Assumption"))
            value = assumption.get("value")
            source = str(assumption.get("source", "UNKNOWN"))
            if value:
                value = str(value)
                if field_name == "Unit system":
                    value = (_WF_FA_UNITS if fa else _WF_EN_UNITS).get(value, value)
                if fa:
                    field_name = _WF_FA_FIELDS.get(field_name, field_name)
                    source = _WF_FA_SOURCE.get(source, source)
                assumption_lines.append(f"- {field_name}: {value} ({source})")
        if assumption_lines:
            lines.append(("فرض‌ها" if fa else "Assumptions") + ":\n" + "\n".join(assumption_lines))

    missing = engineering_task.get("missing_required_inputs") or []
    if missing:
        missing_lines = "\n".join(
            f"- {(_WF_FA_MISSING.get(str(item), str(item)) if fa else item)}" for item in missing[:8]
        )
        lines.append(("ورودی‌های ناقص" if fa else "Missing inputs") + f":\n{missing_lines}")

    limitations = engineering_task.get("limitations") or []
    if limitations and not fa:
        limitation_lines = "\n".join(f"- {item}" for item in limitations[:5])
        lines.append(f"Limitations:\n{limitation_lines}")

    artifacts = engineering_task.get("artifacts") or []
    generated = [
        item for item in artifacts if isinstance(item, dict) and item.get("generation_status") == "generated"
    ]
    if generated:
        artifact_lines = "\n".join(
            f"- {item.get('artifact_type', 'artifact')}"
            + (f" ({item.get('filename')})" if item.get("filename") else "")
            for item in generated[:5]
        )
        lines.append(("خروجی‌ها" if fa else "Deliverables") + f":\n{artifact_lines}")

    if len(lines) <= 1:
        return None
    return "\n".join(lines)


def _extract_engineering_results(record) -> dict | None:
    if record.agent_result is None:
        return None
    output = record.agent_result.structured_output or {}
    demo = output.get("demo_rc_beam")
    if isinstance(demo, dict):
        return demo
    frame = output.get("frame3d_analysis")
    if isinstance(frame, dict):
        return frame
    opt = output.get("frame_optimization")
    if isinstance(opt, dict):
        return opt
    aci = output.get("aci_rc_beam")
    return aci if isinstance(aci, dict) else None


def _extract_artifacts(record) -> list[dict[str, str | None]]:
    artifacts: list[dict[str, str | None]] = []
    if not record.agent_result or not record.agent_result.generated_artifacts:
        return artifacts

    project_id = str(record.project_id)
    for index, raw in enumerate(record.agent_result.generated_artifacts[:10]):
        if not isinstance(raw, dict):
            continue
        artifact_type = str(raw.get("type") or raw.get("artifact_type") or "artifact")
        name = str(raw.get("name") or raw.get("filename") or f"{artifact_type.replace('_', ' ').title()} {index + 1}")
        description = raw.get("description")
        href = None
        file_id = raw.get("file_id")
        report_id = raw.get("report_id")
        if file_id:
            href = f"/api/v1/projects/{project_id}/files/{file_id}/content"
        elif report_id:
            href = "/workspace/reports"
        elif artifact_type == "engineering_report":
            href = "/workspace/reports"
        elif artifact_type in {"cad_drawing", "dxf", "dwg"}:
            href = "/workspace/cad"
        artifacts.append(
            {
                "id": str(raw.get("id") or file_id or report_id or f"{record.id}-{index}"),
                "name": name,
                "artifact_type": artifact_type,
                "description": str(description) if description else None,
                "href": href,
            }
        )
    return artifacts
