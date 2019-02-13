(function() {

    function toggleCurrent (elem) {
        var parent_li = elem.closest('li');
        parent_li.siblings('li.current').removeClass('current');
        parent_li.siblings().find('li.current').removeClass('current');
        parent_li.find('> ul li.current').removeClass('current');
        parent_li.toggleClass('current');
    }
    $('#sidebar ul').siblings('a').each(function () {
        var link = $(this);
        var expand = $('<span class="toctree-expand"></span>');
        expand.on('click', function (ev) {
            toggleCurrent(link);
            ev.stopPropagation();
            return false;
        });
        link.prepend(expand);
    });

    function body_height() {
        // firefox needs document.body, chrome needs document.documentElement
        return Math.min(document.documentElement.scrollHeight, document.body.scrollHeight);
    }

    $("table.docutils:not(.field-list)").wrap("<div class=\"responsive-table\"></div>");

    var sidebar = $("#sidebar");
    var toctree = $("#toctree");
    var sidebar_placeholder;
    var footer = $("footer");
    var header_height, footer_height;
    var margin_size = parseInt(getComputedStyle(footer[0].previousElementSibling).marginBottom);
    $(window).resize(function() {
        if (window.innerWidth > 640) {
            header_height = (
                Math.round(document.getElementById("top-bar").getBoundingClientRect().height)
                + Math.round(document.getElementById("hero").getBoundingClientRect().height)
                + margin_size
            );
            footer_height = footer.height() + 2 + margin_size;
            sidebar.addClass("sticky");
            sidebar.width(sidebar.parent().width());
        } else {
            sidebar.removeClass("sticky").css({"width": "", "top": "", "bottom": ""});
            if (!sidebar_placeholder) {
                sidebar_placeholder = $("#sidebar-placeholder").height(sidebar.height());
            }
            footer.css("margin-top", "0");
        }
        $(window).scroll();
    }).resize();
    $(window).scroll(function() {
        if (window.innerWidth > 640) {
            if (window.pageYOffset < header_height) {
                sidebar.css("top", header_height - window.pageYOffset + "px");
            } else {
                sidebar.css("top", "0");
            }
            var distance_from_bottom = (body_height() - window.innerHeight) - window.pageYOffset;
            if (distance_from_bottom < footer_height) {
                var scroll_distance = (footer_height - distance_from_bottom) - parseInt(sidebar.css("bottom"));
                var new_bottom_position = footer_height - distance_from_bottom + "px";
            } else {
                var scroll_distance = -parseInt(sidebar.css("bottom"));
                var new_bottom_position = 0;
            }
            // If we're scrolling down, move the sidebar before scrolling it.
            // If we're scrolling up, move the sidebar after scrolling it.
            // This prevents the scrolling from not being applied because of reaching the maximum scroll distance.
            if (scroll_distance >= 0) {
                sidebar.css("bottom", new_bottom_position);
            }
            if (scroll_distance && !parseInt(sidebar.css("top"))) {
                toctree[0].scrollTop += scroll_distance;
            }
            if (scroll_distance < 0) {
                sidebar.css("bottom", new_bottom_position);
            }
        } else {
            if (sidebar[0].parentNode.getBoundingClientRect().top <= 0) {
                sidebar.addClass("mobile-sticky");
            } else {
                sidebar.removeClass("mobile-sticky");
            }
        }
    }).scroll();
    var current_link = $("a.current");
    if (window.innerWidth > 640 && current_link.length > 0) {
        var parent = current_link.offsetParent();
        var parent_middle = -parent.height() / 2;
        var current_link_bottom = current_link[0].getBoundingClientRect().bottom;
        var parent_bottom = parent[0].getBoundingClientRect().bottom;
        var current_link_overflow = current_link_bottom - parent_bottom;
        if (current_link_overflow > parent_middle) {
            parent[0].scrollTop = parent[0].scrollTop + current_link_overflow - parent_middle;
        }
    }

    $("#mobile-title").click(function() {
        sidebar.toggleClass("show-toctree");
        if (sidebar.hasClass("show-toctree") && current_link.length > 0) {
            current_link[0].scrollIntoView();
        }
    });
    $("#sidebar-overlay").click(function() {
        sidebar.removeClass("show-toctree");
    });
    $("#sidebar a.internal").click(function() {
        sidebar.removeClass("show-toctree");
    });
    window.addEventListener("load", function() {
        if (window.innerWidth <= 640 && location.hash) {
            window.scrollBy(0, -sidebar_placeholder.height());
        }
    });
    window.addEventListener("hashchange", function() {
        if (window.innerWidth <= 640) {
            window.scrollBy(0, -sidebar_placeholder.height());
        }
    });

    $("#version-dropdown").change(function() {
        var page_path = location.pathname.substr(location.pathname.indexOf("/", 6));
        location.href = "/docs/" + this.value + page_path + location.search + location.hash;
    });

})();
