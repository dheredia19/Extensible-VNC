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

#import "DesktopView.h"
#import "AppDelegate.h"

@interface DesktopView ()

/**
 * This property keeps a cache of the desktop framebuffer received from the 
 * server. It is not thread-safe - accessing the main image should be 
 * @synchronized with this Desktop View.
 */
@property (strong) UIImage *mainImage;

@end

@implementation DesktopView

/**
 * Designated initializer with the viewer Object
 */
- (id)initWithViewer:(ViewerAdapter *)viewer
{
  if (self = [super init]) {
    self.viewer = viewer;
    self.viewer.frameBufferChangesDelegate = self;
    self.userInteractionEnabled = YES;
  }
  return self;
}

/**
 * Called from the server when there is new pixel data to show in a specific 
 * CGRect. This object should refresh its cache of the desktop framebuffer and
 * redisplay it.
 * @note This method must be called on the SDK thread (which it is in this
 * sample).
 */
- (void)viewerFrameBufferUpdated:(ViewerAdapter *)viewer rect:(CGRect)rect
{
  [self snapshotDesktopAndDrawInBounds];
}

/**
 * We override setFrame to update the SDK's framebuffer size whenever we resize
 * the desktop view.
 */
- (void)setFrame:(CGRect)frame
{
  [super setFrame:frame];
  [self updateDesktopBounds:frame];
}

/**
 * Called whenever the server's framebuffer has changed size. Update the
 * bounds of the DesktopView so it's displayed correctly under different
 * zoom levels in the scroll view.
 */
- (void)updateDesktopBounds:(CGRect)newBounds
{
  [super setBounds:newBounds];
  if (_viewer) {
    /* 
     * Update the viewer frame buffer with the new render size, and refresh the
     * cache of the desktop framebuffer.
     */
    [[AppDelegate instance].sdkThread performBlockSync:^{
      BOOL success = [self.viewer setFrameBufferParametersWithSize:newBounds.size];
      if (YES == success) {
        [self snapshotDesktopAndDrawInBounds];
      }
    }];
  };
}

#pragma mark - Desktop rendering

/**
 * This method should take a snapshot of the desktop image from the viewer and
 * display it on screen.
 * @note The superclass UIImageView does the hard work of displaying the image
 * on screen on the main thread. Approaches using drawRect: will also work,
 * but may end up costing either memory or performance.
 * @note This method must be called on the SDK thread, callers should enforce 
 * this.
 */
- (void)snapshotDesktopAndDrawInBounds
{
  /* 
   * Need a safety check before populating the image cache - CGImageRef won't 
   * produce anything useful if it's asked to create an image in a zero-size
   * frame:
   */
  if (NO == CGRectEqualToRect(self.bounds, CGRectZero)) {
    [self populateImageFromBounds];
    /* Image drawing has to happen on the main thread: */
    dispatch_async(dispatch_get_main_queue(), ^() {
      @synchronized(self) {
        /*
         * Use -[UIImageView setImage:] to draw the cached desktop image on 
         * screen:
         */
        self.image = self.mainImage;
      }
    });
  }
}

/**
 * This method does the work for taking an image snapshot of the Remote Desktop
 * using the image data provided by the SDK.
 * @note This method must be called on the SDK thread, callers should enforce this.
 */
- (void)populateImageFromBounds
{
  CGImageRef newImage = [self.viewer createDesktopImageForFrame:self.bounds];
  /*
   * Cache the new image for use on the main thread - use @synchronized to make
   * certain the main thread doesn't try to consume the image data before its 
   * ready.
   */
  @synchronized(self) {
    self.mainImage = [UIImage imageWithCGImage:newImage];
    CGImageRelease(newImage);
  }
}

#pragma mark - Touch handling

/**
 * Used for sending to the viewer the new coordinates of a touch event with
 * the button state.
 */
- (void)sendPointerEvent:(CGPoint)pos withButtonState:(vnc_Viewer_MouseButton)btnState
{
  if (nil != self.viewer) {
    [[AppDelegate instance].sdkThread performBlockAsync:^{
      /**
       * This method is ignoring any errors emitted by 
       * sendPointerEvent as the user should get instant
       * feedback on if the click worked or not.
       */
      [self.viewer sendPoint:pos withButtonState:btnState];
    }];
  }
}

@end
