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

/*
 * This sample code implements a basic VNC Viewer app. There exists a single
 * instance of the application object (window.App) which comprises of
 * application controller object (App.Controller). The application controller
 * contains a desktop controller (App.Controller.Desktop) which is responsible
 * for rendering the VNC Viewer's framebuffer and forwarding input events from
 * the browser to the remote VNC Server's desktop. Pointer and keyboard input
 * events are managed by both desktop controller's pointer event handler
 * (App.MouseHandler) and key event handler (App.KeyHandler) respectively.
 */

 "use strict";

(function ($) {


    /* For Cloud connections, hard-code the Cloud address for the Viewer, for example:
     * LxygGgSrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRsVnXoDoue4Xqm
     */
    var localCloudAddress = "XuaDAjGnLXbb5VcNqkn.XuaPXMscq4JtoRMtg99.devEX1Sg2Txs1CgVuW4.XuaPRobeXsBDcjFZU7S";

    /* Hard-code the Cloud password associated with this Cloud address, for example:
     * KMDgGgELSvAdvscgGfk2
     */
    var localCloudPassword = "CI953desmW4yTcrjNNYA";

    /* Hard-code the Cloud address of the Server (peer) to connect to, for example:
     * LxyDgGgrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRydf9ZczNo13BcD
     */
    var peerCloudAddress = "XuaDAjGnLXbb5VcNqkn.XuaPXMscq4JtoRMtg99.devEX1Sg2Txs1CgVuW4.XuaPRQM4qvDGAzVgJoa";

    /* The application instance. */
    window.App = {};

    /* The application's controller object.
     * For this sample we use jQuery's extend API to implement
     * vncsdk.Viewer.ConnectionCallback interface on this object.
     */
    window.App.Controller = {};

    window.App.Controller = function () {
        var self = this;
        self.viewer = null;
        self.isConnected = false;
        self.init();
    };

    jQuery.extend(App.Controller.prototype,
                  vncsdk.Viewer.ConnectionCallback.prototype, {
        /* Initialize the application controller. */
        init: function () {
            try {
                var self = this;
                /* Setup logger and initialize the SDK. */
                vncsdk.Logger.createBrowserLogger();
                vncsdk.init();
                /* Create the data store. We call DataStore.createBrowserStore()
                   to store app data in the browser's localStorage. */
                try {
                    vncsdk.DataStore.createBrowserStore('vncviewer');
                } catch(e) {
                    throw new Error("Could not open data store");
                }
                /* Setup new Viewer and desktop controller. */
                self.setupDesktopViewer();
            } catch (e) {
                statusDialog.reportError(e.message);
            }
        },

        /* Setup a new Viewer instance and desktop controller. */
        setupDesktopViewer: function () {
            var self = this;
            self.isConnected = false;
            /* Create VNC Viewer instance. */
            try {
                self.viewer = new vncsdk.Viewer();
            } catch(e) {
                throw new Error("Failed to create Viewer: " + e.message);
            }

            try {
                /* Set up connection callbacks and create the desktop controller. */
                self.viewer.setConnectionCallback(self);
            } catch(e) {
                throw new Error("Failed to set connection callbacks: " +
                                e.message);
            }
            self.desktopController = new window.App.Controller.Desktop(self.viewer);
            self.desktopController.hide();
            /* Show Status Dialog in Connect mode. */
            statusDialog.show(false);
            statusDialog.setStatus("", "Click the button to connect to a Server");
        },

        /* Show the viewer's framebuffer. */
        showViewerFb: function () {
            statusDialog.hide();
            this.desktopController.show();
        },

        /* Create a VNC Cloud connection to the peer Cloud address. */
        connect: function () {
            var self = this;
            if (!localCloudAddress || !localCloudPassword || !peerCloudAddress ||
                !localCloudAddress.length || !localCloudPassword.length ||
                !peerCloudAddress.length) {
                statusDialog.reportError("You must provide a local Cloud address, " +
                    "local Cloud password and peer Cloud address.");
            } else {
                var cloud = null;
                try {
                    cloud = new vncsdk.CloudConnector(localCloudAddress,
                                                      localCloudPassword);
                    cloud.connect(peerCloudAddress,
                                  self.viewer.getConnectionHandler());
                    /* We show the viewer's framebuffer now as we're expecting
                       in-framebuffer connection prompts. */
                    this.showViewerFb();
                } catch (e) {
                    alert(e);
                    statusDialog.reportError("Could not connect to VNC Cloud:<br/>" +
                                             e.message);
                } finally {
                    if (cloud !== null) {
                        cloud.destroy();
                    }
                }
            }
        },

        /* Disconnect VNC Viewer from the peer Cloud address. */
        disconnect: function () {
            try {
                this.viewer.disconnect();
            } catch (e) {
                console.error("call to viewer.disconnect failed:" + e);
            }
        },

        /* Send Ctrl-Alt-Del command to VNC Server. This command will only be interpreted by
           Windows and Linux hosts. */
        sendCtrlAltDel: function () {
            try {
                var ctrl = vncsdk.Keyboard.XK_Control_L;
                var alt = vncsdk.Keyboard.XK_Alt_L;
                var del = vncsdk.Keyboard.XK_Delete;
                this.viewer.sendKeyDown(ctrl, ctrl);
                this.viewer.sendKeyDown(alt, alt);
                this.viewer.sendKeyDown(del, del);
                this.viewer.sendKeyUp(del);
                this.viewer.sendKeyUp(alt);
                this.viewer.sendKeyUp(ctrl);
            } catch (e) {
                console.error("call to viewer.sendCtrlAltDel failed:" + e);
            }
        },

        /* The following functions implement the ConnectionCallback interface. */

        disconnected: function (viewer, reason, flags) {
            /* Set status message and show the Status Dialog in Restart mode */
            if (this.isConnected) {
                statusDialog.setStatus("", "Disconnected: " + reason);
            } else {
                statusDialog.setStatus("", "Disconnected while attempting to establish " +
                                           "a connection<br/>Disconnect reason: " + reason);
            }
            statusDialog.show(true);
            if (this.desktopController) {
                this.desktopController.hide();
            }
            $("#ctrlAltDelBtn").toggle(false);
            /* Cleanup */
            this.viewer.destroy();
            this.viewer = 0;
        },

        connecting: function (viewer) { },
        connected: function (viewer)  {
            this.isConnected = true;
            $("#ctrlAltDelBtn").toggle(true);
        }

    });


    /*
     * The desktop controller renders the VNC Viewer's framebuffer and forwards
     * input events from the browser to the VNC Server's desktop.
     * This object implements vncsdk.Viewer.FrameBufferCallback interface.
     */
    window.App.Controller.Desktop = function (viewer) {
        this.init(viewer);
    };

    jQuery.extend(App.Controller.Desktop.prototype,
                    vncsdk.Viewer.FramebufferCallback.prototype, {
        /* Initialize the application's desktop controller. */
        init: function (viewer) {
            var self = this;
            self.viewer = viewer;

            self.canvas = $('#framebuffer');
            self.canvasContext =
                new vncsdk.Viewer.ViewerCanvasContext(self.canvas[0]);
            self.pixelFormat = vncsdk.PixelFormat.bgr888();

            /* Create the framebuffer at the default size as we don't yet
               know the dimensions of the server's framebuffer. The framebuffer
               will be used initially to show the in-framebuffer UI.
            */
            self.scaleToFit = 1.0;
            self.fbWidth = this.viewer.getViewerFbWidth();
            self.fbHeight = this.viewer.getViewerFbHeight();
            try {
                this.viewer.setViewerFb(this.pixelFormat, this.fbWidth,
                                        this.fbHeight);
                this.updateCanvas();
            } catch (e) {
                console.error("call to viewer.setViewerFb failed:" + e);
            }

            self.cx1 = self.cy1 = self.cx2 = self.cy2 = 0;
            self.animationFrame = null;

            self.enabled = false;
            self.keyHandler =
                new window.App.KeyHandler(self.canvas, self.viewer);
            self.mouseHandler =
                new window.App.MouseHandler(self.canvas, self.viewer);

            try {
                self.viewer.setFramebufferCallback(self);
            } catch (e) {
                console.error("call to viewer.setFramebufferCallback failed:" + e);
            }

            /* Disable right-click context menu on canvas. */
            $('body').on('contextmenu', '#framebuffer',
                         function (e) { return false; });

            /* Hook up buttons to corresponding actions. */
            $('#disconnectBtn').click(function () { window.app.disconnect(); });
            $('#ctrlAltDelBtn').click(function () { window.app.sendCtrlAltDel(); });

            /* Ensure canvas adapts to the size of the browser window. */
            $(window).resize(function () {
                if ($('#desktop').is(':visible')) {
                    if (self.viewer) {
                        try {
                            self.viewerFbUpdated(self.viewer, 0, 0, self.fbWidth, self.fbHeight);
                            self.updateCanvas();
                        } catch (e) {
                            console.error("call to viewer.setViewerFb failed:" + e);
                        }
                    }
                }
            });

            /* Update message if canvas gained or lost focus. */
            $('#framebuffer').blur(function () {
                $('#message').text("Click desktop to gain input focus.");
            });
            $('#framebuffer').focus(function () {
                $('#message').text("");
            });
        },

        /* Show the viewer's framebuffer. */
        show: function () {
            this.enabled = true;
            /* Enable keyboard and mouse inputs. */
            this.keyHandler.enable(true);
            this.mouseHandler.enable(true);
            /* Show the <div> element containing the canvas and set the focus to
               the canvas so we can immediately receive input events from the
               user. */
            $('#desktop').toggle(true);
            this.updateCanvas();
            this.canvas.focus();
        },

        /* Hide the viewer's framebuffer. */
        hide: function () {
            this.enabled = false;
            /* Cancel pending viewer framebuffer update. */
            if (self.animationFrame !== null) {
                window.cancelAnimationFrame(self.animationFrame);
            }
            /* Disable inputs and hide the <div> element containing the canvas. */
            this.keyHandler.enable(false);
            this.mouseHandler.enable(false);
            $('#desktop').toggle(false);
        },

        /* Scale the presented framebuffer. We don't scale the viewer's framebuffer but
           instead we scale the image rendered on the canvas element which takes
           advantage of hardware acceleration routines provided in most browsers. */
        updateCanvas: function () {
            /* Obtain the useable dimensions for presenting the framebuffer. */
            var actualWidth = $(window).width();
            var actualHeight = $(window).height() - $("#desktopBarFrame").height();
            $('#desktop').width(actualWidth);
            $('#desktop').height(actualHeight);

            /* Calculate required scaling factor to fit viewer's framebuffer in
               the available space by resizing the canvas.  Note that the aspect
               ratio of the server's framebuffer will be preserved by this adjustment. */
            var scaleX = (actualWidth)/this.fbWidth;
            var scaleY = (actualHeight)/this.fbHeight;
            /* Save the scaling factor so we can use this to adjust canvas
               pointer events intended for the unscaled viewer's framebuffer. */
            this.scaleToFit = Math.min(scaleX, scaleY);

            /* Update canvas dimensions and center the element. */
            var scaledWidth = this.scaleToFit*this.fbWidth;
            var scaledHeight = this.scaleToFit*this.fbHeight;
            this.canvas[0].width = this.fbWidth;
            this.canvas[0].height = this.fbHeight;
            var top = 0;
            if (scaledHeight < this.canvas[0].height) {
                top = (actualHeight - scaledHeight) / 2;
            }
            var left = 0;
            if (scaledWidth < actualWidth) {
                left = (actualWidth - scaledWidth) / 2;
            }
            $('#framebuffer').css({
                'position': 'absolute', 'top': top, 'left':  left,
                'width': scaledWidth, 'height': scaledHeight,
            });
        },

        /* The following functions implement the FramebufferCallback interface. */

        /* Server's framebuffer size has changed. */
        serverFbSizeChanged: function (viewer, w, h) {
            this.resetDirtyRegion();
            /* Save the server's framebuffer dimensions. We will use these values to
             adjust the canvas element. */
            this.fbWidth = w;
            this.fbHeight = h;
            try{
                this.viewer.setViewerFb(this.pixelFormat,
                                        this.fbWidth,
                                        this.fbHeight);
                this.updateCanvas();
            } catch (e) {
                console.error("call to viewer.setViewerFb failed:" + e);
            }
        },

        /* Framebuffer rect has been updated. We update the framebuffer when the browser
           performs its next repaint. We will coalesce the dirty update region in-between
           repaints. */
        viewerFbUpdated: function (viewer, x, y, w, h) {
            var self = this;
            self.updateDirtyRegion(x, y, w, h);
            if (!self.animationFrame) {
                /* Schedule viewer framebuffer update in the next repaint. */
                self.animationFrame = window.requestAnimationFrame(function () {
                    self.animationFrame = null;
                    if (!self.enabled) return;
                    var width = self.cx2 - self.cx1;
                    var height = self.cy2 - self.cy1;
                    try {
                        /* Render the dirty part of the viewer's framebuffer to our canvas
                           element. */
                        self.viewer.putViewerFbData(self.cx1, self.cy1,
                                                    width, height,
                                                    self.canvasContext);
                    } catch (e) {
                        console.error("call to viewer.putViewerFb failed: " + e);
                    }
                    self.resetDirtyRegion();
                 });
            }
        },

        /* Reset the dirty region. */
        resetDirtyRegion: function () {
            this.cx1 = this.cy1 = Number.MAX_VALUE;
            this.cx2 = this.cy2 = 0;
        },

        /* Coalesce dirty region until we're ready to render. */
        updateDirtyRegion: function (x, y, w, h) {
            this.cx1 = Math.min(this.cx1, x);
            this.cy1 = Math.min(this.cy1, y);
            this.cx2 = Math.max(this.cx2, x+w);
            this.cy2 = Math.max(this.cy2, y+h);
        },

    });


    /*
    * Input handler for mouse pointer and mouse wheel events.
    */
    window.App.MouseHandler = function (control, viewer) {
        this.init(control, viewer);
        this.buttonPos = { x:0, y:0 };
        this.buttonPressed = [];
    };

    jQuery.extend(App.MouseHandler.prototype, {
        /* Initialize the input handler. */
        init: function (control, viewer) {
            this.control = control;
            this.viewer = viewer;
        },

        /* Enable or disable event listeners for mouse pointer and mouse wheel
           events. */
        enable: function (enabled) {
            if (enabled) {
                this.control.mousedown(this.mouseDown);
                this.control.mouseup(this.mouseUp);
                this.control.mousemove(this.mouseMove);
                this.control.mouseleave(this.mouseLeave);
                this.control[0].addEventListener('wheel', this.scrollEvent);
            } else {
                this.control.unbind("mousedown", this.mouseDown);
                this.control.unbind("mouseup", this.mouseUp);
                this.control.unbind("mousemove", this.mouseMove);
                this.control.unbind("mouseleave", this.mouseLeave);
                this.control[0].removeEventListener('wheel', this.scrollEvent);
            }
        },

        /* Convert mouse wheel delta values to scroll ticks. We scale the scroll
           amount to ensure at least one scroll "tick" is propagated to the viewer. */
        getScrollTicks : function (delta, scale) {
           var WHEEL_DELTA = 120;  /* Nominal mouse wheel amount for one click of the
                                      mouse wheel i.e. scroll "tick". */
           var result = delta*scale/WHEEL_DELTA;
           if (Math.abs(result) < 1.0) {
               return (result > 0) ? 1.0 : -1.0;
           } else {
               return result;
           }
        },

        /* Handle mouse wheel events */
        scrollEvent: function (event) {
            /* We support the following delta modes and perform appropriate mappings
               * DOM_DELTA_PIXEL : delta values are exact pixels
               * DOM_DELTA_LINE  : delta values are specified in lines and are
                                   multiplied by 12 pixels per line
               * DOM_DELTA_PAGE  : delta values are specified in pages and are
                                   multiplied by either the scaled desktop's width
                                   or height
               Converted delta values are scaled accordingly and then converted to
               scroll "ticks" */
            var desktop = window.app.desktopController;
            var self = desktop.mouseHandler;
            var scaleX = 1.0/desktop.scaleToFit;
            var scaleY = 1.0/desktop.scaleToFit;
            if (event.deltaMode == event.DOM_DELTA_LINE) {
                scaleX *= 12; scaleY *= 12;
            }
            if (event.deltaMode == event.DOM_DELTA_PAGE) {
                scaleX *= desktop.fbWidth;
                scaleY *= desktop.fbHeight;
            }
            try {
                if (event.deltaX) {
                    desktop.viewer.sendScrollEvent(self.getScrollTicks(event.deltaX, scaleX),
                        vncsdk.Viewer.MouseWheel.MOUSE_WHEEL_HORIZONTAL);
                }
                if (event.deltaY) {
                    desktop.viewer.sendScrollEvent(self.getScrollTicks(event.deltaY, scaleY),
                        vncsdk.Viewer.MouseWheel.MOUSE_WHEEL_VERTICAL);
                }
            } catch (e) {
                console.error("call to viewer.sendScrollEvent failed:" + e);
            }
            event.preventDefault();
        },

        /* Convert mouse position to coordinate relative to the viewer's framebuffer. */
        updatePos: function (event) {
            var desktop = window.app.desktopController;
            var scaleX = 1.0/desktop.scaleToFit;
            var scaleY = 1.0/desktop.scaleToFit;
            var self = window.app.desktopController.mouseHandler;
            var offset = self.control.offset();
            self.buttonPos.x = scaleX*(event.pageX - offset.left);
            self.buttonPos.y = scaleY*(event.pageY - offset.top);
        },

        /* Handle mouse down events received on the canvas and forward them to the server. */
        mouseDown: function (event) {
            var self = window.app.desktopController.mouseHandler;
            /* Determine which button was pressed and add to the vncsdk.Viewer.MouseButton[]
               array. This array will accumulate all the mouse buttons that are down. */
            if (event.which == 1) {
                self.buttonPressed.push(vncsdk.Viewer.MouseButton.MOUSE_BUTTON_LEFT);
            } else if (event.which == 2) {
                self.buttonPressed.push(vncsdk.Viewer.MouseButton.MOUSE_BUTTON_MIDDLE);
            } else if (event.which == 3) {
                self.buttonPressed.push(vncsdk.Viewer.MouseButton.MOUSE_BUTTON_RIGHT);
            }
            self.updatePos(event);
            try {
                self.viewer.sendPointerEvent(self.buttonPos.x, self.buttonPos.y,
                                             self.buttonPressed, false);
            } catch (e) {
                console.error("call to viewer.sendPointerEvent failed:" + e);
            }
        },

        /* Handle mouse up events received on the canvas and forward them to the server. */
        mouseUp: function (event) {
            var self = window.app.desktopController.mouseHandler;
            /* Determine which button was released and remove it from the
               vncsdk.Viewer.MouseButton[] array. */
            for (var i = self.buttonPressed.length - 1; i >= 0; i--) {
                if (event.which == 1 && self.buttonPressed[i] == vncsdk.Viewer.MouseButton.MOUSE_BUTTON_LEFT ||
                    event.which == 2 && self.buttonPressed[i] == vncsdk.Viewer.MouseButton.MOUSE_BUTTON_MIDDLE ||
                    event.which == 3 && self.buttonPressed[i] == vncsdk.Viewer.MouseButton.MOUSE_BUTTON_RIGHT) {
                    self.buttonPressed.splice(i, 1); /* Remove mouse button. */
                }
            }
            self.updatePos(event);
            try {
                self.viewer.sendPointerEvent(self.buttonPos.x, self.buttonPos.y,
                                             self.buttonPressed, false);
            } catch (e) {
                console.error("call to viewer.sendPointerEvent failed:" + e);
            }
            event.preventDefault();
        },

        /* Handle mouse move events received on the canvas and forward them to the server. */
        mouseMove: function (event) {
            if (!$('#framebuffer').is(":focus")) {
                return; /* Ignore if not in focus. */
            }
            var self = window.app.desktopController.mouseHandler;
            self.updatePos(event);
            try {
                self.viewer.sendPointerEvent(self.buttonPos.x, self.buttonPos.y,
                                             self.buttonPressed, false);
            } catch (e) {
                console.error("call to viewer.sendPointerEvent failed:" + e);
            }
            event.preventDefault();
        },

        /* Handle mouse exit events received on the canvas and and forward these as meaningful
           mouse up events to the server. */
        mouseLeave: function (event){
            var self = window.app.desktopController.mouseHandler;
            /* Determine which button had dragged across and remove it from the
               vncsdk.Viewer.MouseButton[] array. */
            self.mouseUp(event);
        }

    });


    /*
    * Input handler for keyboard events.
    */
    window.App.KeyHandler = function (control, viewer) {
        this.init(control, viewer);
    };

    jQuery.extend(App.KeyHandler.prototype, {
        /* Initialize the input handler. */
        init: function (control, viewer) {
            var self = this;
            self.control = control;
            self.viewer = viewer;
            /* Map our non-printable keys from virtual keys to keysyms
             Configure other keymapping below if needed */
            self.keyMap = {
                8: vncsdk.Keyboard.XK_BackSpace,
                13: vncsdk.Keyboard.XK_Return,
                16: vncsdk.Keyboard.XK_Shift_L,
                17: vncsdk.Keyboard.XK_Control_L,
                93: vncsdk.Keyboard.XK_Alt_L,
                19: vncsdk.Keyboard.XK_Pause,
                27: vncsdk.Keyboard.XK_Escape,
                33: vncsdk.Keyboard.XK_Page_Up,
                34: vncsdk.Keyboard.XK_Page_Down,
                35: vncsdk.Keyboard.XK_End,
                36: vncsdk.Keyboard.XK_Home,
                37: vncsdk.Keyboard.XK_Left,
                38: vncsdk.Keyboard.XK_Up,
                39: vncsdk.Keyboard.XK_Right,
                40: vncsdk.Keyboard.XK_Down,
                44: vncsdk.Keyboard.XK_Print,
                45: vncsdk.Keyboard.XK_Insert,
                46: vncsdk.Keyboard.XK_Delete,
                9: vncsdk.Keyboard.XK_Tab,
                112: vncsdk.Keyboard.XK_F1,
                113: vncsdk.Keyboard.XK_F2,
                114: vncsdk.Keyboard.XK_F3,
                115: vncsdk.Keyboard.XK_F4,
                116: vncsdk.Keyboard.XK_F5,
                117: vncsdk.Keyboard.XK_F6,
                118: vncsdk.Keyboard.XK_F7,
                119: vncsdk.Keyboard.XK_F8,
                120: vncsdk.Keyboard.XK_F9,
                121: vncsdk.Keyboard.XK_F10,
                122: vncsdk.Keyboard.XK_F11,
                123: vncsdk.Keyboard.XK_F12
            };
        },

        /* Handle key down events received on the canvas and forward them to the server. */
        onKeyDown: function (event) {
            var self = window.app.desktopController.keyHandler;
            var keysym = self.keyMap[event.keyCode];
            /* Handle special non-printable keys that are in our KeyMap here.
               Otherwise wait for the keyPress event for printable characters. */
            if (keysym) {
                try {
                    self.viewer.sendKeyDown(keysym, event.keyCode);
                } catch (e) {
                    console.error("call to viewer.sendKeyDown failed:" + e);
                }
                event.preventDefault();
            }
        },

        /* Handle key up events received on the canvas and forward them to the server. */
        onKeyUp: function (event) {
            var self = window.app.desktopController.keyHandler;
            try {
                self.viewer.sendKeyUp(event.keyCode);
            } catch (e) {
                console.error("call to viewer.sendKeyUp failed:" + e);
            }
        },

        /* Handle key press events received on the canvas and forward them to the server. */
        onKeyPress: function (event) {
            var self = window.app.desktopController.keyHandler;
            /* Control + key combinations require special handling. */
            var k = event.which;
            var c = (event.ctrlKey && k > 0 && k < 32) ? 0x60+k : k;
            var keysym = vncsdk.unicodeToKeysym(c);
            try {
                self.viewer.sendKeyDown(keysym, 0);
            } catch (e) {
                console.error("call to viewer.sendKeyDown failed:" + e);
            }
            try {
                self.viewer.sendKeyUp(0);
            } catch (e) {
                console.error("call to viewer.sendKeyUp failed:" + e);
            }
            event.preventDefault();
        },

        /* Release all pressed keys if we lose focus. */
        onBlur: function (event) {
            var self = window.app.desktopController.keyHandler;
            try {
                self.viewer.releaseAllKeys();
            } catch (e) {
                console.error("call to viewer.releaseAllKeys failed:" + e);
            }
        },

        /* Enable or disable event listeners for keyboard events. */
        enable: function (enabled) {
            var ctrl = this.control[0];
            if (enabled) {
                ctrl.addEventListener('keydown', this.onKeyDown, false);
                ctrl.addEventListener('keyup', this.onKeyUp, false);
                ctrl.addEventListener('keypress', this.onKeyPress, false);
                ctrl.addEventListener('blur', this.onBlur, false);
            } else {
                try {
                    this.viewer.releaseAllKeys();
                } catch (e) {
                    console.error("call to viewer.releaseAllKeys failed:" + e);
                }
                ctrl.removeEventListener('keydown', this.onKeyDown);
                ctrl.removeEventListener('keyup', this.onKeyUp);
                ctrl.removeEventListener('keypress', this.onKeyPress);
                ctrl.removeEventListener('blur', this.onBlur);
            }
        }

    });

    /*
    * Create basic UI to display status/errors strings and a button to start
    * the Cloud connections.
    */

    var StatusDialog = function() {
    }

    /* Show the Status Dialog.
       When the app is loaded, the Status Dialog is initially presented in
       Connect mode ('restart' flag is False). When a desktop session ends
       the Status Dialog is reshown but in Restart mode ('restart' flag is True).
     */
    StatusDialog.prototype.show = function (restart) {
        var self = this;
        $("#container").toggle(true);
        $("#connectBtnFrame").toggle(true);
        $("#connectBtn").unbind();
        if (restart) {
            /* Restart mode. Show the "Start Over" button - clicking this button
               will bring the Status Dialog back to Connect mode. */
            $("#connectBtn").text('Start Over');
            $('#connectBtn').click(function () {
                /* Setup new Viewer and desktop controller. */
                $("#connectBtn").text('Connect');
                try {
                    window.app.setupDesktopViewer();
                } catch (e) {
                    self.setStatus("Error", e.message);
                }
            });
        } else {
            /* Connect mode. Show the "Connect" button - clicking this button
               will initiate a Cloud connection. */
            $("#connectBtn").text('Connect');
            $('#connectBtn').click(function () {
                self.connectClicked();
            });
        }
    };

    /* Hide the Status Dialog. */
    StatusDialog.prototype.hide = function hide() {
        $("#container").toggle(false);
    };

    /* Set status text. */
    StatusDialog.prototype.setStatus = function (title, msg) {
        var showTitle = (title !== undefined) && (title.length > 0);
        var showMsg = (msg !== undefined) && (msg.length > 0);
        $("#statusTitle").html(title);
        $("#statusContent").html(msg);
        $("#statusTitle").toggle(showTitle);
        $("#statusContent").toggle(showMsg);
    };

    /* Report an error on the Status Dialog. */
    StatusDialog.prototype.reportError = function (msg) {
        this.setStatus("Error", msg);
        this.show(true);  /* Show in Restart mode so we can try again. */
    };

    /* Hook up Status Dialog's Connect button to trigger a VNC Viewer connection. */
    StatusDialog.prototype.connectClicked = function () {
        window.app.connect();
    };

    /*
    * Create the Status Dialog and application controller when the page loads.
    */
    $(document).ready(function () {
        window.statusDialog = new StatusDialog();
        window.app = new window.App.Controller();
    });

})(jQuery);
