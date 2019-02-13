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

#import "ViewerAdapter.h"
#import "AppDelegate.h"

#pragma mark - Global namespace callback handlers

void serverFbSizeChanged(void* userData, vnc_Viewer* viewer, int w, int h)
{
  ViewerAdapter *adapter = (__bridge ViewerAdapter *)userData;
  if (nil != adapter.frameBufferSizeChangedDelegate) {
    [adapter.frameBufferSizeChangedDelegate serverFrameBufferSizeChanged:adapter size:CGSizeMake(w, h)];
  }
}

void viewerFbUpdated(void* userData, vnc_Viewer* viewer, int x, int y, int w, int h)
{
  ViewerAdapter *adapter = (__bridge ViewerAdapter *)userData;
  if (nil != adapter.frameBufferChangesDelegate) {
    [adapter.frameBufferChangesDelegate viewerFrameBufferUpdated:adapter rect:CGRectMake(x, y, w, h)];
  }
}

@interface ViewerAdapter ()
{
  vnc_Viewer *_viewer;
  CGColorSpaceRef _colorSpace;
}

/**
 * The number of bytes of memory for each horizontal row of the bitmap image
 * of the remote desktop.
 */
- (int)bytesPerRow;

/**
 * The width of the remote desktop.
 */
- (int)viewerFrameBufferWidth;

/**
 * The height of the remote desktop.
 */
- (int)viewerFrameBufferHeight;

@end

@implementation ViewerAdapter

- (instancetype)init {
  self = [super init];
  if (nil != self) {
    _viewer = vnc_Viewer_create();
    if (NULL == _viewer) {
      /**
       * Unable to initialise a new viewer - return nil and let the calling
       * object decide what to do.
       */
      return nil;
    }
    
    /* Set the Framebuffer Callbacks */
    vnc_Viewer_FramebufferCallback callback;
    memset(&callback, 0, sizeof(vnc_Viewer_FramebufferCallback));
    callback.serverFbSizeChanged = &serverFbSizeChanged;
    callback.viewerFbUpdated = &viewerFbUpdated;
    if (!vnc_Viewer_setFramebufferCallback(_viewer, &callback, (__bridge void *)self)) {
      NSLog(@"Unable to register for the framebuffer callbacks:%s", vnc_getLastError());
      return nil;
    }
    
    _colorSpace = CGColorSpaceCreateDeviceRGB();
  }
  return self;
}

- (void)dealloc {
  [[AppDelegate instance].sdkThread performBlockSync:^{
    /**
     * We have to destroy the remote desktop adapter here, but we
     * can't let the main thread do anything either until the
     * viewer has been properly destroyed.
     */
    vnc_Viewer_destroy(_viewer);
  }];
  
  _viewer = NULL;
  CGColorSpaceRelease(_colorSpace);
  _colorSpace = NULL;
}

- (vnc_Viewer *)desktopViewer
{
  return _viewer;
}

- (vnc_ConnectionHandler *)connectionHandler
{
  return vnc_Viewer_getConnectionHandler(_viewer);
}

- (int)bytesPerRow
{
  return 4 * vnc_Viewer_getViewerFbStride(_viewer);
}

- (int)viewerFrameBufferWidth
{
  return vnc_Viewer_getViewerFbWidth(_viewer);
}

- (int)viewerFrameBufferHeight
{
  return vnc_Viewer_getViewerFbHeight(_viewer);
}

- (void)sendKey:(vnc_uint32_t)keyCode
{
  /**
   * Sends a key down event followed immediately by a key up
   * event. These can return an error if the key event isn't
   * sent correctly, but this should be immediately apparent
   * to the user.
   */
  vnc_Viewer_sendKeyDown(_viewer, keyCode, keyCode);
  vnc_Viewer_sendKeyUp(_viewer, keyCode);
}

- (void)sendKeyDown:(vnc_uint32_t)keyCode
{
  vnc_Viewer_sendKeyDown(_viewer, keyCode, keyCode);
}

- (void)sendKeyUp:(vnc_uint32_t)keyCode
{
  vnc_Viewer_sendKeyUp(_viewer, keyCode);
}

int clamp(int val, int min, int max) { return val < min ? min : (val > max ? max : val); }

- (CGImageRef)createDesktopImageForFrame:(CGRect)frame
{
  int width = [self viewerFrameBufferWidth];
  int height = [self viewerFrameBufferHeight];
  
  frame.origin.x = clamp(frame.origin.x, 0, width);
  frame.origin.y = clamp(frame.origin.y, 0, height);
  frame.size.width = clamp(frame.size.width, 0, width - frame.origin.x);
  frame.size.height = clamp(frame.size.height, 0, height - frame.origin.y);
  
  const vnc_DataBuffer *vncbuf = vnc_Viewer_getViewerFbData(_viewer, frame.origin.x, frame.origin.y,
                                                            frame.size.width, frame.size.height);
  if (NULL == vncbuf) {
    NSLog(@"Unable to get frame buffer data: %s", vnc_getLastError());
    return nil;
  }
  int size = 0;
  const void *data = vnc_DataBuffer_getData(vncbuf, &size);
  if (NULL == data) {
    NSLog(@"Unable to get frame buffer data: %s", vnc_getLastError());
    return nil;
  }
  
  CGDataProviderRef provider = CGDataProviderCreateWithData(nil, data, size, nil);
  
  /* Configuring the image to receive data to be consistent with the pixel format used by
   the viewer's frame buffer set in the DesktopViewController init function.
   Please see SDK: PixelFormat.h and Viewer.h for more details. */
  CGImageRef newImage = CGImageCreate(frame.size.width,                                  // width
                                      frame.size.height,                                 // height
                                      8,                                                       // bitsPerComponent
                                      32,                                                      // bitsPerPixel
                                      [self bytesPerRow],                                             // bytesPerRow
                                      _colorSpace,                                             // colorSpace
                                      kCGBitmapByteOrder32Little | kCGImageAlphaNoneSkipFirst, // bitmapInfo
                                      provider,                                                // provider
                                      nil,                                                     // decode
                                      NO,                                                      // shouldInterpolate
                                      kCGRenderingIntentDefault);                              // intent
  CGDataProviderRelease(provider);
  return newImage;
}

- (void)sendPoint:(CGPoint)point withButtonState:(vnc_Viewer_MouseButton)buttonState
{
  vnc_Viewer_sendPointerEvent(_viewer, point.x, point.y, buttonState, 0);
}

- (BOOL)setFrameBufferParametersWithSize:(CGSize)size
{
  vnc_status_t status = vnc_Viewer_setViewerFb(_viewer, nil, 0, vnc_PixelFormat_rgb888(), size.width, size.height, 0);
  return (vnc_success == status);
}

@end
