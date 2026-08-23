/** Очередь качества; совпадает с backend `TRACKER_QUEUE=STAZH`. */
export const STAZH_QUEUE = 'STAZH' as const;

export type IssueType =
    | 'bug'
    | 'sla_incident'
    | 'channel_conflict'
    | 'process_improvement'
    | 'development'
    | 'content'
    | 'security_privacy'
    | 'analytics_hypothesis'
    | 'partner_request';

export type Direction = 'ops' | 'product' | 'dev' | 'content' | 'security' | 'partners';
export type Source = 'cabinet' | 'max' | 'web' | 'amocrm' | 'staff' | 'analytics' | 'partner';
export type Channel = 'max' | 'web' | 'phone' | 'email' | 'unknown';
export type Repeatability = 'once' | 'recurring' | 'systemic';
export type Priority = 'critical' | 'high' | 'normal' | 'low';

export type SelectOption<T extends string> = {
    value: T;
    content: string;
};

export const ISSUE_TYPE_OPTIONS: SelectOption<IssueType>[] = [
    { value: 'bug', content: 'Ошибка' },
    { value: 'sla_incident', content: 'Инцидент SLA' },
    { value: 'channel_conflict', content: 'Конфликт каналов' },
    { value: 'process_improvement', content: 'Улучшение процесса' },
    { value: 'development', content: 'Разработка' },
    { value: 'content', content: 'Контент' },
    { value: 'security_privacy', content: 'Безопасность / ПДн' },
    { value: 'analytics_hypothesis', content: 'Аналитическая гипотеза' },
    { value: 'partner_request', content: 'Партнёрский запрос' },
];

export const DIRECTION_OPTIONS: SelectOption<Direction>[] = [
    { value: 'ops', content: 'Операции' },
    { value: 'product', content: 'Продукт' },
    { value: 'dev', content: 'Разработка' },
    { value: 'content', content: 'Контент' },
    { value: 'security', content: 'Безопасность' },
    { value: 'partners', content: 'Партнёры' },
];

export const SOURCE_OPTIONS: SelectOption<Source>[] = [
    { value: 'staff', content: 'Сотрудник' },
    { value: 'cabinet', content: 'Кабинет' },
    { value: 'max', content: 'MAX' },
    { value: 'web', content: 'Сайт' },
    { value: 'amocrm', content: 'amoCRM' },
    { value: 'analytics', content: 'Аналитика' },
    { value: 'partner', content: 'Партнёр' },
];

export const CHANNEL_OPTIONS: SelectOption<Channel>[] = [
    { value: 'unknown', content: 'Не определён' },
    { value: 'max', content: 'MAX' },
    { value: 'web', content: 'Web' },
    { value: 'phone', content: 'Телефон' },
    { value: 'email', content: 'E-mail' },
];

export const REPEAT_OPTIONS: SelectOption<Repeatability>[] = [
    { value: 'once', content: 'Единично' },
    { value: 'recurring', content: 'Повторяется' },
    { value: 'systemic', content: 'Системно' },
];

export const PRIORITY_OPTIONS: SelectOption<Priority>[] = [
    { value: 'critical', content: 'Критический' },
    { value: 'high', content: 'Высокий' },
    { value: 'normal', content: 'Обычный' },
    { value: 'low', content: 'Низкий' },
];

/** Маппинг приоритета UI → ключ приоритета Tracker API. */
export const PRIORITY_TO_TRACKER: Record<Priority, string> = {
    critical: 'critical',
    high: 'critical',
    normal: 'normal',
    low: 'minor',
};

export function labelForIssueType(type: IssueType): string {
    return ISSUE_TYPE_OPTIONS.find((o) => o.value === type)?.content ?? type;
}

export function tagsForIssue(params: {
    issueType: IssueType;
    direction: Direction;
    source: Source;
    channel: Channel;
    repeatability: Repeatability;
}): string[] {
    const tags = [
        `type:${params.issueType}`,
        `dir:${params.direction}`,
        `src:${params.source}`,
        'quality',
        'stazh',
    ];
    if (params.channel !== 'unknown') {
        tags.push(`ch:${params.channel}`);
    }
    if (params.repeatability !== 'once') {
        tags.push(`rep:${params.repeatability}`);
    }
    return tags;
}

export function defaultDirectionFor(type: IssueType): Direction {
    switch (type) {
        case 'bug':
        case 'development':
            return 'dev';
        case 'sla_incident':
        case 'channel_conflict':
            return 'ops';
        case 'content':
            return 'content';
        case 'security_privacy':
            return 'security';
        case 'partner_request':
            return 'partners';
        case 'analytics_hypothesis':
        case 'process_improvement':
        default:
            return 'product';
    }
}
