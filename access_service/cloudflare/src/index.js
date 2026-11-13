// Same desktop API as the Python prototype. No Node runtime or paid bindings.
import { GUILD_ID, ROLE_ID } from './constants.js';
import { AccessError } from './errors.js';
import { username, password, digest, verify } from './passwords.js';
import { search as aiSearch, quota as aiQuota, importCatalog } from './ai_search.js';
const SCOPES = 'identify guilds.members.read';
const API = 'https://discord.com/api/v10';
const now = () => Math.floor(Date.now() / 1000);
const encoder = new TextEncoder();


function randomKey(bytes = 32) {
  return base64url(crypto.getRandomValues(new Uint8Array(bytes)));
}
function base64url(bytes) {
  return btoa(String.fromCharCode(...bytes)).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '');
}
async function hash(value) {
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(value)))].map(b => b.toString(16).padStart(2, '0')).join('');
}
function identity(data) {
  const { install_id, release_id } = data;
  if (typeof install_id !== 'string' || !/^[\w-]{20,100}$/.test(install_id)
      || typeof release_id !== 'string' || !/^[\w.+-]{1,100}$/.test(release_id)) {
    throw new AccessError(400, 'Некорректный идентификатор установки.');
  }
  return { install_id, release_id };
}
function bearer(request) {
  const match = /^Bearer ([A-Za-z0-9_-]{32,128})$/.exec(request.headers.get('Authorization') || '');
  if (!match) throw new AccessError(401, 'Войдите в аккаунт хелпера.');
  return match[1];
}
function config(env) {
  let url;
  try { url = new URL(env.ACCESS_PUBLIC_URL); } catch { /* checked below */ }
  if (!url || url.protocol !== 'https:' || url.username || url.password || url.search || url.hash
      || url.pathname !== '/' || url.hostname.includes('your_subdomain')
      || !/^\d{17,20}$/.test(env.DISCORD_CLIENT_ID || '')
      || !env.DISCORD_CLIENT_SECRET || !env.DISCORD_BOT_TOKEN || !env.DB) {
    throw new AccessError(503, 'Сервис аккаунтов ещё не настроен.');
  }
  return { clientId: env.DISCORD_CLIENT_ID, callback: url.origin + '/oauth/callback' };
}
async function readBody(request, maxSize=4096) {
  if (request.headers.has('Origin')) throw new AccessError(403, 'Этот запрос разрешён только из хелпера.');
  if ((request.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase() !== 'application/json') {
    throw new AccessError(400, 'Ожидается JSON.');
  }
  if (!request.body) throw new AccessError(400, 'Некорректный запрос.');
  const reader = request.body.getReader();
  let size = 0;
  const chunks = [];
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > maxSize) { await reader.cancel(); throw new AccessError(413, 'Слишком большой запрос.'); }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  try {
    const result = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
    if (!result || typeof result !== 'object' || Array.isArray(result)) throw new Error();
    return result;
  } catch { throw new AccessError(400, 'Некорректный запрос.'); }
}
function requireRole(member) {
  if (!Array.isArray(member?.roles) || !member.roles.includes(ROLE_ID) || member.pending) {
    throw new AccessError(403, 'Для доступа нужна роль «Участник» на сервере CARLEONE HELPER.');
  }
}
async function discordRequest(path, options = {}, bot = false) {
  let response;
  try {
    response = await fetch(API + path, { ...options, redirect: 'manual', signal: AbortSignal.timeout(15000) });
  } catch { throw new AccessError(503, 'Discord временно недоступен. Повторите проверку.'); }
  if (bot && response.status === 404) {
    throw new AccessError(403, 'Для доступа вступите в CARLEONE HELPER и получите роль «Участник».');
  }
  if (!response.ok) {
    const status = bot || response.status === 429 || response.status >= 500 ? 503 : 403;
    throw new AccessError(status, status === 503 ? 'Проверка Discord временно недоступна.' : 'Discord не подтвердил доступ. Войдите снова.');
  }
  try {
    const body = await response.text();
    if (body.length > 65536) throw new Error();
    const result = JSON.parse(body);
    if (!result || typeof result !== 'object' || Array.isArray(result)) throw new Error();
    return result;
  } catch { throw new AccessError(503, 'Discord вернул некорректный ответ.'); }
}
async function checkMember(env, userId) {
  const member = await discordRequest(`/guilds/${GUILD_ID}/members/${userId}`,
    { headers: { Authorization: 'Bot ' + env.DISCORD_BOT_TOKEN } }, true);
  requireRole(member);
}
async function exchange(env, cfg, code, verifier) {
  const token = await discordRequest('/oauth2/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'authorization_code', code, redirect_uri: cfg.callback,
      client_id: cfg.clientId, client_secret: env.DISCORD_CLIENT_SECRET, code_verifier: verifier }),
  });
  const granted = typeof token.scope === 'string' ? token.scope.split(/\s+/) : [];
  if (!SCOPES.split(' ').every(scope => granted.includes(scope))) {
    throw new AccessError(403, 'Для подтверждения аккаунта нужны разрешения профиля и проверки роли.');
  }
  if (typeof token.access_token !== 'string' || !token.access_token) throw new AccessError(503, 'Discord не вернул подтверждение входа.');
  const headers = { Authorization: 'Bearer ' + token.access_token };
  const user = await discordRequest('/users/@me', { headers });
  const member = await discordRequest(`/users/@me/guilds/${GUILD_ID}/member`, { headers });
  requireRole(member);
  if (typeof user.id !== 'string' || !/^\d{17,20}$/.test(user.id)) throw new AccessError(503, 'Некорректный профиль Discord.');
  await checkMember(env, user.id);
  return { id: user.id, display_name: String(user.global_name || user.username || user.id).slice(0, 100) };
}
const authorized = account => ({ status: 'authorized', account: {
  id: account.id, discord_id: account.discord_id, display_name: account.display_name, username: account.username,
}, guild_id: GUILD_ID, role_id: ROLE_ID });

