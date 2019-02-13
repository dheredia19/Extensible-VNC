'''
Copyright (C) 2016-2017 RealVNC Limited. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation
and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
may be used to endorse or promote products derived from this software without
specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''

# -------------------------------------------------------------
# Wrappers for making VNC Cloud API requests
# -------------------------------------------------------------

import sys
import json
import ssl
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.poolmanager import PoolManager

# Cloud API host
CLOUD_API_HOST = "https://api.vnc.com"

# Cloud API calls
STATIC_ADDRESS_API = "/cloud/1.0/static-address"


class APIError(Exception):
    """Exception type containing a human-readable error message resulting from
    remote Cloud API call.
    """
    pass


def log_request(prepped, response):
    """Log Cloud API request and response to console
    """
    log = "---> %s %s HTTP/1.1\n" % (prepped.method, prepped.path_url)
    log = log + "Host: %s\nHeaders:" % CLOUD_API_HOST
    for hdr in prepped.headers:
        if hdr == 'Authorization':
            log = log + "\n  %s: Basic [REDACTED]" % (hdr)
        else:
            log = log + "\n  %s: %s" % (hdr, prepped.headers[hdr])
    log = log + "\n\n%s" % prepped.body
    log = log + "\n\n<--- Response (%d)\n" % (response.status_code,)
    if response.content:
        log = log + response.content
    print(log + "\n")


def request_cloud_address(key, secret, listen, group):
    """Request a static Cloud address for a given action and group.
    The "listen" action requests a server Cloud address while the "connect"
    action requests a viewer Cloud address.

    :param key: Cloud API key
    :type key: string
    :param secret: Cloud API secret
    :type secret: string
    :param listen: flag to indicate "listen" when True, "connect"
      otherwise
    :type listen: boolean
    :param group: group to be assigned to Cloud address
    :type group: string
    :return: list of Cloud addresses created by Cloud API
    :rtype: list of dictionary objects
    """
    headers = {'content-type': 'application/json'}
    if listen:
        data = {"allowedActions": ["listen"],
                "accessControl": {"groups": [group]}}
    else:
        data = {"allowedActions": ["connect"], "groups": [group]}
    req = requests.Request('POST',
                           CLOUD_API_HOST + STATIC_ADDRESS_API,
                           headers=headers,
                           auth=(key, secret),
                           data=json.dumps(data))
    result = None
    msg = "Cannot create %s Cloud address." % \
          ("server" if listen else "viewer")
    try:
        prepped = req.prepare()
        s = requests.Session()
        response = s.send(prepped, verify=True)
        log_request(prepped, response)  # Log the response to console
        if response.content:
            result = json.loads(response.content)
        if response.status_code == 401:
            raise APIError("%s Request made with invalid API key or secret." %
                           msg)
        elif response.status_code == 403:
            raise APIError("%s Authenticating with invalid API key." % msg)
        elif response.status_code != 201:
            if result:
                raise APIError("%s (%d, %s, '%s')" % (msg,
                                                      response.status_code,
                                                      result["errorCode"],
                                                      result["errorMessage"]))
            else:
                raise APIError("%s (%d)" % (msg, response.status_code))
    except requests.exceptions.ConnectionError as e:
        raise APIError("Connection error (%s)" % e.message)
    except Exception as e:
        raise APIError("Unexpected error (%s)" % e.message)
    return result
