import contextlib
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import cli


class CliTests(unittest.TestCase):
    def invoke(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), patch('sys.stdin.isatty', return_value=False):
            status = cli.main(args)
        return status, out.getvalue(), err.getvalue()

    def test_name_search_displays_details_and_every_reported_country(self):
        status, out, err = self.invoke(['--demo', 'Interstellar'])
        self.assertEqual(status, 0)
        self.assertEqual(err, '')
        self.assertIn('DEMO', out)
        for value in ['Interstellar (2014)', 'Beschreibung', 'Deutschland [DE]', 'USA [US]', 'Japan [JP]', 'Großbritannien [GB]']:
            self.assertIn(value, out)
        self.assertNotIn('\033', out)

    def test_combined_filters_in_machine_readable_output(self):
        status, out, _ = self.invoke(['--demo', 'Dune', '--country', 'de,ca', '--provider', 'Netflix', '--abo', '--json'])
        self.assertEqual(status, 0)
        result = json.loads(out)
        self.assertEqual(result['mode'], 'demo')
        self.assertEqual(result['movie']['offers'], [{'country':'CA','provider':'Netflix','type':'Abo','link':None}])

    def test_empty_offers_still_show_movie_information(self):
        status, out, _ = self.invoke(['--demo', 'Dune', '--country', 'DE', '--abo'])
        self.assertEqual(status, 0)
        self.assertIn('Dune: Part Two', out)
        self.assertIn('Keine gemeldeten Angebote', out)

    def test_multi_word_name_without_quotes(self):
        status, out, _ = self.invoke(['--demo', 'House', 'of', 'the', 'Dragon'])
        self.assertEqual(status, 0)
        self.assertIn('Typ: Serie', out)

    def test_missing_token_does_not_silently_invent_live_offers(self):
        with patch.object(cli.catalog, 'TOKEN', ''):
            status, out, err = self.invoke(['Interstellar'])
        self.assertEqual(status, 2)
        self.assertEqual(out, '')
        self.assertIn('TMDB_READ_ACCESS_TOKEN fehlt', err)

    def test_unknown_title_returns_nonzero_status(self):
        status, out, err = self.invoke(['--demo', 'unknown-xyz'])
        self.assertEqual(status, 1)
        self.assertEqual(out, '')
        self.assertIn('Keine Treffer', err)

    def test_ambiguous_search_requires_explicit_selection_in_scripts(self):
        matches = [dict(id=1,title='Dune',year='1984',series=False), dict(id=2,title='Dune',year='2021',series=False)]
        with patch.object(cli.catalog, 'TOKEN', 'test'), patch.object(cli, 'search', return_value=matches), patch.object(cli, 'details') as details:
            status, out, err = self.invoke(['Dune', '--json'])
        self.assertEqual(status, 2)
        self.assertEqual(out, '')
        self.assertIn('--pick N', err)
        details.assert_not_called()

    def test_live_flow_fetches_selected_title_credits_and_availability(self):
        match = dict(id=42,media_type='movie',title='Film',release_date='2024-01-01')
        raw = dict(id=42,title='Film',original_title='Movie',release_date='2024-01-01',runtime=120,genres=[{'id':18,'name':'Drama'}],credits={'cast':[{'name':'Actor'}],'crew':[{'name':'Director','job':'Director'}]})
        regions = {'results':{'DE':{'flatrate':[{'provider_name':'Netflix'}],'link':'https://example.com/offers'}}}
        with patch.object(cli.catalog, 'TOKEN', 'test'), patch.object(cli.catalog, 'tmdb', side_effect=[{'results':[match]}, raw, regions]) as api:
            status, out, err = self.invoke(['Film','--json'])
        self.assertEqual(status, 0)
        self.assertEqual(err, '')
        movie = json.loads(out)['movie']
        self.assertEqual(movie['runtime'],120)
        self.assertEqual(movie['cast'],['Actor'])
        self.assertEqual(movie['creators'],['Director'])
        self.assertEqual(movie['offers'][0]['country'],'DE')
        self.assertEqual(api.call_args_list[1].kwargs, {'append_to_response':'credits'})

    def test_api_errors_are_errors_not_no_availability(self):
        for error, text in [(HTTPError('https://example.com',401,'unauthorized',{},None),'ungültig'), (URLError('network'),'Verbindung')]:
            with self.subTest(error=error), patch.object(cli.catalog, 'TOKEN', 'test'), patch.object(cli.catalog, 'tmdb', side_effect=error):
                status, out, err = self.invoke(['Film'])
                self.assertEqual(status,2)
                self.assertEqual(out,'')
                self.assertIn(text,err)

    def test_interactive_selection_reprompts_then_selects(self):
        matches = [{'title':'Film','year':'2020','series':False}, {'title':'Film','year':'2024','series':False}]
        with patch('builtins.input',side_effect=['bad','2']):
            selected = cli.choose(matches,None,True,'Film',io.StringIO())
        self.assertEqual(selected,matches[1])

    def test_invalid_selection_is_not_an_arbitrary_match(self):
        status, out, err = self.invoke(['--demo','Interstellar','--pick','0'])
        self.assertEqual(status,2)
        self.assertEqual(out,'')
        self.assertIn('--pick',err)


if __name__ == '__main__':
    unittest.main()
