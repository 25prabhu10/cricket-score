#  This file is part of Headphones.
#
#  Headphones is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Headphones is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Headphones.  If not, see <http://www.gnu.org/licenses/>.
# <https://github.com/rembo10/headphones/tree/master/headphones>

import os
import sys

import requests
from bs4 import BeautifulSoup
from logzero import logger as log


class FakeLock(object):
    """
    If no locking or request throttling is needed, use this
    """

    def __enter__(self):
        """
        Do nothing on enter
        """
        pass

    def __exit__(self, type, value, traceback):
        """
        Do nothing on exit
        """
        pass


def bool_int(value):
    """
    Casts a config value into a 0 or 1
    """
    if isinstance(value, str):
        if value.lower() in ('', '0', 'false', 'f', 'no', 'n', 'off'):
            value = 0
    return int(bool(value))


def setproxy():
    """
    SETS PROXY AND USER AGENTS
    """

    # set proxies from os environment variable http_proxy
    proxy_ip = ''

    if 'http_proxy' in os.environ:
        proxy_ip = os.environ['http_proxy']

    proxies = {
        'http': proxy_ip,
        'https': proxy_ip,
    }

    # Set user agents
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:49.0) Gecko/20100101 Firefox/49.0'
    }
    return proxies, headers


# Disable SSL certificate warnings. We have our own handling
requests.packages.urllib3.disable_warnings()


def request_response(url, method="get", auto_raise=True, add_proxies=True, whitelist_status_code=None, lock=FakeLock(), **kwargs):
    """
    Convenient wrapper for `requests.get', which will capture the exceptions
    and log them. On success, the Response object is returned. In case of a
    exception, None is returned.
    Additionally, there is support for rate limiting. To use this feature,
    supply a tuple of (lock, request_limit). The lock is used to make sure no
    other request with the same lock is executed. The request limit is the
    minimal time between two requests (and so 1/request_limit is the number of
    requests per seconds).
    """

    proxies, headers = setproxy() if add_proxies else (None, None)

    # Convert whitelist_status_code to a list if needed
    if whitelist_status_code and isinstance(whitelist_status_code, list):
        whitelist_status_code = [whitelist_status_code]

    # Disable verification of SSL certificates if requested. Note: this could
    # pose a security issue!
    VERIFY_SSL_CERT = (bool_int, 'Advanced', 1)
    kwargs["verify"] = bool(VERIFY_SSL_CERT)

    # This fix is put in place for systems with broken SSL (like QNAP)
    if not VERIFY_SSL_CERT and sys.version_info >= (2, 7, 9):
        try:
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
        except:
            pass

    # Map method to the request.XXX method. This is a simple hack, but it
    # allows requests to apply more magic per method. See lib/requests/api.py.
    request_method = getattr(requests, method.lower())

    try:
        # Request URL and wait for response
        with lock:
            log.debug(f"Requesting URL via {method.upper()} method: {url}")
            response = request_method(
                url, proxies=proxies, headers=headers, **kwargs)

        # If status code != OK, then raise exception, except if the status code
        # is white listed.
        if whitelist_status_code and auto_raise:
            if response.status_code not in whitelist_status_code:
                try:
                    response.raise_for_status()
                except:
                    log.debug(
                        f"Response status code {response.status_code} is not white listed, raised exception")
                    raise
        elif auto_raise:
            response.raise_for_status()

        return response
    except requests.exceptions.SSLError as e:
        if kwargs["verify"]:
            log.error(
                "Unable to connect to remote host because of a SSL error. "
                "It is likely that your system cannot verify the validity "
                "of the certificate. The remote certificate is either "
                "self-signed, or the remote server uses SNI. See the wiki for "
                "more information on this topic.")
        else:
            log.exception(
                "SSL error raised during connection, with certificate "
                f"verification turned off: {e}")
    except requests.ConnectionError:
        log.error(
            "Unable to connect to remote host. Check if the remote "
            "host is up and running.")
    except requests.Timeout:
        log.error(
            "Request timed out. The remote host did not respond in a timely "
            "manner.")
    except requests.HTTPError as e:
        if e.response is not None:
            if e.response.status_code >= 500:
                cause = "remote server error"
            elif e.response.status_code >= 400:
                cause = "local client error"
            else:
                # I don't think we will end up here, but for completeness
                cause = "unknown"

            log.exception(
                f"Request raise HTTP error with status code {e.response.status_code} ({cause}).")
        else:
            log.error("Request raised HTTP error.")
    except requests.RequestException as e:
        log.exception(f"Request raised exception: {e}")


def request_soup(url, **kwargs):
    """
    Wrapper for `request_response', which will return a BeatifulSoup object if
    no exceptions are raised.
    """

    parser = kwargs.pop("parser", "lxml")
    response = request_response(url, **kwargs)

    if response:
        return BeautifulSoup(response.text, parser)


def request_json(url, **kwargs):
    """
    Wrapper for `request_response', which will decode the response as JSON
    object and return the result, if no exceptions are raised.
    As an option, a validator callback can be given, which should return True
    if the result is valid.
    """

    validator = kwargs.pop("validator", None)
    response = request_response(url, **kwargs)

    if response is not None:
        try:
            result = response.json()

            if validator and not validator(result):
                log.error("JSON validation result failed")
            else:
                return result
        except ValueError:
            log.error("Response returned invalid JSON data")


def request_content(url, **kwargs):
    """
    Wrapper for `request_response', which will return the raw content.
    """

    response = request_response(url, **kwargs)

    if response:
        return response.content


# def server_message(response):
#     """
#     Extract server message from response and log in to logger with DEBUG level.
#     Some servers return extra information in the result. Try to parse it for
#     debugging purpose. Messages are limited to 150 characters, since it may
#     return the whole page in case of normal web page URLs
#     """

#     message = None

#     # First attempt is to 'read' the response as HTML
#     if response.headers.get("content-type") and "text/html" in response.headers.get("content-type"):
#         try:
#             soup = BeautifulSoup(response.content, "html5lib")
#         except Exception:
#             pass

#         # Find body and cleanup common tags to grab content, which probably
#         # contains the message.
#         message = soup.find("body")
#         elements = ("header", "script", "footer", "nav", "input", "textarea")

#         for element in elements:

#             for tag in soup.find_all(element):
#                 tag.replaceWith("")

#         message = message.text if message else soup.text
#         message = message.strip()

#     # Second attempt is to just take the response
#     if message is None:
#         message = response.content.strip()

#     if message:
#         # Truncate message if it is too long.
#         if len(message) > 150:
#             message = message[:150] + "..."

#         log.debug(f"Server responded with message: {message}")
