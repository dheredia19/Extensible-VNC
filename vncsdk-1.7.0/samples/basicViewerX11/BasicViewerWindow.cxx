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

#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <limits.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>

#include "BasicViewerWindow.h"


const char* WINDOW_TITLE = "Basic viewer sample";
static Atom WM_DELETE_WINDOW = 0;

/* Static callbacks, call on to the BasicViewerWindow object */

static void connected(void* userData, vnc_Viewer* viewer)
{ ((BasicViewerWindow*)userData)->connected(); }

static void disconnected(void* userData, vnc_Viewer* viewer, const char* reason,
                         int flags)
{ ((BasicViewerWindow*)userData)->disconnected(reason, flags); }

static void serverFbSizeChanged(void* userData, vnc_Viewer* viewer,
                                int w, int h)
{ ((BasicViewerWindow*)userData)->serverFbSizeChanged(w, h); }

static void viewerFbUpdated(void* userData, vnc_Viewer* viewer, int x, int y,
                            int w, int h)
{ ((BasicViewerWindow*)userData)->viewerFbUpdated(x, y, w, h); }

static void serverFriendlyNameChanged(void* userData, vnc_Viewer* viewer,
                                      const char* name)
{ ((BasicViewerWindow*)userData)->serverFriendlyNameChanged(name); }

/*
 * Basic Viewer Window Constructor.
 * This creates a simple X11 window and graphics context, sets viewer callbacks
 * and initializes the framebuffer.
 */
BasicViewerWindow::BasicViewerWindow(Display* dpy_, vnc_Viewer* viewer_)
  : viewer(viewer_), dpy(dpy_),
    width(vnc_Viewer_getViewerFbWidth(viewer)),
    height(vnc_Viewer_getViewerFbHeight(viewer)),
    win(XCreateSimpleWindow(dpy, DefaultRootWindow(dpy), 0, 0, width, height,
                            0, 0, 0)),
    gc(XCreateGC(dpy, win, 0, NULL)),
    im(0), isConnected(0), buttonMask(0), emptyCursor(0)
{
  /* Set the Connection, Framebuffer and Event callbacks for the Viewer */
  vnc_Viewer_ConnectionCallback connCb;
  memset(&connCb, 0, sizeof(vnc_Viewer_ConnectionCallback));
  connCb.connected = &::connected;
  connCb.disconnected = &::disconnected;
  if(!vnc_Viewer_setConnectionCallback(viewer, &connCb, this))
    fprintf(stderr, "call to vnc_Viewer_setConnectionCallback failed: %s\n", vnc_getLastError());
  vnc_Viewer_FramebufferCallback fbCb;
  memset(&fbCb, 0, sizeof(vnc_Viewer_FramebufferCallback));
  fbCb.serverFbSizeChanged = &::serverFbSizeChanged;
  fbCb.viewerFbUpdated = &::viewerFbUpdated;
  if(!vnc_Viewer_setFramebufferCallback(viewer, &fbCb, this))
    fprintf(stderr, "call to vnc_Viewer_setFramebufferCallback failed: %s\n", vnc_getLastError());
  vnc_Viewer_ServerEventCallback seCb;
  memset(&seCb, 0, sizeof(vnc_Viewer_ServerEventCallback));
  seCb.serverFriendlyNameChanged = &::serverFriendlyNameChanged;
  if(!vnc_Viewer_setServerEventCallback(viewer, &seCb, this))
    fprintf(stderr, "call to vnc_Viewer_setServerEventCallback failed: %s\n", vnc_getLastError());

  /* Setup the X11 window */  
  XSetWindowBackgroundPixmap(dpy, win, None);
  XStoreName(dpy, win, WINDOW_TITLE);
  XMapWindow(dpy, win);
  if (!WM_DELETE_WINDOW) 
    WM_DELETE_WINDOW = XInternAtom(dpy, "WM_DELETE_WINDOW", false);
  XSetWMProtocols(dpy, win, &WM_DELETE_WINDOW, 1);

  XSelectInput(dpy, win, ExposureMask | KeyPressMask | KeyReleaseMask |
               ButtonPressMask | ButtonReleaseMask | StructureNotifyMask |
               PointerMotionMask | LeaveWindowMask | FocusChangeMask);

  /* Create an empty cursor */
  char zero = 0;
  Pixmap empty = XCreateBitmapFromData(dpy, win, &zero, 1, 1);
  XColor black = {0,};
  emptyCursor = XCreatePixmapCursor(dpy, empty, empty, &black, &black, 0, 0);
  XFreePixmap(dpy, empty);

  createBuffer();
}

