export type PiiHit = {
    kind: 'phone' | 'email' | 'snils' | 'cabinet_url' | 'uuid';
    label: string;
};

const EMAIL_RE = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
const PHONE_RE = /(?:\+?7|8)[\s()-]?\d{3}[\s()-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}/g;
const SNILS_RE = /\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b/g;
const UUID_RE = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi;
const CABINET_URL_RE = /https?:\/\/(?:cabinet|admin)\.proverkastaza\.ru[^\s]*/gi;

export function detectPii(text: string): PiiHit[] {
    const hits: PiiHit[] = [];
    const seen = new Set<string>();

    const push = (kind: PiiHit['kind'], label: string) => {
        const key = `${kind}:${label}`;
        if (seen.has(key)) return;
        seen.add(key);
        hits.push({ kind, label });
    };

    if ((text.match(EMAIL_RE) ?? []).length > 0) {
        push('email', 'email');
    }
    if ((text.match(PHONE_RE) ?? []).length > 0) {
        push('phone', 'телефон');
    }
    for (const snilsMatch of text.match(SNILS_RE) ?? []) {
        const digits = snilsMatch.replace(/\D/g, '');
        if (digits.length === 11) {
            push('snils', 'СНИЛС');
        }
    }
    if ((text.match(UUID_RE) ?? []).length > 0) {
        push('uuid', 'UUID дела');
    }
    if ((text.match(CABINET_URL_RE) ?? []).length > 0) {
        push('cabinet_url', 'ссылка cabinet/admin');
    }

    return hits;
}

export function formatPiiBlock(hits: PiiHit[]): string {
    const kinds = [...new Set(hits.map((h) => h.label))].join(', ');
    return (
        `В тексте обнаружены запрещённые данные (${kinds}). ` +
        `В STAZH нельзя передавать ФИО, телефон, e-mail, СНИЛС, UUID дела, ` +
        `ссылки на кабинет, переписку и содержимое ИЛС. Уберите их и повторите.`
    );
}
