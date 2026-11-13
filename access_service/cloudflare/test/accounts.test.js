import assert from 'node:assert/strict';
import { before, after, beforeEach, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { Miniflare, Response } from 'miniflare';
import { GUILD_ID, ROLE_ID } from '../src/constants.js';
import { applySchema } from './schema.js';

const origin = 'https://accounts.example.com';
const identity = { install_id: 'installation-123456789012345678', release_id: '1.0.4' };
const bindings = { ACCESS_PUBLIC_URL: origin, DISCORD_CLIENT_ID: '123456789012345678',
  DISCORD_CLIENT_SECRET: 'test-client-secret', DISCORD_BOT_TOKEN: 'test-bot-token', AUTH_PASSWORD_PEPPER: 'test-pepper-' + 'x'.repeat(43) };
const user = { id: '123456789012345678', username: 'example', global_name: 'Example' };
let mf, db, memberStatus, roles, pending, scope, requests, upstreamFailure, holdMember;
const options = () => ({ modules: true, scriptPath: fileURLToPath(new URL('../src/index.js', import.meta.url)),
  modulesRules: [{ type: 'ESModule', include: ['**/*.js'] }],
  compatibilityDate: '2026-07-30', d1Databases: { DB: '00000000-0000-0000-0000-000000000001' }, bindings,
  outboundService: async request => {
    const url = new URL(request.url);
    assert.equal(url.hostname, 'discord.com');
    const body = request.method === 'POST' ? await request.text() : '';
    requests.push({ path: url.pathname, body, authorization: request.headers.get('Authorization') });
    if (upstreamFailure) return Response.json({ error: 'not exposed: test-client-secret' }, { status: upstreamFailure });
    if (url.pathname === '/api/v10/oauth2/token') {
      const params = new URLSearchParams(body);
      assert.equal(params.get('client_secret'), bindings.DISCORD_CLIENT_SECRET);
      assert.equal(params.get('redirect_uri'), origin + '/oauth/callback');
      assert.ok(params.get('code_verifier').length >= 43);
      return Response.json({ access_token: 'private-user-oauth-token', refresh_token: 'not-stored', scope });
    }
    if (url.pathname === '/api/v10/users/@me') return Response.json(user);
    if (url.pathname === `/api/v10/users/@me/guilds/${GUILD_ID}/member`) return Response.json({ roles, pending });
    if (url.pathname === `/api/v10/guilds/${GUILD_ID}/members/${user.id}`) {
      assert.equal(request.headers.get('Authorization'), 'Bot ' + bindings.DISCORD_BOT_TOKEN);
      if (holdMember) await holdMember;
      return Response.json({ roles, pending }, { status: memberStatus });
    }
    throw new Error('Unexpected Discord request: ' + url.pathname);
  },
});

before(async () => {
  mf = new Miniflare(options());
  db = await mf.getD1Database('DB');
  await applySchema(db);
});
after(async () => { if (mf) await mf.dispose(); });
beforeEach(async () => {
  roles = [ROLE_ID]; pending = false; memberStatus = 200; scope = 'identify guilds.members.read';
  requests = []; upstreamFailure = null; holdMember = null;
  await db.batch(['ai_answer_cache','ai_daily_usage','ai_global_usage','credential_intents', 'account_credentials', 'sessions', 'accounts', 'login_attempts', 'login_rate_limits'].map(table => db.prepare('DELETE FROM ' + table)));
});

async function post(path, data = identity, key = '', extraHeaders = {}) {
  return mf.dispatchFetch(origin + path, { method: 'POST', headers: { 'Content-Type': 'application/json',
    ...(key ? { Authorization: 'Bearer ' + key } : {}), ...extraHeaders }, body: JSON.stringify(data) });
}
const credentials = { username: 'example', password: 'test-password-very-long-123' };
async function begin() {
  const exists = await db.prepare('SELECT account_id FROM account_credentials WHERE username=?').bind(credentials.username).first();
  const response = await post(exists ? '/v2/recover' : '/v2/register', { ...identity, ...credentials });
  assert.equal(response.status, 200, await response.clone().text());
  return response.json();
}
async function confirm(login, extra = {}) {
  const params = new URL(login.browser_url).searchParams;
  return mf.dispatchFetch(origin + '/oauth/callback?' + new URLSearchParams({ state: params.get('state'),
    code: 'test-oauth-code', iss: 'https://discord.com', ...extra }));
}
async function poll(login, data = identity, secret = login.polling_secret) {
  return post('/v2/registration/' + login.login_id, data, secret);
}
async function login() {
  if (await db.prepare('SELECT account_id FROM account_credentials LIMIT 1').first()) {
    const response = await post('/v2/login', { ...identity, ...credentials });
    assert.equal(response.status, 200, await response.clone().text());
    return { result: await response.json() };
  }
  const attempt = await begin();
  const callback = await confirm(attempt);
  assert.equal(callback.status, 200, await callback.clone().text());
  const response = await poll(attempt);
  assert.equal(response.status, 200, await response.clone().text());
  return { attempt, result: await response.json() };
}

test('health checks the D1 schema and never caches account responses', async () => {
  const response = await mf.dispatchFetch(origin + '/health');
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: 'ok', storage: 'd1', accounts: 'password-discord' });
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
});

