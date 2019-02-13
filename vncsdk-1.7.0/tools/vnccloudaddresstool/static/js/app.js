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
 * Maximum number of Cloud addresses that can be created per batch using this
 * application.
 */
var MAX_CLOUD_ADDRESSES = 25;

/**
 * Initialize jQuery spinner widget. Bound the number of Cloud addresses
 * that can be entered using up/down buttons or text field.
 *
 * @param input_elem  <input> element that implements the spinner widget
 */
function init_spinner(input_elem)
{
    input_elem.spinner().spinner("value", 1);
    input_elem.spinner('option', 'min', 1);
    input_elem.spinner('option', 'max', MAX_CLOUD_ADDRESSES);
    input_elem.keyup(function () {
        var value = input_elem.spinner().spinner("value");
        if (value == undefined) return;
        if (value > MAX_CLOUD_ADDRESSES) {
            input_elem.spinner().spinner("value", MAX_CLOUD_ADDRESSES);
        } else if (value < 1) {
            input_elem.spinner().spinner("value", 1);
        } else {
            input_elem.spinner().spinner("value", Math.floor(value));
        }
    });
    input_elem.blur(function () {
        var value = input_elem.spinner().spinner("value");
        if (value == undefined) {
            input_elem.spinner().spinner("value", 1);
        }
    });
}

/**
 * Common error and notification elements specified in partial Jinja template.
 * These templates are inlined as required in a page.
 */

/**
 * Show inline error box on page.
 *
 * @param s  text to display in error box
 */
function show_error(s)
{
    $("#error").text(s).show("fast");
}

/**
 * Hide inline error box.
 */
function hide_error()
{
    $("#error").hide("slow");
}

/**
 * Show inline notification box on page.
 *
 * @param s  text to display in error box
 */
function show_notify(s)
{
    $("#notify").text(s).show("fast");
}

/*
 * Hide inline notification box.
 */
function hide_notify()
{
    $("#notify").hide("slow");
}

/**
 * Show simple error box (default #error) and hide it a short time afterwards.
 *
 * @param s   text to display in error box
 * @param id  ID of alternative error box element to show
 */
function error(s, id)
{
  if (typeof(id)==='undefined') id = "#error";
  $(id)
      .text(s)
      .show("fast")
      .stopTime("hide_error")
      .oneTime(3000, "hide_error", function () {
          $(id).hide("slow");
      });
}

/**
 * Show simple notification (default #notify) and hide it a short time
 * afterwards.
 *
 * @param s   text to display in error box
 * @param id  ID of alternative error box element to show
 */
function notify(s, id)
{
  if (typeof(id)==='undefined') id = "#notify";
  $(id)
      .text(s)
      .show("fast")
      .stopTime("hide_notify")
      .oneTime(3000, "hide_notify", function () {
          $(id).hide("slow");
      });
}

/*
 * A hash function with good distribution (sdbm) for mapping input strings to
 * a hash code (see http://www.cse.yorku.ca/~oz/hash.html).
 * This is used to map a Cloud address group name to a hash code used to generate
 * a unique HTML ID name.
 *
 * @param str  text used to generate a hash code
 */
function hash_code(str)
{
    var hash = 0;
    for (var i = 0; i < str.length; i++) {
        var c = str.charCodeAt(i);
        hash = c + (hash << 6) + (hash << 16) - hash;
    }
    return hash;
}

/**
 * HTML encode using jQuery in-memory <div> element
 *
 * @param str  string to be encoded
 */
function html_encode(str)
{
    return $('<div>').text(str).html();
}

/**
 * Update code syntax highlighting in <pre code> element.
 * Uses highlight.js module.
 */
function highlight_code()
{
    $('pre code').each(function (i, block) {
        hljs.highlightBlock(block);
    });
}

/**
 * Create range for given element ID and add to window's selection.
 *
 * @param elem_id  ID of page element to add to window's selection
 */
function addSelection(elem_id) {
    var node = document.getElementById(elem_id);
    var range = document.createRange();
    range.selectNodeContents(node);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
}

