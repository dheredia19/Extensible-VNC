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
#include <vncsdk/Vnc.h>
#import "ViewerAdapter.h"

/**
 * This view takes a vnc_Viewer object to draw the remote desktop into an
 * interactive image view.
 */
@interface DesktopView : UIImageView <frameBufferChangesDelegate>

@property (strong, nonatomic) ViewerAdapter *viewer;

/**
 * Designated initialiser for the Desktop View object.
 */
- (id)initWithViewer:(ViewerAdapter *)viewer;

/**
 * Called whenever the server's framebuffer has changed size. Update the
 * bounds of the DesktopView so it's displayed correctly under different
 * zoom levels in the scroll view.
 */
- (void)updateDesktopBounds:(CGRect)newBounds;

/**
 * This method is used for sending to the viewer the new coordinates of the
 * mouse with the button state.
 */
- (void)sendPointerEvent:(CGPoint)pos
         withButtonState:(vnc_Viewer_MouseButton)btnState;

@end
