import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'catalog.dart';

const ink = Color(0xFF101319);
const panel = Color(0xFF191E26);
const mint = Color(0xFFA3F5CD);
const muted = Color(0xFF939CA9);
void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // Keep web controls accessible to screen readers and browser automation.
  WidgetsBinding.instance.ensureSemantics();
  runApp(const Where2Watch());
}

class Where2Watch extends StatelessWidget {
  const Where2Watch({super.key, this.client});
  final http.Client? client;
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'where2watch · Dein Film. Deine Welt.',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: ink,
      colorScheme: const ColorScheme.dark(primary: mint, surface: panel),
      fontFamily: 'Inter',
      useMaterial3: true,
      textTheme: const TextTheme(
        bodyMedium: TextStyle(fontSize: 14, height: 1.5),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: panel,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
      ),
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        side: const BorderSide(color: Color(0xFF303640)),
      ),
    ),
    home: DiscoverPage(client: client),
  );
}

class DiscoverPage extends StatefulWidget {
  const DiscoverPage({super.key, this.client});
  final http.Client? client;
  @override
  State<DiscoverPage> createState() => _DiscoverPageState();
}

class _DiscoverPageState extends State<DiscoverPage> {
  List<Movie> movies = demoMovies;
  Map<String, Movie> savedMovies = {};
  Set<String> services = {}, saved = {};
  String country = 'Alle Länder',
      category = 'Alle',
      query = '',
      section = 'Entdecken';
  bool subscriptionOnly = false, live = false, loading = false;
  String? error;
  Timer? debounce;
  int request = 0;
  final searchController = TextEditingController();
  SharedPreferences? prefs;
  @override
  void initState() {
    super.initState();
    restore();
    load('');
  }

  Future<void> restore() async {
    prefs = await SharedPreferences.getInstance();
    final snapshots = prefs!.getString('savedMovies');
    if (snapshots != null) {
      try {
        savedMovies = {
          for (final m in (jsonDecode(snapshots) as List).map(
            (j) => Movie.fromJson(j),
          ))
            m.key: m,
        };
      } catch (_) {
        savedMovies = {};
      }
    }
    if (!mounted) return;
    setState(() {
      services = (prefs!.getStringList('services') ?? []).toSet();
      saved = (prefs!.getStringList('saved') ?? []).toSet();
      country = prefs!.getString('country') ?? 'Alle Länder';
    });
  }

  Future<void> persist() async {
    await prefs?.setStringList('services', services.toList());
    await prefs?.setStringList('saved', saved.toList());
    await prefs?.setString('country', country);
    await prefs?.setString(
      'savedMovies',
      jsonEncode(savedMovies.values.map((m) => m.toJson()).toList()),
    );
  }

