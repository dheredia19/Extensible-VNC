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

#import "DesktopViewController.h"
#import "DesktopView.h"
#import "DesktopScrollView.h"
#import "AppDelegate.h"

#import <vncsdk/Vnc.h>

static const CGFloat kToolbarHeight = 44;
static NSString * const kHideKeyboardText = @"Hide";
static NSString * const kShowKeyboardText = @"Show";

/**
 * DesktopViewController is used to present the remote desktop view and provides an interface to handle touch
 * interaction and send those events to the viewer
 */
@implementation DesktopViewController {
  DesktopView *_desktopView;
  UITextField *_textField;
  DesktopScrollView *_scrollView;
  UINavigationBar *_navBar;
  UIBarButtonItem *_leftButton;
  UIBarButtonItem *_rightButton;
  UITapGestureRecognizer *_tap;
  UITapGestureRecognizer *_doubleTap;
  float _aspectRatio;
  CGSize _serverDesktopSize;
}

/**
 * Designated initializer with the viewer, used to configure the 
 * viewer frame buffer and its callbacks
 */
- (id)initWithViewer:(ViewerAdapter *)viewer
{
  if (self = [super init]) {
    /* We do not dispatch_thread_sync here because this init method is being called from the SDK Thread already. */
    self.viewer = viewer;
    self.viewer.frameBufferSizeChangedDelegate = self;
    /* Set a reasonable frame buffer size to use until we receive the server's resolution */
    _serverDesktopSize = CGSizeMake(640, 480);
    BOOL success = [self.viewer setFrameBufferParametersWithSize:_serverDesktopSize];
    if (NO == success) {
      NSLog(@"Unable to setup the viewer frame buffer:%s", vnc_getLastError());
      return nil;
    }
  }
  return self;
}

#pragma mark - View lifecycle

/**
 * Setting up the views for when we are about to load DesktopViewController's view.
 */
- (void)loadView
{
  self.view = [[UIView alloc] initWithFrame:[[UIScreen mainScreen] bounds]];
  self.view.backgroundColor = [UIColor whiteColor];
  
  _navBar = [[UINavigationBar alloc] initWithFrame:CGRectMake(0, 0, self.view.frame.size.width, kToolbarHeight)];
  _navBar.backgroundColor = [UIColor whiteColor];
  
  UINavigationItem *navItem = [[UINavigationItem alloc] init];
  navItem.title = @"basicVieweriOS";
  
  _leftButton = [[UIBarButtonItem alloc] initWithTitle:@"Disconnect" style:UIBarButtonItemStylePlain target:self action:@selector(stopViewerSession)];
  navItem.leftBarButtonItem = _leftButton;
  
  _rightButton = [[UIBarButtonItem alloc] initWithTitle:kHideKeyboardText style:UIBarButtonItemStylePlain target:self action:@selector(toggleKeyboard)];
  navItem.rightBarButtonItem = _rightButton;
  
  _navBar.items = @[ navItem ];
  [self.view addSubview:_navBar];
  
  _scrollView = [[DesktopScrollView alloc] initWithFrame:CGRectMake(0, kToolbarHeight, self.view.frame.size.width, self.view.frame.size.height - kToolbarHeight)];
  _scrollView.delegate = self;
  [self.view addSubview:_scrollView];
  
  _desktopView = [[DesktopView alloc] initWithViewer:self.viewer];
  _desktopView.frame = CGRectMake(0, 0, _serverDesktopSize.width, _serverDesktopSize.height);
  
  _scrollView.contentSize = _desktopView.frame.size;
  [_scrollView addSubview:_desktopView];
  _scrollView.clipsToBounds = YES;
  
  _textField = [[UITextField alloc] init];
  _textField.delegate = self;
  
  /* Quick workaround to hide suggestions/third party keyboards on iOS8.
     We do this because we don't want the device corrupting the text we're sending to the sdk */
  _textField.secureTextEntry = YES;
  _textField.inputAccessoryView = [self exampleKeyboardAccessoryView];
  
  /* We setup the frame of the textfield to be off the screen, so it does not capture any touch events
     We are using this control to present/dismiss keyboard and to keys pressed to send keycodes through the sdk */
  _textField.frame = CGRectMake(-100, -100, 0, 0);
  [self.view addSubview:_textField];
  
  /* Adding Gestures to DesktopView */
  _tap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(handleTap:)];
  _tap.numberOfTapsRequired = 1;
  
  _doubleTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(handleDoubleTap:)];
  _doubleTap.numberOfTapsRequired = 2;
  [_tap requireGestureRecognizerToFail:_doubleTap];
  
  [_desktopView addGestureRecognizer:_tap];
  [_desktopView addGestureRecognizer:_doubleTap];
}

