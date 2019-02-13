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
# 3. Neither the name of the copyright holder nor the names of its
# contributors may be used to endorse or promote products derived from this
# software without specific prior written permission.
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

import os
import traceback
import json
import uuid
import logging
from flask import (Flask, g, render_template, request, redirect, session,
                   url_for)
from werkzeug.exceptions import InternalServerError

import vnccloud
import datastore


# ------------------------------------------------------------------------
# Set up the Flask application
# ------------------------------------------------------------------------

# Create the application singleton and assign secret key for cookie handling
app = Flask(__name__)
app.secret_key = str(uuid.uuid4())

# Setup application's data store.
root = os.path.dirname(os.path.abspath(__file__))
db_file = os.path.join(root, 'app.db')
sql_file = os.path.join(root, 'sql', 'app.sql')
data_store = datastore.DataStore(app, db_file, sql_file)


# Suppress most of the chatty logging when in-app HTTP requests are made in the
# 'werkzeug' module.


class WerkzeugLogFilter(logging.Filter):
    def filter(self, record):
        return record.getMessage().find("Running on") != -1

logging.getLogger('werkzeug').addFilter(WerkzeugLogFilter())


# ------------------------------------------------------------------------
# Register functions to be called during request handling and teardown of
# Flask application context
# ------------------------------------------------------------------------

@app.teardown_request
def cleanup(exception):
    """Teardown request handler. Print any exceptions.
    """
    if exception:
        app.logger.error("teardown_request: called with %r: %r" %
                         (exception.__class__.__name__, str(exception)))
        print("teardown_request: called with %r: %r" % \
            (exception.__class__.__name__, str(exception)))
        print(traceback.format_exc())


@app.teardown_appcontext
def close_connection(exception):
    """Destroy database connection when app context is torn down
    """
    if hasattr(g, '_database'):
        g._database.close()
        setattr(g, '_database', None)


# ------------------------------------------------------------------------
# Set up URL triggers for GET requests to the Flask application
# ------------------------------------------------------------------------

class RequestError(InternalServerError):
    """Exception to return an error string via a HTTP 500 response. This
    makes it available to the Web page error handler.
    """
    def __init__(self, error):
        super(RequestError, self).__init__(error)
        self._error = error

    def get_headers(self, environ):
        return [('Content-Type', 'text/plain')]

    def get_body(self, environ):
        return self._error


@app.route("/", methods=["GET"])
def login():
    """Show Cloud ID login page
    """
    if 'record_id' in session and 'api_key' in session:
        return render_template("addresses.html",
                               record_id=session['record_id'],
                               key=session['api_key'])
    # Fallback to login page
    return render_template("login.html")


@app.route("/logout", methods=["GET"])
def logout():
    session.pop('record_id', None)
    session.pop('api_secret', None)
    # Show login page
    return redirect(url_for("login"))


def create_cloud_addresses(group, num_viewers, num_servers):
    """Create Cloud addresses by making multiple API requests and return all
    created addresses to the caller. We auto-generate a label that will be
    unique to each Cloud address in this batch.

    :param group: group to be assigned to Cloud addresses
    :type group: string
    :param num_viewers: number of viewer Cloud addresses to create
    :type num_viewers: integer
    :param num_servers: number of server Cloud addresses to create
    :type num_servers: integer
    :return: list of Cloud addresses created by Cloud API with annotation
    :rtype: list of dictionary objects
    """
    cloud_addresses = []
    for v in range(1, num_viewers+1):
        results = vnccloud.request_cloud_address(session['api_key'],
                                                 session['api_secret'],
                                                 False,
                                                 group)
        label = group + '-viewer-' + str(v).zfill(2)
        addr = {
            'group': group,
            'cloud_address': results['cloudAddress'],
            'cloud_password': results['cloudPassword'],
            'label': label,
            'is_server': False
        }
        cloud_addresses.append(addr)
    for s in range(1, num_servers+1):
        results = vnccloud.request_cloud_address(session['api_key'],
                                                 session['api_secret'],
                                                 True,
                                                 group)
        label = group + '-server-' + str(s).zfill(2)
        addr = {
            'group': group,
            'cloud_address': results['cloudAddress'],
            'cloud_password': results['cloudPassword'],
            'label': label,
            'is_server': True
        }
        cloud_addresses.append(addr)
    return cloud_addresses


# ------------------------------------------------------------------------
# Set up URL triggers for POST requests to the Flask application.
# These are requests for data, made in response to some user action on a Web
# page. We expect to read a JSON-encoded payload from the request and we reply
# back with a JSON-encoded response.
# ------------------------------------------------------------------------


@app.route("/_create_cloud_addresses", methods=["POST"])
def _create_cloud_addresses():
    """Create Cloud addresses, save them to the data store and return
    JSON-encoded addresses back to the caller.
    """
    if 'record_id' not in session:
        raise RequestError(json.dumps(
            {'code': 405, 'message': 'Not allowed.'}, sort_keys=True))
    record_id = request.json.get("record_id")
    group = request.json.get('group').replace(" ", "")
    num_viewers = int(request.json.get('num_viewers'))
    num_servers = int(request.json.get('num_servers'))
    try:
        cloud_addresses = create_cloud_addresses(group, num_viewers,
                                                 num_servers)
        data_store.write_cloud_addresses(record_id, cloud_addresses)
        # Return all Cloud address entries from data store
        return json.dumps(data_store.get_cloud_addresses(record_id))
    except Exception as e:
        raise RequestError(e)


@app.route("/_get_cloud_addresses", methods=["POST"])
def _get_cloud_addresses():
    """Retrieve Cloud address entries from the data store and return
    JSON-encoded addresses back to the caller.
    """
    if 'record_id' not in session:
        raise RequestError(json.dumps(
            {'code': 405, 'message': 'Not allowed.'}, sort_keys=True))
    record_id = request.json.get('record_id')
    try:
        return json.dumps(data_store.get_cloud_addresses(record_id))
    except Exception as e:
        raise RequestError(e)


@app.route("/_save_api_key", methods=["POST"])
def _save_api_key():
    """Save Cloud API key to the data store and cache both key and secret
    in the current session.
    """
    key = request.json.get('key')
    secret = request.json.get('secret')
    try:
        record_id = data_store.get_record_id(key)
        if record_id is None:
            record_id = data_store.add_cloud_key(key)
        session['record_id'] = record_id
        session['api_key'] = key
        session['api_secret'] = secret
    except Exception as e:
        raise RequestError(e)
    return json.dumps(key if record_id else "null")