test('desktop protocol creates an account, keeps a hashed device key and checks the exact role', async () => {
  const { attempt, result } = await login();
  assert.equal(result.status, 'authorized');
  assert.equal(result.role_id, ROLE_ID);
  assert.equal(result.guild_id, GUILD_ID);
  assert.equal(result.account.discord_id, user.id);
  assert.equal(result.account.display_name, user.global_name);
  const params = new URL(attempt.browser_url).searchParams;
  assert.equal(params.get('scope'), scope);
  assert.equal(params.get('code_challenge_method'), 'S256');
  assert.ok(!attempt.browser_url.includes(attempt.polling_secret));
  assert.ok(!attempt.browser_url.includes(result.session_key));
  const session = await db.prepare('SELECT * FROM sessions').first();
  assert.notEqual(session.key_hash, result.session_key);
  assert.equal(session.key_hash.length, 64);
  assert.equal(await db.prepare('SELECT count(*) AS n FROM login_attempts').first('n'), 0);
  const checked = await post('/v1/session/check', identity, result.session_key);
  assert.equal(checked.status, 200);
  assert.deepEqual((await checked.json()).account, result.account);
});

test('pending login survives a Worker isolate replacement', async () => {
  const attempt = await begin();
  await mf.setOptions({ ...options(), bindings: { ...bindings, ROLLOUT: 'pending-restart' } });
  db = await mf.getD1Database('DB');
  assert.equal((await confirm(attempt)).status, 200);
  const response = await poll(attempt);
  assert.equal(response.status, 200);
  const saved = await response.json();
  await mf.setOptions({ ...options(), bindings: { ...bindings, ROLLOUT: 'session-restart' } });
  db = await mf.getD1Database('DB');
  assert.equal((await post('/v1/session/check', identity, saved.session_key)).status, 200);
});

test('same Discord user keeps one account after a second installation or login', async () => {
  const first = await login();
  const second = await login();
  assert.equal(second.result.account.id, first.result.account.id);
  assert.equal(await db.prepare('SELECT count(*) AS n FROM accounts').first('n'), 1);
  assert.equal(await db.prepare('SELECT count(*) AS n FROM sessions').first('n'), 1);
  assert.equal((await post('/v1/session/check', identity, first.result.session_key)).status, 401);
});

test('other version or installation cannot reuse a device session', async () => {
  const { result } = await login();
  for (const data of [{ ...identity, release_id: '1.0.5' }, { ...identity, install_id: 'another-installation-123456789' }]) {
    assert.equal((await post('/v1/session/check', data, result.session_key)).status, 401);
  }
});

