import {labelForIssueType, type IssueType} from '../types/stazh';

export type Prefill = {
    summary: string;
    description: string;
};

export function getPrefill(issueType: IssueType): Prefill {
    const label = labelForIssueType(issueType);
    return {
        summary: `[${label}] `,
        description: [
            '## Описание (обезличено)',
            '',
            '',
            '## Метаданные',
            '- case_ref: (только псевдоним из кабинета, не UUID)',
            '- funnel_stage:',
            '- age_bucket:',
            '- correlation_id:',
            '',
            '## Предложение',
            '- шаблон / FAQ / чек-лист / фикс:',
            '',
        ].join('\n'),
    };
}