- (void)viewWillAppear:(BOOL)animated
{
  [super viewWillAppear:animated];
  
  /* Ensure the scrollview is in a clean zoom state */
  [self adjustViewsToInterfaceOrientation];
  
  /* By having the textfield with an empty space, we make sure UITextfield delegate method shouldChangeCharactersInRange is called when backspace is pressed. */
  _textField.text = @" ";
  
  /* Show the keyboard and ensure the button is in the right state */
  [_rightButton setTitle:kHideKeyboardText];
  [_textField becomeFirstResponder];
}

/**
 * Hides/Shows the keyboard
 */
-(void)toggleKeyboard
{
  if ([_rightButton.title isEqualToString:kHideKeyboardText]) {
    [_rightButton setTitle:kShowKeyboardText];
    [_textField resignFirstResponder];
  } else {
    [_rightButton setTitle:kHideKeyboardText];
    [_textField becomeFirstResponder];
  }
}

/**
 * Presents an alert to the user to confirm that they want to terminate the Viewer Session.
 */
-(void)stopViewerSession
{
  UIAlertView *alert = [[UIAlertView alloc] initWithTitle:@"basicVieweriOS"
                                                  message:@"Do you want to terminate the viewer session?"
                                                 delegate:self
                                        cancelButtonTitle:@"Yes"
                                        otherButtonTitles:@"No", nil];
  [alert show];
}

- (void)alertView:(UIAlertView *)alertView didDismissWithButtonIndex:(NSInteger)buttonIndex
{
  if (buttonIndex == 0) {
    [[AppDelegate instance] stopViewerSession];
  }
}

/**
 * Adjusts the views during the interface rotations and initialization
 */
-(void)adjustViewsToInterfaceOrientation
{
  _navBar.frame = CGRectMake(0, 0, self.view.frame.size.width, kToolbarHeight);
  _scrollView.frame = CGRectMake(0, kToolbarHeight, self.view.frame.size.width, self.view.frame.size.height - kToolbarHeight);
  [self fitDesktopToScrollView];
  _scrollView.contentOffset = CGPointMake(_scrollView.contentOffset.x, 0);
}

/**
 * Adjusts the scrollView's zoom scale to ensure the whole desktop is visible.
 */
- (void)fitDesktopToScrollView
{
  _scrollView.minimumZoomScale = 0;
  if (_serverDesktopSize.width > _serverDesktopSize.height) {
    _scrollView.zoomScale = _scrollView.frame.size.width / _serverDesktopSize.width;
  } else {
    _scrollView.zoomScale = _scrollView.frame.size.height / _serverDesktopSize.height;
  }
  _scrollView.minimumZoomScale = _scrollView.zoomScale;
}

#pragma mark - Special key handling

/**
 * Adding extra buttons to the keyboard to handle Esc and F1
 * 
 * @return toolbar to use as accessoryview of the keyboard
 */
- (UIView*)exampleKeyboardAccessoryView
{
  UIToolbar *toolbar = [[UIToolbar alloc] initWithFrame:CGRectMake(0, 0, self.view.frame.size.width, kToolbarHeight)];
  UIBarButtonItem *esc = [[UIBarButtonItem alloc] initWithTitle:@"Esc"
                                                          style:UIBarButtonItemStylePlain target:self action:@selector(escTapped)];
  UIBarButtonItem *f1 = [[UIBarButtonItem alloc] initWithTitle:@"F1"
                                                         style:UIBarButtonItemStylePlain target:self action:@selector(f1Tapped)];
  UIBarButtonItem *cad = [[UIBarButtonItem alloc] initWithTitle:@"Ctrl-Alt-Del"
                                                         style:UIBarButtonItemStylePlain target:self action:@selector(cadTapped)];
  toolbar.items = @[esc, f1, cad];
  return toolbar;
}

/**
 * Esc tapped and send the key event to the sdkThread
 */
- (void)escTapped
{
  NSLog(@"Escape");
 [[AppDelegate instance].sdkThread performBlockAsync:^{
   [self.viewer sendKey:XK_Escape];
  }];
}

/**
 * F1 tapped and send the key event to the sdkThread
 */
- (void)f1Tapped
{
  NSLog(@"F1");
  [[AppDelegate instance].sdkThread performBlockAsync:^{
    [self.viewer sendKey:XK_F1];
  }];
}

/**
 * Ctrl-Alt-Del button tapped. Send the key events to the sdkThread
 */
- (void)cadTapped
{
  NSLog(@"Ctrl-Alt-Del");
  [[AppDelegate instance].sdkThread performBlockAsync:^{
    [self.viewer sendKeyDown:XK_Control_L];
    [self.viewer sendKeyDown:XK_Alt_L];
    [self.viewer sendKeyDown:XK_Delete];
    [self.viewer sendKeyUp:XK_Delete];
    [self.viewer sendKeyUp:XK_Alt_L];
    [self.viewer sendKeyUp:XK_Control_L];
  }];
}