test('missing role, unrelated role and pending membership deny initial access', async () => {
  for (const kind of ['missing', 'other', 'pending']) {
    roles = kind === 'missing' ? [] : kind === 'other' ? [GUILD_ID] : [ROLE_ID];
    pending = kind === 'pending';
    const attempt = await begin();
    assert.equal((await confirm(attempt)).status, 403);
    assert.equal((await poll(attempt)).status, 403);
  }
  assert.equal(await db.prepare('SELECT count(*) AS n FROM accounts').first('n'), 0);
});

test('role removal and leaving the server revoke the saved device session', async () => {
  for (const kind of ['role', 'left']) {
    roles = [ROLE_ID]; memberStatus = 200;
    const { result } = await login();
    if (kind === 'role') roles = [];
    else memberStatus = 404;
    assert.equal((await post('/v1/session/check', identity, result.session_key)).status, 403);
    roles = [ROLE_ID]; memberStatus = 200;
    assert.equal((await post('/v1/session/check', identity, result.session_key)).status, 401);
  }
});

test('Discord outages, rate limits and bot permissions never delete a valid session', async () => {
  const { result } = await login();
  for (const status of [401, 403, 429, 500]) {
    memberStatus = status;
    const response = await post('/v1/session/check', identity, result.session_key);
    assert.equal(response.status, 503);
    assert.ok(!(await response.text()).includes(bindings.DISCORD_BOT_TOKEN));
  }
  memberStatus = 200;
  assert.equal((await post('/v1/session/check', identity, result.session_key)).status, 200);
});

test('OAuth state is single-use, polling needs the secret and the same device', async () => {
  const { attempt, result } = await login();
  assert.equal((await confirm(attempt)).status, 400);
  assert.equal((await poll(attempt)).status, 401);
  const other = await begin();
  assert.equal((await poll(other, identity, other.login_id)).status, 401);
  assert.equal((await confirm(other)).status, 200);
  assert.equal((await poll(other, { ...identity, release_id: 'different' })).status, 401);
  assert.equal((await poll(other)).status, 200);
  assert.ok(result.session_key);
});

test('concurrent callbacks and polls issue at most one device credential', async () => {
  const attempt = await begin();
  const callbacks = await Promise.all([confirm(attempt), confirm(attempt)]);
  assert.deepEqual(callbacks.map(r => r.status).sort(), [200, 400]);
  const responses = await Promise.all([poll(attempt), poll(attempt)]);
  assert.equal(responses.filter(r => r.status === 200).length, 1);
  assert.ok([401, 429].includes(responses.find(r => r.status !== 200).status));
  assert.equal(await db.prepare('SELECT count(*) AS n FROM sessions').first('n'), 1);
});

test('parallel logout wins over an in-flight role check', async () => {
  const { result } = await login();
  let release;
  holdMember = new Promise(resolve => { release = resolve; });
  const checking = post('/v1/session/check', identity, result.session_key);
  // Wait for the mocked Discord member request, not a timing-dependent sleep.
  const previousCount = requests.filter(r => r.path.includes('/members/')).length;
  const deadline = Date.now() + 3000;
  while (requests.filter(r => r.path.includes('/members/')).length <= previousCount) {
    if (Date.now() > deadline) throw new Error('Member request did not start');
    await new Promise(resolve => setTimeout(resolve, 5));
  }
  assert.equal((await post('/v1/session/logout', identity, result.session_key)).status, 200);
  release(); holdMember = null;
  assert.equal((await checking).status, 401);
});

test('expired state cannot authorize and abandoned logins are removable without affecting accounts', async () => {
  const { result } = await login();
  const attempt = await begin();
  await db.prepare('UPDATE login_attempts SET expires_at=0 WHERE id=?').bind(attempt.login_id).run();
  assert.equal((await confirm(attempt)).status, 400);
  assert.equal((await poll(attempt)).status, 401);
  assert.equal((await post('/v1/session/check', identity, result.session_key)).status, 200);
});

