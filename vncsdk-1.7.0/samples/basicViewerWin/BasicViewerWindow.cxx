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

#include <map>
#include <iostream>
#include <sstream>
#include <tchar.h>
#include <vnc/Vnc.h>

#include "BasicViewerWindow.h"


/* A helper function */
static int imax(int i1, int i2) { return i1 > i2 ? i1 : i2; }

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

/* Window procedure callback, calls on to the BasicViewerWindow's
   WndProc via the windows map */

typedef std::map<HWND, BasicViewerWindow*> WindowHandleMap;
static WindowHandleMap windows;

LRESULT CALLBACK wndProc(HWND hwnd, UINT msg, WPARAM w, LPARAM l)
{
  WindowHandleMap::const_iterator i = windows.find(hwnd);
  if (i != windows.end())
    return i->second->wndProc(hwnd, msg, w, l);
  return DefWindowProc(hwnd, msg, w, l);
}

/* Helper function to center a given window on the current monitor. */
static void centerWindow(HWND hwnd, RECT* r)
{
  HMONITOR monitor = MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST);
  if (!monitor)
    throw std::exception("Failed to get monitor");
  MONITORINFOEX mi;
  ZeroMemory(&mi, sizeof(MONITORINFOEX));
  mi.cbSize = sizeof(MONITORINFOEX);
  if (!GetMonitorInfo(monitor, &mi))
    throw std::exception("Failed to get monitor info");
  int width = r->right - r->left;
  int height = r->bottom - r->top;
  int xPos = (mi.rcWork.left + mi.rcWork.right - width) / 2;
  int yPos = (mi.rcWork.top + mi.rcWork.bottom - height) / 2;
  if (xPos < mi.rcWork.left) xPos = mi.rcWork.left;
  if (yPos < mi.rcWork.top) yPos = mi.rcWork.top;
  SetWindowPos(hwnd, 0, xPos, yPos, width, height,
    SWP_NOZORDER | SWP_NOACTIVATE);
}

/*
 * Basic Viewer Window Constructor
 * Creates Viewer callbacks, sets up the framebuffer
 */
BasicViewerWindow::BasicViewerWindow(vnc_Viewer* viewer_)
  : viewer(viewer_), hwnd(0), bitmap(0),
    lastKeyDownKeyCode(0), emptyCursor(0), isConnected(false)
{
  /* Set the Connection and Framebuffer callbacks for the Viewer */
  vnc_Viewer_ConnectionCallback connCb;
  memset(&connCb, 0, sizeof(vnc_Viewer_ConnectionCallback));
  connCb.connected = &::connected;
  connCb.disconnected = &::disconnected;
  if(!vnc_Viewer_setConnectionCallback(viewer, &connCb, this))
    std::cerr << "call to vnc_Viewer_setConnectionCallback failed: " << vnc_getLastError() << std::endl;
  vnc_Viewer_FramebufferCallback fbCb;
  memset(&fbCb, 0, sizeof(vnc_Viewer_FramebufferCallback));
  fbCb.serverFbSizeChanged = &::serverFbSizeChanged;
  fbCb.viewerFbUpdated = &::viewerFbUpdated;
  if(!vnc_Viewer_setFramebufferCallback(viewer, &fbCb, this))
    std::cerr << "call to vnc_Viewer_setFramebufferCallback failed: " << vnc_getLastError() << std::endl;

  /* Create a window class and window object */
  WNDCLASSEX wcex = {
    sizeof(WNDCLASSEX), 0, &::wndProc, 0, 0, GetModuleHandle(0), 0,
    LoadCursor(0, IDC_ARROW), 0, 0, _T("BasicViewerWindowClass"), 0
  };
  if (!RegisterClassEx(&wcex))
    throw std::exception("Could not create native window");
  wc = wcex;

  int initialWidth = vnc_Viewer_getViewerFbWidth(viewer);
  int initialHeight = vnc_Viewer_getViewerFbHeight(viewer);
  RECT rect = {0, 0, initialWidth, initialHeight};
  hwnd = CreateWindowEx(
    0, wc.lpszClassName, _T("basicViewer"),
    WS_OVERLAPPEDWINDOW | WS_CLIPCHILDREN, rect.left, rect.top,
    rect.right - rect.left, rect.bottom - rect.top, 0, 0,
    GetModuleHandle(0), this);
  if (!hwnd)
    throw std::exception("Could not create native window");
  centerWindow(hwnd, &rect);

  createBuffer(initialWidth, initialHeight);
  createEmptyCursor();

  windows[hwnd] = this;
  ShowWindow(hwnd, SW_SHOW);

  /* Map our non-printable keys from virtual keys to keysyms
     Configure other keymapping below if needed */
  keyMap[VK_RETURN] = XK_Return;
  keyMap[VK_SHIFT] = XK_Shift_L;
  keyMap[VK_CONTROL] = XK_Control_L;
  keyMap[VK_MENU] = XK_Alt_L;
  keyMap[VK_PAUSE] = XK_Pause;
  keyMap[VK_ESCAPE] = XK_Escape;
  keyMap[VK_PRIOR] = XK_Page_Up;
  keyMap[VK_NEXT] = XK_Page_Down;
  keyMap[VK_END] = XK_End;
  keyMap[VK_HOME] = XK_Home;
  keyMap[VK_LEFT] = XK_Left;
  keyMap[VK_UP] = XK_Up;
  keyMap[VK_RIGHT] = XK_Right;
  keyMap[VK_DOWN] = XK_Down;
  keyMap[VK_SNAPSHOT] = XK_Print;
  keyMap[VK_INSERT] = XK_Insert;
  keyMap[VK_DELETE] = XK_Delete;
  keyMap[VK_APPS] = XK_Menu;
  keyMap[VK_F1] = XK_F1;
  keyMap[VK_F2] = XK_F2;
  keyMap[VK_F3] = XK_F3;
  keyMap[VK_F4] = XK_F4;
  keyMap[VK_F5] = XK_F5;
  keyMap[VK_F6] = XK_F6;
  keyMap[VK_F7] = XK_F7;
  keyMap[VK_F8] = XK_F8;
  keyMap[VK_F9] = XK_F9;
  keyMap[VK_F10] = XK_F10;
  keyMap[VK_F11] = XK_F11;
  keyMap[VK_F12] = XK_F12;
}

