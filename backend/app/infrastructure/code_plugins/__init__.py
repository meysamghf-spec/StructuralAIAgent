"""CodeEngine plugin registry."""

from app.infrastructure.code_plugins.us_default_plugins import build_us_default_plugins

__all__ = ["build_default_plugin_registry"]


def build_default_plugin_registry() -> dict[str, object]:
    plugins = build_us_default_plugins()
    return {plugin.plugin_id: plugin for plugin in plugins}
