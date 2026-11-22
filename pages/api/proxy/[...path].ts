import type { NextApiRequest, NextApiResponse } from 'next';

export const config = { api: { bodyParser: { sizeLimit: '1mb' } } };

export default async function apiProxy(req: NextApiRequest, res: NextApiResponse) {
  const pathParts = req.query.path;
  const path = Array.isArray(pathParts) ? pathParts : [pathParts].filter(Boolean) as string[];
  const allowedMethods = new Set(['GET', 'POST', 'DELETE']);
  if (!allowedMethods.has(req.method || '')) {
    return res.status(405).json({ detail: 'Method not allowed' });
  }

  const apiBase = (process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
  const url = new URL(`${apiBase}/${path.map(encodeURIComponent).join('/')}`);
  for (const [key, value] of Object.entries(req.query)) {
    if (key !== 'path' && typeof value === 'string') url.searchParams.set(key, value);
  }

  try {
    const headers: Record<string, string> = { accept: 'application/json' };
    if (process.env.API_AUTH_TOKEN) headers.authorization = `Bearer ${process.env.API_AUTH_TOKEN}`;
    const idempotencyKey = req.headers['idempotency-key'];
    if (typeof idempotencyKey === 'string') headers['Idempotency-Key'] = idempotencyKey;
    if (process.env.ADMIN_API_TOKEN && req.method === 'DELETE') {
      headers['x-admin-token'] = process.env.ADMIN_API_TOKEN;
    }
    if (req.body !== undefined && req.method !== 'GET') headers['content-type'] = 'application/json';

    const upstream = await fetch(url, {
      method: req.method,
      headers,
      body: req.body !== undefined && req.method !== 'GET' ? JSON.stringify(req.body) : undefined,
      cache: 'no-store',
    });
    const payload = await upstream.text();
    res.status(upstream.status);
    res.setHeader('content-type', upstream.headers.get('content-type') || 'application/json');
    res.setHeader('cache-control', 'no-store');
    return res.send(payload);
  } catch {
    return res.status(502).json({ detail: 'API service is unavailable' });
  }
}
