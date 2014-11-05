# -*- coding: utf-8  -*-
"""
Test aspects to allow fine grained control over what tests are executed.

Several parts of the test infrastructure are implemented as mixins,
such as API result caching and excessive test durations.  An unused
mixin to show cache usage is included.
"""
#
# (C) Pywikibot team, 2014
#
# Distributed under the terms of the MIT license.
#
from __future__ import print_function
__version__ = '$Id$'
"""
    TODO:

        skip if the user is blocked.
        sysop flag, implement in site & page, and
            possibly some of the script tests.
        labs flag, for wikidataquery
        slow flag
            wikiquerydata - quite slow
            weblib - also slow
            (this class, and a FastTest, could error/pass based
             it consumed more than a specified amount of time allowed.)
        net flag should disable network libraries
        UITestCase:
            Not integrated; direct subclass of unittest.TestCase.
"""
import time
import sys
import os
import inspect

import pywikibot

from pywikibot import config, log, Site
from pywikibot.site import BaseSite
from pywikibot.family import WikimediaFamily
from pywikibot.data.api import Request as _original_Request

import tests
from tests import unittest, patch_request, unpatch_request


class TestCaseBase(unittest.TestCase):

    """Base class for all tests."""

    if not hasattr(unittest.TestCase, 'assertRaisesRegex'):
        def assertRaisesRegex(self, *args, **kwargs):
            """
            Wrapper of unittest.assertRaisesRegexp for Python 2 unittest.

            assertRaisesRegexp is deprecated in Python 3.
            """
            return self.assertRaisesRegexp(*args, **kwargs)

    if not hasattr(unittest.TestCase, 'assertRegex'):
        def assertRegex(self, *args, **kwargs):
            """
            Wrapper of unittest.assertRegexpMatches for Python 2 unittest.

            assertRegexpMatches is deprecated in Python 3.
            """
            return self.assertRegexpMatches(*args, **kwargs)

    if not hasattr(unittest.TestCase, 'assertCountEqual'):

        def assertCountEqual(self, *args, **kwargs):
            """
            Wrapper of unittest.assertItemsEqual for Python 2 unittest.

            assertItemsEqual is removed in Python 3.
            """
            return self.assertItemsEqual(*args, **kwargs)

    def assertPageInNamespaces(self, page, namespaces):
        """
        Assert that Pages is in namespaces.

        @param page: Page
        @type page: Page
        @param namespaces: expected namespaces
        @type namespaces: int or set of int
        """
        if isinstance(namespaces, int):
            namespaces = set([namespaces])

        self.assertIn(page.namespace(), namespaces,
                      "%s not in namespace %r" % (page, namespaces))

    def assertPagesInNamespaces(self, gen, namespaces):
        """
        Assert that generator returns Pages all in namespaces.

        @param gen: generator to iterate
        @type gen: generator
        @param namespaces: expected namespaces
        @type namespaces: int or set of int
        """
        if isinstance(namespaces, int):
            namespaces = set([namespaces])

        for page in gen:
            self.assertPageInNamespaces(page, namespaces)

    def assertPagesInNamespacesAll(self, gen, namespaces, skip=False):
        """
        Try to confirm that generator returns Pages for all namespaces.

        @param gen: generator to iterate
        @type gen: generator
        @param namespaces: expected namespaces
        @type namespaces: int or set of int
        @param count: maximum results to process
        @type count: int
        @param skip: skip test if not all namespaces found
        @param skip: bool
        """
        if isinstance(namespaces, int):
            namespaces = set([namespaces])
        else:
            assert(isinstance(namespaces, set))

        page_namespaces = [page.namespace() for page in gen]

        if skip and set(page_namespaces) != namespaces:
            raise unittest.SkipTest('Pages in namespaces %r not found.'
                                    % list(namespaces - set(page_namespaces)))
        else:
            self.assertEqual(set(page_namespaces), namespaces)