/*
 * BasicViewerWindow Destructor
 */
BasicViewerWindow::~BasicViewerWindow()
{
  vnc_Viewer_destroy(viewer);
  destroyBuffer();
  DestroyCursor(emptyCursor);
  windows.erase(hwnd);
  DestroyWindow(hwnd);
  UnregisterClass(wc.lpszClassName, GetModuleHandle(0));
}

/*
 * Notifications that the viewer has successfully connected to a server
 * (after authentication).
 */
void BasicViewerWindow::connected() { isConnected = true; }

/*
 * Notification of a disconnection.
 */
void BasicViewerWindow::disconnected(const char* reason, int flags)
{
  /* Display the disconnect reason, if there is one */
  if(flags & vnc_Viewer_AlertUser) {
    std::ostringstream msgbuf;
    msgbuf.str("");
    if (!isConnected)
      msgbuf << "Disconnected while attempting to establish a connection\n";
    isConnected = false;
    msgbuf << "Disconnect reason: " << reason;
    MessageBox(hwnd, msgbuf.str().c_str(), "Error", MB_OK);
  }
  isConnected = false;
}

/*
 * Notification that the frame buffer size has changed, resize the viewer
 * frame buffer and change the window size mantaining the aspect ratio.
 */

void BasicViewerWindow::serverFbSizeChanged(int w, int h)
{
  RECT r;
  GetClientRect(hwnd, &r);
  int clientWidth = imax(r.right - r.left, 10);
  int clientHeight = imax(r.bottom - r.top, 10);
  float aspectRatio = w / (float)h;
  clientHeight = (int)(clientWidth / aspectRatio);
  r.bottom = r.top + clientHeight;
  AdjustWindowRect(&r, GetWindowLong(hwnd, GWL_STYLE), FALSE);
  centerWindow(hwnd, &r);
  createBuffer(clientWidth, clientHeight);
}

/*
 * Notification that an area of the frame buffer has changed. Invalidate this
 * area of the window so it will be redrawn.
 */
void BasicViewerWindow::viewerFbUpdated(int x, int y, int w, int h)
{
  RECT invalid = { x, y, x + w, y + h };
  InvalidateRect(hwnd, &invalid, FALSE);
  UpdateWindow(hwnd);
}

HWND BasicViewerWindow::getHwnd() const
{
  return hwnd;
}

