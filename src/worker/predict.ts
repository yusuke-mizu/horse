import { confidenceCap, gateBand, mulberry32, paceEn, predictedTime, tConfidence } from "./math";

export type RaceRow = {
  id: number;
  date: string;
  course: string;
  surface: string;
  distance: number;
  track_condition: string | null;
  race_name: string | null;
  race_number: number | null;
  pace_label: string | null;
};

type EntryRow = {
  horse_id: number;
  gate: number | null;
  odds: number | null;
  running_style: string | null;
  name: string;
};

type PerfRow = {
  horse_id: number;
  date: string;
  course: string;
  surface: string;
  distance: number;
  track_condition: string | null;
  gate: number | null;
  running_style: string | null;
  pace: string | null;
  adjusted_performance: number | null;
  estimated_ability: number | null;
};

export type HorseCard = {
  horse_id: number;
  name: string;
  base_ability: number;
  ability_sd: number;
  expression_rate: number;
  predicted_ability: number;
  predicted_time: number;
  p_win: number;
  p_second: number;
  p_third: number;
  p_show: number;
  mean_rank: number;
  ability_low: number;
  ability_high: number;
  expression_low: number;
  expression_high: number;
  confidence: string;
  n_starts: number;
  odds: number | null;
  market_win_prob: number | null;
  edge: number | null;
  expected_value: number | null;
  plus: string[];
  minus: string[];
  weak: string[];
  method: string[];
  mark_ability: boolean;
  mark_value: boolean;
};

export type RacePrediction = {
  race: RaceRow;
  pace: { slow: number; normal: number; fast: number };
  horses: HorseCard[];
};

export async function predictRace(db: D1Database, raceId: number, draws = 1500): Promise<RacePrediction | null> {
  const race = await db.prepare("SELECT * FROM races WHERE id = ?").bind(raceId).first<RaceRow>();
  if (!race) return null;
  const entries = await db
    .prepare(
      `SELECT e.horse_id, e.gate, e.odds, e.running_style, h.name
       FROM race_entries e JOIN horses h ON h.id = e.horse_id
       WHERE e.race_id = ?`,
    )
    .bind(raceId)
    .all<EntryRow>();
  if (!entries.results.length) return null;

  const past = await db
    .prepare(
      `SELECT horse_id, date, course, surface, distance, track_condition, gate, running_style, pace,
              adjusted_performance, estimated_ability
       FROM horse_performances WHERE date < ?`,
    )
    .bind(race.date)
    .all<PerfRow>();

  const byHorse = new Map<number, PerfRow[]>();
  for (const p of past.results) {
    const list = byHorse.get(p.horse_id) ?? [];
    list.push(p);
    byHorse.set(p.horse_id, list);
  }

  const pop = populationShifts(past.results);
  const front =
    entries.results.filter((e) => e.running_style === "逃げ" || e.running_style === "先行").length /
    Math.max(entries.results.length, 1);
  const pacePrior = paceFromFront(front);

  type Input = {
    entry: EntryRow;
    base: number;
    sd: number;
    n: number;
    expr: number;
    plus: string[];
    minus: string[];
    weak: string[];
    method: string[];
  };
  const inputs: Input[] = [];
  for (const entry of entries.results) {
    const hist = byHorse.get(entry.horse_id) ?? [];
    const ab = abilityAsOf(hist);
    const factors = horseFactors(hist, race, entry);
    const popF = applyPop(pop, race, entry);
    const merged = mergeGoing([...factors, ...popF]);
    const expr = clamp(merged.reduce((r, f) => r * f.mult, 1), 0.9, 1.1);
    const plus = merged.filter((f) => f.used && f.mult > 1).map((f) => f.text);
    const minus = merged.filter((f) => f.used && f.mult < 1).map((f) => f.text);
    const weak = merged.filter((f) => !f.used).map((f) => f.text);
    inputs.push({
      entry,
      base: ab.base,
      sd: ab.sd,
      n: ab.n,
      expr,
      plus,
      minus,
      weak,
      method: [
        `${entry.name} の基礎能力 ${ab.base.toFixed(1)} は出走日より前の ${ab.n} 走の補正パフォーマンス。縮小率 ${ab.shrink.toFixed(2)}。`,
        `今回発揮率 ${(expr * 100).toFixed(1)}%。条件補正は当該走より前の残差から推定。固定加点は未使用。`,
      ],
    });
  }

  const sim = monteCarlo(inputs, pacePrior, pop.stylePace, draws);
  const horses: HorseCard[] = inputs.map((inp) => {
    const hid = inp.entry.horse_id;
    const predAb = inp.base * inp.expr;
    const odds = inp.entry.odds;
    const mkt = odds && odds > 1 ? 1 / odds : null;
    const pWin = sim.pWin.get(hid) ?? 0;
    return {
      horse_id: hid,
      name: inp.entry.name,
      base_ability: round1(inp.base),
      ability_sd: round1(inp.sd),
      expression_rate: inp.expr,
      predicted_ability: round1(predAb),
      predicted_time: Math.round(predictedTime(predAb, race.distance) * 100) / 100,
      p_win: pWin,
      p_second: sim.p2.get(hid) ?? 0,
      p_third: sim.p3.get(hid) ?? 0,
      p_show: sim.show.get(hid) ?? 0,
      mean_rank: sim.rank.get(hid) ?? 0,
      ability_low: round1((inp.base - 1.28 * inp.sd) * (inp.expr - 0.02)),
      ability_high: round1((inp.base + 1.28 * inp.sd) * (inp.expr + 0.02)),
      expression_low: Math.max(0.85, inp.expr - 0.03),
      expression_high: Math.min(1.08, inp.expr + 0.03),
      confidence: inp.n >= 8 && inp.sd <= 2.2 ? "高" : inp.n >= 4 ? "中" : "低",
      n_starts: inp.n,
      odds,
      market_win_prob: mkt,
      edge: mkt == null ? null : pWin - mkt,
      expected_value: odds && odds > 1 ? pWin * odds : null,
      plus: inp.plus,
      minus: inp.minus,
      weak: inp.weak,
      method: inp.method,
      mark_ability: false,
      mark_value: false,
    };
  });
  horses.sort((a, b) => b.p_win - a.p_win);
  const bestA = horses.reduce((a, b) => (a.predicted_ability >= b.predicted_ability ? a : b));
  const valued = horses.filter((h) => h.expected_value != null);
  const bestV = valued.length ? valued.reduce((a, b) => ((a.expected_value ?? 0) >= (b.expected_value ?? 0) ? a : b)) : null;
  for (const h of horses) {
    h.mark_ability = h.horse_id === bestA.horse_id;
    h.mark_value = bestV != null && h.horse_id === bestV.horse_id;
  }
  const total = sim.pace.slow + sim.pace.normal + sim.pace.fast || 1;
  return {
    race,
    pace: {
      slow: sim.pace.slow / total,
      normal: sim.pace.normal / total,
      fast: sim.pace.fast / total,
    },
    horses,
  };
}

