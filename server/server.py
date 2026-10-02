#!/usr/bin/env python3
"""Same-origin Flutter host and TMDB adapter. API credentials stay on the server."""
import concurrent.futures
import functools
import json
import os
import time
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = os.getenv('TMDB_READ_ACCESS_TOKEN', '')
CACHE = {}
GENRES = {28:'Action',12:'Abenteuer',16:'Animation',35:'Komödie',80:'Krimi',99:'Dokumentation',18:'Drama',10751:'Familie',14:'Fantasy',27:'Horror',10749:'Romantik',878:'Science-Fiction',53:'Thriller',10765:'Sci-Fi & Fantasy'}


def tmdb(path, **params):
    params.setdefault('language', 'de-DE')
    url = 'https://api.themoviedb.org/3/' + path + '?' + urllib.parse.urlencode(params)
    cached = CACHE.get(url)
    if cached and time.monotonic() - cached[0] < 21600:
        return cached[1]
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + TOKEN, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.load(response)
    CACHE[url] = (time.monotonic(), data)
    return data


def normalize(item, kind, include_offers=True):
    offers = []
    if include_offers:
        regions = tmdb(f'{kind}/{item["id"]}/watch/providers').get('results', {})
        for country, data in regions.items():
            for api_type, display in [('flatrate','Abo'),('free','Kostenlos'),('ads','Mit Werbung'),('rent','Leihen'),('buy','Kaufen')]:
                for provider in data.get(api_type, []):
                    name = provider['provider_name']
                    name = {'Amazon Prime Video':'Prime Video','Amazon Prime Video with Ads':'Prime Video','Disney Plus':'Disney+','Apple TV Plus':'Apple TV+'}.get(name,name)
                    offers.append({'country': country, 'provider': name, 'type': display, 'link': data.get('link')})
    genres = item.get('genre_ids') or [g['id'] for g in item.get('genres', [])]
    return {'id': item['id'], 'title': item.get('title') or item.get('name',''), 'year': (item.get('release_date') or item.get('first_air_date') or '')[:4], 'genre': GENRES.get(genres[0], 'Film' if kind == 'movie' else 'Serie') if genres else 'Film' if kind == 'movie' else 'Serie', 'overview': item.get('overview') or 'Für diesen Titel ist noch keine Beschreibung verfügbar.', 'rating': round(item.get('vote_average', 0),1), 'series': kind == 'tv', 'poster': 'https://image.tmdb.org/t/p/w500'+item['poster_path'] if item.get('poster_path') else '', 'offers': offers}


class Handler(SimpleHTTPRequestHandler):
    def json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith('/api/'):
            return super().do_GET()
        params = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == '/api/catalog':
                if not TOKEN:
                    return self.json_response({'mode':'demo', 'movies':[]})
                q = params.get('q', [''])[0].strip()[:150]
                data = tmdb('search/multi', query=q) if q else tmdb('trending/all/week')
                items = [m for m in data.get('results',[]) if m.get('media_type') in ('movie','tv')][:20]
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    movies = list(pool.map(lambda m: normalize(m,m['media_type']), items))
                return self.json_response({'mode':'live','movies':movies})
            if parsed.path == '/api/title' and TOKEN:
                kind = params.get('type',['movie'])[0]
                ident = params.get('id',[''])[0]
                if kind not in ('movie','tv') or not ident.isdigit():
                    return self.json_response({'error':'Invalid title'},400)
                return self.json_response(normalize(tmdb(f'{kind}/{ident}'),kind))
            return self.json_response({'error':'Not found'},404)
        except Exception:
            return self.json_response({'error':'Streaming data temporarily unavailable'},502)


if __name__ == '__main__':
    port = int(os.getenv('PORT','8096'))
    handler = functools.partial(Handler, directory=str(ROOT / 'build/web'))
    print(f'where2watch: http://127.0.0.1:{port} ({"live" if TOKEN else "demo"})', flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),handler).serve_forever()