async function rateLimit(request, db, name = '') {
  const timestamp = now(), bucket = Math.floor(timestamp / 60);
  // CF-Connecting-IP is supplied by Cloudflare, not X-Forwarded-For from clients.
  const ipHash = await hash('ip:' + (request.headers.get('CF-Connecting-IP') || 'local'));
  const rate = await db.prepare(`INSERT INTO login_rate_limits(ip_hash,bucket,count) VALUES(?,?,1)
    ON CONFLICT(ip_hash,bucket) DO UPDATE SET count=count+1 RETURNING count`).bind(ipHash, bucket).first();
  if (rate.count > 10) throw new AccessError(429, 'Слишком много попыток входа. Подождите минуту.');
  if (name) {
    const accountRate = await db.prepare(`INSERT INTO login_rate_limits(ip_hash,bucket,count) VALUES(?,?,1)
      ON CONFLICT(ip_hash,bucket) DO UPDATE SET count=count+1 RETURNING count`).bind(await hash('user:' + name), bucket).first();
    if (accountRate.count > 10) throw new AccessError(429, 'Слишком много попыток входа. Подождите минуту.');
  }
}
async function newLogin(request, data, env, db, cfg, mode = 'register') {
  const { install_id, release_id } = identity(data);
  const name = username(data.username);
  password(data.password);
  await rateLimit(request, db, name);
  const existing = await db.prepare('SELECT account_id FROM account_credentials WHERE username=?').bind(name).first();
  if (mode === 'register' && existing) throw new AccessError(409, 'Этот логин занят. Войдите или выберите другой.');
  if (mode === 'recover' && !existing) throw new AccessError(400, 'Проверьте логин аккаунта для восстановления.');
  const passwordDigest = await digest(data.password, env.AUTH_PASSWORD_PEPPER);
  const timestamp = now();
  const loginId = randomKey(), secret = randomKey(), state = randomKey(), verifier = randomKey();
  const insert = await db.prepare(`INSERT INTO login_attempts
    (id,secret_hash,state_hash,pkce_verifier,install_id,release_id,status,created_at,expires_at)
    SELECT ?,?,?,?,?,?,'pending',?,? WHERE (SELECT COUNT(*) FROM login_attempts WHERE expires_at>?)<2000`)
    .bind(loginId, await hash(secret), await hash(state), verifier, install_id, release_id, timestamp, timestamp + 600, timestamp).run();
  if (!insert.meta.changes) throw new AccessError(429, 'Сервис занят. Повторите вход позже.');
  await db.prepare('INSERT INTO credential_intents(login_id,mode,username,password_digest,account_id) VALUES(?,?,?,?,?)')
    .bind(loginId, mode, name, passwordDigest, existing?.account_id || null).run();
  const challenge = base64url(new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(verifier))));
  const params = new URLSearchParams({ client_id: cfg.clientId, response_type: 'code', scope: SCOPES,
    redirect_uri: cfg.callback, state, code_challenge: challenge, code_challenge_method: 'S256' });
  return { login_id: loginId, polling_secret: secret, expires_in: 600, browser_url: 'https://discord.com/oauth2/authorize?' + params };
}