function abilityAsOf(hist: PerfRow[]): { base: number; sd: number; n: number; shrink: number } {
  const xs = hist
    .filter((p) => p.adjusted_performance != null)
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((p) => p.adjusted_performance as number);
  const k = 4;
  if (!xs.length) return { base: 100, sd: 3.5, n: 0, shrink: 1 };
  let w = 1;
  let wsum = 0;
  let xsum = 0;
  for (let i = xs.length - 1; i >= 0; i--) {
    xsum += w * xs[i];
    wsum += w;
    w *= 0.85;
  }
  const mean = xsum / wsum;
  const n = xs.length;
  const shrink = k / (n + k);
  const base = (1 - shrink) * mean + shrink * 100;
  let sd = 2.8;
  if (xs.length >= 2) {
    const m = xs.reduce((s, x) => s + x, 0) / xs.length;
    sd = Math.sqrt(xs.reduce((s, x) => s + (x - m) ** 2, 0) / (xs.length - 1));
  }
  sd = Math.max(0.8, sd) * Math.sqrt(1 + shrink);
  return { base: round3(base), sd: round3(sd), n, shrink: round3(shrink) };
}

type Fac = { name: string; mult: number; used: boolean; text: string };

function horseFactors(hist: PerfRow[], race: RaceRow, entry: EntryRow): Fac[] {
  const scored = hist.filter((p) => p.adjusted_performance != null);
  return [
    distanceCurve(scored, race.distance),
    matchMean(scored, "馬場", (p) => p.track_condition === race.track_condition, race.track_condition ?? "不明"),
    matchMean(scored, "コース", (p) => p.course === race.course, race.course),
  ];
}

function distanceCurve(past: PerfRow[], target: number): Fac {
  const pairs = past.map((p) => [p.distance, p.adjusted_performance as number] as const);
  if (!pairs.length) {
    return { name: "horse_distance", mult: 1, used: false, text: "距離適性: 当該走以前の走なし。補正なし。" };
  }
  const overall = pairs.reduce((s, [, y]) => s + y, 0) / pairs.length;
  let wsum = 0;
  let xsum = 0;
  for (const [d, y] of pairs) {
    const w = Math.exp(-(((d - target) / 250) ** 2));
    wsum += w;
    xsum += w * y;
  }
  const kernel = wsum > 0 ? xsum / wsum : overall;
  const effect = (kernel - overall) / 100;
  const n = pairs.length;
  const used = wsum >= 2.5 && n >= 4;
  const conf = tConfidence(kernel - overall, 2.5, n);
  const strength = used ? Math.min(1, n / 12) * Math.max(conf, 0.15) : 0;
  const delta = effect * strength;
  return {
    name: "horse_distance",
    mult: 1 + delta,
    used: used && Math.abs(delta) > 1e-6,
    text: `距離適性: 今回${target}mのカーネル平均 ${kernel.toFixed(1)}、自己平均 ${overall.toFixed(1)}、サンプル ${n}。${used ? "" : "サンプル不足のため補正なし。"}`,
  };
}

