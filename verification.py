"""Optional Linux Netflix checker: isolated VPN proxy, persistent Chrome profile.

An advancing video on the selected /watch/ route is required for success.
Missing DRM, ambiguous search, login and network failures remain unverified.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import sys
import time
import unicodedata
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parent
STATE = ROOT / '.verify-state'
VPN_ENV = ROOT / '.env.verify'
PROJECT = 'where2watch-verify-' + hashlib.sha256(str(ROOT).encode()).hexdigest()[:8]
COUNTRY_NAMES = {
    'CA':'Canada', 'US':'United States', 'GB':'United Kingdom', 'DE':'Germany',
    'FR':'France', 'NL':'Netherlands', 'JP':'Japan', 'AU':'Australia', 'AT':'Austria',
    'CH':'Switzerland', 'BE':'Belgium', 'ES':'Spain', 'IT':'Italy', 'BR':'Brazil',
    'MX':'Mexico', 'IN':'India', 'SE':'Sweden', 'NO':'Norway', 'DK':'Denmark',
    'FI':'Finland', 'PL':'Poland', 'PT':'Portugal', 'NZ':'New Zealand', 'KR':'South Korea',
    'IE':'Ireland', 'ZA':'South Africa', 'TR':'Turkey', 'CZ':'Czech Republic',
}
LABELS = {'playable':'Wiedergabe bestätigt', 'not_found':'Titel nicht gefunden',
          'vpn_blocked':'VPN von Netflix blockiert', 'login_required':'Anmeldung nötig',
          'region_mismatch':'VPN-Land nicht bestätigt', 'unverified':'Nicht überprüfbar',
          'vpn_error':'VPN-Verbindung fehlgeschlagen', 'unsupported_country':'Land noch nicht angebunden'}


def read_local_settings():
    if not VPN_ENV.exists():
        raise ValueError('VPN-Einrichtung fehlt. Starte bash scripts/setup-verification.sh.')
    if VPN_ENV.stat().st_mode & 0o077:
        raise ValueError('.env.verify muss nur für dich lesbar sein: chmod 600 .env.verify')
    settings = {}
    for line in VPN_ENV.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, separator, value = line.partition('=')
            if separator:
                settings[key.strip()] = value
    return settings


def load_settings():
    settings = read_local_settings()
    if settings.get('VPN_SERVICE_PROVIDER', 'surfshark') not in ('surfshark','nordvpn','protonvpn'):
        raise ValueError('Aktuell sind Surfshark, NordVPN und ProtonVPN über OpenVPN konfigurierbar.')
    if not settings.get('OPENVPN_USER') or not settings.get('OPENVPN_PASSWORD'):
        raise ValueError('OpenVPN-Service-Zugangsdaten fehlen in .env.verify.')
    return settings


def candidates(movie, explicit=None, limit=5):
    if explicit:
        ordered = list(dict.fromkeys(explicit))
    else:
        available = sorted({o['country'] for o in movie['offers']
                            if 'netflix' in o['provider'].casefold() and o['type'] == 'Abo'})
        ordered = ['CA'] + [c for c in available if c != 'CA']
    return ordered[:limit], ordered[limit:]


@contextmanager
def exclusive_session():
    import fcntl
    STATE.mkdir(mode=0o700, exist_ok=True)
    with (STATE / 'session.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Eine Netflix-Prüfung läuft bereits. Bitte warten.') from None
        yield


class GluetunVPN:
    """Country switching affects only this dedicated Docker project."""
    def __init__(self, settings):
        self.provider = settings.get('VPN_SERVICE_PROVIDER', 'surfshark')
        self.settings = settings
        self.started = False
        self.command = ['docker','compose','--project-name',PROJECT,'--env-file','/dev/null',
                        '--file',str(ROOT / 'deploy/compose.verify.yml')]

    def compose(self, args, country='CA', timeout=180):
        env = dict(os.environ, W2W_VPN_COUNTRY=COUNTRY_NAMES[country],
                   W2W_VPN_PROVIDER=self.provider,
                   W2W_OPENVPN_USER=self.settings.get('OPENVPN_USER', ''),
                   W2W_OPENVPN_PASSWORD=self.settings.get('OPENVPN_PASSWORD', ''))
        try:
            return subprocess.run(self.command + args, env=env, capture_output=True,
                                  text=True, timeout=timeout, check=True).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            raise ValueError('VPN-Container konnte nicht gesteuert werden. Docker-Zugriff und VPN-Einrichtung prüfen.') from None

    def connect(self, country):
        self.started = True  # Also clean up a partially started container.
        self.compose(['up','--detach','--force-recreate','vpn'],country)
        ident = self.compose(['ps','--quiet','vpn'],country)
        if not ident:
            raise ValueError('VPN-Container wurde nicht gestartet.')
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            result = subprocess.run(['docker','inspect','--format','{{.State.Health.Status}}',ident],
                                    capture_output=True,text=True,timeout=10)
            if result.returncode == 0 and result.stdout.strip() == 'healthy':
                return
            time.sleep(2)
        raise ValueError('VPN wurde innerhalb von 90 Sekunden nicht bereit.')

    def close(self):
        if self.started:
            self.compose(['down'],timeout=45)


def normalized_title(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text).casefold() if c.isalnum())


def matching_ids(cards, movie):
    names = {normalized_title(t) for t in (movie['title'], movie.get('original_title')) if t}
    matches = set()
    for card in cards:
        if any(normalized_title(name) in names for name in card['names'] if name):
            match = re.search(r'/(?:watch|title)/(\d+)', card['href'])
            if match:
                matches.add(match.group(1))
    return matches


def year_matches(texts, expected):
    years = {t.strip() for t in texts if re.fullmatch(r'\d{4}', t.strip())}
    return bool(expected) and years == {str(expected)}


def feature_length(duration, movie):
    # Reject short previews/ad clips; compare movie duration when metadata allows it.
    runtime = movie.get('runtime')
    if runtime:
        expected = runtime * 60
        return expected >= 600 and abs(duration - expected) <= max(60, expected * .1)
    return duration >= 600


def page_error(url, text):
    if '/login' in url or '/signup' in url:
        return 'login_required', 'Bitte im eigenen Prüf-Browser bei Netflix anmelden.'
    if re.search(r'[MF]7111-5059|(?:using|use|verwendest|verwendet|benutzt|scheinst).{0,100}(?:VPN|proxy|unblocker)', text, re.I | re.S):
        return 'vpn_blocked', 'Netflix meldet eine VPN-/Proxy-Sperre.'
    return None


class NetflixBrowser:
    @staticmethod
    def validate_runtime(headless=False):
        try:
            import playwright.sync_api
        except ImportError:
            raise ValueError('Prüf-Abhängigkeit fehlt: pip install -r requirements-verify.txt') from None
        if not headless and not (os.getenv('DISPLAY') or os.getenv('WAYLAND_DISPLAY')):
            raise ValueError('Kein Linux-Desktop erreichbar. Für die Anmeldung DISPLAY bereitstellen; --headless erst nach erfolgreicher Anmeldung nutzen.')
        if not shutil.which('google-chrome') and not Path('/opt/google/chrome/chrome').exists():
            raise ValueError('Google Chrome fehlt: python -m playwright install chrome')

    def __init__(self, headless=False):
        self.validate_runtime(headless)
        from playwright.sync_api import sync_playwright
        self.playwright = sync_playwright().start()
        self.context = None
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                str(STATE / 'chrome'), channel='chrome', headless=headless,
                proxy={'server':'http://127.0.0.1:41488'},
                args=['--disable-quic','--force-webrtc-ip-handling-policy=disable_non_proxied_udp'],
                locale='en-US', viewport={'width':1280,'height':900})
            self.page = self.context.new_page()
            self.page.set_default_timeout(15000)
            self.page.set_default_navigation_timeout(45000)
        except Exception:
            try:
                if self.context is not None:
                    self.context.close()
            finally:
                self.playwright.stop()
            raise ValueError('Google Chrome konnte nicht gestartet werden. Chrome installieren und das Prüfprofil schließen.') from None

    def close(self):
        try:
            self.context.close()
        finally:
            self.playwright.stop()

    def location(self):
        # This page uses the same browser proxy as the Netflix playback page.
        response = self.page.goto('https://api.country.is', wait_until='domcontentloaded')
        if response is None or not response.ok:
            raise ValueError('Das Ausgangsland des Prüf-Browsers konnte nicht ermittelt werden.')
        return response.json()

    def probe(self, movie):
        page = self.page
        page.goto('https://www.netflix.com/search?q=' + quote(movie['title']), wait_until='domcontentloaded')
        page.wait_for_timeout(2500)
        error = page_error(page.url, page.locator('body').inner_text())
        if error:
            return dict(status=error[0], note=error[1])
        if page.locator('.profile-gate-label:visible').count():
            return dict(status='login_required', note='Bitte im Prüf-Browser ein Netflix-Profil auswählen.')
        # Do not count recommendations or approximate titles as a match.
        cards = page.locator('.title-card').evaluate_all('''cards => cards.map(card => ({
          href: card.querySelector('a[href]')?.href || '',
          names: [...card.querySelectorAll('img[alt], .fallback-text, [aria-label]')].map(e => e.alt || e.getAttribute('aria-label') || e.textContent)
        }))''')
        ids = matching_ids(cards, movie)
        if not ids:
            if page.locator('[data-uia="search-no-results"], .noResults').count():
                return dict(status='not_found', note='Netflix zeigt ausdrücklich keine Suchtreffer.')
            return dict(status='unverified', note='Kein eindeutiger Titel gefunden. Suchlayout, Übersetzung oder verzögertes Laden können die Ursache sein.')
        if len(ids) != 1:
            return dict(status='unverified', note='Mehrere gleichnamige Netflix-Titel; keine automatische Wiedergabe gestartet.')
        ident = ids.pop()
        # A remake can share the same title: establish the release/start year too.
        page.goto(f'https://www.netflix.com/title/{ident}', wait_until='domcontentloaded')
        page.wait_for_timeout(1500)
        error = page_error(page.url, page.locator('body').inner_text())
        if error:
            return dict(status=error[0], note=error[1], netflix_id=ident)
        years = page.locator('[data-uia="videoMetadata--year"], .year, .item-year, .release-year, .title-year').all_text_contents()
        if not year_matches(years, movie.get('year')):
            return dict(status='unverified', note='Erscheinungsjahr/Serienstart konnte dem gesuchten Titel nicht eindeutig zugeordnet werden.', netflix_id=ident)
        page.goto(f'https://www.netflix.com/watch/{ident}', wait_until='domcontentloaded')
        deadline = time.monotonic() + 45
        baseline = None
        while time.monotonic() < deadline:
            error = page_error(page.url, page.locator('body').inner_text())
            if error:
                return dict(status=error[0], note=error[1], netflix_id=ident)
            videos = page.locator('video').evaluate_all('''vs => vs.filter(v => {
              const r = v.getBoundingClientRect(); return r.width > 200 && r.height > 100;
            }).map(v => ({time:v.currentTime, paused:v.paused, ready:v.readyState, duration:Number.isFinite(v.duration) ? v.duration : 0}))''')
            watch = re.fullmatch(r'/watch/(\d+)', urlparse(page.url).path)
            # Netflix may redirect a series ID to its first episode ID.
            on_target = watch is not None and (movie['series'] or watch.group(1) == ident)
            # Multiple visible videos could include an unrelated preview: stay conservative.
            if on_target and len(videos) == 1 and not videos[0]['paused'] and videos[0]['ready'] >= 2 and feature_length(videos[0]['duration'], movie):
                current = videos[0]['time']
                now = time.monotonic()
                if baseline is None or current < baseline[0]:
                    baseline = current, now
                elif current - baseline[0] >= 5 and now - baseline[1] >= 5:
                    page.locator('video').evaluate_all('vs => vs.forEach(v => v.pause())')
                    return dict(status='playable', note='Videowiedergabe hat mindestens fünf Sekunden fortgeschritten.', netflix_id=ident, playback_id=watch.group(1))
            else:
                baseline = None
            page.wait_for_timeout(1000)
        return dict(status='unverified', note='Wiedergabe nicht bestätigt. DRM, Profilwahl, Konto, Autoplay oder Playerfehler prüfen.', netflix_id=ident)


def run_checks(movie, countries, vpn, browser_factory, progress=None):
    results = []
    for code in countries:
        if progress:
            progress(f'{code}: VPN verbinden und Netflix prüfen …')
        record = {'country':code,'vpn_provider':vpn.provider,
                  'started_at':datetime.now(timezone.utc).isoformat(timespec='seconds')}
        browser = None
        stage = 'vpn'
        try:
            if code not in COUNTRY_NAMES:
                record.update(status='unsupported_country',note='Für diesen Ländercode fehlt die VPN-Länderzuordnung.')
            else:
                vpn.connect(code)
                stage = 'browser'
                browser = browser_factory()
                geo = browser.location()
                record['observed_country'] = geo.get('country')
                record['public_ip'] = geo.get('ip')
                if geo.get('country') != code:
                    record.update(status='region_mismatch',note='Der Prüf-Browser meldet ein anderes Ausgangsland. Netflix wurde nicht getestet.')
                else:
                    record.update(browser.probe(movie))
        except ValueError as error:
            record.update(status='vpn_error' if stage == 'vpn' else 'unverified',note=str(error))
        except Exception:
            record.update(status='vpn_error' if stage == 'vpn' else 'unverified',note='Browser-/Netzwerkprüfung fehlgeschlagen; keine Aussage zur Verfügbarkeit.')
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    record['cleanup_note'] = 'Browser konnte nicht sauber geschlossen werden.'
        record['checked_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        results.append(record)
        if progress:
            progress(f'{code}: {LABELS[record["status"]]} · {record["note"]}')
        if record.get('cleanup_note') or record['status'] in ('playable','login_required'):
            break
    return results


def verify(movie, explicit=None, limit=5, headless=False):
    settings = load_settings()
    NetflixBrowser.validate_runtime(headless)
    selected, remaining = candidates(movie, explicit, limit)
    with exclusive_session():
        vpn = GluetunVPN(settings)
        cleanup_error = None
        try:
            results = run_checks(movie, selected, vpn, lambda: NetflixBrowser(headless),
                                 progress=lambda message: print(message, file=sys.stderr, flush=True))
        finally:
            try:
                vpn.close()
            except ValueError:
                cleanup_error = 'VPN-Container konnte nicht beendet werden. ./where2watch --verify-stop ausführen.'
        attempted = {r['country'] for r in results}
        report = {'results':results,'not_checked':[c for c in selected if c not in attempted] + remaining,
                  'cleanup_error':cleanup_error,
                  'scope':'Momentaufnahme für diesen VPN-Ausgang und dieses Netflix-Konto; IP-Land laut country.is.'}
        path = STATE / f'{"tv" if movie["series"] else "movie"}-{movie["id"]}-{time.time_ns()}.json'
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor,'w') as file:
            json.dump(dict(movie_id=movie['id'],title=movie['title'],**report),file,ensure_ascii=False,indent=2)
        report['report_path'] = str(path)
        return report


def login():
    settings = load_settings()
    NetflixBrowser.validate_runtime()
    with exclusive_session():
        vpn = GluetunVPN(settings)
        browser = None
        try:
            vpn.connect('CA')
            browser = NetflixBrowser()
            if browser.location().get('country') != 'CA':
                raise ValueError('Kanadischer VPN-Ausgang konnte nicht bestätigt werden.')
            browser.page.goto('https://www.netflix.com/login',wait_until='domcontentloaded')
            input('Im geöffneten Chrome anmelden und ein Profil auswählen. Danach hier Enter drücken: ')
            if '/browse' not in browser.page.url or browser.page.locator('.profile-gate-label:visible').count():
                raise ValueError('Netflix-Anmeldung/Profilwahl wurde noch nicht bestätigt.')
            print('Netflix-Prüfprofil gespeichert. Die VPN-Verbindung wird beendet.')
        finally:
            try:
                if browser is not None:
                    browser.close()
            finally:
                vpn.close()


def stop():
    with exclusive_session():
        vpn = GluetunVPN({})
        vpn.started = True
        vpn.close()
    print('Der eigene Prüf-VPN wurde beendet.')
