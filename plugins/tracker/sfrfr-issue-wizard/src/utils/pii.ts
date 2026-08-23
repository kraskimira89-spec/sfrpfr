export type PiiHit = {
    kind: 'phone' | 'email' | 'snils';
    label: string;
};

const EMAIL_RE = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
const PHONE_RE = /(?:\+?7|8)[\s\-()]?\d{3}[\s\-()]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}/g;
const SNILS_RE = /\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b/g;

export function detectPii(text: string): PiiHit[] {
    const hits: PiiHit[] = [];
    const seen = new Set<string>();

    const push = (kind: PiiHit['kind'], label: string) => {
        const key = `${kind}:${label}`;
        if (seen.has(key)) return;
        seen.add(key);
        hits.push({kind, label});
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

    return hits;
}

export function formatPiiWarning(hits: PiiHit[]): string {
    const kinds = [...new Set(hits.map((h) => h.label))].join(', ');
    return `В тексте похоже на ПДн (${kinds}). В Трекере ПДн не храним — CRM в amo. Всё равно создать задачу?`;
}