function matchMean(past: PerfRow[], label: string, pred: (p: PerfRow) => boolean, key: string): Fac {
  const all = past.map((p) => p.adjusted_performance as number);
  if (!all.length) return { name: label, mult: 1, used: false, text: `${label}適性: データなし。` };
  const matched = past.filter(pred).map((p) => p.adjusted_performance as number);
  const overall = all.reduce((s, x) => s + x, 0) / all.length;
  if (!matched.length) {
    return { name: label, mult: 1, used: false, text: `${label}適性: ${key} での過去走なし。補正なし。` };
  }
  const m = matched.reduce((s, x) => s + x, 0) / matched.length;
  const effect = (m - overall) / 100;
  const n = matched.length;
  const used = n >= 4;
  const conf = tConfidence(m - overall, 2.5, n);
  const delta = used ? effect * Math.min(1, n / 12) * Math.max(conf, 0.15) : 0;
  return {
    name: label,
    mult: 1 + delta,
    used: used && Math.abs(delta) > 1e-6,
    text: `${label}適性: ${key} 平均 ${m.toFixed(1)} vs 自己平均 ${overall.toFixed(1)}、サンプル ${n}。${used ? "" : "サンプル不足のため補正なし。"}`,
  };
}

type Pop = {
  going: Map<string, { effect: number; n: number; conf: number }>;
  gate: Map<string, { effect: number; n: number; conf: number }>;
  stylePace: Map<string, number>;
};

function populationShifts(rows: PerfRow[]): Pop {
  const goingVals = new Map<string, number[]>();
  const gateVals = new Map<string, number[]>();
  const spVals = new Map<string, number[]>();
  const pre = new Map<number, number>();
  const ordered = rows.slice().sort((a, b) => a.date.localeCompare(b.date));
  for (const p of ordered) {
    const prev = pre.get(p.horse_id) ?? 100;
    const adj = p.adjusted_performance ?? 100;
    const residual = adj - prev;
    if (p.track_condition) push(goingVals, `${p.surface}|${p.track_condition}`, residual);
    const band = gateBand(p.gate);
    if (band) {
      push(gateVals, `${p.course}|${p.surface}|${band}`, residual);
      push(gateVals, `${p.surface}|${band}`, residual);
      push(gateVals, band, residual);
    }
    const pace = paceEn(p.pace);
    if (p.running_style && pace) push(spVals, `${p.running_style}|${pace}`, residual);
    if (p.estimated_ability != null) pre.set(p.horse_id, p.estimated_ability);
  }
  return {
    going: summarize(goingVals),
    gate: summarize(gateVals),
    stylePace: styleShifts(spVals),
  };
}

function push(map: Map<string, number[]>, k: string, v: number): void {
  const arr = map.get(k) ?? [];
  arr.push(v);
  map.set(k, arr);
}

function summarize(map: Map<string, number[]>): Map<string, { effect: number; n: number; conf: number }> {
  const out = new Map<string, { effect: number; n: number; conf: number }>();
  for (const [k, vals] of map) {
    const n = vals.length;
    const mean = vals.reduce((s, x) => s + x, 0) / n;
    const sd =
      n > 1 ? Math.sqrt(vals.reduce((s, x) => s + (x - mean) ** 2, 0) / (n - 1)) : 0;
    out.set(k, { effect: mean / 100, n, conf: tConfidence(mean, sd, n) });
  }
  return out;
}

function styleShifts(map: Map<string, number[]>): Map<string, number> {
  const out = new Map<string, number>();
  for (const [k, vals] of map) {
    const n = vals.length;
    const mean = vals.reduce((s, x) => s + x, 0) / n;
    const sd = n > 1 ? Math.sqrt(vals.reduce((s, x) => s + (x - mean) ** 2, 0) / (n - 1)) : 0;
    const conf = tConfidence(mean, sd, n);
    const cap = confidenceCap(n, conf);
    out.set(k, (mean / 100) * 100 * cap * 0.5);
  }
  return out;
}

