"""Name-first terminal interface. Python standard library only; no web server needed."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import sys
import textwrap
from urllib.error import HTTPError, URLError

from server import server as catalog

COUNTRIES = {
    'DE': 'Deutschland', 'AT': 'Österreich', 'CH': 'Schweiz', 'US': 'USA',
    'GB': 'Großbritannien', 'CA': 'Kanada', 'FR': 'Frankreich', 'NL': 'Niederlande',
    'JP': 'Japan', 'AU': 'Australien', 'BE': 'Belgien', 'ES': 'Spanien',
    'IT': 'Italien', 'BR': 'Brasilien', 'MX': 'Mexiko', 'IN': 'Indien',
    'SE': 'Schweden', 'NO': 'Norwegen', 'DK': 'Dänemark', 'FI': 'Finnland',
    'PL': 'Polen', 'PT': 'Portugal', 'NZ': 'Neuseeland', 'KR': 'Südkorea',
    'IE': 'Irland', 'ZA': 'Südafrika', 'TR': 'Türkei', 'CZ': 'Tschechien',
}
TYPES = {'Abo': 'Im Abo', 'Kostenlos': 'Kostenlos', 'Mit Werbung': 'Mit Werbung',
         'Leihen': 'Leihen', 'Kaufen': 'Kaufen'}
DEMO_PATH = Path(__file__).resolve().parent / 'data/demo.json'


def safe(value):
    """Avoid terminal control sequences from external metadata."""
    return ''.join(c for c in str(value) if c.isprintable() or c == '\n')


def country_codes(value):
    codes = [c.strip().upper() for c in value.split(',')]
    if not all(re.fullmatch('[A-Z]{2}', c) for c in codes):
        raise argparse.ArgumentTypeError('Länder als zweistellige Codes angeben, z. B. DE,US,CA.')
    return codes


def parser():
    p = argparse.ArgumentParser(
        prog='where2watch', description='Film oder Serie suchen und Streamingangebote weltweit vergleichen.',
        epilog='Beispiele: ./where2watch Interstellar | ./where2watch --demo Dune --abo --country US,CA')
    p.add_argument('name', nargs='*', help='Film- oder Serienname (auch ohne Anführungszeichen)')
    p.add_argument('--demo', action='store_true', help='Explizit mit erfundenen Beispielangeboten ausprobieren')
    p.add_argument('--country', type=country_codes, default=[], metavar='DE,US', help='Auf Länder einschränken; standardmäßig alle gemeldeten Länder')
    p.add_argument('--provider', action='append', default=[], metavar='NAME', help='Anbieter filtern; mehrfach möglich, z. B. --provider Netflix')
    p.add_argument('--abo', action='store_true', help='Nur im Abo enthaltene Angebote')
    p.add_argument('--type', choices=['all', 'movie', 'tv'], default='all', help='Filme oder Serien auswählen')
    p.add_argument('--year', type=int, metavar='JAHR', help='Erscheinungsjahr bzw. Serienstart')
    p.add_argument('--pick', type=int, metavar='N', help='Treffer N auswählen; hilfreich für Skripte')
    p.add_argument('--json', action='store_true', help='Ergebnis als JSON; keine interaktiven Auswahlfragen')
    return p


def search(query, demo=False, kind='all', year=None):
    if demo:
        items = json.loads(DEMO_PATH.read_text(encoding='utf-8'))
        matches = [m for m in items if query.casefold() in m['title'].casefold()]
    else:
        response = catalog.tmdb('search/multi', query=query)
        matches = [dict(m, series=m['media_type'] == 'tv',
                        title=m.get('title') or m.get('name', ''),
                        year=(m.get('release_date') or m.get('first_air_date') or '')[:4])
                   for m in response.get('results', []) if m.get('media_type') in ('movie', 'tv')]
    return [m for m in matches
            if (kind == 'all' or m['series'] == (kind == 'tv'))
            and (year is None or m.get('year') == str(year))]


def details(match, demo=False):
    if demo:
        return dict(match)
    kind = 'tv' if match['series'] else 'movie'
    raw = catalog.tmdb(f'{kind}/{match["id"]}', append_to_response='credits')
    result = catalog.normalize(raw, kind)
    credits = raw.get('credits', {})
    result.update(
        original_title=raw.get('original_title') or raw.get('original_name'),
        genres=[g['name'] for g in raw.get('genres', [])],
        runtime=raw.get('runtime'),
        episode_runtime=raw.get('episode_run_time', []),
        seasons=raw.get('number_of_seasons'), episodes=raw.get('number_of_episodes'),
        status=raw.get('status'), release_date=raw.get('release_date') or raw.get('first_air_date'),
        languages=[s.get('english_name') or s.get('name') for s in raw.get('spoken_languages', [])],
        cast=[c['name'] for c in credits.get('cast', [])[:8]],
        creators=([p['name'] for p in raw.get('created_by', [])] if kind == 'tv'
                  else [p['name'] for p in credits.get('crew', []) if p.get('job') == 'Director']),
        tmdb_url=f'https://www.themoviedb.org/{kind}/{match["id"]}',
    )
    return result


def filter_offers(offers, countries, providers, abo):
    return [o for o in offers
            if (not countries or o['country'] in countries)
            and (not providers or any(p.casefold() in o['provider'].casefold() for p in providers))
            and (not abo or o['type'] == 'Abo')]


def choose(matches, pick, interactive, query, output):
    if pick is not None:
        if 1 <= pick <= len(matches):
            return matches[pick - 1]
        raise ValueError(f'--pick muss zwischen 1 und {len(matches)} liegen.')
    if len(matches) == 1:
        return matches[0]
    print(f'Mehrere Treffer für „{safe(query)}“:', file=output)
    for i, m in enumerate(matches, 1):
        print(f'  {i:2}. {safe(m["title"])} ({m.get("year") or "Jahr unbekannt"}) · '
              f'{"Serie" if m["series"] else "Film"}', file=output)
    if not interactive:
        raise ValueError('Bitte den gewünschten Treffer mit --pick N auswählen.')
    while True:
        answer = input(f'Welcher Titel? [1–{len(matches)}, q beendet] ').strip()
        if answer.casefold() in ('q', 'quit', 'exit'):
            raise KeyboardInterrupt
        if answer.isdigit() and 1 <= int(answer) <= len(matches):
            return matches[int(answer) - 1]
        print('Bitte eine gültige Nummer eingeben.', file=output)


def render(result, stream):
    width = max(40, min(shutil.get_terminal_size((96, 24)).columns, 110))
    color = stream.isatty()
    def heading(text):
        print(f'\033[1;38;2;163;245;205m{safe(text)}\033[0m' if color else safe(text), file=stream)
    def line(label, value):
        if value:
            print(textwrap.fill(f'{label}: {safe(value)}', width, subsequent_indent='  '), file=stream)
    def section(text):
        print(file=stream)
        heading(text)
    movie = result['movie']
    heading('where2watch · Dein Film. Deine Welt.')
    if result['mode'] == 'demo':
        print('DEMO · Erfundenes Beispielangebot, keine bestätigte Verfügbarkeit.', file=stream)
    section(f'{movie["title"]} ({movie.get("year") or "Jahr unbekannt"})')
    line('Typ', 'Serie' if movie['series'] else 'Film')
    line('Originaltitel', movie.get('original_title'))
    line('Genres', ', '.join(movie.get('genres') or [movie.get('genre', '')]))
    line('Bewertung (TMDB)', f'{movie["rating"]}/10' if movie.get('rating') else 'Noch keine Bewertung')
    line('Veröffentlichung', movie.get('release_date'))
    line('Laufzeit', f'{movie["runtime"]} Minuten' if movie.get('runtime') else None)
    line('Episodenlaufzeit', ', '.join(str(n) for n in movie.get('episode_runtime', [])) + ' Minuten' if movie.get('episode_runtime') else None)
    line('Staffeln / Episoden', f'{movie.get("seasons", "?")} / {movie.get("episodes", "?")}' if movie.get('seasons') else None)
    line('Status', movie.get('status'))
    line('Originalsprachen', ', '.join(movie.get('languages', [])))
    line('Schöpfer' if movie['series'] else 'Regie', ', '.join(movie.get('creators', [])))
    line('Besetzung', ', '.join(movie.get('cast', [])))
    section('Beschreibung')
    print(textwrap.fill(safe(movie['overview']), width), file=stream)
    offers = movie['offers']
    regions = sorted({o['country'] for o in offers}, key=lambda c: COUNTRIES.get(c, c))
    section(f'Streamingangebote · {len(regions)} Länder')
    if not offers:
        print('Keine gemeldeten Angebote für diese Auswahl. Das bestätigt keine weltweite Nichtverfügbarkeit.', file=stream)
    for code in regions:
        heading(f'{COUNTRIES.get(code, code)} [{code}]')
        seen = set()
        links = set()
        for offer in (o for o in offers if o['country'] == code):
            item = (offer['provider'], offer['type'])
            if item not in seen:
                print(textwrap.fill(f'  {safe(offer["provider"])} · {TYPES.get(offer["type"], offer["type"])}', width, subsequent_indent='    '), file=stream)
                seen.add(item)
            if offer.get('link'):
                links.add(offer['link'])
        for link in sorted(links):
            print(f'  Angebotsübersicht: {safe(link)}', file=stream)
        print(file=stream)
    line('TMDB', movie.get('tmdb_url'))
    print(f'Abfrage: {result["queried_at"]}', file=stream)
    if result['mode'] == 'live':
        print('Filmdaten: TMDB · Streamingdaten: JustWatch via TMDB', file=stream)
        print('This product uses the TMDB API but is not endorsed or certified by TMDB.', file=stream)
    print('Landesverfügbarkeit bestätigt keinen Zugriff mit einem bestimmten VPN oder Konto.', file=stream)
    if movie.get('languages'):
        print('Filmdaten-Sprachen sind keine Aussage über Tonspuren beim Streaminganbieter.', file=stream)


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    query = ' '.join(args.name).strip()
    interactive = sys.stdin.isatty() and not args.json
    try:
        if not query:
            if not interactive:
                p.error('Bitte einen Film- oder Seriennamen angeben.')
            query = input('Welchen Film oder welche Serie suchst du? ').strip()
            if not query:
                raise ValueError('Bitte einen Namen eingeben.')
        if not args.demo and not catalog.TOKEN:
            raise ValueError('TMDB_READ_ACCESS_TOKEN fehlt. Für echte Daten als Umgebungsvariable setzen; '
                             'zum Ausprobieren: ./where2watch --demo Interstellar')
        matches = search(query, args.demo, args.type, args.year)
        if not matches:
            print(f'Keine Treffer für „{safe(query)}“' + (' im Demo-Katalog.' if args.demo else '.'), file=sys.stderr)
            return 1
        selected = choose(matches, args.pick, interactive, query, sys.stderr)
        movie = details(selected, args.demo)
        movie['offers'] = filter_offers(movie['offers'], args.country, args.provider, args.abo)
        result = {'mode': 'demo' if args.demo else 'live', 'query': query,
                  'queried_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                  'filters': {'countries': args.country, 'providers': args.provider, 'subscription_only': args.abo},
                  'movie': movie}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            render(result, sys.stdout)
        return 0
    except HTTPError as error:
        message = {401: 'TMDB-Token ist ungültig oder abgelaufen.', 403: 'TMDB-Zugriff wurde verweigert.',
                   429: 'TMDB-Anfragelimit erreicht. Bitte später erneut versuchen.'}.get(error.code, f'TMDB ist gerade nicht erreichbar (HTTP {error.code}).')
        print(f'Fehler: {message}', file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0
    except (URLError, TimeoutError, ConnectionError):
        print('Fehler: TMDB konnte nicht erreicht werden. Bitte Verbindung prüfen und erneut versuchen.', file=sys.stderr)
        return 2
    except ValueError as error:
        print(f'Fehler: {safe(error)}', file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print('\nAbgebrochen.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
