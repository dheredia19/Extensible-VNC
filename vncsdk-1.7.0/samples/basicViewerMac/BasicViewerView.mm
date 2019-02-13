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

#import "BasicViewerView.h"
#import <Carbon/Carbon.h>
#pragma mark - Global namespace callback handlers

/* Static callbacks, call on to the BasicViewerView object */

static void connected(void* userData, vnc_Viewer* viewer)
{ [(__bridge BasicViewerView*)userData connected]; }

static void disconnected(void* userData, vnc_Viewer* viewer, const char* reason, int flags)
{ [(__bridge BasicViewerView*)userData disconnected:reason withFlags:flags]; }

static void serverFbSizeChanged(void* userData, vnc_Viewer* viewer,
                                int w, int h)
{ [(__bridge BasicViewerView*)userData serverFbSizeChanged:NSMakeSize(w, h)]; }

static void viewerFbUpdated(void* userData, vnc_Viewer* viewer, int x, int y,
                            int w, int h)
{ [(__bridge BasicViewerView*)userData viewerFbUpdated:NSMakeRect(x, y, w, h)]; }

bool modifierPressed(NSEventModifierFlags prev, NSEventModifierFlags curr,
                     NSEventModifierFlags mask)
{
  return !(prev & mask) && (curr & mask);
}

bool modifierReleased(NSEventModifierFlags prev, NSEventModifierFlags curr,
                      NSEventModifierFlags mask)
{
  return (prev & mask) && !(curr & mask);
}

/*
 * Function to create an image based on a Data representation, width and height.
 * Used to create a blank image to be used as a cursor.
 */
NSImage* createNSImage(unsigned char* data, int w, int h)
{
  NSBitmapImageRep* rep = [[NSBitmapImageRep alloc]
                           initWithBitmapDataPlanes:NULL pixelsWide:w
                           pixelsHigh:h bitsPerSample:8 samplesPerPixel:4
                           hasAlpha:YES isPlanar:NO
                           colorSpaceName:NSDeviceRGBColorSpace
                           bytesPerRow:(4 * w) bitsPerPixel:32];
  unsigned char* bitmapData = [rep bitmapData];
  memcpy(bitmapData, data, w * h * 4);
  NSImage* im = [[NSImage alloc] initWithSize:NSMakeSize(w, h)];
  [im addRepresentation:rep];
  return im;
}

@implementation BasicViewerView

/* A note about coordinate systems:
   NSView's coordinate system has its origin at the bottom-left corner of the
   view, whereas the Viewer SDK's coordinate system has its origin at the
   top-left of the framebuffer. This means that when passing coordinates to or
   from the SDK we have to vertically flip them. We define some helper functions
   here to do this. */

- (NSPoint)flipPoint: (NSPoint)point
{
  return NSMakePoint(
                     point.x,
                     self.bounds.size.height - point.y
                     );
}

- (NSRect)flipRect: (NSRect)rect
{
  return NSMakeRect(
                    rect.origin.x,
                    self.bounds.size.height - (rect.origin.y + rect.size.height),
                    rect.size.width,
                    rect.size.height
                    );
}

/*
 * Method for the configuration of callbacks, keys, framebuffer of the Viewer
 */
