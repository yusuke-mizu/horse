import { mulberry32, parSeconds, timeFigure } from "./math";

const COURSES = ["京都", "阪神", "東京", "中山"];
const DISTANCES = [1200, 1400, 1600, 1800, 2000];
const CONDITIONS = ["良", "稍重", "重", "不良"];
const STYLES = ["逃げ", "先行", "差し", "追込"];
const PACE_JP = { slow: "スロー", normal: "平均", fast: "ハイ" } as const;

function pickPace(rng: () => number, front: number): keyof typeof PACE_JP {
  const fast = 0.18 + 0.35 * front;
  const slow = 0.22 + 0.25 * (1 - front);
  const normal = Math.max(0.15, 1 - fast - slow);
  const u = rng() * (slow + normal + fast);
  if (u < slow) return "slow";
  if (u < slow + normal) return "normal";
  return "fast";
}

function iso(start: Date, week: number): string {
  const d = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate() + week * 7));
  return d.toISOString().slice(0, 10);
}

export async function seedIfEmpty(db: D1Database): Promise<boolean> {
  const row = await db.prepare("SELECT COUNT(*) AS c FROM races").first<{ c: number }>();
  if (row && row.c > 0) return false;
  await seed(db);
  return true;
}

export async function seed(db: D1Database, seedNum = 42): Promise<void> {
  const rng = mulberry32(seedNum);
  const nHorses = 32;
  const nDays = 12;
  const racesPerDay = 2;
  const horses: {
    id: number;
    name: string;
    ability: number;
    style: string;
    pref: number;
    going: number;
  }[] = [];

  const horseStmts: D1PreparedStatement[] = [];
  for (let i = 0; i < nHorses; i++) {
    const id = i + 1;
    const name = `シンセティック${String(id).padStart(3, "0")}`;
    horses.push({
      id,
      name,
      ability: 100 + gauss(rng) * 3.2,
      style: STYLES[i % 4],
      pref: DISTANCES[i % DISTANCES.length],
      going: gauss(rng) * 0.12,
    });
    horseStmts.push(
      db.prepare("INSERT INTO horses (id, name, sex, birth_year) VALUES (?, ?, ?, ?)").bind(
        id,
        name,
        ["牡", "牝", "セ"][i % 3],
        2018 + (i % 5),
      ),
    );
  }
  await execBatches(db, horseStmts);

  const start = new Date(Date.UTC(2022, 0, 1));
  let raceId = 0;
  const raceStmts: D1PreparedStatement[] = [];
  const entryStmts: D1PreparedStatement[] = [];
  const perfStmts: D1PreparedStatement[] = [];
  const preAbility = new Map<number, number>();
  for (const h of horses) preAbility.set(h.id, 100);

  for (let day = 0; day < nDays; day++) {
    const date = iso(start, day);
    const course = COURSES[day % COURSES.length];
    for (let rn = 1; rn <= racesPerDay; rn++) {
      raceId += 1;
      const surface = rn % 2 ? "turf" : "dirt";
      const distance = DISTANCES[(day + rn) % DISTANCES.length];
      const going = rng() < 0.7 ? "良" : CONDITIONS[Math.floor(rng() * CONDITIONS.length)];
      const field = sample(horses, Math.min(12, horses.length), rng);
      const gates = shuffle(
        field.map((_, i) => i + 1),
        rng,
      );
      const front = field.filter((h) => h.style === "逃げ" || h.style === "先行").length / field.length;
      const pace = pickPace(rng, front);
      const ran: { h: (typeof horses)[0]; gate: number; t: number }[] = [];
      for (let i = 0; i < field.length; i++) {
        const h = field[i];
        const gate = gates[i];
        let t = parSeconds(distance) - (h.ability - 100) * 0.22 + gauss(rng) * 0.35;
        t += (0.14 * Math.abs(distance - h.pref)) / 400;
        if (going === "重" || going === "不良") t -= h.going;
        if (surface === "turf" && gate <= 4) t -= 0.05;
        if (pace === "slow" && (h.style === "逃げ" || h.style === "先行")) t -= 0.09;
        if (pace === "fast" && (h.style === "差し" || h.style === "追込")) t -= 0.08;
        if (pace === "fast" && h.style === "逃げ") t += 0.11;
        ran.push({ h, gate, t });
      }
      ran.sort((a, b) => a.t - b.t);
      const winner = ran[0].t;
      raceStmts.push(
        db
          .prepare(
            "INSERT INTO races (id, date, course, surface, distance, track_condition, race_name, race_number, winning_time, pace_label) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
          )
          .bind(
            raceId,
            date,
            course,
            surface,
            distance,
            going,
            `${course}${rn}R`,
            rn,
            Math.round(winner * 10) / 10,
            PACE_JP[pace],
          ),
      );
      const fieldMean =
        ran.reduce((s, x) => s + (preAbility.get(x.h.id) ?? 100), 0) / Math.max(ran.length, 1);
      for (let pos = 0; pos < ran.length; pos++) {
        const { h, gate, t } = ran[pos];
        const odds = Math.max(1.3, (1.5 + rng() * 38) * (0.4 + 0.08 * (pos + 1)));
        entryStmts.push(
          db
            .prepare(
              "INSERT INTO race_entries (race_id, horse_id, gate, weight, odds, popularity, running_style) VALUES (?, ?, ?, ?, ?, ?, ?)",
            )
            .bind(raceId, h.id, gate, 55 + (h.id % 5), Math.round(odds * 10) / 10, pos + 1, h.style),
        );
        const raw = timeFigure(t, parSeconds(distance), distance);
        const adj = raw + 0.45 * (fieldMean - 100);
        const prev = preAbility.get(h.id) ?? 100;
        const next = 0.78 * prev + 0.22 * adj;
        preAbility.set(h.id, next);
        perfStmts.push(
          db
            .prepare(
              `INSERT INTO horse_performances (
                horse_id, race_id, date, course, surface, distance, track_condition, gate, running_style, pace,
                finish_position, finish_time, last_3f, margin, raw_performance, adjusted_performance, estimated_ability
              ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            )
            .bind(
              h.id,
              raceId,
              date,
              course,
              surface,
              distance,
              going,
              gate,
              h.style,
              PACE_JP[pace],
              pos + 1,
              Math.round(t * 10) / 10,
              Math.round((33.5 + gauss(rng) * 0.6) * 10) / 10,
              Math.round((t - winner) * 50) / 10,
              round3(raw),
              round3(adj),
              round3(next),
            ),
        );
      }
    }
  }
  await execBatches(db, raceStmts);
  await execBatches(db, entryStmts);
  await execBatches(db, perfStmts);
}

function round3(n: number): number {
  return Math.round(n * 1000) / 1000;
}

function gauss(rng: () => number): number {
  const u = Math.max(rng(), 1e-9);
  const v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function sample<T>(arr: T[], k: number, rng: () => number): T[] {
  const copy = arr.slice();
  shuffle(copy, rng);
  return copy.slice(0, k);
}

function shuffle<T>(arr: T[], rng: () => number): T[] {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

async function execBatches(db: D1Database, stmts: D1PreparedStatement[]): Promise<void> {
  const size = 40;
  for (let i = 0; i < stmts.length; i += size) {
    await db.batch(stmts.slice(i, i + size));
  }
}
