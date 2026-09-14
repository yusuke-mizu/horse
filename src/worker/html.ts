import type { RacePrediction, RaceRow } from "./predict";

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
}

function pct(n: number): string {
  return (n * 100).toFixed(1);
}

const css = `
body { font-family: sans-serif; margin: 24px; background: #111; color: #eee; }
a { color: #9cf; }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid #333; padding: 8px; text-align: left; }
h1 { font-size: 20px; }
.meta { color: #aaa; margin-bottom: 16px; }
.card { border: 1px solid #333; padding: 16px; margin-bottom: 12px; background: #1a1a1a; }
.plus { color: #8d8; }
.minus { color: #d88; }
.weak { color: #aaa; font-size: 13px; }
.mark { color: #fc6; }
`;

export function renderIndex(races: RaceRow[], seeded: boolean): string {
  const rows = races
    .map(
      (r) => `<tr>
      <td><a href="/races/${r.id}">${r.id}</a></td>
      <td>${esc(r.date)}</td>
      <td>${esc(r.course)}</td>
      <td>${esc(r.race_name ?? "")}</td>
      <td>${esc(r.surface)}</td>
      <td>${r.distance}</td>
      <td>${esc(r.track_condition ?? "")}</td>
    </tr>`,
    )
    .join("");
  return `<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>競馬予想シミュレーション</title><style>${css}</style></head>
<body>
<h1>レース一覧</h1>
<p>基礎能力 → 今回発揮率 → 予測走破性能 → 順位確率。人気は能力の入力にしていません。Cloudflare Workers + D1。</p>
${seeded ? "<p>初回アクセスで合成データを投入しました。</p>" : ""}
<table>
<tr><th>ID</th><th>日付</th><th>場</th><th>R</th><th>馬場</th><th>距離</th><th>状態</th></tr>
${rows}
</table>
</body></html>`;
}

export function renderRace(pred: RacePrediction): string {
  const r = pred.race;
  const cards = pred.horses
    .map((h) => {
      const mkt = h.market_win_prob
        ? `${pct(h.market_win_prob)}%（オッズ ${h.odds}） 差 ${((h.edge ?? 0) * 100).toFixed(1)}pt`
        : "未取得";
      const ev = h.expected_value != null ? h.expected_value.toFixed(2) : "—";
      const plus = h.plus.length ? h.plus.map(esc).join("<br>") : "推定済みのプラス補正なし（固定加点は未使用）";
      const minus = h.minus.length ? h.minus.map(esc).join("<br>") : "推定済みのマイナス補正なし";
      const weak = [...h.method, ...h.weak].map(esc).join("<br>");
      return `<div class="card">
        <h2>${esc(h.name)} ${h.mark_ability ? '<span class="mark">◎能力</span>' : ""} ${h.mark_value ? '<span class="mark">★期待値</span>' : ""}</h2>
        <table>
          <tr><th>基礎能力</th><td>${h.base_ability.toFixed(1)} ± ${h.ability_sd.toFixed(1)}</td></tr>
          <tr><th>今回発揮率</th><td>${pct(h.expression_rate)}%（${pct(h.expression_low)}〜${pct(h.expression_high)}%）</td></tr>
          <tr><th>予測能力</th><td>${h.predicted_ability.toFixed(1)}（${h.ability_low.toFixed(1)}〜${h.ability_high.toFixed(1)}）</td></tr>
          <tr><th>予測タイム</th><td>${h.predicted_time}</td></tr>
          <tr><th>1着 / 2着 / 3着</th><td>${pct(h.p_win)}% / ${pct(h.p_second)}% / ${pct(h.p_third)}%</td></tr>
          <tr><th>複勝率 / 平均着順</th><td>${pct(h.p_show)}% / ${h.mean_rank.toFixed(2)}</td></tr>
          <tr><th>市場勝率</th><td>${mkt}</td></tr>
          <tr><th>期待値</th><td>${ev}</td></tr>
          <tr><th>信頼度</th><td>${esc(h.confidence)}（使用走数 ${h.n_starts}）</td></tr>
        </table>
        <p class="plus">プラス要因<br>${plus}</p>
        <p class="minus">マイナス要因<br>${minus}</p>
        <p class="weak">根拠<br>${weak}</p>
      </div>`;
    })
    .join("");
  return `<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>${esc(r.course)} ${esc(r.race_name ?? "")}</title><style>${css}</style></head>
<body>
<p><a href="/">← 一覧</a></p>
<h1>${esc(r.course)} ${esc(r.race_name ?? "")}</h1>
<div class="meta">
${esc(r.date)}　${esc(r.surface)} ${r.distance}m　${esc(r.track_condition ?? "")}<br>
展開予測　スロー ${Math.round(pred.pace.slow * 100)}%　平均 ${Math.round(pred.pace.normal * 100)}%　ハイ ${Math.round(pred.pace.fast * 100)}%
</div>
${cards}
</body></html>`;
}