- (void)createDesktop: (vnc_Viewer*)viewer_
{
  viewer = viewer_;
  vnc_Viewer_ConnectionCallback connCb;
  memset(&connCb, 0, sizeof(vnc_Viewer_ConnectionCallback));
  connCb.connected = &::connected;
  connCb.disconnected = &::disconnected;
  if(!vnc_Viewer_setConnectionCallback(viewer, &connCb, (__bridge void*)self))
    NSLog(@"call to vnc_Viewer_setConnectionCallback failed: %s", vnc_getLastError());
  vnc_Viewer_FramebufferCallback fbCb;
  memset(&fbCb, 0, sizeof(vnc_Viewer_FramebufferCallback));
  fbCb.serverFbSizeChanged = &::serverFbSizeChanged;
  fbCb.viewerFbUpdated = &::viewerFbUpdated;
  if(!vnc_Viewer_setFramebufferCallback(viewer, &fbCb, (__bridge void*)self))
    NSLog(@"call to vnc_Viewer_setFramebufferCallback failed: %s", vnc_getLastError());

  colorSpace = CGColorSpaceCreateDeviceRGB();

  /* Map our non-printable keys from Mac virtual keycodes to keysyms
     Configure other keymapping below if needed */
  keyMap.clear();
  keyMap[kVK_Return] = XK_Return;
  keyMap[kVK_Delete] = XK_BackSpace;
  keyMap[kVK_ForwardDelete] = XK_Delete;
  keyMap[kVK_Escape] = XK_Escape;
  keyMap[kVK_Shift] = XK_Shift_L;
  keyMap[kVK_Control] = XK_Control_L;
  keyMap[kVK_RightShift] = XK_Shift_R;
  keyMap[kVK_RightControl] = XK_Control_R;
  keyMap[kVK_F1] = XK_F1;
  keyMap[kVK_F2] = XK_F2;
  keyMap[kVK_F3] = XK_F3;
  keyMap[kVK_F4] = XK_F4;
  keyMap[kVK_F5] = XK_F5;
  keyMap[kVK_F6] = XK_F6;
  keyMap[kVK_F7] = XK_F7;
  keyMap[kVK_F8] = XK_F8;
  keyMap[kVK_F9] = XK_F9;
  keyMap[kVK_F10] = XK_F10;
  keyMap[kVK_F11] = XK_F11;
  keyMap[kVK_F12] = XK_F12;
  keyMap[kVK_Home] = XK_Home;
  keyMap[kVK_End] = XK_End;
  keyMap[kVK_PageUp] = XK_Page_Up;
  keyMap[kVK_PageDown] = XK_Page_Down;
  keyMap[kVK_LeftArrow] = XK_Left;
  keyMap[kVK_RightArrow] = XK_Right;
  keyMap[kVK_DownArrow] = XK_Down;
  keyMap[kVK_UpArrow] = XK_Up;

  unsigned char blank[] = { 0, 0, 0, 0 };
  blankCursor = [[NSCursor alloc] initWithImage:createNSImage(blank, 1, 1)
                                        hotSpot:NSMakePoint(0, 0)];

  [self.window setAcceptsMouseMovedEvents:YES];
  scrollWheelTotal = CGPoint();

  [self updateBasicViewerView];
}

/*
 * Notifications that the viewer has successfully connected to a server
 * (after authentication).
 */
- (void)connected
{
  isConnected = true;
  /* Set empty local cursor, since the viewer will be drawing the cursor within
     the framebuffer. */
  [self.window invalidateCursorRectsForView:self];
}

/*
 * Notification of a disconnection. Simply terminate the app in this case.
 */
- (void)disconnected: (const char*)reason withFlags:(int)flags
{
  if(flags & vnc_Viewer_AlertUser) {
    NSString* message;
    if(!isConnected)
      message = [NSString stringWithFormat:@"Disconnected while attempting to establish a connection\nDisconnect reason: %s", reason];
    else
      message = [NSString stringWithFormat:@"Disconnect reason: %s", reason];
    NSAlert *alert = [[NSAlert alloc] init];
    [alert setMessageText:message];
    [alert addButtonWithTitle:@"OK"];
    [alert runModal];
  }
  /* Perform elegant shutdown in next event loop run */
  [NSApp performSelector:@selector(terminate:) withObject:nil afterDelay:0.0];
}

/*
 * Notification that the framebuffer size has changed, resize the viewer
 * framebuffer and change the window size maintaining the aspect ratio.
 */
