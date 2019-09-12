from __future__ import print_function, unicode_literals

try:
    from urllib.parse import urljoin, urlparse, urlunparse
except ImportError:
    from urlparse import urljoin, urlparse, urlunparse

try:
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
except ImportError:
    from urllib2 import urlopen, Request, HTTPError

import json

from .camera import UnifiVideoCamera
from .recording import UnifiVideoRecording
from .collections import UnifiVideoCollection

try:
    type(unicode)
except NameError:
    unicode = str

endpoints = {
    'login': 'login',
    'cameras': 'camera',
    'recordings': lambda x: 'recording?idsOnly=false&' \
        'sortBy=startTime&sort=desc&limit={}'.format(x),
    'bootstrap': 'bootstrap',
}

class UnifiVideoVersionError(ValueError):
    """Unsupported UniFi Video version"""

    def __init__(self, message=None):
        if not message:
            message = 'Unsupported UniFi Video version'
        super(UnifiVideoVersionError, self).__init__(message)


class UnifiVideoAPI(object):
    """Encapsulates a single UniFi Video server.
    """

    _supported_ufv_versions = ['3.9.12']

    def __init__(self, api_key=None, username=None, password=None,
            addr='localhost', port=7080, schema='http', verify_cert=True,
            check_ufv_version=True):

        if not verify_cert and schema == 'https':
            import ssl
            self._ssl_context = ssl._create_unverified_context()

        if not api_key and not (username and password):
            raise ValueError('To init {}, provide either API key ' \
                'or username password pair'.format(type(self).__name__))

        self.api_key = api_key
        self.login_attempts = 0
        self.jsession_av = None
        self.username = username
        self.password = password
        self.base_url = '{}://{}:{}/api/2.0/'.format(schema, addr, port)
        self._version_stickler = check_ufv_version

        self._load_data(self.get(endpoints['bootstrap']))

        self.cameras = UnifiVideoCollection(UnifiVideoCamera)
        self.recordings = UnifiVideoCollection(UnifiVideoRecording)
        self.refresh_cameras()
        self.refresh_recordings()

    def _load_data(self, data):
        if not isinstance(data, dict):
            raise ValueError('Server responded with unknown bootstrap data')
        self._data = data.get('data', [{}])
        self._name = self._data[0].get('nvrName', None)
        self._version = self._data[0].get('systemInfo', {}).get('version', None)
        self._is_supported = self._version in \
            UnifiVideoAPI._supported_ufv_versions

        #if self._version_stickler and not self._is_supported:
        #    raise UnifiVideoVersionError()

    def _ensure_headers(self, req):
        req.add_header('Content-Type', 'application/json')
        if self.jsession_av:
            req.add_header('Cookie', 'JSESSIONID_AV={}'\
                .format(self.jsession_av))

    def _build_req(self, url, data=None, method=None):
        url = urljoin(self.base_url, url)
        if self.api_key:
            _s, _nloc, _path, _params, _q, _f = urlparse(url)
            _q = '{}&apiKey={}'.format(_q, self.api_key) if len(_q) \
                else 'apiKey={}'.format(self.api_key)
            url = urlunparse((_s, _nloc, _path, _params, _q, _f))
        req = Request(url, bytes(json.dumps(data).encode('utf8'))) \
            if data else Request(url)
        self._ensure_headers(req)
        if method:
            req.get_method = lambda: method
        return req

    def _parse_cookies(self, res, return_existing=False):
        if 'Set-Cookie' not in res.headers:
            return False
        cookies = res.headers['Set-Cookie'].split(',')
        for cookie in cookies:
            for part in cookie.split(';'):
                if 'JSESSIONID_AV' in part:
                    self.jsession_av = part\
                        .replace('JSESSIONID_AV=', '').strip()
                    return True

    def _urlopen(self, req):
        try:
            return urlopen(req, context=self._ssl_context)
        except AttributeError:
            return urlopen(req)

    def _get_response_content(self, res, raw=False):
        try:
            if res.headers['Content-Type'] == 'application/json':
                return json.loads(res.read().decode('utf8'))
            raise KeyError
        except KeyError:
            upstream_filename = None

            if 'Content-Disposition' in res.headers:
                for part in res.headers['Content-Disposition'].split(';'):
                    part = part.strip()
                    if part.startswith('filename='):
                        upstream_filename = part.split('filename=').pop()

            if isinstance(raw, str) or isinstance(raw, unicode):
                filename = raw if len(raw) else upstream_filename
                with open(filename, 'wb') as f:
                    while True:
                        chunk = res.read(4096)
                        if not chunk:
                            break
                        f.write(chunk)
                    f.truncate()
                    return True
            elif isinstance(raw, bool):
                return res.read()
            else:
                try:
                    return res.read().decode('utf8')
                except UnicodeDecodeError:
                    return res.read()

    def _handle_http_401(self, url, raw):
        if self.api_key:
            raise ValueError('Invalid API key')
        elif self.login():
            return self.get(url, raw)

    def get(self, url, raw=False):
        """Send GET request.

        :param str url: API endpoint URL
        :param raw: Set `str` filename if you want to save the response to a file.
            Set to `True` if you want the to return raw response data.
        :type raw: bool or str
        """
        req = self._build_req(url)
        try:
            res = self._urlopen(req)
            self._parse_cookies(res)
            return self._get_response_content(res, raw)
        except HTTPError as err:
            if err.code == 401 and self.login_attempts == 0:
                return self._handle_http_401(url, raw)
            return False

    def post(self, url, data=None, raw=False, method=None):
        """Send POST request.

        :param str url: API endpoint URL
        :param data: Post data
        :type data: dict or NoneType
        :param raw: Set `str` filename if you want to save the response to a file.
            Alternatively, set to `True` if you want the raw response as
            return value.
        :type raw: bool or str

        Note:
            - ``url`` will be appended to the API base URL
            - Return value will be a ``dict`` if server responds
                with ``Content-Type: application/json``, regardless of
                of the ``raw`` param.
        """

        if data:
            req = self._build_req(url, data, method)
        else:
            req = self._build_req(url, method=method)
        try:
            res = self._urlopen(req)
            self._parse_cookies(res)
            return self._get_response_content(res, raw)
        except HTTPError as err:
            if err.code == 401 and url != 'login' and self.login_attempts == 0:
                return self._handle_http_401(url, raw)
            return False

    def put(self, url, data=None, raw=False):
        """Send PUT request. See :func:`~unifi_video.UnifiVideoAPI.post`.
        """
        return self.post(url, data, raw, 'PUT')

    def delete(self, url, data=None, raw=False):
        """Send DELETE request. See :func:`~unifi_video.UnifiVideoAPI.post`.
        """
        return self.post(url, data, raw, 'DELETE')

    def login(self):
        self.login_attempts = 1
        res_data = self.post(endpoints['login'], {
            'username': self.username,
            'password': self.password})
        if res_data:
            self.login_attempts = 0
            return True
        else:
            return False

    def refresh_cameras(self):
        """GET cameras from the server and update ``self.cameras``.
        """
        cameras = self.get(endpoints['cameras'])
        if isinstance(cameras, dict):
            for camera in cameras.get('data', []):
                self.cameras.add(UnifiVideoCamera(self, camera))

    def refresh_recordings(self, limit=300):
        """GET recordings from the server and update local ``self.recordings``.

        :param int limit: Limit the number of recording items
            to fetch (``0`` for no limit).
        """
        recordings = self.get(endpoints['recordings'](limit))
        if isinstance(recordings, dict):
            for recording in recordings.get('data', []):
                self.recordings.add(UnifiVideoRecording(self, recording))

    def get_camera(self, search_term):
        """Get a camera whose ``name``, ``_id``, or ``overlay_text``
        matches ``search_term``.

        :return: Camera (if found).
        :rtype: :class:`~unifi_video.camera.UnifiVideoCamera` or `NoneType`
        """
        search_term = search_term.lower()
        for camera in self.cameras:
            if camera._id == search_term or \
                    camera.name.lower() == search_term or \
                    camera.overlay_text.lower() == search_term:
                return camera

    def __str__(self):
        return '{}: {}'.format(type(self).__name__, {
            'name': self._name,
            'version': self._version,
            'supported_version': self._is_supported
        })


__all__ = ['UnifiVideoAPI']
