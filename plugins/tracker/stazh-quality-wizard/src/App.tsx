import { useCallback, useMemo, useState } from 'react';

import { Button, Select, Text, TextArea, TextInput, ThemeProvider } from '@gravity-ui/uikit';
import { trackerApi, uiApi, useTrackerPluginContext } from '@weavix/tracker-plugin-sdk-react';

import {
    CHANNEL_OPTIONS,
    type Channel,
    DIRECTION_OPTIONS,
    type Direction,
    ISSUE_TYPE_OPTIONS,
    type IssueType,
    PRIORITY_OPTIONS,
    PRIORITY_TO_TRACKER,
    type Priority,
    REPEAT_OPTIONS,
    type Repeatability,
    SOURCE_OPTIONS,
    STAZH_QUEUE,
    type Source,
    defaultDirectionFor,
    labelForIssueType,
    tagsForIssue,
} from './types/stazh';
import { detectPii, formatPiiBlock } from './utils/pii';
import { getPrefill } from './utils/prefills';

import './App.scss';

const App = () => {
    const { theme } = useTrackerPluginContext<'navigation'>();
    const [issueType, setIssueType] = useState<IssueType>('process_improvement');
    const [direction, setDirection] = useState<Direction>('product');
    const [source, setSource] = useState<Source>('staff');
    const [channel, setChannel] = useState<Channel>('unknown');
    const [repeatability, setRepeatability] = useState<Repeatability>('once');
    const [priority, setPriority] = useState<Priority>('normal');
    const [summary, setSummary] = useState(() => getPrefill('process_improvement').summary);
    const [description, setDescription] = useState(
        () => getPrefill('process_improvement').description,
    );
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const previewTags = useMemo(
        () => tagsForIssue({ issueType, direction, source, channel, repeatability }),
        [channel, direction, issueType, repeatability, source],
    );

    const onIssueTypeChange = useCallback((next: string[]) => {
        const type = (next[0] as IssueType) || 'process_improvement';
        const prefill = getPrefill(type);
        setIssueType(type);
        setDirection(defaultDirectionFor(type));
        setSummary(prefill.summary);
        setDescription(prefill.description);
        setError(null);
    }, []);

    const validate = useCallback((): string | null => {
        if (!summary.trim()) return 'Укажите название задачи';
        if (summary.trim().length < 8) return 'Слишком короткое название';
        const piiHits = detectPii(`${summary}\n${description}`);
        if (piiHits.length > 0) {
            return formatPiiBlock(piiHits);
        }
        return null;
    }, [description, summary]);

    const createIssue = useCallback(async () => {
        const tags = tagsForIssue({ issueType, direction, source, channel, repeatability });
        const bodyParams = {
            queue: { key: STAZH_QUEUE },
            summary: summary.trim(),
            priority: PRIORITY_TO_TRACKER[priority],
            ...(description.trim() ? { description: description.trim() } : {}),
            tags,
        };

        // Доки плагинов: путь `/issues`, не `/v2/issues` (иначе scope tracker:v2:write).
        type CreateIssueFn = (payload: {
            bodyParams: Record<string, unknown>;
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
            title: key ? `Создано: ${key}` : 'Задача создана в STAZH',
            theme: 'success',
        });

        if (key) {
            await uiApi.navigate({ path: `/issues/${key}` });
        }
    }, [channel, description, direction, issueType, priority, repeatability, source, summary]);

    const onSubmit = useCallback(async () => {
        const validationError = validate();
        if (validationError) {
            setError(validationError);
            return;
        }
        setError(null);
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
    }, [createIssue, validate]);

    return (
        <ThemeProvider theme={theme}>
            <div className="wizard">
                <Text variant="header-1">Качество STAZH</Text>
                <p className="wizard__hint">
                    Внутренние задачи качества и улучшений. Очередь фиксирована:{' '}
                    <strong>{STAZH_QUEUE}</strong>. Клиентские дела — только в admin.
                </p>

                <div className="wizard__warn" role="alert">
                    Не указывайте ФИО, телефон, e-mail, СНИЛС, номера документов, ссылки на личный
                    кабинет, файлы, текст переписки или содержание ИЛС. Для связи с делом — только
                    обезличенный <code>case_ref</code> из кабинета.
                </div>

                <div className="wizard__field">
                    <Text variant="subheader-2">Тип задачи</Text>
                    <Select
                        value={[issueType]}
                        onUpdate={onIssueTypeChange}
                        options={ISSUE_TYPE_OPTIONS}
                        filterable={false}
                    />
                </div>

                <div className="wizard__row">
                    <div className="wizard__field">
                        <Text variant="subheader-2">Приоритет</Text>
                        <Select
                            value={[priority]}
                            onUpdate={(v) => setPriority((v[0] as Priority) || 'normal')}
                            options={PRIORITY_OPTIONS}
                            filterable={false}
                        />
                    </div>
                    <div className="wizard__field">
                        <Text variant="subheader-2">Направление</Text>
                        <Select
                            value={[direction]}
                            onUpdate={(v) => setDirection((v[0] as Direction) || 'product')}
                            options={DIRECTION_OPTIONS}
                            filterable={false}
                        />
                    </div>
                </div>

                <div className="wizard__row">
                    <div className="wizard__field">
                        <Text variant="subheader-2">Источник</Text>
                        <Select
                            value={[source]}
                            onUpdate={(v) => setSource((v[0] as Source) || 'staff')}
                            options={SOURCE_OPTIONS}
                            filterable={false}
                        />
                    </div>
                    <div className="wizard__field">
                        <Text variant="subheader-2">Канал</Text>
                        <Select
                            value={[channel]}
                            onUpdate={(v) => setChannel((v[0] as Channel) || 'unknown')}
                            options={CHANNEL_OPTIONS}
                            filterable={false}
                        />
                    </div>
                </div>

                <div className="wizard__field">
                    <Text variant="subheader-2">Повторяемость</Text>
                    <Select
                        value={[repeatability]}
                        onUpdate={(v) => setRepeatability((v[0] as Repeatability) || 'once')}
                        options={REPEAT_OPTIONS}
                        filterable={false}
                    />
                </div>

                <div className="wizard__field">
                    <Text variant="subheader-2">Название</Text>
                    <TextInput value={summary} onUpdate={setSummary} size="l" />
                    <Text variant="caption-2" color="secondary">
                        Рекомендуемый вид: [{labelForIssueType(issueType)}] краткий вывод · case_ref
                    </Text>
                </div>

                <div className="wizard__field">
                    <Text variant="subheader-2">Описание (обезличено)</Text>
                    <TextArea value={description} onUpdate={setDescription} minRows={10} size="l" />
                </div>

                <div className="wizard__preview">
                    <Text variant="subheader-2">Теги в Tracker</Text>
                    <Text variant="code-1" className="wizard__tags">
                        {previewTags.join(', ')}
                    </Text>
                </div>

                {error ? <p className="wizard__error">{error}</p> : null}

                <div className="wizard__actions">
                    <Button view="action" size="l" loading={submitting} onClick={onSubmit}>
                        Создать в STAZH
                    </Button>
                </div>
            </div>
        </ThemeProvider>
    );
};

export default App;