async function callback(url, env, db, cfg) {
  for (const name of ['state', 'code', 'error', 'iss']) {
    if (url.searchParams.getAll(name).length > 1) throw new AccessError(400, 'Некорректная ссылка входа.');
  }
  const state = url.searchParams.get('state') || '';
  if (!/^[\w-]{43}$/.test(state)) throw new AccessError(400, 'Ссылка входа недействительна или уже использована.');
  // A conditional UPDATE is the one-time claim. It works across Worker isolates.
  const login = await db.prepare(`UPDATE login_attempts SET status='checking',state_hash=NULL
    WHERE state_hash=? AND status='pending' AND expires_at>? RETURNING *`).bind(await hash(state), now()).first();
  if (!login) throw new AccessError(400, 'Ссылка входа недействительна или уже использована.');
  try {
    const code = url.searchParams.get('code');
    if (url.searchParams.has('error') || !code || code.length > 2048) throw new AccessError(403, 'Вход через Discord отменён.');
    if (url.searchParams.has('iss') && url.searchParams.get('iss') !== 'https://discord.com') throw new AccessError(400, 'Неверный источник авторизации.');
    const user = await exchange(env, cfg, code, login.pkce_verifier);
    const intent = await db.prepare('SELECT * FROM credential_intents WHERE login_id=?').bind(login.id).first();
    if (!intent) throw new AccessError(401, 'Начните регистрацию заново в обновлённом хелпере.');
    const linked = await db.prepare(`SELECT a.id,c.username FROM accounts a LEFT JOIN account_credentials c ON c.account_id=a.id WHERE a.discord_id=?`).bind(user.id).first();
    if (intent.mode === 'recover' && linked?.id !== intent.account_id) throw new AccessError(403, 'Подтвердите Discord, привязанный к этому аккаунту.');
    if (intent.mode === 'register' && linked?.username) throw new AccessError(409, 'Этот Discord уже привязан к аккаунту. Используйте вход или восстановление пароля.');
    const result = await db.prepare(`UPDATE login_attempts SET status='ready',pkce_verifier=NULL,discord_id=?,display_name=?
      WHERE id=? AND status='checking' AND expires_at>?`).bind(user.id, user.display_name, login.id, now()).run();
    if (!result.meta.changes) throw new AccessError(401, 'Ссылка входа истекла. Начните вход заново.');
  } catch (error) {
    const safe = error instanceof AccessError ? error : new AccessError(503, 'Сервис временно недоступен.');
    await db.prepare(`UPDATE login_attempts SET status='denied',pkce_verifier=NULL,error_status=?,message=? WHERE id=?`)
      .bind(safe.status, safe.message, login.id).run();
    throw safe;
  }
  return 'Discord подтверждён. Вернитесь в хелпер для завершения регистрации или восстановления.';
}

