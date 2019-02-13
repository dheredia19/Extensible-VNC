/*
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
*/

-- Database schema for VNC Cloud Address Tool

DROP TABLE IF EXISTS ApiKeys;
DROP TABLE IF EXISTS CloudAddresses;

-- Cloud API keys
CREATE TABLE ApiKeys (
  record_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, /* Record ID */
  key TEXT NOT NULL UNIQUE /* API key */
);

-- Cloud addresses
CREATE TABLE CloudAddresses (
  id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, /* Record ID */
  /* Timestamp used to collate the current batch of Cloud addresses */
  created TEXT NOT NULL,
  cloud_address TEXT UNIQUE NOT NULL, /* Cloud address */
  cloud_password TEXT NOT NULL, /* Cloud password */
  label TEXT NOT NULL, /* Label */
  cloud_address_group TEXT NOT NULL, /* Cloud address group */
  is_server BOOLEAN NOT NULL, /* Flag to indicate server or viewer address */
  api_record INTEGER NOT NULL, /* ApiKeys record ID */
  /* Enforce constraint */
  FOREIGN KEY(api_record) REFERENCES ApiKeys(record_id)
);
