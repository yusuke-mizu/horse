export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a += 0x6d2b79f5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function parSeconds(distance: number): number {
  return distance / 16.4;
}

export function timeFigure(finishTime: number, par: number, distance: number): number {
  const per600 = 600 / Math.max(distance, 1);
  return 100 + (par - finishTime) * 2 * per600 * 5;
}

export function predictedTime(ability: number, distance: number): number {
  const par = parSeconds(distance);
  const per600 = 600 / Math.max(distance, 1);
  return par - (ability - 100) / Math.max(2 * per600 * 5, 1e-6);
}

export function gateBand(gate: number | null): "inner" | "mid" | "outer" | null {
  if (gate == null) return null;
  if (gate <= 4) return "inner";
  if (gate <= 8) return "mid";
  return "outer";
}

export function paceEn(label: string | null): "slow" | "normal" | "fast" | null {
  if (!label) return null;
  if (label === "スロー" || label === "slow") return "slow";
  if (label === "ハイ" || label === "fast") return "fast";
  if (label === "平均" || label === "normal") return "normal";
  return null;
}

export function confidenceCap(n: number, confidence: number): number {
  if (n < 30) return 0;
  if (n < 150) return Math.min(confidence, 0.35) * (n / 150);
  return Math.min(confidence, 1);
}

export function tConfidence(mean: number, sd: number, n: number): number {
  if (n < 3 || sd <= 1e-9) return 0;
  const se = sd / Math.sqrt(n);
  const t = Math.abs(mean) / se;
  return 1 - Math.exp(-0.5 * Math.min(t, 8) ** 2);
}
