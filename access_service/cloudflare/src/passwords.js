import { AccessError } from './errors.js';
const encoder = new TextEncoder();
const hex = bytes => [...new Uint8Array(bytes)].map(b => b.toString(16).padStart(2, '0')).join('');
const unhex = text => Uint8Array.from(text.match(/../g), b => parseInt(b, 16));
const ITERATIONS = 100000; // workerd WebCrypto limit; pepper is stored outside D1.

export function username(value) {
  if (typeof value !== 'string' || !/^[a-zA-Z][a-zA-Z0-9_.-]{2,31}$/.test(value)) {
    throw new AccessError(400, 'Логин: 3–32 латинских символа, первая буква; разрешены цифры, точка, _ и -.');
  }
  return value.toLowerCase();
}
export function password(value) {
  if (typeof value !== 'string' || [...value].length < 12 || [...value].length > 128 || encoder.encode(value).length > 512) {
    throw new AccessError(400, 'Пароль должен содержать от 12 до 128 символов.');
  }
  return value;
}
async function derive(value, salt, pepper) {
  if (typeof pepper !== 'string' || pepper.length < 43) throw new AccessError(503, 'Сервис аккаунтов ещё не настроен.');
  const key = await crypto.subtle.importKey('raw', encoder.encode(value), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: unhex(salt), iterations: ITERATIONS }, key, 256);
  const secret = await crypto.subtle.importKey('raw', encoder.encode(pepper), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return hex(await crypto.subtle.sign('HMAC', secret, bits));
}
export async function digest(value, pepper) {
  password(value);
  const salt = hex(crypto.getRandomValues(new Uint8Array(32)));
  return `pbkdf2-sha256:${ITERATIONS}:${salt}:${await derive(value, salt, pepper)}`;
}
export async function verify(value, stored, pepper) {
  const parts = /^pbkdf2-sha256:100000:([a-f0-9]{64}):([a-f0-9]{64})$/.exec(stored || '');
  const candidate = await derive(value, parts?.[1] || '00'.repeat(32), pepper);
  const expected = parts?.[2] || '00'.repeat(32);
  let different = parts ? 0 : 1;
  for (let i = 0; i < expected.length; i++) different |= expected.charCodeAt(i) ^ candidate.charCodeAt(i);
  return different === 0;
}