- (void)serverFbSizeChanged: (NSSize)size
{
  NSRect windowFrame = self.window.frame;
  NSSize clientSize = self.bounds.size;
  float aspectRatio = size.width / size.height;
  double newHeight = clientSize.width / aspectRatio;
  windowFrame.size.height = newHeight +
    (windowFrame.size.height - clientSize.height);
  [self.window setFrame:windowFrame display:YES];
  [self setBoundsSize:NSMakeSize(clientSize.width, newHeight)];
  /* Note that we are letting the SDK allocate the framebuffer here. It is also
     possible to pass in a pre-allocated buffer if desired, but in this example
     we are drawing this to the screen indirectly via a CGImage. */
  if(!vnc_Viewer_setViewerFb(viewer, 0, 0, vnc_PixelFormat_rgb888(),
                             clientSize.width, newHeight, 0))
    NSLog(@"call to vnc_Viewer_setViewerFb failed :%s", vnc_getLastError());
}

/*
 * Notification that an area of the framebuffer has changed.
 */
- (void)viewerFbUpdated: (NSRect)rect
{
  /* rect is in buffer coords, so have to flip here to convert to view coords. */
  [self setNeedsDisplayInRect:[self flipRect:rect]];
}

/*
 * Adapt Viewer when the window gets resized by the user
 */
- (void)viewDidEndLiveResize
{
  [self updateBasicViewerView];
}

/*
 * Updates the viewer to current window size
 */
- (void)updateBasicViewerView{
  if(!vnc_Viewer_setViewerFb(viewer, 0, 0, vnc_PixelFormat_rgb888(),
                             self.bounds.size.width, self.bounds.size.height, 0))
    NSLog(@"call to vnc_Viewer_setViewerFb failed :%s", vnc_getLastError());
  [self setNeedsDisplay:YES];
}

/*
 * Request cursor rectangles for this view
 */
- (void)resetCursorRects
{
  /* If the viewer is connected than use a blank cursor when the pointer is
     over the view, since the cursor will be drawn within the framebuffer */
  if (isConnected)
    [self addCursorRect:[self visibleRect] cursor:blankCursor];
}

/*
 *  Drawing the viewer's view
 */
- (void)drawRect:(NSRect)dirtyRect
{
  [super drawRect:dirtyRect];

  if (!viewer) return;

  NSGraphicsContext* nsContext = [NSGraphicsContext currentContext];
  CGContextRef context = (CGContextRef)[nsContext graphicsPort];
  /* Turn off default image interpolation as we're scaling the framebuffer in
     the SDK. */
  [nsContext setImageInterpolation:NSImageInterpolationNone];

  int width = vnc_Viewer_getViewerFbWidth(viewer);
  int height = vnc_Viewer_getViewerFbHeight(viewer);

  /* dirtyRect is in view coords, so we have to flip it here to get buffer
     coords to pass to the SDK, then we flip it back to view coords later
     before we draw. */
  NSRect r = NSIntegralRect([self flipRect:dirtyRect]);
  r = NSIntersectionRect(r, NSMakeRect(0,0,width,height));

  const vnc_DataBuffer* vncbuf =
  vnc_Viewer_getViewerFbData(viewer, r.origin.x, r.origin.y,
                             r.size.width, r.size.height);
  int sizeBytes = 0;
  const void* data = vnc_DataBuffer_getData(vncbuf, &sizeBytes);
  int strideBytes = vnc_Viewer_getViewerFbStride(viewer) * 4;

  CGDataProviderRef provider =
  CGDataProviderCreateWithData(nil, data, sizeBytes, nil);

  /* Create a CGImage from the updated section of framebuffer data.
     We specify the appropriate parameters to match the rgb888 pixel format of
     the framebuffer. */
  CGImageRef image =
  CGImageCreate(r.size.width, r.size.height, 8, 32, strideBytes, colorSpace,
                kCGBitmapByteOrder32Little | kCGImageAlphaNoneSkipFirst,
                provider, nil, NO, kCGRenderingIntentDefault);

  CGContextDrawImage(context, [self flipRect:r], image);

  CGImageRelease(image);
  CGDataProviderRelease(provider);
}


#pragma mark - Keyboard and Mouse Handler

- (BOOL)acceptsFirstResponder
{
  return YES;
}

/*
 * KeyDown Keyboard Handler
 */