async function poll(loginId, secret, data, db) {
  const { install_id, release_id } = identity(data);
  const secretHash = await hash(secret), timestamp = now();
  // Don't let one device consume a different installation's successful login.
  const login = await db.prepare(`SELECT * FROM login_attempts WHERE id=? AND secret_hash=?
    AND install_id=? AND release_id=? AND expires_at>?`)
    .bind(loginId, secretHash, install_id, release_id, timestamp).first();
  if (!login) throw new AccessError(401, 'Ссылка входа истекла. Начните вход заново.');
  const throttled = await db.prepare(`UPDATE login_attempts SET last_poll=? WHERE id=? AND secret_hash=? AND last_poll<=?`)
    .bind(timestamp, loginId, secretHash, timestamp - 2).run();
  if (!throttled.meta.changes) throw new AccessError(429, 'Подождите перед повторной проверкой.');
  if (login.status === 'denied') {
    await db.prepare('DELETE FROM login_attempts WHERE id=? AND secret_hash=?').bind(loginId, secretHash).run();
    throw new AccessError(login.error_status || 403, login.message || 'Вход не подтверждён.');
  }
  if (login.status === 'pending' || login.status === 'checking') return { status: 'pending' };
  const claim = randomKey(), sessionKey = randomKey(48), sessionHash = await hash(sessionKey);
  const accountId = randomKey(24);
  // D1 batch is transactional. All writes depend on the same successful claim;
  // competing polls cannot replace a session or return a second credential.
  const results = await db.batch([
    db.prepare(`UPDATE login_attempts SET status='consumed',claim_id=? WHERE id=? AND secret_hash=?
      AND status='ready' AND expires_at>?`).bind(claim, loginId, secretHash, timestamp),
    db.prepare(`INSERT INTO accounts(id,discord_id,display_name,created_at)
      SELECT ?,discord_id,display_name,? FROM login_attempts WHERE id=? AND claim_id=?
      ON CONFLICT(discord_id) DO UPDATE SET display_name=excluded.display_name`).bind(accountId, timestamp, loginId, claim),
    db.prepare(`INSERT INTO account_credentials(account_id,username,password_digest,updated_at,registration_id)
      SELECT a.id,i.username,i.password_digest,?,l.id FROM accounts a JOIN login_attempts l ON a.discord_id=l.discord_id
      JOIN credential_intents i ON i.login_id=l.id WHERE l.id=? AND l.claim_id=? AND i.mode='register'
      ON CONFLICT DO NOTHING`).bind(timestamp, loginId, claim),
    db.prepare(`UPDATE account_credentials SET password_digest=(SELECT password_digest FROM credential_intents WHERE login_id=?),
      updated_at=?,registration_id=? WHERE account_id=(SELECT i.account_id FROM credential_intents i JOIN login_attempts l ON i.login_id=l.id
      WHERE l.id=? AND l.claim_id=? AND i.mode='recover')`).bind(loginId, timestamp, loginId, loginId, claim),
    // Registration invalidates legacy sessions; recovery invalidates every device.
    db.prepare(`DELETE FROM sessions WHERE account_id IN (SELECT c.account_id FROM account_credentials c
      JOIN login_attempts l ON c.registration_id=l.id WHERE l.id=? AND l.claim_id=?)`).bind(loginId, claim),
    db.prepare(`INSERT INTO sessions(key_hash,account_id,install_id,release_id,created_at,last_seen)
      SELECT ?,a.id,l.install_id,l.release_id,?,? FROM accounts a JOIN login_attempts l ON a.discord_id=l.discord_id
      JOIN account_credentials c ON c.account_id=a.id AND c.registration_id=l.id
      WHERE l.id=? AND l.claim_id=?`).bind(sessionHash, timestamp, timestamp, loginId, claim),
    db.prepare(`SELECT a.id,a.discord_id,a.display_name,c.username FROM accounts a JOIN sessions s ON a.id=s.account_id
      JOIN account_credentials c ON c.account_id=a.id WHERE s.key_hash=?`).bind(sessionHash),
    db.prepare('DELETE FROM login_attempts WHERE id=? AND claim_id=?').bind(loginId, claim),
  ]);
  const account = results[6].results[0];
  if (!account) throw new AccessError(409, 'Регистрация уже завершена или логин занят. Используйте вход или другой логин.');
  return { ...authorized(account), session_key: sessionKey };
}