function applyPop(pop: Pop, race: RaceRow, entry: EntryRow): Fac[] {
  const out: Fac[] = [];
  const gKey = `${race.surface}|${race.track_condition ?? ""}`;
  const g = pop.going.get(gKey);
  if (g) out.push(fromPop("going", g, `母集団馬場 ${race.surface}/${race.track_condition}`));
  const band = gateBand(entry.gate);
  if (band) {
    const keys = [`${race.course}|${race.surface}|${band}`, `${race.surface}|${band}`, band];
    for (const k of keys) {
      const ge = pop.gate.get(k);
      if (ge) {
        out.push(fromPop("gate_band", ge, `枠帯=${band}`));
        break;
      }
    }
  }
  return out;
}

function fromPop(name: string, g: { effect: number; n: number; conf: number }, label: string): Fac {
  const cap = confidenceCap(g.n, g.conf);
  const delta = g.effect * cap * 0.5;
  const used = Math.abs(delta) > 1e-6;
  return {
    name,
    mult: 1 + delta,
    used,
    text: `${name} ${label}: 効果量 ${g.effect >= 0 ? "+" : ""}${g.effect.toFixed(4)}, サンプル ${g.n}, 信頼度 ${g.conf.toFixed(2)}。${used ? "" : "信頼度またはサンプル不足のため補正ほぼなし。"}`,
  };
}

function mergeGoing(factors: Fac[]): Fac[] {
  if (factors.some((f) => f.name === "馬場" && f.used)) return factors.filter((f) => f.name !== "going");
  return factors;
}

function paceFromFront(front: number): { slow: number; normal: number; fast: number } {
  const fast = 0.18 + 0.35 * front;
  const slow = 0.22 + 0.25 * (1 - front);
  const normal = Math.max(0.15, 1 - fast - slow);
  const t = slow + normal + fast;
  return { slow: slow / t, normal: normal / t, fast: fast / t };
}

function monteCarlo(
  inputs: { entry: EntryRow; base: number; sd: number; expr: number }[],
  prior: { slow: number; normal: number; fast: number },
  stylePace: Map<string, number>,
  draws: number,
): {
  pWin: Map<number, number>;
  p2: Map<number, number>;
  p3: Map<number, number>;
  show: Map<number, number>;
  rank: Map<number, number>;
  pace: { slow: number; normal: number; fast: number };
} {
  const ids = inputs.map((i) => i.entry.horse_id);
  const win = new Map(ids.map((id) => [id, 0]));
  const p2 = new Map(ids.map((id) => [id, 0]));
  const p3 = new Map(ids.map((id) => [id, 0]));
  const rankSum = new Map(ids.map((id) => [id, 0]));
  const pace = { slow: 0, normal: 0, fast: 0 };
  const rng = mulberry32(7);
  for (let d = 0; d < draws; d++) {
    const u = rng();
    let label: "slow" | "normal" | "fast" = "normal";
    if (u < prior.slow) label = "slow";
    else if (u < prior.slow + prior.normal) label = "normal";
    else label = "fast";
    pace[label] += 1;
    const samples = inputs.map((inp) => {
      const expr = gauss(rng, inp.expr, 0.012);
      const ability = gauss(rng, inp.base, inp.sd);
      const noise = gauss(rng, 0, 1.4);
      const style = inp.entry.running_style ?? "";
      const shift = stylePace.get(`${style}|${label}`) ?? 0;
      return { id: inp.entry.horse_id, perf: ability * expr + noise + shift };
    });
    samples.sort((a, b) => b.perf - a.perf);
    samples.forEach((s, idx) => {
      rankSum.set(s.id, (rankSum.get(s.id) ?? 0) + idx + 1);
      if (idx === 0) win.set(s.id, (win.get(s.id) ?? 0) + 1);
      if (idx === 1) p2.set(s.id, (p2.get(s.id) ?? 0) + 1);
      if (idx === 2) p3.set(s.id, (p3.get(s.id) ?? 0) + 1);
    });
  }
  const n = draws;
  return {
    pWin: mapDiv(win, n),
    p2: mapDiv(p2, n),
    p3: mapDiv(p3, n),
    show: new Map(ids.map((id) => [id, ((win.get(id) ?? 0) + (p2.get(id) ?? 0) + (p3.get(id) ?? 0)) / n])),
    rank: mapDiv(rankSum, n),
    pace,
  };
}

function mapDiv(m: Map<number, number>, n: number): Map<number, number> {
  return new Map([...m.entries()].map(([k, v]) => [k, v / n]));
}

function gauss(rng: () => number, mu: number, sd: number): number {
  const u = Math.max(rng(), 1e-9);
  const v = rng();
  return mu + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

function round3(n: number): number {
  return Math.round(n * 1000) / 1000;
}
