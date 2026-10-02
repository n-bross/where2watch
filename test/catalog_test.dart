import 'package:flutter_test/flutter_test.dart';
import 'package:where2watch/catalog.dart';

void main() {
  test('combines country, service and subscription filters', () {
    final dune = demoMovies.first;
    expect(
      matchingOffers(
        dune,
        services: {'Netflix'},
        country: 'CA',
        subscriptionOnly: true,
      ).length,
      1,
    );
    expect(
      matchingOffers(
        dune,
        services: {'Netflix'},
        country: 'DE',
        subscriptionOnly: true,
      ),
      isEmpty,
    );
    expect(matchingOffers(dune, country: 'DE').single.type, 'Leihen');
    expect(
      matchingOffers(dune, country: 'DE', subscriptionOnly: true),
      isEmpty,
    );
  });
  test('no service selection means all services', () {
    expect(matchingOffers(demoMovies.first).length, 5);
  });
  test('movie and series IDs remain distinct in watchlist', () {
    const movie = Movie(
      id: 1,
      title: 'A',
      year: '',
      genre: '',
      overview: '',
      poster: '',
      rating: 0,
    );
    const series = Movie(
      id: 1,
      title: 'B',
      year: '',
      genre: '',
      overview: '',
      poster: '',
      rating: 0,
      series: true,
    );
    expect(movie.key, isNot(series.key));
  });
}
