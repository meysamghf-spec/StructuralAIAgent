"""Reusable platform helper: free-LLM chat assistant that knows the platform, plus bug self-reporting.

Generic on purpose (no imports from the host application) so it can be ported to other products
(e.g. TrafficLens) by supplying: a knowledge file, an issue store and a few hooks. See docs/PLATFORM_HELPER.md.
"""

from app.platform_helper.config import HelperSettings, load_settings  # noqa: F401
from app.platform_helper.issues import IssueReport, IssueStore, InMemoryIssueStore, IssueNotifier  # noqa: F401
from app.platform_helper.llm import LLMClient, LLMError, ProviderConfig  # noqa: F401
from app.platform_helper.service import HelperReply, HelperService  # noqa: F401
