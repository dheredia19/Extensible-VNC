var mailchimp_responses = [
    "default",
    "Too many subscribe attempts for this email address. Please try again in about 5 minutes.",
    "Please enter a value",
    "email address is invalid",
    "is already subscribed to list VNC Developer",
];
var vnc_responses = [
    "Something went wrong. Email us at <a href=\"mailto:developer-support@realvnc.com\">developer-support@realvnc.com</a>.",
    "Please wait before trying this email again.",
    "Please fill in all the fields.",
    "This e-mail address is not valid.",
    "This e-mail address is already registered.",
];

(function() {

    var subscribe_response = $("#subscribe-response");
    var submit_button = $("#subscribe-form button");
    $("#subscribe-form").submit(function() {
        var form = $(this);
        subscribe_response.html("");
        var original_text = submit_button.text();
        submit_button.attr("disabled", "disabled").text("Submitting...");
        ga("send", "event", "button", "click", "subscribe");
        $.ajax({
            url: form.attr("action").replace("/post?", "/post-json?").concat("&c=?"),
            data: form.serialize(),
            dataType: "jsonp",
            error: function (resp, text) {
                console.log("mailchimp ajax submit error: " + text);
            },
            success: function(resp) {
                if (resp.result === "success") {
                    subscribe_response.removeClass("error").text("Please now check your email and confirm.");
                    $(window).resize();
                } else {
                    var msg = vnc_responses[0];
                    try {
                        for (var i = 1; i < mailchimp_responses.length; i++) {
                            if (resp.msg.indexOf(mailchimp_responses[i]) > -1) {
                                msg = vnc_responses[i];
                                break;
                            }
                        }
                    } catch (e) {}
                    subscribe_response.addClass("error").html(msg);
                }
            },
            complete: function() {
                submit_button.removeAttr("disabled").text(original_text);
            },
        });
        return false;
    });

    // Stick the footer to the bottom of the window.
    function body_height() {
        // firefox needs document.body, chrome needs document.documentElement
        return Math.min(document.documentElement.scrollHeight, document.body.scrollHeight);
    }
    var footer = $("footer");
    var margin_size = parseInt(getComputedStyle(footer[0].previousElementSibling).marginBottom);
    var gap = 0;
    $(window).resize(function() {
        if (body_height() < window.innerHeight) {
            gap += window.innerHeight - body_height();
            footer.css("margin-top", gap + margin_size + "px");
        } else if (body_height() - window.innerHeight < gap) {
            gap -= (body_height() - window.innerHeight);
            footer.css("margin-top", gap + margin_size + "px");
        }
    }).resize();

})();