class TestLoggingMixin(TestCaseBase):

    """Logging for test cases."""

    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        cls._log_prefix = inspect.getfile(cls) + ':' + cls.__name__

    def setUp(self):
        """Set up each unit test."""
        super(TestLoggingMixin, self).setUp()

        if hasattr(self, '_outcomeForDoCleanups'):
            # Python 3 unittest & nose
            outcome = self._outcomeForDoCleanups
        elif hasattr(self, '_outcome'):
            # Python 3.4 nose
            outcome = self._outcome
        elif hasattr(self, '_resultForDoCleanups'):
            # Python 2 unittest & nose
            outcome = self._resultForDoCleanups
        else:
            return

        self._previous_errors = len(outcome.errors)
        # nose 3.4 doesn't has failures
        if hasattr(outcome, 'failures'):
            self._previous_failures = len(outcome.failures)

        log('START ' + self._log_prefix + '.' + self._testMethodName)

    def tearDown(self):
        """Tear down test."""
        super(TestLoggingMixin, self).tearDown()

        if hasattr(self, '_outcomeForDoCleanups'):
            # Python 3 unittest & nose
            outcome = self._outcomeForDoCleanups
        elif hasattr(self, '_outcome'):
            # Python 3.4 nose
            outcome = self._outcome
        elif hasattr(self, '_resultForDoCleanups'):
            # Python 2 unittest & nose
            outcome = self._resultForDoCleanups
        else:
            return

        if len(outcome.errors) > self._previous_errors:
            status = ' NOT OK: ERROR'
        # nose 3.4 doesn't has failures
        elif (hasattr(outcome, 'failures') and
                len(outcome.failures) > self._previous_failures):
            status = ' NOT OK: FAILURE'
        else:
            status = ' OK'

        log('END ' + self._log_prefix + '.' + self._testMethodName + status)


class TestTimerMixin(TestCaseBase):

    """Time each test and report excessive durations."""

    # Number of seconds each test may consume
    # before a note is added after the test.
    test_duration_warning_interval = 10

    def setUp(self):
        """Set up test."""
        super(TestTimerMixin, self).setUp()
        self.test_start = time.time()

    def tearDown(self):
        """Tear down test."""
        self.test_completed = time.time()
        duration = self.test_completed - self.test_start

        if duration > self.test_duration_warning_interval:
            print(' %0.3fs' % duration, end=' ')
            sys.stdout.flush()

        super(TestTimerMixin, self).tearDown()


class DisableSiteMixin(TestCaseBase):

    """Test cases not connected to a Site object.

    Do not use this for mock Site objects.

    Never set a class or instance variable called 'site'
    As it will prevent tests from executing when invoked as:
    $ nosetests -a '!site' -v
    """

    def setUp(self):
        """Set up test."""
        self.old_Site_lookup_method = pywikibot.Site
        pywikibot.Site = lambda *args: self.fail('%s: Site() not permitted'
                                                 % self.__class__.__name__)

        super(DisableSiteMixin, self).setUp()

    def tearDown(self):
        """Tear down test."""
        super(DisableSiteMixin, self).tearDown()

        pywikibot.Site = self.old_Site_lookup_method


class ForceCacheMixin(TestCaseBase):

    """Aggressively cached API test cases.

    Patches pywikibot.data.api to aggressively cache
    API responses.
    """

    def setUp(self):
        """Set up test."""
        patch_request()

        super(ForceCacheMixin, self).setUp()

    def tearDown(self):
        """Tear down test."""
        super(ForceCacheMixin, self).tearDown()

        unpatch_request()


class SiteNotPermitted(pywikibot.site.BaseSite):

    """Site interface to prevent sites being loaded."""

    def __init__(self, code, fam=None, user=None, sysop=None):
        raise pywikibot.SiteDefinitionError(
            'Loading site %s:%s during dry test not permitted'
            % (fam, code))


class DisconnectedSiteMixin(TestCaseBase):

    """Test cases using a disconnected Site object.

    Do not use this for mock Site objects.

    Never set a class or instance variable called 'site'
    As it will prevent tests from executing when invoked as:
    $ nosetests -a '!site' -v
    """

    def setUp(self):
        """Set up test."""
        self.old_config_interface = config.site_interface
        # TODO: put a dummy subclass into config.site_interface
        #       as the default, to show a useful error message.
        config.site_interface = SiteNotPermitted

        pywikibot.data.api.Request = tests.utils.DryRequest

        super(DisconnectedSiteMixin, self).setUp()

    def tearDown(self):
        """Tear down test."""
        super(DisconnectedSiteMixin, self).tearDown()

        config.site_interface = self.old_config_interface
        pywikibot.data.api.Request = _original_Request