test('limited OAuth permissions, denied consent and a wrong issuer create no accounts', async () => {
  scope = 'identify';
  assert.equal((await confirm(await begin())).status, 403);
  scope = 'identify guilds.members.read';
  assert.equal((await confirm(await begin(), { error: 'access_denied' })).status, 403);
  assert.equal((await confirm(await begin(), { iss: 'https://other.example' })).status, 400);
  assert.equal(await db.prepare('SELECT count(*) AS n FROM accounts').first('n'), 0);
});

test('input validation and request limits do not leak upstream details', async () => {
  assert.equal((await post('/v2/register', { ...identity, ...credentials }, '', { Origin: 'https://other.example' })).status, 403);
  assert.equal((await post('/v2/register', { ...credentials, install_id: 'short', release_id: '1.0.4' })).status, 400);
  assert.equal((await post('/v2/register', { ...identity, ...credentials, padding: 'x'.repeat(5000) })).status, 413);
  assert.equal((await post('/v1/session/check')).status, 401);
  const attempt = await begin();
  upstreamFailure = 500;
  const failed = await confirm(attempt);
  assert.equal(failed.status, 503);
  const text = await failed.text();
  assert.ok(!text.includes(bindings.DISCORD_CLIENT_SECRET));
  assert.ok(!text.includes('test-oauth-code'));
  assert.equal(failed.headers.get('Referrer-Policy'), 'no-referrer');
});

test('login rate limit persists across Worker replacement', async () => {
  for (let i = 0; i < 10; i++) await begin();
  await mf.setOptions({ ...options(), bindings: { ...bindings, ROLLOUT: 'rate-limit-restart' } });
  db = await mf.getD1Database('DB');
  assert.equal((await post('/v2/register', { ...identity, ...credentials })).status, 429);
});

test('registration stores only a salted digest and cannot sign in before Discord confirmation', async () => {
  const attempt = await begin();
  assert.equal((await post('/v2/login', { ...identity, ...credentials })).status, 401);
  assert.equal(await db.prepare('SELECT count(*) AS n FROM account_credentials').first('n'), 0);
  const intent = await db.prepare('SELECT * FROM credential_intents').first();
  assert.ok(intent.password_digest.startsWith('pbkdf2-sha256:100000:'));
  assert.ok(!JSON.stringify(intent).includes(credentials.password));
  assert.equal((await confirm(attempt)).status, 200);
  assert.equal((await poll(attempt)).status, 200);
  assert.equal(await db.prepare('SELECT count(*) AS n FROM credential_intents').first('n'), 0);
  assert.equal((await post('/v2/login', { ...identity, ...credentials, username: 'EXAMPLE' })).status, 200);
  const wrong = await post('/v2/login', { ...identity, ...credentials, password: 'wrong-password-12345' });
  const unknown = await post('/v2/login', { ...identity, ...credentials, username: 'unknown' });
  assert.equal(wrong.status, 401);
  assert.equal(await wrong.text(), await unknown.text());
  assert.equal((await post('/v1/login')).status, 410);
});

test('one Discord cannot acquire another login and duplicate names cannot replace credentials', async () => {
  const first = await login();
  assert.equal((await post('/v2/register', { ...identity, ...credentials, username: 'EXAMPLE' })).status, 409);
  const duplicate = await post('/v2/register', { ...identity, ...credentials, username: 'different' });
  const attempt = await duplicate.json();
  assert.equal((await confirm(attempt)).status, 409);
  assert.equal((await poll(attempt)).status, 409);
  assert.equal((await post('/v1/session/check', identity, first.result.session_key)).status, 200);
  assert.equal(await db.prepare('SELECT count(*) AS n FROM account_credentials').first('n'), 1);
});

