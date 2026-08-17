"""Shared runtime context: the live TradingRuntime + Scheduler singletons.

Held here so API routes, the telegram bot, and startup can all reach the
same running instances without import cycles.
"""

RUNTIME: dict = {
    'runtime': None,
    'scheduler': None,
    'telegram': None,
}
