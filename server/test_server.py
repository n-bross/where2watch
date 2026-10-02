import unittest
from unittest.mock import patch
import server

class AdapterTests(unittest.TestCase):
    def test_regions_offer_types_and_provider_names(self):
        item = {'id':1,'title':'Test','release_date':'2024-01-01','genre_ids':[878],'vote_average':8.24}
        response = {'results':{'DE':{'link':'https://www.themoviedb.org/movie/1/watch?locale=DE','flatrate':[{'provider_name':'Amazon Prime Video'}],'rent':[{'provider_name':'Apple TV'}]},'US':{'ads':[{'provider_name':'Example'}]}}}
        with patch.object(server,'tmdb',return_value=response):
            m = server.normalize(item,'movie')
        self.assertEqual(m['year'],'2024')
        self.assertEqual(m['offers'][0]['provider'],'Prime Video')
        self.assertEqual([o['type'] for o in m['offers']], ['Abo','Leihen','Mit Werbung'])
        self.assertEqual(m['offers'][0]['country'],'DE')
        self.assertEqual(m['rating'],8.2)

    def test_missing_region_data_is_empty_not_invented(self):
        with patch.object(server,'tmdb',return_value={}):
            m = server.normalize({'id':1,'name':'Series'},'tv')
        self.assertTrue(m['series'])
        self.assertEqual(m['offers'],[])

    def test_upstream_error_is_not_missing_availability(self):
        with patch.object(server,'tmdb',side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                server.normalize({'id':1},'movie')

if __name__ == '__main__': unittest.main()