class CacheInfoMixin(TestCaseBase):

    """Report cache hits and misses."""

    def setUp(self):
        """Set up test."""
        super(CacheInfoMixin, self).setUp()
        self.cache_misses_start = tests.cache_misses
        self.cache_hits_start = tests.cache_hits

    def tearDown(self):
        """Tear down test."""
        self.cache_misses = tests.cache_misses - self.cache_misses_start
        self.cache_hits = tests.cache_hits - self.cache_hits_start

        if self.cache_misses:
            print(' %d cache misses' % self.cache_misses, end=' ')
        if self.cache_hits:
            print(' %d cache hits' % self.cache_hits, end=' ')

        if self.cache_misses or self.cache_hits:
            sys.stdout.flush()

        super(CacheInfoMixin, self).tearDown()


class SiteWriteMixin(TestCaseBase):

    """
    Test cases involving writing to the server.

    When editing, the API should not be patched to use
    CachedRequest.  This class prevents that.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up the test class.

        Prevent test classes to write to the site and also cache results.

        Skip the test class if environment variable PYWIKIBOT2_TEST_WRITE
        does not equal 1.
        """
        if os.environ.get('PYWIKIBOT2_TEST_WRITE', '0') != '1':
            raise unittest.SkipTest(
                '%r write tests disabled. '
                'Set PYWIKIBOT2_TEST_WRITE=1 to enable.'
                % cls.__name__)

        if issubclass(cls, ForceCacheMixin):
            raise Exception(
                '%s can not be a subclass of both '
                'SiteEditTestCase and ForceCacheMixin'
                % cls.__name__)

        super(SiteWriteMixin, cls).setUpClass()


class RequireUserMixin(TestCaseBase):

    """Run tests against a specific site, with a login."""

    user = True

    @classmethod
    def require_site_user(cls, family, code, sysop=False):
        """Check the user config has a valid login to the site."""
        if not cls.has_site_user(family, code, sysop=sysop):
            raise unittest.SkipTest(
                '%s: No %susername for %s:%s'
                % (cls.__name__,
                   "sysop " if sysop else "",
                   family, code))

    @classmethod
    def setUpClass(cls):
        """
        Set up the test class.

        Skip the test class if the user config does not have
        a valid login to the site.
        """
        super(RequireUserMixin, cls).setUpClass()

        sysop = hasattr(cls, 'sysop') and cls.sysop

        for site in cls.sites.values():
            cls.require_site_user(site['family'], site['code'], sysop)

            site['site'].login(sysop)

            if not site['site'].user():
                raise unittest.SkipTest(
                    '%s: Unable able to login to %s as %s'
                    % (cls.__name__,
                       'sysop' if sysop else 'bot',
                       site['site']))

    def setUp(self):
        """
        Set up the test case.

        Login to the site if it is not logged in.
        """
        super(RequireUserMixin, self).setUp()

        sysop = hasattr(self, 'sysop') and self.sysop

        # There may be many sites, and setUp doesnt know
        # which site is to be tested; ensure they are all
        # logged in.
        for site in self.sites.values():
            site = site['site']

            if not site.logged_in(sysop):
                site.login(sysop)


