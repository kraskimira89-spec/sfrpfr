"""База знаний: реестр кейсов и импорт диалогов."""

from sfrfr.ai.knowledge.batch_depersonalize import depersonalize_dir
from sfrfr.ai.knowledge.deepseek_export import import_deepseek_conversations
from sfrfr.ai.knowledge.feedback import apply_expert_feedback
from sfrfr.ai.knowledge.importer import import_dialog_to_case
from sfrfr.ai.knowledge.registry import KnowledgeCaseRegistry

__all__ = [
    "KnowledgeCaseRegistry",
    "apply_expert_feedback",
    "depersonalize_dir",
    "import_deepseek_conversations",
    "import_dialog_to_case",
]
