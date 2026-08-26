/**
 * Компилятор VisualMatrix → промпты Midjourney / GPT Image (DALL·E).
 * Не вызывает API генерации изображений.
 */

export type VisualMatrix = {
  topic: string;
  audience: string;
  problem: string;
  emotionBefore: string;
  desiredState: string;
  coreMessage: string;
  metaphor: string;
  action: string;
  subject: string;
  visualStyle: string;
  mood: string;
  brandPalette: string;
  composition: string;
  textSafeArea: string;
  aspectRatio: "16:9" | "4:3" | "1:1" | "9:16";
  prohibitions: string[];
};

export type CompiledPrompts = {
  midjourneyPrompt: string;
  midjourneyParameters: string;
  dallePrompt: string;
  negativePrompt: string;
  altText: string;
};

const aspectToMidjourney = {
  "16:9": "--ar 16:9",
  "4:3": "--ar 4:3",
  "1:1": "--ar 1:1",
  "9:16": "--ar 9:16",
} as const;

export function compileVisualPrompts(matrix: VisualMatrix): CompiledPrompts {
  const negativePrompt = [
    "readable text",
    "letters",
    "numbers",
    "personal data",
    "passport",
    "SNILS",
    "official seals",
    "government emblems",
    "logos",
    "banknotes",
    "money",
    "medical symbols",
    "hospital setting",
    "fear",
    "panic",
    "dramatic suffering",
    "helpless elderly person",
    ...matrix.prohibitions,
  ].join(", ");

  const midjourneyPrompt = [
    matrix.visualStyle,
    matrix.subject,
    matrix.action,
    `visual metaphor: ${matrix.metaphor}`,
    `mood: ${matrix.mood}, ${matrix.desiredState}`,
    matrix.brandPalette,
    matrix.composition,
    `clear empty ${matrix.textSafeArea} for external headline`,
    "clean editorial composition",
    "high visual clarity",
    "no text in image",
  ].join(", ");

  const midjourneyParameters = [
    aspectToMidjourney[matrix.aspectRatio],
    "--stylize 120",
    "--chaos 6",
    `--no ${negativePrompt}`,
  ].join(" ");

  const dallePrompt = [
    `Create a ${matrix.visualStyle} for a Russian informational post.`,
    `Topic: ${matrix.topic}.`,
    `Audience: ${matrix.audience}.`,
    `Core message: ${matrix.coreMessage}.`,
    `Show: ${matrix.subject}.`,
    `Action: ${matrix.action}.`,
    `Use the visual metaphor: ${matrix.metaphor}.`,
    `Emotional transition: from ${matrix.emotionBefore} to ${matrix.desiredState}.`,
    `Mood: ${matrix.mood}.`,
    `Color direction: ${matrix.brandPalette}.`,
    `Composition: ${matrix.composition}.`,
    `Leave the ${matrix.textSafeArea} intentionally simple and empty for a title added later.`,
    "No written text or letters inside the image.",
    "No identifiable personal documents, passport, SNILS, faces with distress, logos, seals, government symbols, money, medical symbols, or promises of pension increases.",
    "Clean, respectful, high-contrast editorial image.",
  ].join(" ");

  const altText = `${matrix.coreMessage}. ${matrix.action}.`.slice(0, 180);

  return {
    midjourneyPrompt,
    midjourneyParameters,
    dallePrompt,
    negativePrompt,
    altText,
  };
}