class MetaTestCaseClass(type):

    """Test meta class."""

    def __new__(cls, name, bases, dct):
        """Create the new class."""
        def wrap_method(key, sitedata, func):

            def wrapped_method(self):
                sitedata = self.sites[key]
                self.family = sitedata['family']
                self.code = sitedata['code']
                self.site = sitedata['site']
                func(self, key)

            sitename = sitedata['family'] + ':' + sitedata['code']
            if func.__doc__:
                if func.__doc__.endswith('.'):
                    wrapped_method.__doc__ = func.__doc__[:-1]
                else:
                    wrapped_method.__doc__ = func.__doc__
                wrapped_method.__doc__ += ' on ' + sitename
            else:
                wrapped_method.__doc__ = 'Test ' + sitename

            return wrapped_method

        tests = [attr_name
                 for attr_name in dct
                 if attr_name.startswith('test')]

        dct['abstract_class'] = len(tests) == 0

        # Bail out if it is the abstract class.
        if dct['abstract_class']:
            return super(MetaTestCaseClass, cls).__new__(cls, name, bases, dct)

        # Inherit superclass attributes
        for base in bases:
            for key in ('pwb', 'net', 'site', 'user', 'sysop', 'write',
                        'sites', 'family', 'code', 'dry',
                        'cached', 'cacheinfo', 'wikibase'):
                if hasattr(base, key) and key not in dct:
                    # print('%s has %s; copying to %s'
                    #       % (base.__name__, key, name))
                    dct[key] = getattr(base, key)

        if 'pwb' in dct and dct['pwb']:
            dct['spawn'] = True
            if 'site' not in dct:
                raise Exception(
                    '%s: Test classes using pwb must set "site"'
                    % name)

        if 'net' in dct and dct['net'] is False:
            dct['site'] = False

        if 'sites' in dct and 'site' not in dct:
            dct['site'] = True

        # If either are specified, assume both should be specified
        if 'family' in dct or 'code' in dct:
            dct['site'] = True

            if (('sites' not in dct or not len(dct['sites']))
                    and 'family' in dct
                    and 'code' in dct and dct['code'] != '*'):
                # Add entry to self.sites
                dct['sites'] = {
                    str(dct['family'] + ':' + dct['code']): {
                        'code': dct['code'],
                        'family': dct['family'],
                    }
                }

        if 'dry' in dct and dct['dry'] is True:
            dct['net'] = False

        if (('sites' not in dct and 'site' not in dct) or
                ('site' in dct and not dct['site'])):
            # Prevent use of pywikibot.Site
            bases = tuple([DisableSiteMixin] + list(bases))

            # If the 'site' attribute is a false value,
            # remove it so it matches !site in nose.
            if 'site' in dct:
                del dct['site']

            # If there isn't a site, require declaration of net activity.
            if 'net' not in dct:
                raise Exception(
                    '%s: Test classes without a site configured must set "net"'
                    % name)

            # If the 'net' attribute is a false value,
            # remove it so it matches !net in nose.
            if not dct['net']:
                del dct['net']

            return super(MetaTestCaseClass, cls).__new__(cls, name, bases, dct)

        # The following section is only processed if the test uses sites.

        if 'dry' in dct and dct['dry']:
            bases = tuple([DisconnectedSiteMixin] + list(bases))
            del dct['net']
        else:
            dct['net'] = True

        if 'cacheinfo' in dct and dct['cacheinfo']:
            bases = tuple([CacheInfoMixin] + list(bases))

        if 'cached' in dct and dct['cached']:
            bases = tuple([ForceCacheMixin] + list(bases))

        if 'write' in dct and dct['write']:
            bases = tuple([SiteWriteMixin] + list(bases))

        if ('user' in dct and dct['user']) or ('sysop' in dct and dct['sysop']):
            bases = tuple([RequireUserMixin] + list(bases))

        for test in tests:
            test_func = dct[test]

            # method decorated with unittest.expectedFailure has no arguments
            # so it is assumed to not be a multi-site test method.
            if test_func.__code__.co_argcount == 0:
                continue

            # a normal test method only accepts 'self'
            if test_func.__code__.co_argcount == 1:
                continue

            # a multi-site test method only accepts 'self' and the site-key
            if test_func.__code__.co_argcount != 2:
                raise Exception(
                    '%s: Test method %s must accept either 1 or 2 arguments; '
                    ' %d found'
                    % (name, test, test_func.__code__.co_argcount))

            # create test methods processed by unittest
            for (key, sitedata) in dct['sites'].items():
                test_name = test + '_' + key

                dct[test_name] = wrap_method(key, sitedata, dct[test])

                if key in dct.get('expected_failures', []):
                    dct[test_name] = unittest.expectedFailure(dct[test_name])

            del dct[test]

        return super(MetaTestCaseClass, cls).__new__(cls, name, bases, dct)