  Future<http.Response> fetch(Uri uri) =>
      widget.client?.get(uri) ?? http.get(uri);
  Future<void> load(String search) async {
    final generation = ++request;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final response = await fetch(
        Uri.base
            .resolve('/api/catalog')
            .replace(queryParameters: {'q': search}),
      ).timeout(const Duration(seconds: 20));
      if (response.statusCode != 200) {
        throw Exception('Datenquelle nicht erreichbar');
      }
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      if (!mounted || generation != request) return;
      setState(() {
        live = data['mode'] == 'live';
        movies = live
            ? (data['movies'] as List).map((m) => Movie.fromJson(m)).toList()
            : demoMovies;
        loading = false;
      });
    } catch (_) {
      if (!mounted || generation != request) return;
      setState(() {
        loading = false;
        error =
            'Die Datenquelle ist gerade nicht erreichbar. Bitte erneut versuchen.';
      });
    }
  }

  @override
  void dispose() {
    debounce?.cancel();
    searchController.dispose();
    super.dispose();
  }

  void toggleSaved(Movie m) {
    setState(() {
      if (saved.contains(m.key)) {
        saved.remove(m.key);
        savedMovies.remove(m.key);
      } else {
        saved.add(m.key);
        savedMovies[m.key] = m;
      }
    });
    persist();
  }

  List<Movie> get visible =>
      (section == 'Watchlist' ? savedMovies.values.toList() : movies)
          .where(
            (m) =>
                ((live && section != 'Watchlist') ||
                    m.title.toLowerCase().contains(query.toLowerCase())) &&
                (category == 'Alle' ||
                    (category == 'Filme' && !m.series) ||
                    (category == 'Serien' && m.series)) &&
                (section != 'Watchlist' || saved.contains(m.key)) &&
                ((services.isEmpty &&
                        country == 'Alle Länder' &&
                        !subscriptionOnly) ||
                    matchingOffers(
                      m,
                      services: services,
                      country: country,
                      subscriptionOnly: subscriptionOnly,
                    ).isNotEmpty),
          )
          .toList();
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final wide = constraints.maxWidth >= 900;
      return Scaffold(
        body: SafeArea(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (wide) sidebar(),
              Expanded(
                child: CustomScrollView(
                  slivers: [
                    SliverToBoxAdapter(
                      child: Center(
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 1340),
                          child: Padding(
                            padding: EdgeInsets.symmetric(
                              horizontal: wide ? 46 : 20,
                              vertical: 28,
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                header(wide),
                                const SizedBox(height: 36),
                                if (section == 'Entdecken' &&
                                    query.isEmpty) ...[
                                  hero(wide),
                                  const SizedBox(height: 32),
                                ],
                                Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        section == 'Watchlist'
                                            ? 'Deine Watchlist'
                                            : 'Die Welt ist dein Kino.',
                                        style: TextStyle(
                                          fontSize: wide ? 29 : 24,
                                          fontWeight: FontWeight.w700,
                                          letterSpacing: -.8,
                                        ),
                                      ),
                                    ),
                                    if (wide)
                                      Text(
                                        '${visible.length} Titel entdecken',
                                        style: const TextStyle(color: muted),
                                      ),
                                  ],
                                ),
                                const SizedBox(height: 6),
                                const Text(
                                  'Finde deinen nächsten Film. Über Ländergrenzen hinweg.',
                                  style: TextStyle(color: muted),
                                ),
                                const SizedBox(height: 22),
                                filters(),
                                const SizedBox(height: 22),
                                if (!live) demoNotice(),
                                if (error != null)
                                  Padding(
                                    padding: const EdgeInsets.only(bottom: 16),
                                    child: Row(
                                      children: [
                                        Expanded(
                                          child: Text(
                                            error!,
                                            style: const TextStyle(
                                              color: Colors.orangeAccent,
                                            ),
                                          ),
                                        ),
                                        TextButton(
                                          onPressed: () => load(query),
                                          child: const Text('Erneut versuchen'),
                                        ),
                                      ],
                                    ),
                                  ),
                                if (loading)
                                  const LinearProgressIndicator(minHeight: 2),
                                const SizedBox(height: 18),
                                if (visible.isEmpty && !loading)
                                  Container(
                                    padding: const EdgeInsets.all(40),
                                    alignment: Alignment.center,
                                    child: Column(
                                      children: [
                                        const Icon(
                                          Icons.travel_explore,
                                          size: 44,
                                          color: muted,
                                        ),
                                        const SizedBox(height: 16),
                                        Text(
                                          section == 'Watchlist'
                                              ? 'Hier ist Platz für deine nächsten Filmabende.'
                                              : 'Keine Titel für diese Auswahl.',
                                          style: const TextStyle(fontSize: 18),
                                        ),
                                        const SizedBox(height: 8),
                                        const Text(
                                          'Passe deine Filter an oder suche einen anderen Titel.',
                                          style: TextStyle(color: muted),
                                        ),
                                        TextButton(
                                          onPressed: () {
                                            setState(() {
                                              services.clear();
                                              country = 'Alle Länder';
                                              subscriptionOnly = false;
                                              category = 'Alle';
                                              query = '';
                                              searchController.clear();
                                            });
                                            persist();
                                            load('');
                                          },
                                          child: const Text(
                                            'Filter zurücksetzen',
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                LayoutBuilder(
                                  builder: (context, c) {
                                    final count = c.maxWidth >= 1100
                                        ? 5
                                        : c.maxWidth >= 760
                                        ? 4
                                        : c.maxWidth >= 520
                                        ? 3
                                        : 2;
                                    final width =
                                        (c.maxWidth - (count - 1) * 18) / count;
                                    return Wrap(
                                      spacing: 18,
                                      runSpacing: 26,
                                      children: visible
                                          .map(
                                            (m) => SizedBox(
                                              width: width,
                                              child: movieCard(m),
                                            ),
                                          )
                                          .toList(),
                                    );
                                  },
                                ),
                                const SizedBox(height: 44),
                                footer(),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        bottomNavigationBar: wide
            ? null
            : NavigationBar(
                selectedIndex: section == 'Entdecken' ? 0 : 1,
                onDestinationSelected: (i) => setState(
                  () => section = i == 0 ? 'Entdecken' : 'Watchlist',
                ),
                destinations: const [
                  NavigationDestination(
                    icon: Icon(Icons.explore_outlined),
                    label: 'Entdecken',
                  ),
                  NavigationDestination(
                    icon: Icon(Icons.bookmark_border),
                    label: 'Watchlist',
                  ),
                ],
              ),
      );
    },
  );
  Widget sidebar() => Container(
    width: 218,
    decoration: const BoxDecoration(
      border: Border(right: BorderSide(color: Color(0xFF252A32))),
    ),
    padding: const EdgeInsets.all(24),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        brand(),
        const SizedBox(height: 48),
        const Text(
          'DEIN KINO',
          style: TextStyle(color: muted, fontSize: 10, letterSpacing: 2),
        ),
        const SizedBox(height: 16),
        nav('Entdecken', Icons.explore_outlined),
        const SizedBox(height: 8),
        nav('Watchlist', Icons.bookmark_border),
        const Spacer(),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: mint.withValues(alpha: .06),
            borderRadius: BorderRadius.circular(14),
          ),
          child: const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.public, color: mint),
              SizedBox(height: 12),
              Text(
                'Mehr Welt.\nMehr Filme.',
                style: TextStyle(fontWeight: FontWeight.w700, fontSize: 18),
              ),
              SizedBox(height: 8),
              Text(
                'Entdecke, was jenseits deiner Ländergrenze läuft.',
                style: TextStyle(fontSize: 12, color: muted),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        const Text(
          'OPEN SOURCE · MADE FOR MOVIE LOVERS',
          style: TextStyle(fontSize: 8, color: muted, letterSpacing: 1),
        ),
      ],
    ),
  );
  Widget brand() => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: 29,
        height: 29,
        decoration: BoxDecoration(
          color: mint,
          borderRadius: BorderRadius.circular(9),
        ),
        child: const Icon(Icons.play_arrow_rounded, color: ink, size: 24),
      ),
      const SizedBox(width: 9),
      const Text(
        'where',
        style: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w800,
          letterSpacing: -.8,
        ),
      ),
      const Text(
        '2',
        style: TextStyle(
          color: mint,
          fontSize: 18,
          fontWeight: FontWeight.w800,
        ),
      ),
      const Text(
        'watch',
        style: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w800,
          letterSpacing: -.8,
        ),
      ),
    ],
  );
  Widget nav(String name, IconData icon) => InkWell(
    borderRadius: BorderRadius.circular(10),
    onTap: () => setState(() => section = name),
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 13),
      decoration: BoxDecoration(
        color: section == name
            ? mint.withValues(alpha: .10)
            : Colors.transparent,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Icon(icon, color: section == name ? mint : muted, size: 21),
          const SizedBox(width: 12),
          Text(
            name,
            style: TextStyle(
              color: section == name ? mint : muted,
              fontWeight: FontWeight.w600,
            ),
          ),
          if (name == 'Watchlist' && saved.isNotEmpty) ...[
            const Spacer(),
            Text('${saved.length}', style: const TextStyle(color: mint)),
          ],
        ],
      ),
    ),
  );
  Widget header(bool wide) => Column(
    children: [
      if (!wide) ...[
        Wrap(
          spacing: 18,
          runSpacing: 12,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [brand(), modeBadge()],
        ),
        const SizedBox(height: 22),
      ],
      Row(
        children: [
          Expanded(
            child: TextField(
              controller: searchController,
              onChanged: (s) {
                setState(() => query = s);
                debounce?.cancel();
                debounce = Timer(
                  const Duration(milliseconds: 400),
                  () => load(s),
                );
              },
              decoration: InputDecoration(
                hintText: 'Filme und Serien suchen …',
                hintStyle: const TextStyle(color: muted, fontSize: 14),
                prefixIcon: const Icon(Icons.search, color: muted),
                suffixIcon: query.isEmpty
                    ? null
                    : IconButton(
                        tooltip: 'Suche löschen',
                        onPressed: () {
                          searchController.clear();
                          setState(() => query = '');
                          load('');
                        },
                        icon: const Icon(Icons.close),
                      ),
                contentPadding: const EdgeInsets.all(16),
              ),
            ),
          ),
          if (wide) ...[
            const SizedBox(width: 24),
            modeBadge(),
            const SizedBox(width: 18),
            const CircleAvatar(
              radius: 21,
              backgroundColor: panel,
              child: Icon(Icons.person_outline, color: muted),
            ),
          ],
        ],
      ),
    ],
  );
  Widget modeBadge() => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
    decoration: BoxDecoration(
      border: Border.all(color: const Color(0xFF343C46)),
      borderRadius: BorderRadius.circular(20),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.circle, color: live ? mint : Colors.amber, size: 6),
        const SizedBox(width: 7),
        Text(
          live ? 'Live-Daten' : 'Demo entdecken',
          style: const TextStyle(fontSize: 11, color: muted),
        ),
      ],
    ),
  );
  Widget hero(bool wide) => Container(
    constraints: BoxConstraints(minHeight: wide ? 330 : 360),
    clipBehavior: Clip.antiAlias,
    decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(22),
      color: const Color(0xFF353B38),
    ),
    child: Stack(
      children: [
        Positioned(
          right: 0,
          top: -100,
          bottom: -130,
          width: wide ? 400 : 260,
          child: Image.asset(
            'assets/images/dune.jpg',
            fit: BoxFit.cover,
            errorBuilder: (_, _, _) => const SizedBox(),
          ),
        ),
        Positioned.fill(
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  const Color(0xFF1C2827),
                  const Color(0xFF1C2827).withValues(alpha: .93),
                  const Color(0xFF1C2827).withValues(alpha: .10),
                ],
                stops: const [0, .45, 1],
              ),
            ),
          ),
        ),
        Padding(
          padding: EdgeInsets.all(wide ? 34 : 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Row(
                children: [
                  Icon(Icons.public, color: mint, size: 16),
                  SizedBox(width: 8),
                  Text(
                    'DEIN FILM. DEINE WELT.',
                    style: TextStyle(
                      color: mint,
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 2,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 17),
              Text(
                'Gute Filme kennen\nkeine Grenzen.',
                style: TextStyle(
                  fontSize: wide ? 43 : 33,
                  height: 1.08,
                  letterSpacing: -1.5,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'Vergleiche Streamingangebote weltweit.\nFinde heraus, wo dein nächster Filmabend beginnt.',
                style: TextStyle(
                  color: Color(0xFFBCC9C4),
                  height: 1.6,
                  fontSize: 13,
                ),
              ),
              const SizedBox(height: 22),
              FilledButton.icon(
                onPressed: () => showMovie(
                  live && movies.isNotEmpty ? movies.first : demoMovies.first,
                ),
                icon: const Icon(Icons.travel_explore, size: 18),
                label: const Text('Ländervergleich entdecken'),
                style: FilledButton.styleFrom(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 17,
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    ),
  );
  Widget filters() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Wrap(
        spacing: 10,
        runSpacing: 10,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: panel,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: ['Alle', 'Filme', 'Serien']
                  .map(
                    (s) => InkWell(
                      onTap: () => setState(() => category = s),
                      borderRadius: BorderRadius.circular(8),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 17,
                          vertical: 9,
                        ),
                        decoration: BoxDecoration(
                          color: category == s
                              ? const Color(0xFF343D44)
                              : Colors.transparent,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          s,
                          style: TextStyle(
                            fontSize: 12,
                            color: category == s ? Colors.white : muted,
                          ),
                        ),
                      ),
                    ),
                  )
                  .toList(),
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              color: panel,
              borderRadius: BorderRadius.circular(12),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: country,
                icon: const Icon(Icons.keyboard_arrow_down, size: 18),
                style: const TextStyle(color: Colors.white, fontSize: 12),
                items: [
                  const DropdownMenuItem(
                    value: 'Alle Länder',
                    child: Text('🌍  Alle Länder'),
                  ),
                  ...countries.entries.map(
                    (c) => DropdownMenuItem(
                      value: c.key,
                      child: Text('${flags[c.key]}  ${c.value}'),
                    ),
                  ),
                ],
                onChanged: (s) {
                  setState(() => country = s!);
                  persist();
                },
              ),
            ),
          ),
          FilterChip(
            label: const Text('Nur im Abo', style: TextStyle(fontSize: 12)),
            selected: subscriptionOnly,
            onSelected: (s) => setState(() => subscriptionOnly = s),
          ),
          if (services.isNotEmpty ||
              subscriptionOnly ||
              country != 'Alle Länder')
            TextButton(
              onPressed: () {
                setState(() {
                  services.clear();
                  country = 'Alle Länder';
                  subscriptionOnly = false;
                });
                persist();
              },
              child: const Text('Zurücksetzen', style: TextStyle(fontSize: 12)),
            ),
        ],
      ),
      const SizedBox(height: 17),
      Wrap(
        spacing: 9,
        runSpacing: 8,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          const Padding(
            padding: EdgeInsets.only(right: 5),
            child: Text(
              'DEINE DIENSTE',
              style: TextStyle(fontSize: 10, color: muted, letterSpacing: 1.4),
            ),
          ),
          ...providers.map(
            (p) => FilterChip(
              avatar: providerIcon(p, 20),
              label: Text(p, style: const TextStyle(fontSize: 11)),
              selected: services.contains(p),
              onSelected: (s) {
                setState(() => s ? services.add(p) : services.remove(p));
                persist();
              },
            ),
          ),
        ],
      ),
    ],
  );
  Widget demoNotice() => Container(
    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
    decoration: BoxDecoration(
      color: const Color(0xFF22251E),
      borderRadius: BorderRadius.circular(10),
      border: Border.all(color: const Color(0xFF3C412E)),
    ),
    child: const Row(
      children: [
        Icon(Icons.info_outline, color: Color(0xFFD3D9A2), size: 17),
        SizedBox(width: 10),
        Expanded(
          child: Text(
            'Demo mit beispielhaften Länderangeboten. Keine bestätigte Verfügbarkeit oder VPN-Zugriffsgarantie.',
            style: TextStyle(color: Color(0xFFD3D9A2), fontSize: 11),
          ),
        ),
      ],
    ),
  );
  Widget poster(Movie m, {BoxFit fit = BoxFit.cover}) =>
      m.poster.startsWith('http')
      ? Image.network(
          m.poster,
          fit: fit,
          errorBuilder: (_, _, _) => posterFallback(m),
        )
      : Image.asset(
          'assets/images/${m.poster}',
          fit: fit,
          errorBuilder: (_, _, _) => posterFallback(m),
        );
  Widget posterFallback(Movie m) => Container(
    color: panel,
    alignment: Alignment.center,
    padding: const EdgeInsets.all(12),
    child: Text(m.title, textAlign: TextAlign.center),
  );
  Widget movieCard(Movie m) {
    final offers = matchingOffers(
      m,
      services: services,
      country: country,
      subscriptionOnly: subscriptionOnly,
    );
    final regions = offers.map((o) => o.country).toSet();
    return InkWell(
      onTap: () => showMovie(m),
      borderRadius: BorderRadius.circular(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AspectRatio(
            aspectRatio: .68,
            child: Stack(
              fit: StackFit.expand,
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(14),
                  child: poster(m),
                ),
                Positioned(
                  top: 9,
                  left: 9,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 7,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: .75),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.star_rounded,
                          color: Color(0xFFF3CF79),
                          size: 13,
                        ),
                        const SizedBox(width: 3),
                        Text(
                          '${m.rating}',
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                Positioned(
                  top: 5,
                  right: 5,
                  child: IconButton.filledTonal(
                    tooltip: saved.contains(m.key)
                        ? 'Aus Watchlist entfernen'
                        : 'Zur Watchlist hinzufügen',
                    onPressed: () => toggleSaved(m),
                    style: IconButton.styleFrom(
                      backgroundColor: Colors.black.withValues(alpha: .55),
                    ),
                    icon: Icon(
                      saved.contains(m.key)
                          ? Icons.bookmark
                          : Icons.bookmark_border,
                      size: 18,
                      color: saved.contains(m.key) ? mint : Colors.white,
                    ),
                  ),
                ),
                Positioned(
                  left: 8,
                  bottom: 8,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 5,
                    ),
                    decoration: BoxDecoration(
                      color: ink.withValues(alpha: .9),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.public, size: 12, color: mint),
                        const SizedBox(width: 5),
                        Text(
                          '${regions.length} Länder',
                          style: const TextStyle(fontSize: 10, color: mint),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 11),
          Text(
            m.title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
          ),
          const SizedBox(height: 3),
          Text(
            '${m.year}  ·  ${m.genre}',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 11, color: muted),
          ),
          const SizedBox(height: 9),
          Row(
            children: [
              ...offers
                  .map((o) => o.provider)
                  .toSet()
                  .take(3)
                  .map(
                    (p) => Padding(
                      padding: const EdgeInsets.only(right: 5),
                      child: providerIcon(p, 22),
                    ),
                  ),
              const Spacer(),
              const Icon(Icons.arrow_forward, size: 15, color: muted),
            ],
          ),
        ],
      ),
    );
  }

  Widget footer() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Divider(color: Color(0xFF2A3039)),
      const SizedBox(height: 18),
      Wrap(
        spacing: 20,
        runSpacing: 10,
        children: [
          const Text(
            'where2watch · Entdecke mehr von deiner Welt.',
            style: TextStyle(color: muted, fontSize: 11),
          ),
          TextButton(
            onPressed: () => showDialog(
              context: context,
              builder: (c) => AlertDialog(
                title: const Text('Über where2watch'),
                content: const SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Open Source für Filmfans. Einstellungen und Watchlist werden lokal auf diesem Gerät gespeichert.',
                      ),
                      SizedBox(height: 16),
                      Text(
                        'Poster und Filmdaten: TMDB.\nThis product uses the TMDB API but is not endorsed or certified by TMDB.',
                      ),
                      SizedBox(height: 12),
                      Text(
                        'Live-Verfügbarkeiten über TMDB: Quelle JustWatch. Demo-Angebote sind erfundene Beispieldaten. Verfügbarkeit im Land bestätigt keinen Zugriff über VPN.',
                      ),
                      SizedBox(height: 16),
                      Image(
                        image: AssetImage('assets/images/tmdb.png'),
                        width: 120,
                      ),
                    ],
                  ),
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(c),
                    child: const Text('Schließen'),
                  ),
                ],
              ),
            ),
            child: const Text(
              'Über & Datenquellen',
              style: TextStyle(fontSize: 11),
            ),
          ),
        ],
      ),
      const SizedBox(height: 12),
    ],
  );
  Future<void> showMovie(Movie original) async {
    Movie movie = original;
    if (live) {
      try {
        final r = await fetch(
          Uri.base
              .resolve('/api/title')
              .replace(
                queryParameters: {
                  'id': '${original.id}',
                  'type': original.series ? 'tv' : 'movie',
                },
              ),
        ).timeout(const Duration(seconds: 20));
        if (r.statusCode != 200) throw Exception();
        movie = Movie.fromJson(jsonDecode(r.body));
      } catch (_) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(
                'Länderangebote konnten nicht geladen werden. Bitte erneut versuchen.',
              ),
            ),
          );
        }
        return;
      }
    }
    if (!mounted) return;
    String selectedCountry = country;
    bool onlyAbo = subscriptionOnly, onlyMine = services.isNotEmpty;
    await showDialog(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, update) {
          final offers = matchingOffers(
            movie,
            services: onlyMine ? services : {},
            country: selectedCountry,
            subscriptionOnly: onlyAbo,
          );
          final regions = offers.map((o) => o.country).toSet().toList()..sort();
          return Dialog(
            insetPadding: const EdgeInsets.all(16),
            backgroundColor: ink,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(22),
            ),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 850),
              child: SingleChildScrollView(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SizedBox(
                            width: 95,
                            height: 142,
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(9),
                              child: poster(movie),
                            ),
                          ),
                          const SizedBox(width: 20),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'LÄNDERVERGLEICH',
                                  style: TextStyle(
                                    color: mint,
                                    letterSpacing: 1.5,
                                    fontSize: 10,
                                  ),
                                ),
                                const SizedBox(height: 9),
                                Text(
                                  movie.title,
                                  style: const TextStyle(
                                    fontSize: 25,
                                    fontWeight: FontWeight.w700,
                                    height: 1.1,
                                  ),
                                ),
                                const SizedBox(height: 9),
                                Text(
                                  '${movie.year} · ${movie.genre} · ★ ${movie.rating}',
                                  style: const TextStyle(
                                    color: muted,
                                    fontSize: 12,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                TextButton.icon(
                                  onPressed: () {
                                    toggleSaved(movie);
                                    update(() {});
                                  },
                                  icon: Icon(
                                    saved.contains(movie.key)
                                        ? Icons.bookmark
                                        : Icons.bookmark_border,
                                    size: 16,
                                  ),
                                  label: Text(
                                    saved.contains(movie.key)
                                        ? 'Gemerkt'
                                        : 'Merken',
                                  ),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            tooltip: 'Schließen',
                            onPressed: () => Navigator.pop(dialogContext),
                            icon: const Icon(Icons.close),
                          ),
                        ],
                      ),
                      const SizedBox(height: 22),
                      Text(
                        movie.overview,
                        style: const TextStyle(color: muted, fontSize: 13),
                      ),
                      const SizedBox(height: 24),
                      Text(
                        'Wo läuft ${movie.title}?',
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        live
                            ? 'Anbieter nach Land · Datenabfrage beim Öffnen · Quelle: JustWatch via TMDB'
                            : 'Beispielangebote zum Ausprobieren · Keine Live-Verfügbarkeit',
                        style: const TextStyle(color: muted, fontSize: 11),
                      ),
                      const SizedBox(height: 14),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          FilterChip(
                            label: const Text('Nur im Abo'),
                            selected: onlyAbo,
                            onSelected: (v) => update(() => onlyAbo = v),
                          ),
                          FilterChip(
                            label: const Text('Meine Dienste'),
                            selected: onlyMine,
                            onSelected: services.isEmpty
                                ? null
                                : (v) => update(() => onlyMine = v),
                          ),
                          ActionChip(
                            label: Text(
                              selectedCountry == 'Alle Länder'
                                  ? 'Alle Länder'
                                  : countries[selectedCountry] ??
                                        selectedCountry,
                            ),
                            avatar: const Icon(Icons.public, size: 16),
                            onPressed: () =>
                                update(() => selectedCountry = 'Alle Länder'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 18),
                      if (regions.isEmpty)
                        const Padding(
                          padding: EdgeInsets.all(24),
                          child: Text(
                            'Keine gemeldeten Angebote für diese Filter. Versuche alle Länder oder weitere Dienste.',
                          ),
                        ),
                      ...regions.map(
                        (code) => Container(
                          margin: const EdgeInsets.only(bottom: 10),
                          padding: const EdgeInsets.all(15),
                          decoration: BoxDecoration(
                            color: panel,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Text(
                                    flags[code] ?? '🌍',
                                    style: const TextStyle(fontSize: 23),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: Text(
                                      countries[code] ?? code,
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                  ),
                                  Text(
                                    code,
                                    style: const TextStyle(
                                      color: muted,
                                      fontSize: 11,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              ...offers
                                  .where((o) => o.country == code)
                                  .map(
                                    (o) => Padding(
                                      padding: const EdgeInsets.symmetric(
                                        vertical: 5,
                                      ),
                                      child: Row(
                                        children: [
                                          providerIcon(o.provider, 25),
                                          const SizedBox(width: 10),
                                          Expanded(
                                            child: Text(
                                              o.provider,
                                              style: const TextStyle(
                                                fontSize: 12,
                                              ),
                                            ),
                                          ),
                                          Container(
                                            padding: const EdgeInsets.symmetric(
                                              horizontal: 9,
                                              vertical: 5,
                                            ),
                                            decoration: BoxDecoration(
                                              color: o.type == 'Abo'
                                                  ? mint.withValues(alpha: .10)
                                                  : const Color(0xFF303640),
                                              borderRadius:
                                                  BorderRadius.circular(6),
                                            ),
                                            child: Text(
                                              o.type == 'Abo'
                                                  ? 'Im Abo'
                                                  : o.type,
                                              style: TextStyle(
                                                color: o.type == 'Abo'
                                                    ? mint
                                                    : muted,
                                                fontSize: 10,
                                              ),
                                            ),
                                          ),
                                          if (live && o.link != null)
                                            IconButton(
                                              tooltip:
                                                  'Angebote bei TMDB öffnen',
                                              onPressed: () async {
                                                final opened = await launchUrl(
                                                  Uri.parse(o.link!),
                                                  mode: LaunchMode
                                                      .externalApplication,
                                                );
                                                if (!opened &&
                                                    context.mounted) {
                                                  ScaffoldMessenger.of(
                                                    context,
                                                  ).showSnackBar(
                                                    const SnackBar(
                                                      content: Text(
                                                        'Link konnte nicht geöffnet werden.',
                                                      ),
                                                    ),
                                                  );
                                                }
                                              },
                                              icon: const Icon(
                                                Icons.open_in_new,
                                                size: 16,
                                              ),
                                            ),
                                        ],
                                      ),
                                    ),
                                  ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 10),
                      const Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(Icons.info_outline, size: 16, color: muted),
                          SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              'Landesverfügbarkeit ist keine VPN-Zugriffsgarantie. Konto, Dienst und VPN können den Zugriff beeinflussen.',
                              style: TextStyle(fontSize: 11, color: muted),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

Widget providerIcon(String p, double size) {
  final color = switch (p) {
    'Netflix' => const Color(0xFFE50914),
    'Prime Video' => const Color(0xFF47BCF2),
    'Disney+' => const Color(0xFF9AA9FF),
    'Apple TV+' => Colors.white,
    'MUBI' => const Color(0xFFCDD3EE),
    _ => mint,
  };
  final mark = switch (p) {
    'Netflix' => 'N',
    'Prime Video' => 'p',
    'Disney+' => 'D+',
    'Apple TV+' => 'tv',
    'MUBI' => 'm',
    _ => p.substring(0, 1),
  };
  return Container(
    width: size,
    height: size,
    alignment: Alignment.center,
    decoration: BoxDecoration(
      color: const Color(0xFF252B34),
      borderRadius: BorderRadius.circular(5),
    ),
    child: Text(
      mark,
      style: TextStyle(
        color: color,
        fontSize: size * .55,
        fontWeight: FontWeight.w800,
      ),
    ),
  );
}
