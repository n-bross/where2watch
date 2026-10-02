import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:where2watch/main.dart';

void main() {
  testWidgets(
    'mobile search, empty state and watchlist work without overflow',
    (tester) async {
      SharedPreferences.setMockInitialValues({});
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final client = MockClient(
        (_) async => http.Response('{"mode":"demo","movies":[]}', 200),
      );
      await tester.pumpWidget(Where2Watch(client: client));
      await tester.pumpAndSettle();
      expect(find.text('Demo entdecken'), findsOneWidget);
      expect(find.text('Dune: Part Two'), findsOneWidget);
      await tester.enterText(find.byType(TextField), 'does-not-exist');
      await tester.pumpAndSettle(const Duration(milliseconds: 500));
      expect(find.text('Keine Titel für diese Auswahl.'), findsOneWidget);
      await tester.ensureVisible(find.text('Filter zurücksetzen'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Filter zurücksetzen'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(
        find.byTooltip('Zur Watchlist hinzufügen').first,
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Zur Watchlist hinzufügen').first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Watchlist').last);
      await tester.pumpAndSettle();
      expect(find.text('Deine Watchlist'), findsOneWidget);
      expect(find.text('Dune: Part Two'), findsOneWidget);
      expect(find.text('Interstellar'), findsNothing);
      await tester.ensureVisible(find.text('Dune: Part Two'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Dune: Part Two'));
      await tester.pumpAndSettle();
      expect(find.text('LÄNDERVERGLEICH'), findsOneWidget);
      expect(find.text('Kanada'), findsOneWidget);
      await tester.tap(find.byTooltip('Schließen'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    },
  );
}