/*
 * BasicViewerWindow Destructor
 * Destroys the Cursor, Image and window.
 */
BasicViewerWindow::~BasicViewerWindow()
{
  vnc_Viewer_destroy(viewer);
  XFreeCursor(dpy, emptyCursor);
  XDestroyImage(im);
  XDestroyWindow(dpy, win);
}

/*
 * Notifications that the viewer has successfully connected to a server
 * (after authentication).
 */
void BasicViewerWindow::connected()
{
  isConnected = true;
  XDefineCursor(dpy, win, emptyCursor);
}

/*
 * Notification of a disconnection.
 */
void BasicViewerWindow::disconnected(const char* reason, int flags)
{
  /* Display the disconnect reason, if there is one */
  if(flags & vnc_Viewer_AlertUser) {
    if (!isConnected)
      fprintf(stderr, "Disconnected while attempting to establish a connection\n");
    fprintf(stderr, "Disconnect reason: %s\n", reason);
  }
}

/*
 * Notification that the frame buffer size has changed, resize the window and
 * buffer to match.
 */
void BasicViewerWindow::serverFbSizeChanged(int w, int h)
{
  XWindowAttributes attrs;
  XGetWindowAttributes(dpy, win, &attrs);
  /* Subtract a little bit to allow for taskbars and borders */
  int maxWidth = WidthOfScreen(attrs.screen) - 40;
  int maxHeight = HeightOfScreen(attrs.screen) - 70;

  width = w;
  height = h;
  float aspect = (float)w / h;
  if (width > maxWidth) {
    width = maxWidth;
    height = maxWidth / aspect;
  }
  if (height > maxHeight) {
    height = maxHeight;
    width = maxHeight * aspect;
  }

  XResizeWindow(dpy, win, width, height);
  createBuffer();
}

/*
 * Notification that an area of the frame buffer has changed. Redraw this area
 * of the buffer onto the window to reflect these changes.
 */
void BasicViewerWindow::viewerFbUpdated(int x, int y, int w, int h)
{
  XPutImage(dpy, win, gc, im, x, y, x, y, w, h);
}

/*
 * Notification that the server's friendly name has changed, update the window
 * title.
 */
void BasicViewerWindow::serverFriendlyNameChanged(const char* name)
{
  char title[256];
  snprintf(title, 256, "%s - connected to %s", WINDOW_TITLE, name);
  title[255] = 0;
  XStoreName(dpy, win, title);
}

/*
 * Handle X11 events.
 * keyboard and mouse events, detects event type. 
 * Sends the appropriate action to the Viewer
 */