async function checkSession(key, data, env, db) {
  const { install_id, release_id } = identity(data), keyHash = await hash(key);
  const account = await db.prepare(`SELECT a.id,a.discord_id,a.display_name,c.username FROM sessions s JOIN accounts a ON a.id=s.account_id
    LEFT JOIN account_credentials c ON c.account_id=a.id
    WHERE s.key_hash=? AND s.install_id=? AND s.release_id=?`).bind(keyHash, install_id, release_id).first();
  if (!account) throw new AccessError(401, 'Войдите в аккаунт хелпера после обновления или переустановки.');
  try { await checkMember(env, account.discord_id); }
  catch (error) {
    if (error instanceof AccessError && error.status === 403) {
      await db.prepare('DELETE FROM sessions WHERE key_hash=?').bind(keyHash).run();
    }
    throw error;
  }
  // Re-check after the Discord request: a concurrent logout must win.
  const update = await db.prepare('UPDATE sessions SET last_seen=? WHERE key_hash=? AND install_id=? AND release_id=?')
    .bind(now(), keyHash, install_id, release_id).run();
  if (!update.meta.changes) throw new AccessError(401, 'Сессия отозвана. Войдите снова.');
  return account.username ? authorized(account) : { ...authorized(account), status: 'setup_required' };
}

async function issueSession(account, device, db, expectedDigest) {
  const key = randomKey(48), keyHash = await hash(key), timestamp = now();
  const results = await db.batch([
    db.prepare(`DELETE FROM sessions WHERE account_id=? AND install_id=? AND EXISTS
      (SELECT 1 FROM account_credentials WHERE account_id=? AND password_digest=?)`)
      .bind(account.id, device.install_id, account.id, expectedDigest),
    db.prepare(`INSERT INTO sessions(key_hash,account_id,install_id,release_id,created_at,last_seen)
      SELECT ?,account_id,?,?,?,? FROM account_credentials WHERE account_id=? AND password_digest=?`)
      .bind(keyHash, device.install_id, device.release_id, timestamp, timestamp, account.id, expectedDigest),
  ]);
  if (!results[1].meta.changes) throw new AccessError(401, 'Пароль изменён. Повторите вход.');
  return { ...authorized(account), session_key: key };
}
async function passwordLogin(request, data, env, db) {
  const device = identity(data), name = username(data.username);
  password(data.password);
  await rateLimit(request, db, name);
  const account = await db.prepare(`SELECT a.*,c.username,c.password_digest FROM account_credentials c JOIN accounts a ON a.id=c.account_id WHERE c.username=?`).bind(name).first();
  const valid = await verify(data.password, account?.password_digest, env.AUTH_PASSWORD_PEPPER);
  if (!account || !valid) throw new AccessError(401, 'Неверный логин или пароль.');
  await checkMember(env, account.discord_id);
  return issueSession(account, device, db, account.password_digest);
}
async function setupAccount(request, data, key, env, db) {
  const device = identity(data), name = username(data.username);
  password(data.password);
  await rateLimit(request, db, name);
  const checked = await checkSession(key, device, env, db);
  if (checked.status !== 'setup_required') throw new AccessError(409, 'У аккаунта уже есть логин и пароль.');
  const passwordDigest = await digest(data.password, env.AUTH_PASSWORD_PEPPER);
  const keyHash = await hash(key);
  const inserted = await db.prepare(`INSERT INTO account_credentials(account_id,username,password_digest,updated_at,registration_id)
    SELECT a.id,?,?,?,? FROM accounts a JOIN sessions s ON s.account_id=a.id
    WHERE s.key_hash=? AND s.install_id=? AND s.release_id=? ON CONFLICT DO NOTHING`)
    .bind(name, passwordDigest, now(), randomKey(), keyHash, device.install_id, device.release_id).run();
  if (!inserted.meta.changes) throw new AccessError(409, 'Логин занят или аккаунт уже настроен.');
  return checkSession(key, device, env, db);
}

