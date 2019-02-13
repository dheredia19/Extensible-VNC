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

#ifndef _BASICVIEWERWINDOW_H_
#define _BASICVIEWERWINDOW_H_

#include <map>
#include <Windows.h>
#include <vnc/Viewer.h>

/*
 * BasicViewerWindow draws the framebuffer, updating it whenever the SDK
 * notifies us of any change from the server. It also handles keyboard and mouse
 * events, notifying the SDK so they can be sent to the server.
 */
class BasicViewerWindow {
public:

  BasicViewerWindow(vnc_Viewer* viewer_);
  ~BasicViewerWindow();

  void connected();
  void disconnected(const char* reason, int flags);
  void serverFbSizeChanged(int w, int h);
  void viewerFbUpdated(int x, int y, int w, int h);

  HWND getHwnd() const;
  LRESULT CALLBACK wndProc(HWND hwnd, UINT msg, WPARAM w, LPARAM l);

private:

  void createBuffer(int w, int h);
  void destroyBuffer();
  void createEmptyCursor();

  vnc_Viewer* viewer;
  WNDCLASSEX wc;
  HWND hwnd;
  HBITMAP bitmap;
  std::map<int, vnc_uint32_t> keyMap;
  int lastKeyDownKeyCode;
  HCURSOR emptyCursor;
  bool isConnected;
};

#endif
