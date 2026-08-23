export type QueueKey = 'SFRFR' | 'PUB' | 'FUNNEL';

export type QueueOption = {
    key: QueueKey;
    title: string;
    hint: string;
};

export const QUEUE_OPTIONS: QueueOption[] = [
    {
        key: 'SFRFR',
        title: 'SFRFR',
        hint: 'Продукт, infra, agents, деплой, Wiki',
    },
    {
        key: 'PUB',
        title: 'PUB',
        hint: 'Публикации: MAX, VK, блог, SEO, Директ',
    },
    {
        key: 'FUNNEL',
        title: 'FUNNEL',
        hint: 'Ops воронки клиентов (без ПДн в тексте)',
    },
];

export const PUB_TAGS = [
    'publish-max',
    'publish-vk',
    'publish-blog',
    'publish-seo',
    'publish-direct',
] as const;

export const FUNNEL_TAGS = [
    'funnel-lead',
    'funnel-qualify',
    'funnel-diag',
    'funnel-docs',
    'funnel-submit',
    'funnel-result',
    'funnel-review',
    'funnel-loss',
] as const;

export const SFRFR_OPTIONAL_TAGS = ['ops', 'infra', 'agents'] as const;