/*
 * Handles keyboard and mouse events, detects event type.
 * Sends the appropriate action to the Viewer
 */
LRESULT CALLBACK BasicViewerWindow::wndProc(HWND hwnd, UINT msg, WPARAM w, LPARAM l)
{
  switch (msg) {
  case WM_PAINT:
    {
      PAINTSTRUCT ps;
      HDC paintDC = BeginPaint(hwnd, &ps);
      if (!paintDC)
        throw std::exception("Could not start painting");
      RECT& r = ps.rcPaint;
      int x = r.left, y = r.top, w = r.right-r.left, h = r.bottom-r.top;
      HDC bitmapDC = CreateCompatibleDC(paintDC);
      if (!bitmapDC)
        throw std::exception("Could not create device context");
      HBITMAP oldBitmap = (HBITMAP)SelectObject(bitmapDC, bitmap);
      BitBlt(paintDC, x, y, w, h, bitmapDC, x, y, SRCCOPY);
      SelectObject(bitmapDC, oldBitmap);
      DeleteDC(bitmapDC);
      EndPaint(hwnd, &ps);
      return 0;
    }
  case WM_SYSKEYDOWN:
  case WM_KEYDOWN:
    {
      /* Handle special non-printable keys that are in our KeyMap here.
         Otherwise wait for the char event for printable characters. */
      std::map<int, vnc_uint32_t>::const_iterator i = keyMap.find((int)w);
      if (i != keyMap.end())
        if(!vnc_Viewer_sendKeyDown(viewer, i->second, (int)w))
          std::cerr << "call to vnc_Viewer_sendKeyDown failed: " << vnc_getLastError() << std::endl;
      return 0;
    }
  case WM_SYSKEYUP:
  case WM_KEYUP:
    {
      if(!vnc_Viewer_sendKeyUp(viewer, (int)w))
        std::cerr << "call to vnc_Viewer_sendKeyUp failed: " << vnc_getLastError() << std::endl;
      return 0;
    }
  case WM_CHAR:
    {
      /* Control + key combinations require special handling. */
      int k = (int)w;
      int c = (GetKeyState(VK_CONTROL) < 0 && k > 0 && k < 32) ? 0x60+k : k;
      vnc_uint32_t keysym = vnc_unicodeToKeysym(c);
      if (keysym) {
        if(!vnc_Viewer_sendKeyDown(viewer, keysym, 0))
          std::cerr << "call to vnc_Viewer_sendKeyDown failed: " << vnc_getLastError() << std::endl;
        if(!vnc_Viewer_sendKeyUp(viewer, 0))
          std::cerr << "call to vnc_Viewer_sendKeyUp failed: " << vnc_getLastError() << std::endl;
      }
      return 0;
    }
  case WM_MOUSEMOVE:
  case WM_LBUTTONUP:
  case WM_MBUTTONUP:
  case WM_RBUTTONUP:
  case WM_LBUTTONDOWN:
  case WM_MBUTTONDOWN:
  case WM_RBUTTONDOWN:
    {
      int x = LOWORD(l);
      int y = HIWORD(l);
      int buttonState = 0;
      if (LOWORD(w) & MK_LBUTTON) buttonState |= vnc_Viewer_MouseButtonLeft;
      if (LOWORD(w) & MK_MBUTTON) buttonState |= vnc_Viewer_MouseButtonMiddle;
      if (LOWORD(w) & MK_RBUTTON) buttonState |= vnc_Viewer_MouseButtonRight;
      if(!vnc_Viewer_sendPointerEvent(viewer, x, y, buttonState, false))
        std::cerr << "call to vnc_Viewer_sendPointerEvent failed: " << vnc_getLastError() << std::endl;
      return 0;
    }
  case WM_MOUSEWHEEL:
  case WM_MOUSEHWHEEL:
      {
        int winDelta = GET_WHEEL_DELTA_WPARAM(w);
        int delta = (abs(winDelta)+WHEEL_DELTA-1) / WHEEL_DELTA;
        if ((winDelta >= 0) ^ (msg == WM_MOUSEHWHEEL)) delta = -delta;
        if(!vnc_Viewer_sendScrollEvent(viewer, delta,
                                       msg == WM_MOUSEHWHEEL
                                       ? vnc_Viewer_MouseWheelHorizontal
                                       : vnc_Viewer_MouseWheelVertical))
          std::cerr << "call to vnc_Viewer_sendScrollEvent failed: " << vnc_getLastError() << std::endl;
        return 0;
      }
  case WM_GETMINMAXINFO:
    {
      /* Enforce a minumum size for the window */
      MINMAXINFO* mmi = (MINMAXINFO*)l;
      mmi->ptMinTrackSize.x = 100;
      mmi->ptMinTrackSize.y = 100;
      return 0;
    }
  case WM_ACTIVATE:
    {
      bool hasFocus = (w != WA_INACTIVE);
      if (!hasFocus) {
        /* Release any held keys when the viewer window looses focus */
        if(!vnc_Viewer_releaseAllKeys(viewer))
          std::cerr << "call to vnc_Viewer_releaseAllKeys failed: " << vnc_getLastError() << std::endl;
      }
      return 0;
    }
  case WM_SIZE:
    {
      /* Recreate frame buffer to match the new window size */
      RECT r;
      GetClientRect(hwnd, &r);
      /* Don't resize the framebuffer smaller than (10,10) -- sometimes when the
         window is minimized it can become (0,0). */
      int clientWidth = imax(r.right - r.left, 10);
      int clientHeight = imax(r.bottom - r.top, 10);
      createBuffer(clientWidth, clientHeight);
      InvalidateRect(hwnd, &r, FALSE);
      return 0;
    }
  case WM_SETCURSOR:
    {
      if (LOWORD(l) != HTCLIENT || !isConnected) break;
      /* If the viewer is connected the hide the cursor when the pointer is
         over the window's client area, since the cursor will be drawn within
         the framebuffer */
      SetCursor(emptyCursor);
      return 0;
    }
  case WM_CLOSE:
    {
      vnc_Viewer_disconnect(viewer);
      return 0;
    }
  }
  return DefWindowProc(hwnd, msg, w, l);
}