- (void)keyDown:(NSEvent*)ev
{
  unsigned short keyCode = [ev keyCode];
  std::map<unsigned short, vnc_uint32_t>::const_iterator iter =
    keyMap.find(keyCode);
  if (iter != keyMap.end()) {
    /* Handle special non-printable keys that are in keyMap. */
    if(!vnc_Viewer_sendKeyDown(viewer, iter->second, keyCode))
      NSLog(@"call to vnc_Viewer_sendKeyDown: %s", vnc_getLastError());
  } else {
    /* For other keycodes, convert the unicode character(s) from the event
       into keysyms using the SDK and send each as a keypress. */
    NSString* chars =
      (([ev modifierFlags] & (NSControlKeyMask|NSCommandKeyMask)) ?
       [ev charactersIgnoringModifiers] : [ev characters]);
    for (int i = 0; i < [chars length]; ++i) {
      vnc_uint32_t keysym = vnc_unicodeToKeysym([chars characterAtIndex:i]);
      if (keysym) {
        if(!vnc_Viewer_sendKeyDown(viewer, keysym, 0))
          NSLog(@"call to vnc_Viewer_sendKeyDown: %s", vnc_getLastError());
        if(!vnc_Viewer_sendKeyUp(viewer, 0))
          NSLog(@"call to vnc_Viewer_sendKeyUp: %s", vnc_getLastError());
      }
    }
  }
}

/*
 * KeyUp Keyboard Handler
 */
- (void)keyUp:(NSEvent*)ev
{
  unsigned short keyCode = [ev keyCode];

  if(!vnc_Viewer_sendKeyUp(viewer, keyCode))
    NSLog(@"call to vnc_Viewer_sendKeyUp: %s", vnc_getLastError());
}

/*
 * Controlling the Flags for when shift, control, alt keys are pressed
 */
- (void)flagsChanged:(NSEvent*)ev
{
  NSEventModifierFlags newModifiers = [ev modifierFlags];
  if (modifierPressed(modifiers, newModifiers, NSShiftKeyMask)) {
    if(!vnc_Viewer_sendKeyDown(viewer, XK_Shift_L, kVK_Shift))
      NSLog(@"call to vnc_Viewer_sendKeyDown failed: %s", vnc_getLastError());
  } else if (modifierReleased(modifiers, newModifiers, NSShiftKeyMask)) {
    if(!vnc_Viewer_sendKeyUp(viewer, kVK_Shift))
      NSLog(@"call to vnc_Viewer_sendKeyUp failed: %s", vnc_getLastError());
  }
  if (modifierPressed(modifiers, newModifiers, NSControlKeyMask)) {
    if(!vnc_Viewer_sendKeyDown(viewer, XK_Control_L, kVK_Control))
      NSLog(@"call to vnc_Viewer_sendKeyDown failed: %s", vnc_getLastError());
  } else if (modifierReleased(modifiers, newModifiers, NSControlKeyMask)) {
    if(!vnc_Viewer_sendKeyUp(viewer, kVK_Control))
      NSLog(@"call to vnc_Viewer_sendKeyUp failed: %s", vnc_getLastError());
  }
  if (modifierPressed(modifiers, newModifiers, NSCommandKeyMask)) {
    if(!vnc_Viewer_sendKeyDown(viewer, XK_Alt_L, kVK_Command))
      NSLog(@"call to vnc_Viewer_sendKeyDown failed: %s", vnc_getLastError());
  } else if (modifierReleased(modifiers, newModifiers, NSCommandKeyMask)) {
    if(!vnc_Viewer_sendKeyUp(viewer, kVK_Command))
      NSLog(@"call to vnc_Viewer_sendKeyUp failed: %s", vnc_getLastError());
  }
  if (modifierPressed(modifiers, newModifiers, NSAlternateKeyMask)) {
    if(!vnc_Viewer_sendKeyDown(viewer, XK_ISO_Level3_Shift, kVK_Option))
      NSLog(@"call to vnc_Viewer_sendKeyDown failed: %s", vnc_getLastError());
  } else if (modifierReleased(modifiers, newModifiers, NSAlternateKeyMask)) {
    if(!vnc_Viewer_sendKeyUp(viewer, kVK_Option))
      NSLog(@"call to vnc_Viewer_sendKeyUp failed: %s", vnc_getLastError());
  }
  modifiers = newModifiers;
}

