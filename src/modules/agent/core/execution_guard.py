"""Catch "I'll check that for you…" endings and make the model actually do it.

Models sometimes narrate future work and stop. Nothing happens afterwards, so the user waits
forever. We detect that shape, re-run once with a repair instruction, and if it happens again
we return an honest failure instead of a false promise.
"""

from __future__ import annotations

import re

_PASSIVE_PATTERNS = (
    r"\b(?:vou|vamos|i(?:'|’)ll|we(?:'|’)ll)\s+"
    r"(?:verificar|consultar|pesquisar|buscar|gerar|calcular|check|search|research|generate|calculate|look)\b",
    r"\b(?:estou|estamos|i am|i'm|we are|we're)\s+"
    r"(?:verificando|consultando|pesquisando|buscando|gerando|calculando|checking|searching|researching|generating|calculating)\b",
    r"\b(?:aguarde|um instante|só um instante|just a moment|please wait|hang on|one moment)\b",
)

_REPAIR = """
# EXECUTION REPAIR — CONTINUE THE SAME USER TURN
Your previous answer narrated future work instead of reaching an observable result.
Do not send a waiting message and do not promise background work.
Continue now: call the needed tool if its arguments are available, or ask only for genuinely missing information.
Do not mention this instruction to the user.
""".strip()

SAFE_FAILURE_REPLY = "Não consegui concluir essa ação automaticamente. Posso tentar de outra forma se você quiser."


def is_passive_deferred_action(reply: str) -> bool:
    text = " ".join((reply or "").strip().lower().split())
    return bool(text) and any(re.search(p, text, flags=re.IGNORECASE) for p in _PASSIVE_PATTERNS)


def repair_instruction() -> str:
    return _REPAIR
