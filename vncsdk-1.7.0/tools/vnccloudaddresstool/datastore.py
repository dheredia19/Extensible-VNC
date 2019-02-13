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

'''
The Flask application's data store is implemented using a SQLite 3 database
file. The DataStore class wraps Python sqlite3 read/write method calls for
common data store actions.

The database comprises of two tables:
* ApiKeys table for storing the Cloud API key
* CloudAddresses table for storing all Cloud addresses created using a
  particular API key/secret pair

When a new Cloud API key is added, we create a new row entry in
the ApiKeys table. For each new Cloud address, we create a row entry in the
CloudAddresses table.
'''

import os
import time
from datetime import datetime
import sqlite3
from flask import g


class DataStoreError(Exception):
    """Exception type containing a human-readable error message resulting from
    a database operation
    """
    pass


class DataStore():
    """SQLite wrapper for a particular Flask application context
    """
    def __init__(self, app, db_file, sql_file, overwrite=False):
        """ Create a new database or open an existing one
        """
        self.app = app
        self.db_file = db_file
        try:
            if os.path.exists(self.db_file) and not overwrite:
                print("Loading app data from %r" % self.db_file)
                return
            conn = sqlite3.connect(self.db_file)
            with app.open_resource(sql_file, mode='r') as schema:
                conn.cursor().executescript(schema.read())
            if os.path.exists(self.db_file):
                print("Created database at %r" % self.db_file)
        except sqlite3.OperationalError as e:
            # Remove file if database creation had prematurely failed
            if self.db_file is not None and os.path.exists(self.db_file):
                os.remove(self.db_file)
            raise DataStoreError("Cannot create database (%r)" % (e,))

    def connect(self):
        """ Create database connection
        """
        try:
            conn = sqlite3.connect(self.db_file, isolation_level=None)
            setattr(g, '_database', conn)
            return conn
        except sqlite3.OperationalError as e:
            raise DataStoreError("Cannot connect to database (%r)" % (e,))

    def get_db(self):
        """ Get current database connection
        """
        db = getattr(g, '_database', None)
        if db is None:
            db = g._database = self.connect()
        return db

    # Read/write Cloud API credentials

    def add_cloud_key(self, key):
        """Save the Cloud API key to the data store and return the record ID
        (primary key in ApiKeys table).
        This record ID will be used for quick retrieval of Cloud addresses
        from the data store in future calls.
        """
        with self.app.app_context():
            db = self.get_db()
            try:
                try:
                    db.execute("INSERT INTO ApiKeys(key) VALUES (?)", (key,))
                except:  # Try writing to v1.0 database but skip secret
                    db.execute("INSERT INTO ApiKeys(key, secret) VALUES (?,?)",
                               (key, ""))
                c = db.execute('SELECT record_id FROM ApiKeys WHERE key=?',
                               (key,))
                return c.fetchone()[0]
            except sqlite3.OperationalError as e:
                raise DataStoreError("Error saving API credentials (%r, %r)" %
                                     (key, e))

    def get_record_id(self, key):
        """Get the ApiKeys table record ID given the Cloud API key.
        """
        with self.app.app_context():
            db = self.get_db()
            try:
                c = db.execute("SELECT record_id FROM ApiKeys WHERE key=?",
                               (key,))
                try:
                    return c.fetchone()[0]
                except:
                    return None
            except sqlite3.OperationalError as e:
                raise DataStoreError("Error retrieving record ID (%r, %r)" %
                                     (key, e))

    # Read/write Cloud addresses

    def write_cloud_addresses(self, record_id, cloud_addresses):
        """Write Cloud addresses to database for ApiKeys table record ID
        """
        with self.app.app_context():
            # Get a unique timestamp for collating addresses in this batch.
            ts = time.time()
            timestamp = \
                datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            db = self.get_db()
            try:
                for addr in cloud_addresses:
                    argsList = [
                        timestamp,
                        addr['cloud_address'],
                        addr['cloud_password'],
                        addr['label'],
                        addr['group'],
                        addr['is_server'],
                        record_id
                    ]
                    db.execute("INSERT INTO CloudAddresses(created, "
                               "cloud_address, cloud_password, label, "
                               "cloud_address_group, is_server, api_record) "
                               "VALUES (?, ?, ?, ?, ?, ?, ?)",
                               argsList)
            except sqlite3.OperationalError as e:
                raise DataStoreError("Error writing Cloud addresses (%r, %r)" %
                                     (record_id, e))

    def get_cloud_addresses(self, record_id):
        """Get Cloud addresses from database for ApiKeys table record ID
        """
        with self.app.app_context():
            db = self.get_db()
            cloud_addresses = []
            try:
                query = "SELECT cloud_address,cloud_password,label," \
                        "cloud_address_group,is_server,created FROM " \
                        "CloudAddresses WHERE api_record=? ORDER BY created " \
                        "DESC,cloud_address_group ASC"
                for row in db.execute(query, (record_id,)):
                    addr = {
                        'cloud_address': row[0],
                        'cloud_password': row[1],
                        'label': row[2],
                        'group': row[3],
                        'is_server': row[4],
                        'time': row[5]
                    }
                    cloud_addresses.append(addr)
                return cloud_addresses
            except sqlite3.OperationalError as e:
                raise DataStoreError("Error retrieving Cloud addresses "
                                     "(%r, %r)" % (record_id, e))