struct BitmapInfo {
  BITMAPINFOHEADER bmiHeader;
  struct {
    DWORD red;
    DWORD green;
    DWORD blue;
  } mask;
};

/*
 * Creates and sets the viewer frame buffer. The pixel data received from the
 * server will be rendered into the buffer in the given pixel format, scaled to
 * fit the given size, and with the given stride.
 */
void BasicViewerWindow::createBuffer(int w, int h)
{
  destroyBuffer();
  BitmapInfo bi;
  bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
  bi.bmiHeader.biBitCount = 32;
  bi.bmiHeader.biSizeImage = w * h * 4;
  bi.bmiHeader.biPlanes = 1;
  bi.bmiHeader.biWidth = w;
  bi.bmiHeader.biHeight = -h;
  bi.bmiHeader.biCompression = BI_RGB;
  bi.bmiHeader.biClrUsed = 0;
  bi.mask.red = 255 << 16;
  bi.mask.green = 255 << 8;
  bi.mask.blue = 255 << 0;

  void* pixels;
  bitmap = ::CreateDIBSection(
    GetDC(hwnd), (BITMAPINFO*)&bi.bmiHeader, DIB_RGB_COLORS, &pixels, 0, 0);
  if (!bitmap)
    throw std::exception("Could not create DIB section");

  if(!vnc_Viewer_setViewerFb(viewer, pixels, bi.bmiHeader.biSizeImage,
                         vnc_PixelFormat_rgb888(), w, h, 0))
    std::cerr << "call to vnc_Viewer_setViewerFb failed: " << vnc_getLastError() << std::endl;
}

/**
* Destroys the bitmap information associated with the framebuffer
*/
void BasicViewerWindow::destroyBuffer()
{
  if (bitmap) {
    DeleteObject(bitmap);
    bitmap = 0;
  }
}

/**
* Used once the connection succeeds, the system cursor is set to empty and the SDK renders a suitable cursor into the framebuffer
*/
void BasicViewerWindow::createEmptyCursor()
{
  static const int sizeBytes = 32 * 4;

  BYTE andMask[sizeBytes];
  memset(&andMask, 0xFF, sizeBytes);

  BYTE xorMask[sizeBytes];
  memset(&xorMask, 0x00, sizeBytes);

  emptyCursor = CreateCursor(NULL, 0, 0, 32, 32, &andMask, &xorMask);
  if (!emptyCursor)
    throw std::exception("Could not create cursor");
}