const escapeHtml = value => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
function response(value, status = 200, html = false) {
  return new Response(html ? `<!doctype html><html lang="ru"><meta charset="utf-8"><title>CARLEONE HELPER</title><h1>CARLEONE HELPER</h1><p>${escapeHtml(value)}</p></html>` : JSON.stringify(value), {
    status, headers: { 'Content-Type': html ? 'text/html; charset=utf-8' : 'application/json; charset=utf-8',
      'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff',
      'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'" },
  });
}

async function cleanup(env) {
  const timestamp = now();
  // Persistent accounts and device sessions are deliberately not expired here.
  await env.DB.batch([
    env.DB.prepare('DELETE FROM login_attempts WHERE expires_at<=?').bind(timestamp),
    env.DB.prepare('DELETE FROM login_rate_limits WHERE bucket<?').bind(Math.floor(timestamp / 60) - 1),
    env.DB.prepare('DELETE FROM ai_answer_cache WHERE expires_at<=?').bind(timestamp),
    env.DB.prepare('DELETE FROM ai_daily_usage WHERE day<?').bind(new Date((timestamp-7*86400)*1000).toISOString().slice(0,10)),
    env.DB.prepare('DELETE FROM ai_global_usage WHERE day<?').bind(new Date((timestamp-7*86400)*1000).toISOString().slice(0,10)),
  ]);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url), isCallback = url.pathname === '/oauth/callback';
    try {
      const cfg = config(env);
      // Reads start at the primary; revoked sessions must never be accepted from
      // a stale replica if read replication is enabled later.
      const db = env.DB.withSession('first-primary');
      if (request.method === 'GET' && url.pathname === '/health') {
        if (!env.AUTH_PASSWORD_PEPPER || env.AUTH_PASSWORD_PEPPER.length < 43) throw new AccessError(503, 'Сервис аккаунтов ещё не настроен.');
        await db.prepare('SELECT account_id FROM account_credentials LIMIT 1').first();
        return response({ status: 'ok', storage: 'd1', accounts: 'password-discord' });
      }
      if (request.method === 'GET' && isCallback) return response(await callback(url, env, db, cfg), 200, true);
      if (request.method !== 'POST') throw new AccessError(404, 'Страница не найдена.');
      const data = await readBody(request,url.pathname==='/v1/ai/admin/import'?512000:4096);
      let value;
      if (url.pathname.startsWith('/v1/ai/')) {
        const checked=await checkSession(bearer(request),data,env,db);
        if (checked.status!=='authorized') throw new AccessError(403,'Завершите регистрацию аккаунта.');
        if (url.pathname==='/v1/ai/search') value=await aiSearch(data,checked.account.id,env,db);
        else if (url.pathname==='/v1/ai/quota') value={status:'ok',quota:await aiQuota(db,checked.account.id),enabled:env.AI_SEARCH_ENABLED==='true'};
        else if (url.pathname==='/v1/ai/admin/import') value=await importCatalog(data,checked.account,env,db);
        else throw new AccessError(404,'Страница не найдена.');
      }
      else if (url.pathname === '/v1/login') throw new AccessError(410, 'Обновите хелпер: теперь вход по логину и паролю, регистрация подтверждается через Discord.');
      else if (url.pathname === '/v2/register') value = await newLogin(request, data, env, db, cfg);
      else if (url.pathname === '/v2/recover') value = await newLogin(request, data, env, db, cfg, 'recover');
      else if (url.pathname === '/v2/login') value = await passwordLogin(request, data, env, db);
      else if (url.pathname === '/v2/account/setup') value = await setupAccount(request, data, bearer(request), env, db);
      else if (/^\/v2\/registration\/[\w-]{43}$/.test(url.pathname)) value = await poll(url.pathname.split('/').pop(), bearer(request), data, db);
      else if (url.pathname === '/v1/session/check') value = await checkSession(bearer(request), data, env, db);
      else if (url.pathname === '/v1/session/logout') {
        await db.prepare('DELETE FROM sessions WHERE key_hash=?').bind(await hash(bearer(request))).run();
        value = { status: 'signed_out' };
      } else throw new AccessError(404, 'Страница не найдена.');
      return response(value);
    } catch (error) {
      const safe = error instanceof AccessError ? error : new AccessError(503, 'Сервис временно недоступен.');
      return response(isCallback ? safe.message : { error: safe.message,...safe.details }, safe.status, isCallback);
    }
  },
  async scheduled(_controller, env, _ctx) { await cleanup(env); },
};
