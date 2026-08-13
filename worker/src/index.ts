/**
 * half-sheet-label shared state Worker.
 *
 * One Durable Object per printer name gives an atomic top/bottom counter shared
 * across every family Mac — no NAS, no mount. The client falls back to a local
 * file when this is unreachable (see state.py), so this is a convenience layer.
 *
 * Routes (all require `Authorization: Bearer <SHARED_SECRET>`):
 *   GET  /state/:printer          -> { next_half }
 *   PUT  /state/:printer          { next_half }        -> { next_half }
 *   POST /state/:printer/advance                        -> { next_half }   (atomic flip)
 */

export interface Env {
  HALF_COUNTER: DurableObjectNamespace;
  SHARED_SECRET: string;
}

const HALVES = ["top", "bottom"] as const;
type Half = (typeof HALVES)[number];
const other = (h: Half): Half => (h === "top" ? "bottom" : "top");
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const auth = request.headers.get("authorization") || "";
    if (!env.SHARED_SECRET || auth !== `Bearer ${env.SHARED_SECRET}`) {
      return json({ error: "unauthorized" }, 401);
    }
    const url = new URL(request.url);
    const parts = url.pathname.split("/").filter(Boolean); // ["state", printer, (advance?)]
    if (parts.length < 2 || parts[0] !== "state") {
      return json({ error: "not found" }, 404);
    }
    const printer = decodeURIComponent(parts[1]);
    const id = env.HALF_COUNTER.idFromName(printer);
    return env.HALF_COUNTER.get(id).fetch(request);
  },
};

export class HalfCounter {
  constructor(private state: DurableObjectState) {}

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const parts = url.pathname.split("/").filter(Boolean);
    const advance = parts[2] === "advance";

    // Serialize concurrent writes so two Macs can't grab the same half.
    return this.state.blockConcurrencyWhile(async () => {
      let cur = ((await this.state.storage.get<Half>("next_half")) as Half) || "top";

      if (request.method === "GET" && !advance) {
        return json({ next_half: cur });
      }
      if (request.method === "POST" && advance) {
        cur = other(cur);
        await this.state.storage.put("next_half", cur);
        return json({ next_half: cur });
      }
      if (request.method === "PUT" && !advance) {
        const body = (await request.json().catch(() => ({}))) as { next_half?: string };
        if (!body.next_half || !HALVES.includes(body.next_half as Half)) {
          return json({ error: "next_half must be 'top' or 'bottom'" }, 400);
        }
        cur = body.next_half as Half;
        await this.state.storage.put("next_half", cur);
        return json({ next_half: cur });
      }
      return json({ error: "method not allowed" }, 405);
    });
  }
}
