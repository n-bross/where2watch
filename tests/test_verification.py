import unittest
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

import verification
from verification import NetflixBrowser, candidates, feature_length, matching_ids, page_error, run_checks, year_matches

MOVIE = {'id':1,'title':'Interstellar','original_title':'Interstellar','series':False,'runtime':169,
         'offers':[{'country':'JP','provider':'Netflix','type':'Abo'},
                   {'country':'CA','provider':'Netflix','type':'Abo'},
                   {'country':'DE','provider':'Prime Video','type':'Abo'}]}

class VerificationTests(unittest.TestCase):
    def vpn(self):
        vpn = Mock()
        vpn.provider = 'surfshark'
        return vpn

    def browser(self, country, status='playable'):
        browser = Mock()
        browser.location.return_value = {'country':country,'ip':'192.0.2.1'}
        browser.probe.return_value = {'status':status,'note':'test'}
        return browser

    def test_canada_first_then_only_netflix_subscription_candidates(self):
        self.assertEqual(candidates(MOVIE), (['CA','JP'],[]))
        self.assertEqual(candidates(MOVIE, ['US','CA','US'],1), (['US'],['CA']))

    def test_region_mismatch_never_probes_netflix(self):
        browser = self.browser('US')
        results = run_checks(MOVIE,['CA'],self.vpn(),lambda:browser)
        self.assertEqual(results[0]['status'],'region_mismatch')
        browser.probe.assert_not_called()
        browser.close.assert_called_once()

    def test_moves_to_next_country_until_playback_confirmed(self):
        first, second, unused = self.browser('CA','not_found'), self.browser('JP'), self.browser('US')
        factory = Mock(side_effect=[first,second,unused])
        vpn = self.vpn()
        results = run_checks(MOVIE,['CA','JP','US'],vpn,factory)
        self.assertEqual([r['status'] for r in results],['not_found','playable'])
        self.assertEqual(factory.call_count,2)
        self.assertEqual([c.args[0] for c in vpn.connect.call_args_list],['CA','JP'])
        first.close.assert_called_once()
        second.close.assert_called_once()

    def test_login_stops_country_switching(self):
        browser = self.browser('CA','login_required')
        vpn = self.vpn()
        results = run_checks(MOVIE,['CA','JP'],vpn,lambda:browser)
        self.assertEqual(len(results),1)
        vpn.connect.assert_called_once_with('CA')

    def test_browser_failure_is_not_missing_availability(self):
        browser = self.browser('CA')
        browser.probe.side_effect = RuntimeError('browser crashed')
        results = run_checks(MOVIE,['CA'],self.vpn(),lambda:browser)
        self.assertEqual(results[0]['status'],'unverified')
        browser.close.assert_called_once()

    def test_browser_startup_failure_is_not_a_vpn_failure(self):
        results = run_checks(MOVIE,['CA'],self.vpn(),Mock(side_effect=ValueError('Chrome fehlt')))
        self.assertEqual(results[0]['status'],'unverified')

    def test_vpn_failure_does_not_open_browser(self):
        vpn = self.vpn()
        vpn.connect.side_effect = ValueError('VPN konnte nicht verbinden')
        factory = Mock()
        results = run_checks(MOVIE,['CA'],vpn,factory)
        self.assertEqual(results[0]['status'],'vpn_error')
        factory.assert_not_called()

    def test_cleanup_failure_preserves_result(self):
        browser = self.browser('CA')
        browser.close.side_effect = RuntimeError('close failed')
        result = run_checks(MOVIE,['CA'],self.vpn(),lambda:browser)[0]
        self.assertEqual(result['status'],'playable')
        self.assertIn('cleanup_note',result)

    def test_only_exact_title_matches_and_duplicates_stay_ambiguous(self):
        cards=[{'href':'https://www.netflix.com/watch/123','names':['Interstellar']},
               {'href':'https://www.netflix.com/watch/456','names':['Interstellar: Behind the scenes']}]
        self.assertEqual(matching_ids(cards,MOVIE),{'123'})
        cards.append({'href':'https://www.netflix.com/title/789','names':['INTERSTELLAR']})
        self.assertEqual(matching_ids(cards,MOVIE),{'123','789'})

    def test_login_and_vpn_messages_have_distinct_outcomes(self):
        self.assertEqual(page_error('https://www.netflix.com/login','')[0],'login_required')
        self.assertEqual(page_error('https://www.netflix.com/watch/1','Error M7111-5059')[0],'vpn_blocked')
        self.assertIsNone(page_error('https://www.netflix.com/watch/1','Loading'))

    def test_release_year_must_be_unambiguous(self):
        self.assertTrue(year_matches([' 2014 '], '2014'))
        self.assertFalse(year_matches(['2024'], '2014'))
        self.assertFalse(year_matches(['2014','2024'], '2014'))
        self.assertFalse(year_matches([], '2014'))

    def test_ad_or_trailer_duration_does_not_confirm_feature(self):
        self.assertFalse(feature_length(30,MOVIE))
        self.assertFalse(feature_length(120,MOVIE))
        self.assertTrue(feature_length(169*60,MOVIE))
        self.assertFalse(feature_length(90,{'runtime':None}))

