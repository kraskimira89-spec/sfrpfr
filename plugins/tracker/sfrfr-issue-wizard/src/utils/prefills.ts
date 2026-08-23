import type {QueueKey} from '../types/queues';

export type Prefill = {
    summary: string;
    description: string;
};

const PREFILLS: Record<QueueKey, Prefill> = {
    STAZH: {
        summary: '[Качество] ',
        description: [
            '## Тип проблемы',
            '',
            '## Обезличенное описание',
            '',
            '## Метаданные',
            '- case_ref: (если из кабинета — не UUID)',
            '- channel / funnel_stage:',
            '',
            '## Ограничения',
            '- Без ФИО, телефонов, email, СНИЛС, файлов, текста ИЛС, ссылок в кабинет',
            '',
        ].join('\n'),
    },
    SFRFR: {
        summary: '[SFRFR] ',
        description: [
            '## Контекст',
            '',
            '## Шаги / критерии',
            '',
            '## Ограничения',
            '- Без секретов и ПДн в описании',
            '',
        ].join('\n'),
    },
    PUB: {
        summary: '[PUB] ',
        description: [
            '## Канал',
            '',
            '## Черновик / ссылка',
            '',
            '## CTA / UTM',
            '',
            '## Критерий готовности',
            '',
        ].join('\n'),
    },
    FUNNEL: {
        summary: '[FUNNEL] ',
        description: [
            '## Этап воронки',
            '',
            '## Что сделать (без ПДн)',
            '',
            '## Связь с amo (только id сделки, без контактов)',
            '',
        ].join('\n'),
    },
};

export function getPrefill(queue: QueueKey): Prefill {
    return PREFILLS[queue];
}
