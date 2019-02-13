# Copyright (C) 2016-2017 RealVNC Limited. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors
# may be used to endorse or promote products derived from this software without
# specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Note this sample makes use of PySide, which is licensed under the terms of
# the LGPL v2.1.

"""
Connection details.

Provides connection establishment classes and connection constants.
"""

import vncsdk


# For Cloud connections, hard-code the Cloud address for the Viewer.
# Example Cloud address:
# LxygGgSrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRsVnXoDoue4Xqm
LOCAL_CLOUD_ADDRESS = None

# Hard-code the Cloud password associated with this Cloud address.
# Example Cloud password:
# KMDgGgELSvAdvscgGfk2
LOCAL_CLOUD_PASSWORD = None

# To enable direct TCP connectivity you need to copy the content of your
# add-on code into the string below.
DIRECT_TCP_ADDON_CODE = None

# To enable messaging over the custom data channel you need to copy the
# content of your add-on code into the string below.
MESSAGING_ADDON_CODE = None


def canMakeConnections():
    return (
        (LOCAL_CLOUD_ADDRESS is not None and LOCAL_CLOUD_PASSWORD is not None)
        or (DIRECT_TCP_ADDON_CODE is not None))

#
# Run on import!
#
if not canMakeConnections():
    raise EnvironmentError(
        "Settings in ConnectionDetail.py prevent any connections being made.  "
        "Please read the README for this sample.")


def canUseMessaging():
    return MESSAGING_ADDON_CODE is not None


class CloudConnectionDetail(object):
    """
    VNC Cloud connection.  Connects to a Cloud VNC server.
    """
    def __init__(self, target):
        if not LOCAL_CLOUD_ADDRESS:
            raise EnvironmentError(
                "LOCAL_CLOUD_ADDRESS must be set in ConnectionDetail.py")
        if not LOCAL_CLOUD_PASSWORD:
            raise EnvironmentError(
                "LOCAL_CLOUD_PASSWORD must be set in ConnectionDetail.py")

        self.peerCloudAddress = target

    def connect(self, connHandler):
        with vncsdk.CloudConnector(LOCAL_CLOUD_ADDRESS,
                                   LOCAL_CLOUD_PASSWORD) \
          as cloud_connector:
            cloud_connector.connect(self.peerCloudAddress, connHandler)

    def autoVerifyPeer(self):
        return True


class DirectConnectionDetail(object):
    """
    VNC Direct connection.  Connects to a TCP VNC server.
    """
    def __init__(self, address, port):
        if not DIRECT_TCP_ADDON_CODE:
            raise EnvironmentError(
                "Failed to enable Direct TCP add-on; "
                "DIRECT_TCP_ADDON_CODE must be set in ConnectionDetail.py")

        self.tcpAddress = address
        self.tcpPort = port

    def connect(self, connHandler):
        vncsdk.enable_add_on(DIRECT_TCP_ADDON_CODE)
        with vncsdk.DirectTcpConnector() as tcp_connector:
            tcp_connector.connect(self.tcpAddress, self.tcpPort, connHandler)

    def autoVerifyPeer(self):
        return False