/*
 * Handle mouse events
 */
- (void)handleMouseEvent:(NSEvent*)ev
{
  /* NSView's coordinate system has its origin at the bottom-left corner of the
     view, whereas the Viewer SDK's coordinate system has its origin at the
     top-left of the framebuffer. This means that when passing coordinates to
     or from the SDK we have to vertically flip them. We define some helper
     functions here to do this. */
  NSPoint pos = [self flipPoint:[self convertPoint:[ev locationInWindow] fromView:nil]];
  int buttonState = 0;
  unsigned long buttons = [NSEvent pressedMouseButtons];
  if (buttons & (1 << 0)) buttonState |= vnc_Viewer_MouseButtonLeft;
  if (buttons & (1 << 1)) buttonState |= vnc_Viewer_MouseButtonRight;
  if (buttons & (1 << 2)) buttonState |= vnc_Viewer_MouseButtonMiddle;
  if (pos.x >= 0 && pos.x < vnc_Viewer_getViewerFbWidth(viewer) &&
      pos.y >= 0 && pos.y < vnc_Viewer_getViewerFbHeight(viewer))
  {
    if(!vnc_Viewer_sendPointerEvent(viewer, pos.x, pos.y, buttonState, false))
      NSLog(@"call to vnc_Viewer_sendPointerEvent failed: %s", vnc_getLastError());
  }
}

/*
 * Handle scroll wheel events
 */
- (void)handleScrollWheel:(NSEvent*)ev
{
  /* We use a basic heuristic for forwarding scroll wheel events. We accumulate delta
     values until we have enough for a single scroll tick. */
  scrollWheelTotal.x += [ev deltaX];
  scrollWheelTotal.y += [ev deltaY];
  if (fabs(scrollWheelTotal.x) >= 1.0) {
    if (!vnc_Viewer_sendScrollEvent(viewer, -scrollWheelTotal.x,
                                    vnc_Viewer_MouseWheelHorizontal)) {
      NSLog(@"call to vnc_Viewer_sendScrollEvent failed: %s", vnc_getLastError());
    }
    scrollWheelTotal.x = 0.0;
  }
  if (fabs(scrollWheelTotal.y) >= 1.0) {
    if (!vnc_Viewer_sendScrollEvent(viewer, -scrollWheelTotal.y,
                                    vnc_Viewer_MouseWheelVertical)) {
      NSLog(@"call to vnc_Viewer_sendScrollEvent failed: %s", vnc_getLastError());
    }
    scrollWheelTotal.y = 0.0;
  }
}

- (void)mouseDown:(NSEvent*)ev
{
  [self handleMouseEvent:ev];
}

- (void)mouseUp:(NSEvent*)ev
{
  [self handleMouseEvent:ev];
}

- (void)mouseMoved:(NSEvent*)ev
{
  [self handleMouseEvent:ev];
}

- (void)mouseDragged:(NSEvent*)ev
{
  [self handleMouseEvent:ev];
}

- (void)rightMouseDown:(NSEvent*)ev
{
  [self handleMouseEvent:ev];
}

- (void)rightMouseUp:(NSEvent*)ev
{
  [self handleMouseEvent:ev];
}

- (void)rightMouseDragged:(NSEvent*)ev
{
  [self handleMouseEvent:ev];
}

- (void)otherMouseDown:(NSEvent*)ev
{
  [self handleMouseEvent:ev];
}

- (void)otherMouseUp:(NSEvent*)ev
{
  [self handleMouseEvent:ev];
}

- (void)otherMouseDragged:(NSEvent*)ev
{
  [self handleMouseEvent:ev];
}

- (void)scrollWheel:(NSEvent*)ev
{
  [self handleScrollWheel:ev];
}

@end