/**
 * Function to invoke when 'Share' button is clicked. We share all Cloud
 * addresses from the associated table.
 */
var share_handler = function () {
    var res = $(this).attr('id').split("_");
    var group_id = res[1];
    var elem_id = "cloud_addresses_tbody_" + group_id;
    var tbody = $(document.getElementById(elem_id));
    if (tbody) {
        var viewer_addresses = [], server_addresses = [];
        var viewers = 0, servers = 0;
        for (var i = 0; i < tbody.children().length; i++) {
            var child = tbody.children().eq(i);
            var addr = child.children().eq(1).html();
            var pwd = child.children().eq(2).html();
            if (child.attr('class') == "server_cloud_address") {
                server_addresses[servers++] =
                    {"cloud_address" : addr, "cloud_password" : pwd};
            } else {
                viewer_addresses[viewers++] =
                    {"cloud_address" : addr, "cloud_password" : pwd};
            }
        }
        var code = JSON.stringify({"viewer_addresses": viewer_addresses,
            "server_addresses": server_addresses}, null, 4);
        // Show JSON snippet in modal dialog.
        window.getSelection().removeAllRanges(); // Clear window's selection
        $("#snippet").empty();
        $("#snippet").attr("class", "json");
        $("#snippet").append(code);
        $("#dialog").dialog({title: "Cloud addresses",
                             modal: true,
                             resizable: false,
                             width: 'auto',
                             position: {my: "center", at: "center", of: window}
                            });
        $("#snippet").off('click'); // Prevent resize
        highlight_code();
  }
  return false;
};

/**
 * Basic string formatting using positional arguments.
 */
String.prototype.format = function () {
    var args = arguments;
    return this.replace(/\{\{|\}\}|\{(\d+)\}/g, function (match, i) {
        if (match == "{{") { return "{"; }
        if (match == "}}") { return "}"; }
        return args[i];
  });
};

/**
 * Generate a HTML table of Cloud addresses for a given group.
 *
 * @param group  group assigned to batch i of Cloud addresses
 * @param i      batch i of Cloud addresses
 * @param time   timestamp
 */
function generate_addr_table_html(group, i, time)
{
    return addr_table_tmpl.format(html_encode(group), time,
                                  hash_code(group).toString() + i);
}

/**
 * Generate a row in the HTML table of Cloud addresses.
 *
 * @param entry   single Cloud address object
 */
function generate_addr_row_html(entry)
{
    var clazz;
    if (entry.is_server) {
        clazz = 'server_cloud_address';
    } else {
        clazz = 'viewer_cloud_address';
    }
    return addr_row_tmpl.format(clazz, html_encode(entry.label),
                                entry.cloud_address, entry.cloud_password);
}

/**
 * Generate tables of Cloud addresses and bind click handlers to each Share
 * button.
 *
 * @param cloud_addresses  Cloud addresses object created from JSON returned
 *                         from app
 */
function generate_addr_tables(cloud_addresses)
{
    var div = $("#my_cloud_addresses");
    var group = null;
    var timestamp = null;
    var tbody = null;
    $('pre code').each(function (i, block) {
        hljs.highlightBlock(block);
    });

    var num_addresses = cloud_addresses.length;
    div.empty();
    if (num_addresses == 0) {
        var s = '<div id="empty">';
        s += '<p><i>You have no Cloud addresses available</i></p>'
        s +='</div>';
        div.append(s);
    } else {
        for (i = 0; i < num_addresses; i++) {
            var entry = cloud_addresses[i];
            if (timestamp == null || timestamp != entry.time) {
                timestamp = entry.time;
                group = entry.group;
                // Append a new table for current group.
                div.append(generate_addr_table_html(group, i, entry.time));
                var elem_id = "cloud_addresses_tbody_" +
                              hash_code(group).toString() + i;
                tbody = $(document.getElementById(elem_id));
            }
            // Append Cloud address as table row.
            tbody.append(generate_addr_row_html(entry));
        }
  }
  // Register click handlers on page.
  $("[id^=share]").unbind( "click", share_handler );
  $("[id^=share]").bind( "click", share_handler );
}
