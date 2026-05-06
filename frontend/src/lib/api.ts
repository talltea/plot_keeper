export type Ping = {
  ok: boolean;
  schema_version: number;
  now: string;
};

export async function ping(): Promise<Ping> {
  const res = await fetch("/api/ping");
  if (!res.ok) throw new Error(`ping failed: HTTP ${res.status}`);
  return res.json();
}