test('password recovery requires the linked Discord and revokes all previous devices', async () => {
  const first = await login();
  const otherDevice = { ...identity, install_id: 'other-installation-123456789012345' };
  const second = await (await post('/v2/login', { ...otherDevice, ...credentials })).json();
  const newPassword = 'replacement-password-67890';
  let attempt = await (await post('/v2/recover', { ...identity, ...credentials, password: newPassword })).json();
  const originalId = user.id;
  try {
    user.id = '987654321098765432';
    assert.equal((await confirm(attempt)).status, 403);
    assert.equal((await poll(attempt)).status, 403);
  } finally { user.id = originalId; }
  attempt = await (await post('/v2/recover', { ...identity, ...credentials, password: newPassword })).json();
  assert.equal((await confirm(attempt)).status, 200);
  const recovered = await (await poll(attempt)).json();
  assert.equal(recovered.account.id, first.result.account.id);
  assert.equal((await post('/v1/session/check', identity, first.result.session_key)).status, 401);
  assert.equal((await post('/v1/session/check', otherDevice, second.session_key)).status, 401);
  assert.equal((await post('/v2/login', { ...identity, ...credentials })).status, 401);
  assert.equal((await post('/v2/login', { ...identity, ...credentials, password: newPassword })).status, 200);
});

test('legacy Discord account must finish registration and retains its account ID', async () => {
  const key = 'legacy-key-' + 'x'.repeat(45);
  const { createHash } = await import('node:crypto');
  const hashed = createHash('sha256').update(key).digest('hex');
  await db.prepare('INSERT INTO accounts VALUES(?,?,?,?)').bind('legacy-account', user.id, 'Legacy', 1).run();
  await db.prepare('INSERT INTO sessions VALUES(?,?,?,?,?,?)').bind(hashed, 'legacy-account', identity.install_id, identity.release_id, 1, 1).run();
  const checked = await (await post('/v1/session/check', identity, key)).json();
  assert.equal(checked.status, 'setup_required');
  const response = await post('/v2/account/setup', { ...identity, ...credentials }, key);
  assert.equal(response.status, 200, await response.clone().text());
  const saved = await response.json();
  assert.equal(saved.status, 'authorized');
  assert.equal(saved.account.id, 'legacy-account');
  assert.equal(saved.account.username, credentials.username);
  assert.equal((await post('/v2/account/setup', { ...identity, ...credentials }, key)).status, 409);
  assert.equal((await post('/v2/login', { ...identity, ...credentials })).status, 200);
});

test('password login still requires the role and invalid input never reaches Discord', async () => {
  await login();
  roles = [];
  assert.equal((await post('/v2/login', { ...identity, ...credentials })).status, 403);
  const requestCount = requests.length;
  for (const change of [{ password: 'short' }, { username: 'bad name' }, { password: 'x'.repeat(129) }]) {
    assert.equal((await post('/v2/register', { ...identity, ...credentials, ...change })).status, 400);
  }
  assert.equal(requests.length, requestCount);
});


test('AI quota derives account from the session and rejects revoked role or another device', async () => {
  const { result } = await login();
  assert.equal((await post('/v1/ai/quota')).status, 401);
  await db.prepare('INSERT INTO ai_daily_usage VALUES(?,?,5)').bind(result.account.id,new Date().toISOString().slice(0,10)).run();
  const response = await post('/v1/ai/quota', {...identity,account_id:'another-account'}, result.session_key);
  assert.equal(response.status,200);
  assert.equal((await response.json()).quota.remaining,0);
  assert.equal((await post('/v1/ai/quota',{...identity,install_id:'different-installation-123456789'},result.session_key)).status,401);
  roles=[];
  assert.equal((await post('/v1/ai/search',{...identity,server:'murrieta',query:'кража автомобиля'},result.session_key)).status,403);
});
