# -*- coding: utf-8  -*-
#
# (C) Pywikibot team, 2012-2014
#
# Distributed under the terms of the MIT license.
#
__version__ = '$Id$'
#

import datetime
import pywikibot
from pywikibot.data.api import CachedRequest, QueryGenerator
from pywikibot.family import Family
from tests.utils import DummySiteinfo
from tests.aspects import unittest, TestCase, DefaultSiteTestCase


class DryCachedRequestTests(TestCase):

    sites = {
        'basesite': {
            'family': 'wikipedia',
            'code': 'en',
        },
        'altsite': {
            'family': 'wikipedia',
            'code': 'de',
        },
    }

    def setUp(self):
        super(DryCachedRequestTests, self).setUp()
        self.basesite = self.get_site('basesite')
        self.altsite = self.get_site('altsite')
        self.parms = {'site': self.basesite,
                      'action': 'query',
                      'meta': 'userinfo'}
        self.req = CachedRequest(expiry=1, **self.parms)
        self.expreq = CachedRequest(expiry=0, **self.parms)
        self.diffreq = CachedRequest(expiry=1, site=self.basesite, action='query', meta='siteinfo')
        self.diffsite = CachedRequest(expiry=1, site=self.altsite, action='query', meta='userinfo')

    def test_expiry_formats(self):
        self.assertEqual(self.req.expiry, CachedRequest(datetime.timedelta(days=1), **self.parms).expiry)

    def test_expired(self):
        self.assertFalse(self.req._expired(datetime.datetime.now()))
        self.assertTrue(self.req._expired(datetime.datetime.now() - datetime.timedelta(days=2)))

    def test_get_cache_dir(self):
        retval = self.req._get_cache_dir()
        self.assertIn('apicache', retval)

    def test_create_file_name(self):
        self.assertEqual(self.req._create_file_name(), self.req._create_file_name())
        self.assertEqual(self.req._create_file_name(), self.expreq._create_file_name())
        self.assertNotEqual(self.req._create_file_name(), self.diffreq._create_file_name())

    def test_cachefile_path(self):
        self.assertEqual(self.req._cachefile_path(), self.req._cachefile_path())
        self.assertEqual(self.req._cachefile_path(), self.expreq._cachefile_path())
        self.assertNotEqual(self.req._cachefile_path(), self.diffreq._cachefile_path())
        self.assertNotEqual(self.req._cachefile_path(), self.diffsite._cachefile_path())


class MockCachedRequestKeyTests(TestCase):

    net = False

    def setUp(self):
        class MockFamily(Family):

            @property
            def name(self):
                return 'mock'

        class MockSite(pywikibot.site.APISite):

            _loginstatus = pywikibot.site.LoginStatus.NOT_ATTEMPTED

            _namespaces = {2: ['User']}

            def __init__(self):
                self._user = 'anon'
                pywikibot.site.BaseSite.__init__(self, 'mock', MockFamily())
                self._siteinfo = DummySiteinfo({'case': 'first-letter'})

            def version(self):
                return '1.13'  # pre 1.14

            def protocol(self):
                return 'http'

            def languages(self):
                return ['mock']

            def user(self):
                return self._user

            def encoding(self):
                return 'utf-8'

            def encodings(self):
                return []

            @property
            def siteinfo(self):
                return self._siteinfo

            def __repr__(self):
                return "MockSite()"

            def __getattr__(self, attr):
                raise Exception("Attribute %r not defined" % attr)

        self.mocksite = MockSite()
        super(MockCachedRequestKeyTests, self).setUp()

    def test_cachefile_path_different_users(self):
        req = CachedRequest(expiry=1, site=self.mocksite,
                            action='query', meta='siteinfo')
        anonpath = req._cachefile_path()

        self.mocksite._userinfo = {'name': u'MyUser'}
        self.mocksite._loginstatus = 0
        req = CachedRequest(expiry=1, site=self.mocksite,
                            action='query', meta='siteinfo')
        userpath = req._cachefile_path()

        self.assertNotEqual(anonpath, userpath)

        self.mocksite._userinfo = {'name': u'MySysop'}
        self.mocksite._loginstatus = 1
        req = CachedRequest(expiry=1, site=self.mocksite,
                            action='query', meta='siteinfo')
        sysoppath = req._cachefile_path()

        self.assertNotEqual(anonpath, sysoppath)
        self.assertNotEqual(userpath, sysoppath)

    def test_unicode(self):
        self.mocksite._userinfo = {'name': u'محمد الفلسطيني'}
        self.mocksite._loginstatus = 0

        req = CachedRequest(expiry=1, site=self.mocksite,
                            action='query', meta='siteinfo')
        en_user_path = req._cachefile_path()

        self.mocksite._namespaces = {2: [u'مستخدم']}

        req = CachedRequest(expiry=1, site=self.mocksite,
                            action='query', meta='siteinfo')

        expect = u'MockSite()User(User:محمد الفلسطيني)' + \
                  "[('action', 'query'), ('meta', 'siteinfo')]"

        self.assertEqual(repr(req._uniquedescriptionstr()), repr(expect))

        self.assertEqual(req._uniquedescriptionstr().encode('utf-8'),
                         expect.encode('utf-8'))

        ar_user_path = req._cachefile_path()

        self.assertEqual(en_user_path, ar_user_path)


class DryQueryGenTests(DefaultSiteTestCase):

    def test_query_constructor(self):
        """Test QueryGenerator constructor.

        QueryGenerator constructor will call pywikibot.Site()
        if a site paramter is not provided.
        """
        qGen1 = QueryGenerator(action="query", meta="siteinfo")
        qGen2 = QueryGenerator(meta="siteinfo")
        self.assertEqual(str(qGen1.request), str(qGen2.request))


if __name__ == '__main__':
    unittest.main()
