# -*- coding: utf-8 -*-
"""Test onadata.libs.utils.viewer_tools."""
import requests_mock
from django.conf import settings
from django.http import Http404
from django.test.client import RequestFactory
from django.test.utils import override_settings
from django.utils import timezone
from onadata.libs.exceptions import EnketoError

from onadata.apps.logger.models import XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.viewer_tools import (export_def_from_filename,
                                             generate_enketo_form_defaults,
                                             get_client_ip, get_form,
                                             get_form_url,
                                             get_single_submit_url)


class TestViewerTools(TestBase):
    """Test viewer_tools functions."""

    def test_export_def_from_filename(self):
        """Test export_def_from_filename()."""
        filename = "path/filename.xlsx"
        ext, mime_type = export_def_from_filename(filename)
        self.assertEqual(ext, 'xlsx')
        self.assertEqual(mime_type, 'vnd.openxmlformats')

    def test_get_client_ip(self):
        """Test get_client_ip()."""
        request = RequestFactory().get("/")
        client_ip = get_client_ip(request)
        self.assertIsNotNone(client_ip)
        # will this always be 127.0.0.1
        self.assertEqual(client_ip, "127.0.0.1")

    # pylint: disable=C0103
    def test_get_enketo_defaults_without_vars(self):
        """Test generate_enketo_form_defaults() without vars."""
        # create xform
        self._publish_transportation_form()
        # create map without variables
        defaults = generate_enketo_form_defaults(self.xform)

        # should return empty default map
        self.assertEqual(defaults, {})

    # pylint: disable=C0103
    def test_get_enketo_defaults_with_right_xform(self):
        """Test generate_enketo_form_defaults() with xform vars."""
        # create xform
        self._publish_transportation_form()
        # create kwargs with existing xform variable
        xform_variable_name = \
            'available_transportation_types_to_referral_facility'
        xform_variable_value = 'ambulance'
        kwargs = {xform_variable_name: xform_variable_value}
        defaults = generate_enketo_form_defaults(self.xform, **kwargs)

        key = "defaults[/transportation/transport/{}]".format(
            xform_variable_name)
        self.assertEqual(defaults, {key: xform_variable_value})

    # pylint: disable=C0103
    def test_get_enketo_defaults_with_multiple_params(self):
        """Test generate_enketo_form_defaults() with multiple params."""
        # create xform
        self._publish_transportation_form()
        # create kwargs with existing xform variable
        transportation_types = \
            'available_transportation_types_to_referral_facility'
        transportation_types_value = 'ambulance'

        frequency = 'frequency_to_referral_facility'
        frequency_value = 'daily'

        kwargs = {
            transportation_types: transportation_types_value,
            frequency: frequency_value
        }
        defaults = generate_enketo_form_defaults(self.xform, **kwargs)

        transportation_types_key = \
            "defaults[/transportation/transport/{}]".format(
                transportation_types)
        frequency_key = "defaults[/transportation/transport/"\
                        "loop_over_transport_types_frequency/"\
                        "{}/{}]".format(transportation_types_value, frequency)
        self.assertIn(transportation_types_key, defaults)
        self.assertIn(frequency_key, defaults)

    # pylint: disable=C0103
    def test_get_enketo_defaults_with_non_existent_field(self):
        """Test generate_enketo_form_defaults() with non existent field."""
        # create xform
        self._publish_transportation_form()
        # create kwargs with NON-existing xform variable
        kwargs = {'name': 'bla'}
        defaults = generate_enketo_form_defaults(self.xform, **kwargs)
        self.assertEqual(defaults, {})

    def test_get_form(self):
        """Test get_form()."""
        # non existent id_string
        with self.assertRaises(Http404):
            get_form({'id_string': 'non_existent_form'})

        self._publish_transportation_form()

        # valid xform id_string
        kwarg = {'id_string__iexact': self.xform.id_string}
        xform = get_form(kwarg)
        self.assertIsInstance(xform, XForm)

        # pass a queryset
        kwarg['queryset'] = XForm.objects.all()
        xform = get_form(kwarg)
        self.assertIsInstance(xform, XForm)

        # deleted form
        xform.deleted_at = timezone.now()
        xform.save()
        with self.assertRaises(Http404):
            get_form(kwarg)

    @override_settings(TESTING_MODE=False)
    def test_get_form_url(self):
        """Test get_form_url()."""
        request = RequestFactory().get('/')

        # default https://ona.io
        url = get_form_url(request)
        self.assertEqual(url, 'https://ona.io')

        # with username https://ona.io/bob
        url = get_form_url(request, username='bob')
        self.assertEqual(url, 'https://ona.io/bob')

        # with http protocol http://ona.io/bob
        url = get_form_url(request, username='bob', protocol='http')
        self.assertEqual(url, 'http://ona.io/bob')

        # preview url http://ona.io/preview/bob
        url = get_form_url(
            request, username='bob', protocol='http', preview=True)
        self.assertEqual(url, 'http://ona.io/preview/bob')

        # with form pk url http://ona.io/bob/1
        url = get_form_url(request, username='bob', xform_pk=1)
        self.assertEqual(url, 'https://ona.io/bob/1')

    @override_settings(TESTING_MODE=False, ENKETO_URL='https://enketo.ona.io')
    @requests_mock.Mocker()
    def test_get_single_submit_url(self, mocked):
        """Test get_single_submit_url.

        Ensures single submit url is being received.
        """
        request = RequestFactory().get('/')

        mocked_response = {
            "single_url": "https://enketo.ona.io/single/::XZqoZ94y",
            "code": 200
        }

        enketo_url = settings.ENKETO_URL + "/api/v2/survey/single/once"
        username = "bob"
        server_url = get_form_url(
            request, username, settings.ENKETO_PROTOCOL, True, xform_pk=1)

        url = '{}?server_url={}&form_id={}'.format(
            enketo_url, server_url, "tag_team")
        mocked.get(url, json=mocked_response)
        response = get_single_submit_url(
            request, username, id_string="tag_team", xform_pk=1)

        self.assertEqual(
            response, 'https://enketo.ona.io/single/::XZqoZ94y')

    @override_settings(TESTING_MODE=False)
    def test_get_single_submit_url_error_action(self):
        """Test get_single_submit_url to return appropriate error message."""
        request = RequestFactory().get('/')

        with self.assertRaises(EnketoError):
            get_single_submit_url(
                request, username='Milly', id_string="tag_team", xform_pk=1)
