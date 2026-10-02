class Offer {
  final String country, provider, type;
  final String? link;
  const Offer(this.country, this.provider, this.type, [this.link]);
  factory Offer.fromJson(Map<String, dynamic> j) =>
      Offer(j['country'], j['provider'], j['type'], j['link']);
}

class Movie {
  final int id;
  final String title, year, genre, overview, poster;
  final double rating;
  final bool series;
  final List<Offer> offers;
  const Movie({
    required this.id,
    required this.title,
    required this.year,
    required this.genre,
    required this.overview,
    required this.poster,
    required this.rating,
    this.series = false,
    this.offers = const [],
  });
  factory Movie.fromJson(Map<String, dynamic> j) => Movie(
    id: j['id'],
    title: j['title'],
    year: j['year'],
    genre: j['genre'],
    overview: j['overview'],
    poster: j['poster'],
    rating: (j['rating'] as num).toDouble(),
    series: j['series'] ?? false,
    offers: (j['offers'] as List? ?? []).map((o) => Offer.fromJson(o)).toList(),
  );
  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'year': year,
    'genre': genre,
    'overview': overview,
    'poster': poster,
    'rating': rating,
    'series': series,
    'offers': offers
        .map(
          (o) => {
            'country': o.country,
            'provider': o.provider,
            'type': o.type,
            'link': o.link,
          },
        )
        .toList(),
  };
  String get key => '${series ? 'tv' : 'movie'}:$id';
}

const countries = {
  'DE': 'Deutschland',
  'US': 'USA',
  'GB': 'Großbritannien',
  'CA': 'Kanada',
  'FR': 'Frankreich',
  'NL': 'Niederlande',
  'JP': 'Japan',
  'AU': 'Australien',
};
const flags = {
  'DE': '🇩🇪',
  'US': '🇺🇸',
  'GB': '🇬🇧',
  'CA': '🇨🇦',
  'FR': '🇫🇷',
  'NL': '🇳🇱',
  'JP': '🇯🇵',
  'AU': '🇦🇺',
};
const providers = ['Netflix', 'Prime Video', 'Disney+', 'Apple TV+', 'MUBI'];

List<Offer> matchingOffers(
  Movie movie, {
  Set<String> services = const {},
  String country = 'Alle Länder',
  bool subscriptionOnly = false,
}) => movie.offers
    .where(
      (o) =>
          (services.isEmpty || services.contains(o.provider)) &&
          (country == 'Alle Länder' || o.country == country) &&
          (!subscriptionOnly || o.type == 'Abo'),
    )
    .toList();

const demoMovies = [
  Movie(
    id: 693134,
    title: 'Dune: Part Two',
    year: '2024',
    genre: 'Science-Fiction',
    overview:
        'Paul Atreides verbündet sich mit Chani und den Fremen. Zwischen Liebe und dem Schicksal des Universums muss er eine Entscheidung treffen.',
    poster: 'dune.jpg',
    rating: 8.2,
    offers: [
      Offer('US', 'Netflix', 'Abo'),
      Offer('CA', 'Netflix', 'Abo'),
      Offer('DE', 'Prime Video', 'Leihen'),
      Offer('GB', 'Prime Video', 'Abo'),
      Offer('FR', 'Apple TV+', 'Kaufen'),
    ],
  ),
  Movie(
    id: 157336,
    title: 'Interstellar',
    year: '2014',
    genre: 'Science-Fiction',
    overview:
        'Eine Gruppe von Forschern reist durch ein Wurmloch, um der Menschheit eine Zukunft jenseits der Erde zu ermöglichen.',
    poster: 'interstellar.jpg',
    rating: 8.4,
    offers: [
      Offer('DE', 'Netflix', 'Abo'),
      Offer('US', 'Prime Video', 'Abo'),
      Offer('GB', 'Netflix', 'Abo'),
      Offer('JP', 'Netflix', 'Abo'),
    ],
  ),
  Movie(
    id: 872585,
    title: 'Oppenheimer',
    year: '2023',
    genre: 'Drama',
    overview:
        'Der Physiker J. Robert Oppenheimer steht im Zentrum eines Projekts, das die Welt für immer verändern wird.',
    poster: 'oppenheimer.jpg',
    rating: 8.1,
    offers: [
      Offer('DE', 'Prime Video', 'Abo'),
      Offer('US', 'Prime Video', 'Leihen'),
      Offer('CA', 'Netflix', 'Abo'),
    ],
  ),
  Movie(
    id: 569094,
    title: 'Spider-Man: Across the Spider-Verse',
    year: '2023',
    genre: 'Animation',
    overview:
        'Miles Morales reist durch das Multiversum und begegnet einem Team von Spider-People, das dessen Existenz beschützen soll.',
    poster: 'spiderverse.jpg',
    rating: 8.4,
    offers: [
      Offer('US', 'Netflix', 'Abo'),
      Offer('FR', 'Disney+', 'Abo'),
      Offer('DE', 'Prime Video', 'Leihen'),
    ],
  ),
  Movie(
    id: 419430,
    title: 'Get Out',
    year: '2017',
    genre: 'Thriller',
    overview:
        'Ein Besuch bei den Eltern seiner Freundin wird für Chris zu einer zunehmend beunruhigenden Erfahrung.',
    poster: 'getout.jpg',
    rating: 7.6,
    offers: [
      Offer('GB', 'Netflix', 'Abo'),
      Offer('DE', 'Prime Video', 'Abo'),
      Offer('AU', 'Netflix', 'Abo'),
    ],
  ),
  Movie(
    id: 129,
    title: 'Chihiros Reise ins Zauberland',
    year: '2001',
    genre: 'Animation',
    overview:
        'Chihiro gerät in eine Welt voller Geister und Magie und muss ihren Mut finden, um ihre Eltern zu retten.',
    poster: 'spirited.jpg',
    rating: 8.5,
    offers: [
      Offer('DE', 'Netflix', 'Abo'),
      Offer('FR', 'Netflix', 'Abo'),
      Offer('CA', 'Netflix', 'Abo'),
      Offer('US', 'Prime Video', 'Kaufen'),
    ],
  ),
  Movie(
    id: 94997,
    title: 'House of the Dragon',
    year: '2022',
    genre: 'Fantasy',
    overview:
        'Das Haus Targaryen steht auf dem Höhepunkt seiner Macht. Ein Kampf um die Thronfolge droht die Dynastie zu zerreißen.',
    poster: 'dragon.jpg',
    rating: 8.3,
    series: true,
    offers: [
      Offer('DE', 'Prime Video', 'Kaufen'),
      Offer('GB', 'Prime Video', 'Kaufen'),
    ],
  ),
  Movie(
    id: 10681,
    title: 'WALL·E',
    year: '2008',
    genre: 'Animation',
    overview:
        'Ein kleiner Roboter mit einem großen Herzen entdeckt eine neue Bestimmung und folgt seiner Liebe ins All.',
    poster: 'walle.jpg',
    rating: 8.1,
    offers: [
      Offer('DE', 'Disney+', 'Abo'),
      Offer('US', 'Disney+', 'Abo'),
      Offer('GB', 'Disney+', 'Abo'),
      Offer('AU', 'Disney+', 'Abo'),
    ],
  ),
];
