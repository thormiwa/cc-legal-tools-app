from pprint import pprint
from unittest import mock
from unittest.mock import MagicMock, call

import git
import polib
import requests
from django.test import TestCase, override_settings

from i18n import DEFAULT_LANGUAGE_CODE
from licenses.tests.factories import LegalCodeFactory, LicenseFactory
from licenses.transifex import TransifexAuthRequests, TransifexHelper

TEST_PROJECT_SLUG = "proj"
TEST_ORGANIZATION_SLUG = "org"
TEST_TOKEN = "aaaaabbbbbb"
TEST_TRANSIFEX_SETTINGS = {
    "ORGANIZATION_SLUG": TEST_ORGANIZATION_SLUG,
    "PROJECT_SLUG": TEST_PROJECT_SLUG,
    "API_TOKEN": TEST_TOKEN,
}

# To shorten lines of code, make a short alias
# for  'mock.patch' and 'mock.patch.object'
mp = mock.patch
mpo = mock.patch.object


@override_settings(
    TRANSIFEX=TEST_TRANSIFEX_SETTINGS, TRANSLATION_REPOSITORY_DIRECTORY="/trans/repo",
)
class TestTransifex(TestCase):
    def setUp(self):
        self.helper = TransifexHelper()

    def test_request20_success(self):
        with mpo(self.helper.api_v20, "get") as mock_get:
            mock_get.return_value = mock.MagicMock(status_code=200)
            self.helper.request20(
                path="foo/bar", method="get", data={"a": 1}, files=[(1, 2)]
            )
        mock_get.assert_called_with(
            "https://www.transifex.com/api/2/foo/bar", data={"a": 1}, files=[(1, 2)]
        )

    def test_request25_success(self):
        with mpo(self.helper.api_v25, "get") as mock_get:
            mock_get.return_value = mock.MagicMock(status_code=200)
            self.helper.request25(
                path="foo/bar", method="get", data={"a": 1}, files=[(1, 2)]
            )
        mock_get.assert_called_with(
            "https://api.transifex.com/foo/bar", data={"a": 1}, files=[(1, 2)]
        )

    def test_request20_failure(self):
        error_response = requests.Response()
        error_response.status_code = 500
        error_response.reason = "testing"

        with mpo(self.helper.api_v20, "get") as mock_get:
            mock_get.return_value = error_response
            with self.assertRaises(requests.HTTPError):
                self.helper.request20(
                    path="foo/bar", method="get", data={"a": 1}, files=[(1, 2)]
                )
        mock_get.assert_called_with(
            "https://www.transifex.com/api/2/foo/bar", data={"a": 1}, files=[(1, 2)]
        )

    def test_request25_failure(self):
        error_response = requests.Response()
        error_response.status_code = 500
        error_response.reason = "testing"

        with mpo(self.helper.api_v25, "get") as mock_get:
            mock_get.return_value = error_response
            with self.assertRaises(requests.HTTPError):
                self.helper.request25(
                    path="foo/bar", method="get", data={"a": 1}, files=[(1, 2)]
                )
        mock_get.assert_called_with(
            "https://api.transifex.com/foo/bar", data={"a": 1}, files=[(1, 2)]
        )

    def test_get_transifex_resources(self):
        with mpo(self.helper, "request25") as mock_request:
            mock_request.return_value.json.return_value = {"a": 1}
            result = self.helper.get_transifex_resources()
        mock_request.assert_called_with(
            "get", "organizations/org/projects/proj/resources/"
        )
        self.assertEqual({"a": 1}, result)

    def test_files_argument(self):
        result = self.helper.files_argument("foo", "bar", "baz")
        self.assertEqual([("foo", ("bar", "baz", "application/octet-stream"))], result)

    def test_create_resource(self):
        with mpo(self.helper, "request20") as mock_request:
            self.helper.create_resource("slug", "name", "pofilename", "pofilecontent")
        mock_request.assert_called_with(
            "post",
            "project/proj/resources/",
            data={"slug": "slug", "name": "name", "i18n_type": "PO"},
            files=[
                ("content", ("pofilename", "pofilecontent", "application/octet-stream"))
            ],
        )

    def test_update_source_messages(self):
        with mpo(self.helper, "request20") as mock_request:
            self.helper.update_source_messages("slug", "pofilename", "pofilecontent")
        mock_request.assert_called_with(
            "put",
            "project/proj/resource/slug/content/",
            files=[
                ("content", ("pofilename", "pofilecontent", "application/octet-stream"))
            ],
        )

    def test_update_translations(self):
        with mpo(self.helper, "request20") as mock_request:
            self.helper.update_translations(
                "slug", "lang", "pofilename", "pofilecontent"
            )
        mock_request.assert_called_with(
            "put",
            "project/proj/resource/slug/translation/lang/",
            files=[
                ("file", ("pofilename", "pofilecontent", "application/octet-stream"))
            ],
        )

    def test_upload_messages_to_transifex_no_resource_yet(self):
        # English so we can create the resource
        license = LicenseFactory(license_code="by-nd", version="4.0")
        legalcode = LegalCodeFactory(
            license=license, language_code=DEFAULT_LANGUAGE_CODE,
        )

        pofile_content = """
msgid ""
msgstr ""
"Project-Id-Version: by-nd-4.0\n"
"Language: en\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=utf-8\n"
"Content-Transfer-Encoding: 8bit\n"

msgid "license_medium"
msgstr "Attribution-NoDerivatives 4.0 International"
        """
        english_pofile = polib.pofile(pofile=pofile_content)

        with mpo(self.helper, "get_transifex_resources") as mock_gtr:
            mock_gtr.return_value = []

            with mpo(self.helper, "create_resource") as mock_create_resource:
                with mpo(legalcode, "get_pofile") as mock_gpwem:
                    mock_gpwem.return_value = english_pofile
                    with mp("licenses.transifex.get_pofile_content") as mock_gpc:
                        mock_gpc.return_value = "not really"
                        self.helper.upload_messages_to_transifex(legalcode)

        mock_create_resource.assert_called_with(
            "by-nd_40",
            "CC BY-ND 4.0",
            "/trans/repo/legalcode/en/LC_MESSAGES/by-nd_40.po",
            "not really",
        )
        mock_gpwem.assert_called_with()
        mock_gtr.assert_called_with()

    def test_upload_messages_to_transifex_no_resource_yet_not_english(self):
        # Must be english or we can't create the resource
        # If we try this with a non-english language and there's no resource,
        # we should get an error.
        legalcode = LegalCodeFactory(language_code="es")
        test_pofile = polib.POFile()

        with mpo(self.helper, "get_transifex_resources") as mock_gtr:
            mock_gtr.return_value = []
            with mpo(legalcode, "get_pofile") as mock_gpwem:
                mock_gpwem.return_value = test_pofile
                with self.assertRaisesMessage(ValueError, "Must upload English first"):
                    self.helper.upload_messages_to_transifex(legalcode)

        mock_gtr.assert_called_with()
        mock_gpwem.assert_called_with()

    def test_upload_messages_english_resource_exists(self):
        # English because it's the source messages and is handled differently
        license = LicenseFactory(license_code="by-nd", version="4.0")
        legalcode = LegalCodeFactory(
            license=license, language_code=DEFAULT_LANGUAGE_CODE,
        )
        test_resources = [{"slug": license.resource_slug,}]
        test_pofile = polib.POFile()
        with mpo(self.helper, "get_transifex_resources") as mock_gtr:
            mock_gtr.return_value = test_resources
            with mp("licenses.transifex.get_pofile_content") as mock_gpc:
                mock_gpc.return_value = "not really"
                with mpo(self.helper, "update_source_messages") as mock_usm:
                    self.helper.upload_messages_to_transifex(legalcode, test_pofile)

        mock_gtr.assert_called_with()
        mock_gpc.assert_called_with(test_pofile)
        mock_usm.assert_called_with(
            "by-nd_40",
            "/trans/repo/legalcode/en/LC_MESSAGES/by-nd_40.po",
            "not really",
        )

    def test_upload_messages_non_english_resource_exists(self):
        # non-English because it's not the source messages and is handled differently
        license = LicenseFactory(license_code="by-nd", version="4.0")
        legalcode = LegalCodeFactory(license=license, language_code="fr")
        test_resources = [{"slug": license.resource_slug,}]
        test_pofile = mock.MagicMock()
        with mpo(self.helper, "get_transifex_resources") as mock_gtr:
            mock_gtr.return_value = test_resources
            with mp("licenses.transifex.get_pofile_content") as mock_gpc:
                mock_gpc.return_value = "not really"
                with mpo(self.helper, "update_translations") as mock_ut:
                    self.helper.upload_messages_to_transifex(legalcode, test_pofile)

        mock_gtr.assert_called_with()
        mock_gpc.assert_called_with(test_pofile)
        mock_ut.assert_called_with(
            "by-nd_40",
            "fr",
            "/trans/repo/legalcode/fr/LC_MESSAGES/by-nd_40.po",
            "not really",
        )

    def test_get_transifex_resource_stats(self):
        # First call returns a response whose json value is a list of dicts with slug keys
        call0_response = MagicMock()
        call0_response.json.return_value = [{"slug": "slug0"}]

        # second call is more data about slug0 - FIXME
        call1_response = MagicMock()
        call1_response.json.return_value = {"stats": "stats1"}
        with mpo(self.helper, "request25") as mock_request25:
            # Return values for each call to request25
            mock_request25.side_effect = [
                call0_response,
                call1_response,
            ]
            result = self.helper.get_transifex_resource_stats()
        calls = mock_request25.call_args_list
        self.assertEqual([
            call('get', 'organizations/org/projects/proj/resources/'),
            call('get', 'organizations/org/projects/proj/resources/slug0'),
        ], calls)
        self.assertEqual({"slug0": "stats1"}, result)