#pragma mark - Viewer framebuffer callbacks

/**
 * Method called in the SDK thread when the resolution changes in the server
 * 
 * @param viewer is the object where desktopsize has changed
 * @param size is the new size for the viewer desktop
 */
- (void)serverFrameBufferSizeChanged:(ViewerAdapter *)viewer size:(CGSize)size
{
  /* Any change in the server that requires the DesktopView to redraw needs to happen in the UI main thread */
  dispatch_async(dispatch_get_main_queue(), ^{
    _serverDesktopSize = size;
    
    if (_scrollView) {
      /* We need to reset the scrollView's zoomScale before we change the desktopView's bounds. */
      _scrollView.zoomScale = 1;
      [_desktopView updateDesktopBounds:CGRectMake(0, 0, size.width, size.height)];
      [self fitDesktopToScrollView];
      _scrollView.contentSize = size;
    }
  });
}

#pragma mark - UITextFieldDelegate

/**
 * Handling the text input in the textfield
 */
- (BOOL)textField:(UITextField *)textField shouldChangeCharactersInRange:(NSRange)range replacementString:(NSString *)string
{
  /* We need to convert the unicode characters to keysym before being sent */
  [[AppDelegate instance].sdkThread performBlockAsync:^{
    for (int i = 0; i < (int)string.length; ++i) {
      vnc_uint32_t keysym = vnc_unicodeToKeysym([string characterAtIndex:i]);
      [self.viewer sendKey:keysym];
    }
    if (!string.length) /* Handles backspace input */
      [self.viewer sendKey:XK_BackSpace];
  }];
  
  /* Making sure that textfield.text has always an empty space therefore we return NO
     to keep textfield.text property with an empty space. */
  return NO;
}

#pragma mark - Interface Orientation Rotation

- (BOOL)shouldAutorotateToInterfaceOrientation:(UIInterfaceOrientation)interfaceOrientation
{
  return YES;
}

/**
 * Handle interface rotations iOS 8
 */
- (void)viewWillTransitionToSize:(CGSize)size withTransitionCoordinator:(id<UIViewControllerTransitionCoordinator>)coordinator
{
  [super viewWillTransitionToSize:size withTransitionCoordinator:coordinator];
  
  [coordinator animateAlongsideTransition:^(id<UIViewControllerTransitionCoordinatorContext> context) {
    
    [self adjustViewsToInterfaceOrientation];
    
  } completion:nil];
}

#pragma mark - GestureRecognizers Handlers

/**
 * Centralizes the DesktopView in view the X axix, used when zooming.
 */
- (void)offsetView:(UIScrollView *)scrollView
{
  CGFloat offsetX = (scrollView.bounds.size.width > scrollView.contentSize.width)?
  (scrollView.bounds.size.width - scrollView.contentSize.width) * 0.5 : 0.0;
  _desktopView.center = CGPointMake(scrollView.contentSize.width * 0.5 + offsetX,
                                    scrollView.contentSize.height * 0.5);
}

/**
 * Scrollview Delegate method that will centralize the DesktopView when a zoom happens
 */
- (void)scrollViewDidZoom:(UIScrollView *)scrollView
{
  [self offsetView:scrollView];
}

/**
 * Scrollview Method to identify the view to be zoomed by the scrollview
 */
- (UIView *)viewForZoomingInScrollView:(UIScrollView *)scrollView
{
  return _desktopView;
}

/**
 * Handle single tap and sends the pointer events to the sdk
 */
-(void)handleTap:(UITapGestureRecognizer *)sender
{
  if (sender.state == UIGestureRecognizerStateEnded) {
    CGPoint point = [sender locationInView:_desktopView];
    [_desktopView sendPointerEvent:point withButtonState:vnc_Viewer_MouseButtonLeft];
    [_desktopView sendPointerEvent:point withButtonState:0];
  }
}

/**
 * Handle double tap and sends the pointer events to the sdk
 */
-(void)handleDoubleTap:(UITapGestureRecognizer *)sender
{
  if (sender.state == UIGestureRecognizerStateEnded) {
    CGPoint point = [sender locationInView:_desktopView];
    [_desktopView sendPointerEvent:point withButtonState:vnc_Viewer_MouseButtonLeft];
    [_desktopView sendPointerEvent:point withButtonState:0];
    [_desktopView sendPointerEvent:point withButtonState:vnc_Viewer_MouseButtonLeft];
    [_desktopView sendPointerEvent:point withButtonState:0];
  }
}

@end
