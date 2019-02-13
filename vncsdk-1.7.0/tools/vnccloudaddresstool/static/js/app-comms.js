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

/**
 * Send JSON-encoded data to the app using HTTP POST requests and return
 * results in provided callback.
 *
 * @param app_url      local address to send data
 * @param data         data to send
 * @param success      success callback option to invoke if the request succeeds
 * @param errorHandler error callback optuon to invoke if the request fails
 */
function jsonPost(app_url, data, success, errorHandler)
{
    // Set optional error handler to report back the result of the request.
    if (!errorHandler) errorHandler = error;

    $.ajax({
        url: app_url,
        type: "POST",
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        data: JSON.stringify(data),
        success: success,
        error: function (xhr, textStatus, errorThrown) {
            console.log(errorThrown);
            // The RequestError object on the server side will pass an error
            // string via the response body of a 500 response.
            errorHandler(500 ? xhr.responseText : xhr.statusText)
        }
    });
}

/**
 *  Save user entered Cloud API credentials.
 *
 * @param key      Cloud API key
 * @param secret   Cloud API secret
 */
function save_api_credentials(key, secret)
{
    jsonPost(save_key_app_url, { key : key, secret : secret },
        function (result) {
            if (result == "null") {
                show_error("Could not save your API key!");
            } else {
                window.location.href = SCRIPT_ROOT;
            }
        },
        function (msg) {
            show_error(msg);
        }
    );
}

/**
 * Create a group of Cloud addresses. This will make requests to the Cloud API
 * and if successful Cloud addresses will be committed to the data store.
 *
 * @param record_id   record ID used to store Cloud addresses
 * @param group       group to assign to Cloud addresses
 */
function create_cloud_addresses(record_id, group)
{
    // Read viewer and server count from spinner
    var num_viewers = $("#viewer_spinner").spinner().val();
    var num_servers = $("#server_spinner").spinner().val();
    // Now create Cloud addresses for given group using Cloud API
    jsonPost(create_addresses_app_url,
        { record_id : record_id, group : group, num_viewers : num_viewers,
          num_servers : num_servers },
        function (cloud_addresses) {
            hide_error();
            generate_addr_tables(cloud_addresses);
        },
        function (msg) {
            show_error(msg);
        }
    );
}

/**
 * Retrieve all Cloud addresses from the data store for the given record ID
 * and update the page.
 *
 * @param record_id   record ID used to retrieve Cloud addresses
 */
function get_cloud_addresses(record_id)
{
    jsonPost(get_addresses_app_url, { record_id : record_id },
        function (cloud_addresses) {
            generate_addr_tables(cloud_addresses);
        },
        function (msg) {
            show_error(msg);
        }
    );
}