class TestCase(TestTimerMixin, TestLoggingMixin, TestCaseBase):

    """Run tests on pre-defined sites."""

    __metaclass__ = MetaTestCaseClass

    @classmethod
    def setUpClass(cls):
        """
        Set up the test class.

        Prefetch the Site object for each of the sites the test
        class has declared are needed.
        """
        super(TestCase, cls).setUpClass()

        if not hasattr(cls, 'sites'):
            return

        # This stores the site under the site name.
        if not cls.sites:
            cls.sites = {}

        # If the test is not cached, create new Site objects for this class
        if not hasattr(cls, 'cached') or not cls.cached:
            orig_sites = pywikibot._sites
            pywikibot._sites = {}

        interface = None  # defaults to 'APISite'
        if hasattr(cls, 'dry') and cls.dry:
            # Delay load to avoid cyclic import
            from tests.utils import DrySite
            interface = DrySite

        for data in cls.sites.values():
            if 'site' not in data:
                data['site'] = Site(data['code'], data['family'],
                                    interface=interface)

        if not hasattr(cls, 'cached') or not cls.cached:
            pywikibot._sites = orig_sites

        if len(cls.sites) == 1:
            key = next(iter(cls.sites.keys()))
            cls.site = cls.sites[key]['site']

    @classmethod
    def get_site(cls, name=None):
        """Return the prefetched Site object."""
        if not name and hasattr(cls, 'sites'):
            if len(cls.sites) == 1:
                name = next(iter(cls.sites.keys()))
            else:
                raise Exception(
                    '"%s.get_site(name=None)" called with multiple sites'
                    % cls.__name__)

        if name and name not in cls.sites:
            raise Exception('"%s" not declared in %s'
                            % (name, cls.__name__))

        if isinstance(cls.site, BaseSite):
            assert(cls.sites[name]['site'] == cls.site)
            return cls.site

        return cls.sites[name]['site']

    @classmethod
    def has_site_user(cls, family, code, sysop=False):
        """Check the user config has a user for the site."""
        if not family:
            raise Exception('no family defined for %s' % cls.__name__)
        if not code:
            raise Exception('no site code defined for %s' % cls.__name__)

        usernames = config.sysopnames if sysop else config.usernames

        return code in usernames[family] or \
           '*' in usernames[family]

    def __init__(self, *args, **kwargs):
        """Constructor."""
        super(TestCase, self).__init__(*args, **kwargs)

        if not hasattr(self, 'sites'):
            return

        # Create an instance method named the same as the class method
        self.get_site = lambda name=None: self.__class__.get_site(name)

    def get_mainpage(self, site=None):
        """Create a Page object for the sites main page."""
        if not site:
            site = self.get_site()

        if hasattr(self, '_mainpage'):
            # For multi-site test classes, or site is specified as a param,
            # the cached mainpage object may not be the desired site.
            if self._mainpage.site == site:
                return self._mainpage

        mainpage = pywikibot.Page(site, site.siteinfo['mainpage'])
        if mainpage.isRedirectPage():
            mainpage = mainpage.getRedirectTarget()

        self._mainpage = mainpage

        return mainpage

    def get_missing_article(self, site=None):
        """Get a Page which refers to a missing page on the site."""
        if not site:
            site = self.get_site()
        page = pywikibot.Page(pywikibot.page.Link(
                              "There is no page with this title", site))
        if page.exists():
            raise unittest.SkipTest("Did not find a page that does not exist.")

        return page


if sys.version_info[0] > 2:
    import six
    TestCase = six.add_metaclass(MetaTestCaseClass)(TestCase)


class DefaultSiteTestCase(TestCase):

    """Run tests against the config specified site."""

    family = config.family
    code = config.mylang


class DefaultDrySiteTestCase(DefaultSiteTestCase):

    """Run tests using the config specified site in offline mode."""

    dry = True


class WikimediaSiteTestCase(TestCase):

    """Test class uses only WMF sites."""

    wmf = True


class WikimediaDefaultSiteTestCase(DefaultSiteTestCase, WikimediaSiteTestCase):

    """Test class to run against a WMF site, preferring the default site."""

    @classmethod
    def setUpClass(cls):
        """
        Set up the test class.

        Check that the default site is a Wikimedia site.
        Use en.wikipedia.org as a fallback.
        """
        super(WikimediaDefaultSiteTestCase, cls).setUpClass()

        assert(hasattr(cls, 'site') and hasattr(cls, 'sites'))

        assert(len(cls.sites) == 1)

        site = cls.get_site()

        if not isinstance(site.family, WikimediaFamily):
            print('%s using English Wikipedia instead of non-WMF config.family %s.'
                  % (cls.__name__, cls.family))
            cls.family = 'wikipedia'
            cls.code = 'en'
            cls.site = pywikibot.Site('en', 'wikipedia')
            cls.sites = {
                cls.site: {
                    'family': 'wikipedia',
                    'code': 'en',
                    'site': cls.site
                }
            }


