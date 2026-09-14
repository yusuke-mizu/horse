import { predictRace, type RaceRow } from "./predict";
import { renderIndex, renderRace } from "./html";
import { seedIfEmpty } from "./seed";

export default {
  async fetch(request, env): Promise<Response> {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/" && request.method === "GET") {
        const seeded = await seedIfEmpty(env.DB);
        const races = await env.DB.prepare(
          "SELECT id, date, course, surface, distance, track_condition, race_name, race_number, pace_label FROM races ORDER BY date DESC, race_number ASC LIMIT 80",
        ).all<RaceRow>();
        return html(renderIndex(races.results, seeded));
      }

      const raceMatch = url.pathname.match(/^\/races\/(\d+)$/);
      if (raceMatch && request.method === "GET") {
        await seedIfEmpty(env.DB);
        const pred = await predictRace(env.DB, Number(raceMatch[1]));
        if (!pred) return new Response("not found", { status: 404 });
        return html(renderRace(pred));
      }

      const apiMatch = url.pathname.match(/^\/api\/races\/(\d+)$/);
      if (apiMatch && request.method === "GET") {
        await seedIfEmpty(env.DB);
        const pred = await predictRace(env.DB, Number(apiMatch[1]));
        if (!pred) return json({ error: "not found" }, 404);
        return json(pred);
      }

      return new Response("not found", { status: 404 });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return json({ error: message }, 500);
    }
  },
} satisfies ExportedHandler<Env>;

function html(body: string): Response {
  return new Response(body, {
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
