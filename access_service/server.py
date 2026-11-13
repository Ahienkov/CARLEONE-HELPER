"""WSGI Discord account service. Run behind HTTPS with one worker, multiple threads.

Only account identifiers and hashes of device-session keys are persisted. Discord
OAuth credentials remain on this server; users' OAuth tokens are not persisted.
"""
import base64
import hashlib
import html
import json
import os
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

GUILD_ID = '1569352173043589263'
ROLE_ID = '1569352648308686888'
SCOPE = 'identify guilds.members.read'


class AccessError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Config:
    public_url: str
    client_id: str
    client_secret: str
    bot_token: str
    database: str

    def __post_init__(self):
        url = urlparse(self.public_url)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ('', '/')):
            raise ValueError('ACCESS_PUBLIC_URL must be an HTTPS origin')
        if not self.client_id.isdecimal() or not self.client_secret or not self.bot_token:
            raise ValueError('Discord application credentials and bot token are required')

    @property
    def callback(self):
        return self.public_url.rstrip('/') + '/oauth/callback'


class DiscordAPI:
    def __init__(self, config):
        self.config = config

    def request(self, method, url, **kwargs):
        try:
            response = requests.request(method, url, timeout=(5, 15), allow_redirects=False, **kwargs)
        except requests.RequestException:
            raise AccessError(503, 'Discord временно недоступен. Повторите проверку.') from None
        if response.status_code == 429 or response.status_code >= 500:
            raise AccessError(503, 'Discord временно недоступен. Повторите проверку.')
        if not 200 <= response.status_code < 300:
            raise AccessError(403, 'Discord не подтвердил доступ. Войдите снова и проверьте роль «Участник».')
        try:
            return response.json()
        except ValueError:
            raise AccessError(503, 'Discord вернул некорректный ответ.') from None

    def exchange(self, code, verifier):
        token = self.request('POST', 'https://discord.com/api/v10/oauth2/token',
                             auth=(self.config.client_id, self.config.client_secret),
                             data=dict(grant_type='authorization_code', code=code,
                                       redirect_uri=self.config.callback, code_verifier=verifier))
        if not set(SCOPE.split()).issubset(token.get('scope', '').split()):
            raise AccessError(403, 'Для подтверждения аккаунта нужны разрешения профиля и проверки роли.')
        if not isinstance(token.get('access_token'), str) or not token['access_token']:
            raise AccessError(503, 'Discord не вернул подтверждение входа.')
        bearer = {'Authorization': 'Bearer ' + token['access_token']}
        user = self.request('GET', 'https://discord.com/api/v10/users/@me', headers=bearer)
        member = self.request('GET', f'https://discord.com/api/v10/users/@me/guilds/{GUILD_ID}/member', headers=bearer)
        require_role(member)
        return user

    def check_member(self, user_id):
        # Bot credentials stay on the service. This avoids retaining users'
        # Discord refresh tokens for future membership checks.
        try:
            response = requests.get(f'https://discord.com/api/v10/guilds/{GUILD_ID}/members/{user_id}',
                                    headers={'Authorization': 'Bot ' + self.config.bot_token},
                                    timeout=(5, 15), allow_redirects=False)
        except requests.RequestException:
            raise AccessError(503, 'Не удалось проверить роль. Повторите проверку.') from None
        if response.status_code == 404:
            raise AccessError(403, 'Для доступа вступите в CARLEONE HELPER и получите роль «Участник».')
        if response.status_code != 200:
            # Invalid/missing bot privileges are service failures, not a reason
            # to delete a legitimate user's persistent session.
            raise AccessError(503, 'Проверка роли временно недоступна.')
        require_role(response.json())


def require_role(member):
    if ROLE_ID not in member.get('roles', []) or member.get('pending'):
        raise AccessError(403, 'Для доступа нужна роль «Участник» на сервере CARLEONE HELPER.')


