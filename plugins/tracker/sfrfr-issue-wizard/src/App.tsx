import { useCallback, useMemo, useState } from 'react';

import { Button, Select, Text, TextArea, TextInput, ThemeProvider } from '@gravity-ui/uikit';
import { trackerApi, uiApi, useTrackerPluginContext } from '@weavix/tracker-plugin-sdk-react';

import {
    FUNNEL_TAGS,
    PUB_TAGS,
    QUEUE_OPTIONS,
    type QueueKey,
    SFRFR_OPTIONAL_TAGS,
} from './types/queues';
import { detectPii, formatPiiWarning } from './utils/pii';
import { getPrefill } from './utils/prefills';

import './App.scss';

function tagChoices(queue: QueueKey): string[] {
    if (queue === 'PUB') return [...PUB_TAGS];
    if (queue === 'FUNNEL') return [...FUNNEL_TAGS];
    return [...SFRFR_OPTIONAL_TAGS];
}

function isTagRequired(queue: QueueKey): boolean {
    return queue === 'PUB' || queue === 'FUNNEL';
}

const App = () => {
    const { theme } = useTrackerPluginContext<'navigation'>();
    const [queue, setQueue] = useState<QueueKey>('SFRFR');
    const [tag, setTag] = useState<string | undefined>();
    const [summary, setSummary] = useState(() => getPrefill('SFRFR').summary);
    const [description, setDescription] = useState(() => getPrefill('SFRFR').description);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const queueHint = useMemo(
        () => QUEUE_OPTIONS.find((q) => q.key === queue)?.hint ?? '',
        [queue],
    );
    const tags = useMemo(() => tagChoices(queue), [queue]);
    const tagRequired = isTagRequired(queue);

    const onQueueChange = useCallback((next: string[]) => {
        const key = (next[0] as QueueKey) || 'SFRFR';
        const prefill = getPrefill(key);
        setQueue(key);
        setTag(undefined);
        setSummary(prefill.summary);
        setDescription(prefill.description);
        setError(null);
    }, []);

    const validate = useCallback((): string | null => {
        if (!summary.trim()) return 'Укажите название задачи';
        if (tagRequired && !tag) {
            return queue === 'PUB'
                ? 'Для PUB обязателен тег publish-*'
                : 'Для FUNNEL обязателен тег funnel-*';
        }
        return null;
    }, [queue, summary, tag, tagRequired]);

    const createIssue = useCallback(async () => {
        // По докам плагинов путь без /v2: trackerApi.v3.post['/issues']
        // (https://yandex.ru/support/tracker/ru/plugins/examples.md).
        // Вызов '/v2/issues' требует scope tracker:v2:write, которого нет в permissions.data.
        const bodyParams = {
            queue: { key: queue },
            summary: summary.trim(),
            ...(description.trim() ? { description: description.trim() } : {}),
            ...(tag ? { tags: [tag] } : {}),
        };

        type CreateIssueFn = (payload: {
            bodyParams: {
                queue: { key: string };
                summary: string;
                description?: string;
                tags?: string[];
            };
        }) => Promise<{ data: { key?: string } }>;

        const postIssues = (trackerApi.v3.post as unknown as Record<string, CreateIssueFn>)[
            '/issues'
        ];

        const { data: created } = await postIssues({ bodyParams });

        const key =
            typeof created === 'object' && created && 'key' in created
                ? String(created.key)
                : undefined;

        await uiApi.toaster.add({
            title: key ? `Создано: ${key}` : 'Задача создана',
            theme: 'success',
        });

        if (key) {
            await uiApi.navigate({ path: `/issues/${key}` });
        }
    }, [description, queue, summary, tag]);

    const onSubmit = useCallback(async () => {
        const validationError = validate();
        if (validationError) {
            setError(validationError);
            return;
        }
        setError(null);

        const piiHits = detectPii(`${summary}\n${description}`);
        if (piiHits.length > 0) {
            const { confirmed } = await uiApi.confirm.show({
                title: 'Возможные ПДн в тексте',
                message: formatPiiWarning(piiHits),
                textButtonApply: 'Всё равно создать',
                textButtonCancel: 'Отмена',
                theme: 'danger',
            });
            if (!confirmed) return;
        }

        setSubmitting(true);
        try {
            await createIssue();
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Не удалось создать задачу';
            setError(message);
            await uiApi.toaster.add({
                title: 'Ошибка создания',
                theme: 'danger',
                content: message,
            });
        } finally {
            setSubmitting(false);
        }
    }, [createIssue, description, summary, validate]);

    return (
        <ThemeProvider theme={theme}>
            <div className="wizard">
                <Text variant="header-1">Мастер задач SFRFR</Text>
                <p className="wizard__hint">
                    Очереди продукта / публикаций / воронки. ПДн и секреты в текст не вставлять.
                </p>

                <div className="wizard__field">
                    <Text variant="subheader-2">Очередь</Text>
                    <Select
                        value={[queue]}
                        onUpdate={onQueueChange}
                        options={QUEUE_OPTIONS.map((q) => ({
                            value: q.key,
                            content: q.title,
                        }))}
                        filterable={false}
                    />
                    <Text variant="caption-2" color="secondary">
                        {queueHint}
                    </Text>
                </div>

                <div className="wizard__field">
                    <Text variant="subheader-2">
                        Тег{tagRequired ? ' (обязательно)' : ' (опционально: ops / infra / agents)'}
                    </Text>
                    <Select
                        value={tag ? [tag] : []}
                        onUpdate={(values) =>
                            setTag(values[0] === '__none__' ? undefined : values[0])
                        }
                        options={[
                            ...(tagRequired ? [] : [{ value: '__none__', content: 'Без тега' }]),
                            ...tags.map((t) => ({ value: t, content: t })),
                        ]}
                        placeholder={tagRequired ? 'Выберите тег' : 'Без тега'}
                        filterable={false}
                    />
                </div>

                <div className="wizard__field">
                    <Text variant="subheader-2">Название</Text>
                    <TextInput value={summary} onUpdate={setSummary} size="l" />
                </div>

                <div className="wizard__field">
                    <Text variant="subheader-2">Описание</Text>
                    <TextArea value={description} onUpdate={setDescription} minRows={8} size="l" />
                </div>

                {error ? <p className="wizard__error">{error}</p> : null}

                <div className="wizard__actions">
                    <Button view="action" size="l" loading={submitting} onClick={onSubmit}>
                        Создать задачу
                    </Button>
                </div>
            </div>
        </ThemeProvider>
    );
};

export default App;