class WikibaseTestCase(TestCase):

    """Run tests against a wikibase site."""

    wikibase = True

    @classmethod
    def setUpClass(cls):
        """
        Set up the test class.

        Checks that all sites are configured with a Wikibase repository,
        with Site.has_data_repository() returning True, and all sites
        use the same data repository.
        """
        super(WikibaseTestCase, cls).setUpClass()

        for site in cls.sites.values():
            if not site['site'].has_data_repository:
                raise unittest.SkipTest(
                    u'%s: %r does not have data repository'
                    % (cls.__name__, site['site']))

            if (hasattr(cls, 'repo') and
                    cls.repo != site['site'].data_repository()):
                raise Exception(
                    '%s: sites do not all have the same data repository'
                    % cls.__name__)

            cls.repo = site['site'].data_repository()

    @classmethod
    def get_repo(cls):
        """Return the prefetched DataSite object."""
        return cls.repo

    def __init__(self, *args, **kwargs):
        """Constructor."""
        super(WikibaseTestCase, self).__init__(*args, **kwargs)

        if not hasattr(self, 'sites'):
            return

        # Create an instance method named the same as the class method
        self.get_repo = lambda: self.repo


class WikibaseClientTestCase(WikibaseTestCase):

    """Run tests against a specific site connected to a wikibase."""

    @classmethod
    def setUpClass(cls):
        """
        Set up the test class.

        Checks that all sites are configured as a Wikibase client,
        with Site.has_transcluded_data() returning True.
        """
        super(WikibaseClientTestCase, cls).setUpClass()

        for site in cls.sites.values():
            if not site['site'].has_transcluded_data:
                raise unittest.SkipTest(
                    u'%s: %r does not have transcluded data'
                    % (cls.__name__, site['site']))


class DefaultWikibaseClientTestCase(WikibaseClientTestCase,
                                    DefaultSiteTestCase):

    """Run tests against any site connected to a Wikibase."""

    pass


class WikidataTestCase(WikibaseTestCase):

    """Test cases use Wikidata."""

    family = 'wikidata'
    code = 'wikidata'

    cached = True


class DefaultWikidataClientTestCase(DefaultWikibaseClientTestCase):

    """Run tests against any site connected to Wikidata."""

    @classmethod
    def setUpClass(cls):
        """
        Set up the test class.

        Require the data repository is wikidata.org.
        """
        super(WikibaseClientTestCase, cls).setUpClass()

        if str(cls.get_repo()) != 'wikidata:wikidata':
            raise unittest.SkipTest(
                u'%s: %s is not connected to Wikidata.'
                % (cls.__name__, cls.get_site()))


class PwbTestCase(TestCase):

    """Test cases use pwb.py to invoke scripts."""

    pwb = True
    spawn = True
    # pywikibot.handleArgs currently instantiates a Site object
    # and tries to fetch the users messages.
    site = True
    net = True
    user = True


class DeprecationTestCase(TestCase):

    """Test cases for deprecation function in the tools module."""

    deprecation_messages = []

    @staticmethod
    def _record_messages(msg, *args, **kwargs):
        DeprecationTestCase.deprecation_messages.append(msg)

    @staticmethod
    def _reset_messages():
        DeprecationTestCase.deprecation_messages = []

    def assertDeprecation(self, msg):
        self.assertIn(msg, DeprecationTestCase.deprecation_messages)

    def assertNoDeprecation(self, msg=None):
        if msg:
            self.assertNotIn(msg, DeprecationTestCase.deprecation_messages)
        else:
            self.assertEqual([], DeprecationTestCase.deprecation_messages)

    def setUp(self):
        self.tools_warning = pywikibot.tools.warning
        self.tools_debug = pywikibot.tools.debug

        pywikibot.tools.warning = DeprecationTestCase._record_messages
        pywikibot.tools.debug = DeprecationTestCase._record_messages

        super(DeprecationTestCase, self).setUp()

        DeprecationTestCase._reset_messages()

    def tearDown(self):
        pywikibot.tools.warning = self.tools_warning
        pywikibot.tools.debug = self.tools_warning

        super(DeprecationTestCase, self).tearDown()
