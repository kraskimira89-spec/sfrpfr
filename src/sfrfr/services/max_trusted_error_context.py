"""Адаптер доверенного контекста ошибки для MAX E05/F04.

Production-default не подтверждает ошибку сам и не подставляет успех.
Тесты подставляют контролируемый адаптер. Не передавать LLM/клиенту право
создавать TrustedOpResult.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sfrfr.services.max_sfrfr110_bridge import TrustedOpResult

# Тексты по ТЗ интеграционного среза (не свободная генерация).
F04_UNCERTAINTY_TEMPLATE = (
    "В предыдущем результате подтверждена ошибка в {error_description}. "
    "Пока не установлено, повлияла ли она на {impact_area}. "
    "Я не буду сообщать, что исправление завершено."
)

ERROR_NOT_CONFIRMED_TEMPLATE = (
    "Данных пока недостаточно, чтобы подтвердить ошибку или её исправление. "
    "Не буду выдавать предположение за установленный результат."
)


@dataclass(frozen=True)
class TrustedErrorContext:
    """Факты только из системного контура; привязка к делу и версии."""

    case_id: str
    operation_id: str
    error_confirmed: bool
    error_description: str | None = None
    unknown_impact_area: str | None = None
    limit_op: TrustedOpResult | None = None
    result_version: str | None = None
    authorized_for_case_id: str | None = None

    def belongs_to(self, case_id: str) -> bool:
        auth = self.authorized_for_case_id or self.case_id
        return str(auth) == str(case_id) and str(self.case_id) == str(case_id)

    def version_is_current(self, *, current_version: str | None) -> bool:
        if self.result_version is None or current_version is None:
            return True
        return str(self.result_version) == str(current_version)


class TrustedErrorContextPort(Protocol):
    def load_for_case(
        self,
        case_id: str,
        *,
        current_result_version: str | None = None,
    ) -> TrustedErrorContext | None:
        """None = нет активного доверенного контекста (не выдумывать успех)."""
        ...


class NullTrustedErrorContextAdapter:
    """Production-default: явная неопределённость источника, без синтетики."""

    def load_for_case(
        self,
        case_id: str,
        *,
        current_result_version: str | None = None,
    ) -> TrustedErrorContext | None:
        _ = case_id, current_result_version
        return None


class InMemoryTrustedErrorContextAdapter:
    """Только для тестов / контролируемой подстановки в staging-тестах."""

    def __init__(self) -> None:
        self._by_case: dict[str, TrustedErrorContext] = {}

    def put(self, ctx: TrustedErrorContext) -> None:
        self._by_case[str(ctx.case_id)] = ctx

    def clear(self) -> None:
        self._by_case.clear()

    def load_for_case(
        self,
        case_id: str,
        *,
        current_result_version: str | None = None,
    ) -> TrustedErrorContext | None:
        ctx = self._by_case.get(str(case_id))
        if ctx is None:
            return None
        if not ctx.belongs_to(case_id):
            return None
        if not ctx.version_is_current(current_version=current_result_version):
            return None
        # Чужой limit_op отсекаем на уровне контекста
        if ctx.limit_op is not None and str(ctx.limit_op.case_id) != str(case_id):
            return TrustedErrorContext(
                case_id=ctx.case_id,
                operation_id=ctx.operation_id,
                error_confirmed=ctx.error_confirmed,
                error_description=ctx.error_description,
                unknown_impact_area=ctx.unknown_impact_area,
                limit_op=None,
                result_version=ctx.result_version,
                authorized_for_case_id=ctx.authorized_for_case_id,
            )
        return ctx


_default_adapter: TrustedErrorContextPort = NullTrustedErrorContextAdapter()


def get_trusted_error_context_adapter() -> TrustedErrorContextPort:
    return _default_adapter


def set_trusted_error_context_adapter_for_tests(
    adapter: TrustedErrorContextPort | None,
) -> None:
    """Только тесты. Не вызывать из production handler."""
    global _default_adapter
    _default_adapter = adapter or NullTrustedErrorContextAdapter()