class SessionTests(unittest.TestCase):
    def test_settings_preserve_special_characters_and_require_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'vpn.env'
            path.write_text('OPENVPN_USER=service\nOPENVPN_PASSWORD=with $ and "quotes"\nVPN_SERVICE_PROVIDER=surfshark\n')
            path.chmod(0o600)
            with patch.object(verification,'VPN_ENV',path):
                self.assertEqual(verification.load_settings()['OPENVPN_PASSWORD'],'with $ and "quotes"')
                path.chmod(0o644)
                with self.assertRaises(ValueError): verification.load_settings()

    def test_same_profile_cannot_switch_vpn_concurrently(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(verification,'STATE',Path(directory)/'private'):
            with verification.exclusive_session():
                with self.assertRaises(ValueError):
                    with verification.exclusive_session(): pass

    def test_report_is_private_and_vpn_is_stopped_after_browser_failure(self):
        vpn = Mock()
        vpn.provider = 'surfshark'
        with tempfile.TemporaryDirectory() as directory, patch.object(verification,'STATE',Path(directory)/'private'), patch.object(verification,'load_settings',return_value={}), patch.object(verification,'GluetunVPN',return_value=vpn), patch.object(verification,'NetflixBrowser',side_effect=ValueError('Chrome fehlt')):
            report = verification.verify(MOVIE,explicit=['CA','JP'],limit=1)
            path = Path(report['report_path'])
            saved = json.loads(path.read_text())
            self.assertEqual(saved['results'][0]['status'],'unverified')
            self.assertEqual(saved['not_checked'],['JP'])
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
        vpn.close.assert_called_once()

    def test_interrupt_closes_browser_and_vpn(self):
        vpn = Mock()
        vpn.provider = 'surfshark'
        browser = Mock()
        browser.location.return_value = {'country':'CA'}
        browser.probe.side_effect = KeyboardInterrupt
        with tempfile.TemporaryDirectory() as directory, patch.object(verification,'STATE',Path(directory)/'private'), patch.object(verification,'load_settings',return_value={}), patch.object(verification,'GluetunVPN',return_value=vpn), patch.object(verification,'NetflixBrowser',return_value=browser):
            with self.assertRaises(KeyboardInterrupt): verification.verify(MOVIE,explicit=['CA'])
        browser.close.assert_called_once()
        vpn.close.assert_called_once()


class PlaybackTests(unittest.TestCase):
    def setup_browser(self, years=None, frames=None):
        browser = NetflixBrowser.__new__(NetflixBrowser)
        page = Mock()
        page.goto.side_effect = lambda url, **kwargs: setattr(page, 'url', url)
        body = Mock()
        body.inner_text.return_value = 'Netflix'
        profile_gate = Mock()
        profile_gate.count.return_value = 0
        cards = Mock()
        cards.evaluate_all.return_value = [{'href':'https://www.netflix.com/watch/123','names':['Interstellar']}]
        year_node = Mock()
        year_node.all_text_contents.return_value = years if years is not None else ['2014']
        video = Mock()
        video.evaluate_all.side_effect = list(frames or [])
        def locator(selector):
            if selector == 'body': return body
            if selector == '.title-card': return cards
            if selector == '.profile-gate-label:visible': return profile_gate
            if selector == 'video': return video
            return year_node
        page.locator.side_effect = locator
        browser.page = page
        return browser, video

    def movie(self):
        return dict(MOVIE, year='2014')

    def frame(self, seconds, duration=169*60):
        return [{'time':seconds,'duration':duration,'ready':4,'paused':False}]

    def test_actual_feature_progress_over_wall_time_confirms_playback(self):
        browser, video = self.setup_browser(frames=[self.frame(10),self.frame(16),None])
        with patch('verification.time.monotonic',side_effect=[0,1,2,6,7]):
            result = browser.probe(self.movie())
        self.assertEqual(result['status'],'playable')
        self.assertEqual(result['netflix_id'],'123')
        self.assertEqual(result['playback_id'],'123')
        self.assertIn('pause()',video.evaluate_all.call_args.args[0])

    def test_series_redirect_to_episode_is_supported(self):
        browser, _ = self.setup_browser(frames=[self.frame(10),self.frame(16),None])
        browser.page.goto.side_effect = lambda url, **kw: setattr(browser.page, 'url', url.replace('/watch/123','/watch/456'))
        with patch('verification.time.monotonic',side_effect=[0,1,2,6,7]):
            result = browser.probe(dict(self.movie(),series=True,runtime=None))
        self.assertEqual(result['status'],'playable')
        self.assertEqual(result['netflix_id'],'123')
        self.assertEqual(result['playback_id'],'456')

    def test_wrong_year_does_not_start_playback(self):
        browser, video = self.setup_browser(years=['2024'])
        result = browser.probe(self.movie())
        self.assertEqual(result['status'],'unverified')
        video.evaluate_all.assert_not_called()
        self.assertFalse(any('/watch/' in c.args[0] for c in browser.page.goto.call_args_list))

    def test_frozen_video_and_seeks_do_not_confirm_playback(self):
        for frames, clock in [([self.frame(10),self.frame(10)],[0,1,2,8,9,50]),
                              ([self.frame(10),self.frame(20)],[0,1,2,3,4,50]),
                              ([self.frame(5,30)],[0,1,50])]:
            with self.subTest(frames=frames):
                browser, _ = self.setup_browser(frames=frames)
                with patch('verification.time.monotonic',side_effect=clock):
                    result = browser.probe(self.movie())
                self.assertEqual(result['status'],'unverified')


if __name__ == '__main__': unittest.main()