class CheckForTranslationUpdatesTest(TestCase):
    def test_check_for_translation_updates_with_dirty_repo(self):
        helper = TransifexHelper()
        mock_repo = MagicMock()
        mock_repo.is_dirty.return_value = True
        with mpo(git, "Repo") as mock_Repo:
            mock_Repo.return_value = mock_repo

            with self.assertRaisesMessage(Exception, "is dirty. We cannot continue."):
                helper.check_for_translation_updates()

    def test_check_for_translation_updates_with_no_legalcodes(self):
        helper = TransifexHelper()
        mock_repo = MagicMock()
        mock_repo.is_dirty.return_value = False
        print(f"mock_repo = {mock_repo}")
        print(f"mock_repo.is_dirty = {mock_repo.is_dirty}")
        # mock_RepoClass = MagicMock(side_effect=mock_repo)
        # print(f"mock_RepoClass = {mock_RepoClass}")
        with mock.patch("licenses.transifex.git") as mock_git:
            print(f"mock_git = {mock_git}")
            mock_git.Repo.return_value = mock_repo
            helper.check_for_translation_updates()


class TestTransifexAuthRequests(TestCase):
    def test_transifex_auth_requests(self):
        token = "frenchfriedpotatoes"
        auth = TransifexAuthRequests(token)
        self.assertEqual(token, auth.token)
        auth2 = TransifexAuthRequests(token)
        self.assertEqual(auth, auth2)
        auth3 = TransifexAuthRequests("another token")
        self.assertNotEqual(auth, auth3)
        r = mock.Mock(headers={})
        result = auth(r)
        self.assertEqual(r, result)
        self.assertEqual(
            {"Authorization": "Basic YXBpOmZyZW5jaGZyaWVkcG90YXRvZXM="}, result.headers
        )
