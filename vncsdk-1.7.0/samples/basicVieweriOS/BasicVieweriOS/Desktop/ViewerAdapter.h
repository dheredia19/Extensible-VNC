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

#import <UIKit/UIKit.h>
#import <vncsdk/Vnc.h>

@class ViewerAdapter;

@protocol frameBufferSizeChangedDelegate <NSObject>

/**
 * Method called in the SDK thread when the resolution changes in the server
 *
 * @param viewer is the adapter where the framebuffer data can be fetched from.
 * @param size is the new size for the viewer desktop.
 */
- (void)serverFrameBufferSizeChanged:(ViewerAdapter *)viewer size:(CGSize)size;

@end

@protocol frameBufferChangesDelegate <NSObject>

/**
 * Called from the server when there is new pixel data to show in a specific
 * CGRect. This object should refresh its cache of the desktop framebuffer and
 * redisplay it.
 * @note This method must be called on the SDK thread (which it is in this
 * sample).
 */
- (void)viewerFrameBufferUpdated:(ViewerAdapter *)viewer rect:(CGRect)rect;

@end

/**
 * This class adapts the VNC SDK remote desktop viewer to a native
 * Objective-C interface.
 */
@interface ViewerAdapter : NSObject

/**
 * The size delegate is responsible for handling changes when the 
 * remote desktop's resolution changes.
 */
@property (weak, nonatomic) id<frameBufferSizeChangedDelegate>frameBufferSizeChangedDelegate;
/**
 * The changes delegate is responsible for handling changes to the
 * remote desktop's image representation.
 */
@property (weak, nonatomic) id<frameBufferChangesDelegate>frameBufferChangesDelegate;

/**
 * Returns the connection handler for this viewer.
 */
- (vnc_ConnectionHandler *)connectionHandler;

/**
 * The underlying vnc_Viewer object.
 */
- (vnc_Viewer *)desktopViewer;

/**
 * Tell the viewer to transmit a keystroke to the remote desktop:
 */
- (void)sendKey:(vnc_uint32_t)keyCode;

/**
 * Sends a key down (press) event to the server.
 */
- (void)sendKeyDown:(vnc_uint32_t)keyCode;

/**
 * Sends a key up (release) event to the server.
 */
- (void)sendKeyUp:(vnc_uint32_t)keyCode;

/**
 * Get an image of the remote desktop for display in the given frame.
 */
- (CGImageRef)createDesktopImageForFrame:(CGRect)frame;

/**
 * Transmit a touch event to the remote desktop:
 */
- (void)sendPoint:(CGPoint)point withButtonState:(vnc_Viewer_MouseButton)buttonState;

/**
 * Tell the remote frame buffer to update to the given size.
 */
- (BOOL)setFrameBufferParametersWithSize:(CGSize)size;

@end