void BasicViewerWindow::handleXEvent(XEvent* xe)
{
  if (xe->xany.window != win) return;
  switch (xe->type) {

  case Expose: /* Specified area needs to be redrawn */
    XPutImage(dpy, win, gc, im,
              xe->xexpose.x, xe->xexpose.y,
              xe->xexpose.x, xe->xexpose.y,
              xe->xexpose.width, xe->xexpose.height);
    break;

  case ConfigureNotify: /* Window state has changed */
    /* discard any queued events so we just act on the final one */
    while (XCheckTypedWindowEvent(dpy, win, ConfigureNotify, xe));
    if (xe->xconfigure.width != width || xe->xconfigure.height != height) {
      /* Recreate our frame buffer if the window size has changed */
      width = xe->xconfigure.width;
      height = xe->xconfigure.height;
      createBuffer();
    }
    break;

  case MotionNotify: /* Pointer movement */
    /* discard any queued events so we just act on the final one */
    while (XCheckTypedWindowEvent(dpy, win, MotionNotify, xe));
    if(!vnc_Viewer_sendPointerEvent(viewer, xe->xmotion.x, xe->xmotion.y,
                                buttonMask, false))
      fprintf(stderr, "call to vnc_Viewer_sendPointerEvent failed: %s\n", vnc_getLastError());
    break;

  case ButtonPress: /* Pointer button press */
    if (xe->xbutton.button >= 4 && xe->xbutton.button <= 7) {
      /* Buttons 4 and 5 correspond to vertical scrolling, and buttons 6 and 7
         correspond to horizontal scrolling. */
      if(!vnc_Viewer_sendScrollEvent(viewer, (xe->xbutton.button & 1) ? 1 : -1,
                                 (xe->xbutton.button & 2)
                                 ? vnc_Viewer_MouseWheelHorizontal
                                 : vnc_Viewer_MouseWheelVertical))
        fprintf(stderr, "call to vnc_Viewer_sendScrollEvent failed: %s\n", vnc_getLastError());
    } else {
      buttonMask |= (1<<(xe->xbutton.button-1));
      if(!vnc_Viewer_sendPointerEvent(viewer, xe->xmotion.x, xe->xmotion.y,
                                  buttonMask, false))
        fprintf(stderr, "call to vnc_Viewer_sendPointerEvent failed: %s\n", vnc_getLastError());
    }
    break;

  case ButtonRelease: /* Pointer button release */
    if (xe->xbutton.button <= 3) { /* We can ignore the scroll button events */
      buttonMask &= ~(1<<(xe->xbutton.button-1));
      if(!vnc_Viewer_sendPointerEvent(viewer, xe->xmotion.x, xe->xmotion.y,
                                  buttonMask, false))
        fprintf(stderr, "call to vnc_Viewer_sendPointerEvent failed: %s\n",  vnc_getLastError());
    }
    break;

  case LeaveNotify:
    /* Release buttons when the pointer leaves the window */
    if(!vnc_Viewer_sendPointerEvent(viewer, xe->xmotion.x, xe->xmotion.y, 0, false))
      fprintf(stderr, "call to vnc_Viewer_sendPointerEvent failed: %s\n",  vnc_getLastError());
    break;

  case KeyPress: {
    char keyString[256];
    KeySym ks = 0;
    XLookupString(&xe->xkey, keyString, 256, &ks, NULL);
    if(!vnc_Viewer_sendKeyDown(viewer, ks, xe->xkey.keycode))
      fprintf(stderr, "call to vnc_Viewer_sendKeyDown failed: %s\n",  vnc_getLastError());
    }
    break;

  case KeyRelease:
    if(!vnc_Viewer_sendKeyUp(viewer, xe->xkey.keycode))
      fprintf(stderr, "call to vnc_Viewer_sendKeyUp failed: %s\n",  vnc_getLastError());
    break;

  case FocusOut:
    /* Release any held keys when the viewer window looses focus */
    if(!vnc_Viewer_releaseAllKeys(viewer))
      fprintf(stderr, "call to vnc_Viewer_releaseAllKeys failed: %s\n",  vnc_getLastError());
    break;

  case ClientMessage:
    /* User has clicked the close button on the Window's title bar */
    if ((Atom)xe->xclient.data.l[0] == WM_DELETE_WINDOW)
      vnc_Viewer_disconnect(viewer);
    break;
  }
}

/*
 * Creates and sets the viewer frame buffer. The pixel data received from the
 * server will be rendered into the buffer in the given pixel format, scaled to
 * fit the given size, and with the given stride.
 */
void BasicViewerWindow::createBuffer()
{
  if (im) {
    XDestroyImage(im); im = 0;
  }

  /* Attempt to find a suitable visual type for the framebuffer.
     Note that most modern systems will support 24 bits per pixel in rgb888 format,
     so we try this first, followed by 16 bits per pixel in rgb565 format. Other formats
     can be supported, if required, by creating the appropriate custom vnc_PixelFormat. */
  XVisualInfo vi;
  const vnc_PixelFormat* pf = 0;
  if (XMatchVisualInfo(dpy, DefaultScreen(dpy), 24, TrueColor, &vi)) {
    pf = vnc_PixelFormat_rgb888();

  } else if (XMatchVisualInfo(dpy, DefaultScreen(dpy), 16, TrueColor, &vi) &&
             vi.red_mask == 0xf800 && vi.green_mask == 0x07e0 && vi.blue_mask == 0x001f) {
    pf = vnc_PixelFormat_rgb565();

  } else {
    fprintf(stderr,"Unsupported display visual type\n");
    exit(1);
  }

  /* Create the XImage and set this as the viewer framebuffer. Updates received
     from the server will then be rendered directly into this XImage, which can then
     be drawn to the window via XPutImage. */
  im = XCreateImage(dpy, vi.visual, vi.depth, ZPixmap, 0, 0, width, height,
                    BitmapPad(dpy), 0);
  int dataSize = im->bytes_per_line * im->height;
  im->data = (char*)malloc(dataSize);

  if (!vnc_Viewer_setViewerFb(viewer, im->data, dataSize, pf,
                              width, height, 8 * im->bytes_per_line / vnc_PixelFormat_bpp(pf))) {
    fprintf(stderr, "call to vnc_Viewer_setViewerFb failed: %s\n",  vnc_getLastError());
  }
}