class Accounts:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as database:
            database.executescript('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY, discord_id TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL, created_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    key_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL,
                    install_id TEXT NOT NULL, release_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL, last_seen INTEGER NOT NULL,
                    FOREIGN KEY(account_id) REFERENCES accounts(id));
            ''')

    @contextmanager
    def connect(self):
        database = sqlite3.connect(self.path, timeout=15)
        database.row_factory = sqlite3.Row
        try:
            with database:
                yield database
        finally:
            database.close()

    def create_session(self, user, install_id, release_id):
        user_id = user.get('id', '')
        if not user_id.isdecimal():
            raise AccessError(503, 'Некорректный профиль Discord.')
        name = user.get('global_name') or user.get('username') or user_id
        now = int(time.time())
        with self.connect() as database:
            database.execute('INSERT INTO accounts VALUES (?, ?, ?, ?) ON CONFLICT(discord_id) '
                             'DO UPDATE SET display_name=excluded.display_name',
                             (secrets.token_urlsafe(24), user_id, name, now))
            account = dict(database.execute('SELECT * FROM accounts WHERE discord_id=?', (user_id,)).fetchone())
            # One active credential per installation; a new login replaces the old one.
            database.execute('DELETE FROM sessions WHERE account_id=? AND install_id=?', (account['id'], install_id))
            key = secrets.token_urlsafe(48)
            database.execute('INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?)',
                             (digest(key), account['id'], install_id, release_id, now, now))
        return key, account

    def session(self, key, install_id, release_id):
        with self.connect() as database:
            row = database.execute('SELECT accounts.*, sessions.install_id, sessions.release_id '
                                   'FROM sessions JOIN accounts ON accounts.id=sessions.account_id '
                                   'WHERE key_hash=?', (digest(key),)).fetchone()
        if not row or not secrets.compare_digest(row['install_id'], install_id) or row['release_id'] != release_id:
            raise AccessError(401, 'Войдите в аккаунт хелпера после обновления или переустановки.')
        return dict(row)

    def revoke(self, key):
        with self.connect() as database:
            database.execute('DELETE FROM sessions WHERE key_hash=?', (digest(key),))

    def touch(self, key):
        with self.connect() as database:
            database.execute('UPDATE sessions SET last_seen=? WHERE key_hash=?', (int(time.time()), digest(key)))


class Service:
    def __init__(self, config, discord=None, clock=time.time):
        self.config = config
        self.discord = discord or DiscordAPI(config)
        self.accounts = Accounts(config.database)
        self.clock = clock
        self.lock = threading.Lock()
        self.logins = {}
        self.states = {}
        self.starts = {}

    def prune(self):
        now = self.clock()
        for key in [key for key, value in self.logins.items() if value['expires'] <= now]:
            self.logins.pop(key)
        self.states = {state: key for state, key in self.states.items() if key in self.logins}
        self.starts = {ip: times for ip, times in self.starts.items() if times[-1] > now - 60}

    def new_login(self, data, ip):
        install, release = identity(data)
        with self.lock:
            self.prune()
            times = [t for t in self.starts.get(ip, []) if t > self.clock() - 60]
            if len(times) >= 10 or len(self.logins) >= 2000:
                raise AccessError(429, 'Слишком много попыток входа. Подождите минуту.')
            self.starts[ip] = times + [self.clock()]
            login_id, secret, state, verifier = [secrets.token_urlsafe(32) for _ in range(4)]
            self.logins[login_id] = dict(secret_hash=digest(secret), state=state, verifier=verifier,
                                         install_id=install, release_id=release,
                                         expires=self.clock() + 600, status='pending', last_poll=0)
            self.states[state] = login_id
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        params = dict(client_id=self.config.client_id, response_type='code', scope=SCOPE,
                      redirect_uri=self.config.callback, state=state,
                      code_challenge=challenge, code_challenge_method='S256')
        return dict(login_id=login_id, polling_secret=secret, expires_in=600,
                    browser_url='https://discord.com/oauth2/authorize?' + urlencode(params))

    def callback(self, query):
        with self.lock:
            self.prune()
            login_id = self.states.pop(query.get('state', ''), None)
            if not login_id:
                raise AccessError(400, 'Ссылка входа недействительна или уже использована.')
            login = self.logins[login_id]
            login['status'] = 'checking'
        try:
            if query.get('error') or not query.get('code'):
                raise AccessError(403, 'Вход через Discord отменён.')
            if query.get('iss', 'https://discord.com') != 'https://discord.com':
                raise AccessError(400, 'Неверный источник авторизации.')
            user = self.discord.exchange(query['code'], login['verifier'])
            self.discord.check_member(user['id'])
            with self.lock:
                login.update(status='ready', user=user)
        except AccessError as error:
            with self.lock:
                login.update(status='denied', message=error.message)
            raise
        return 'Аккаунт подтверждён. Вернитесь в хелпер. Эту вкладку можно закрыть.'

    def poll(self, login_id, key):
        with self.lock:
            self.prune()
            login = self.logins.get(login_id)
            if not login or not secrets.compare_digest(digest(key), login['secret_hash']):
                raise AccessError(401, 'Ссылка входа истекла. Начните вход заново.')
            if self.clock() - login['last_poll'] < 2:
                raise AccessError(429, 'Подождите перед повторной проверкой.')
            login['last_poll'] = self.clock()
            if login['status'] == 'denied':
                self.logins.pop(login_id)
                raise AccessError(403, login['message'])
            if login['status'] != 'ready':
                return {'status': 'pending'}
            self.logins.pop(login_id)
        key, account = self.accounts.create_session(login['user'], login['install_id'], login['release_id'])
        return dict(status='authorized', session_key=key, account=public_account(account),
                    guild_id=GUILD_ID, role_id=ROLE_ID)

    def check(self, key, data):
        install, release = identity(data)
        account = self.accounts.session(key, install, release)
        try:
            self.discord.check_member(account['discord_id'])
        except AccessError as error:
            if error.status == 403:
                self.accounts.revoke(key)
            raise
        self.accounts.touch(key)
        return dict(status='authorized', account=public_account(account), guild_id=GUILD_ID, role_id=ROLE_ID)

    def __call__(self, environ, start_response):
        headers = [('Cache-Control', 'no-store'), ('Referrer-Policy', 'no-referrer'),
                   ('X-Content-Type-Options', 'nosniff'), ('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")]
        status, content_type = 200, 'application/json; charset=utf-8'
        callback = environ.get('PATH_INFO') == '/oauth/callback'
        try:
            method, path = environ['REQUEST_METHOD'], environ.get('PATH_INFO', '')
            if callback and method == 'GET':
                query = {k: v[0] for k, v in parse_qs(environ.get('QUERY_STRING', ''), keep_blank_values=True).items() if len(v) == 1}
                result = self.callback(query)
            elif method == 'GET' and path == '/health':
                result = {'status': 'ok'}
            elif method == 'POST':
                if environ.get('HTTP_ORIGIN'):
                    raise AccessError(403, 'Этот запрос разрешён только из хелпера.')
                if environ.get('CONTENT_TYPE', '').split(';')[0] != 'application/json':
                    raise AccessError(400, 'Ожидается JSON.')
                try:
                    size = int(environ.get('CONTENT_LENGTH') or '0')
                    if not 0 < size <= 4096:
                        raise ValueError()
                    data = json.loads(environ['wsgi.input'].read(size))
                    if not isinstance(data, dict):
                        raise ValueError()
                except (ValueError, TypeError):
                    raise AccessError(400, 'Некорректный запрос.') from None
                header = environ.get('HTTP_AUTHORIZATION', '')
                key = header.removeprefix('Bearer ') if header.startswith('Bearer ') else ''
                if path == '/v1/login':
                    result = self.new_login(data, environ.get('REMOTE_ADDR', 'unknown'))
                elif path.startswith('/v1/login/'):
                    result = self.poll(path.rsplit('/', 1)[-1], key)
                elif path == '/v1/session/check':
                    result = self.check(key, data)
                elif path == '/v1/session/logout':
                    self.accounts.revoke(key)
                    result = {'status': 'signed_out'}
                else:
                    raise AccessError(404, 'Страница не найдена.')
            else:
                raise AccessError(404, 'Страница не найдена.')
        except AccessError as error:
            status, result = error.status, error.message if callback else {'error': error.message}
        except Exception:
            # Never expose credentials, OAuth codes, SQL or upstream responses.
            status, result = 503, 'Сервис временно недоступен.' if callback else {'error': 'Сервис временно недоступен.'}
        if callback:
            content_type = 'text/html; charset=utf-8'
            payload = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>CARLEONE HELPER</title>'
                       '<h1>CARLEONE HELPER</h1><p>' + html.escape(result) + '</p></html>').encode()
        else:
            payload = json.dumps(result, ensure_ascii=False).encode()
        from http import HTTPStatus
        start_response(f'{status} {HTTPStatus(status).phrase}', headers + [('Content-Type', content_type), ('Content-Length', str(len(payload)))])
        return [payload]


def identity(data):
    install, release = data.get('install_id', ''), data.get('release_id', '')
    if (not isinstance(install, str) or not 20 <= len(install) <= 100
            or not isinstance(release, str) or not 1 <= len(release) <= 100):
        raise AccessError(400, 'Некорректный идентификатор установки.')
    return install, release


def public_account(account):
    return {key: account[key] for key in ('id', 'discord_id', 'display_name')}


def create_application():
    return Service(Config(public_url=os.environ['ACCESS_PUBLIC_URL'], client_id=os.environ['DISCORD_CLIENT_ID'],
                          client_secret=os.environ['DISCORD_CLIENT_SECRET'], bot_token=os.environ['DISCORD_BOT_TOKEN'],
                          database=os.environ.get('ACCESS_DB_PATH', '/data/accounts.sqlite3')))
