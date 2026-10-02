// Serverless proxy for website lead forms -> GoHighLevel Inbound Webhooks.
// Keeps the webhook URLs off the public page source and applies server-side
// spam checks (honeypot + timing + minimal validation) before forwarding.

const WEBHOOKS = {
  'rs-popup':     process.env.GHL_LEADS_WEBHOOK || 'https://services.leadconnectorhq.com/hooks/9vsm93CZ03U3sAiA7RDF/webhook-trigger/329152f3-b6b9-4cf1-87cf-09c0b81fbb11',
  'contact':      process.env.GHL_LEADS_WEBHOOK || 'https://services.leadconnectorhq.com/hooks/9vsm93CZ03U3sAiA7RDF/webhook-trigger/329152f3-b6b9-4cf1-87cf-09c0b81fbb11',
  'comfort-club': process.env.GHL_CLUB_WEBHOOK  || 'https://services.leadconnectorhq.com/hooks/9vsm93CZ03U3sAiA7RDF/webhook-trigger/Lk80E6LPu9AJbaXhUmi2',
  'newsletter':   process.env.GHL_NEWS_WEBHOOK  || 'https://services.leadconnectorhq.com/hooks/9vsm93CZ03U3sAiA7RDF/webhook-trigger/9erw8HrFsgDlYJUFSscp',
};

function readRawBody(req) {
  return new Promise((resolve) => {
    try {
      if (req.body != null) {
        return resolve(typeof req.body === 'string' ? req.body : JSON.stringify(req.body));
      }
    } catch (e) {}
    let d = '';
    req.on('data', (c) => { d += c; if (d.length > 1e6) req.destroy(); });
    req.on('end', () => resolve(d));
    req.on('error', () => resolve(''));
  });
}

module.exports = async (req, res) => {
  const json = (code, obj) => {
    res.statusCode = code;
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify(obj));
  };

  if (req.method !== 'POST') return json(405, { error: 'method_not_allowed' });

  let body = {};
  try { body = JSON.parse((await readRawBody(req)) || '{}'); } catch (e) { body = {}; }

  // 1) Honeypot: real users never fill this hidden field. Silently accept + drop.
  if (body.company) return json(200, { status: 'ok' });

  // 2) Timing: a value that is present but implausibly fast is a bot. Drop silently.
  const elapsed = Number(body.elapsed_ms || 0);
  if (elapsed && elapsed < 1500) return json(200, { status: 'ok' });

  // 3) Minimal validation: must carry a way to contact the lead.
  if (!body.email && !body.phone) return json(400, { error: 'missing_contact' });

  const url = WEBHOOKS[body.form_source] || WEBHOOKS['rs-popup'];

  // Strip internal-only fields before forwarding.
  const { company, elapsed_ms, ...payload } = body;

  try {
    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    return json(502, { error: 'upstream_failed' });
  }
  return json(200, { status: 'forwarded' });
};
