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

package com.realvnc.vncsdk.sample.basicViewerAndroid.ui;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.support.annotation.NonNull;
import android.util.AttributeSet;
import android.util.Log;
import android.view.MotionEvent;
import android.view.View;

import com.realvnc.vncsdk.Library;
import com.realvnc.vncsdk.PixelFormat;
import com.realvnc.vncsdk.Viewer;
import com.realvnc.vncsdk.sample.basicViewerAndroid.SdkThread;
import com.realvnc.vncsdk.sample.basicViewerAndroid.input.TouchEventAdapter;

import java.util.EnumSet;

/**
 * FrameBufferView is responsible for drawing the framebuffer, scaled and translated into the
 * appropriate position.
 *
 * It receives framebuffer update notifications from the VNC SDK in the SdkThread, and so any
 * UI updates are posted to the UI thread. When we are notified of framebuffer updates (via the
 * {@link #viewerFbUpdated} method) we invalidate the viewer canvas via {@link View#postInvalidate},
 * which ensures our draw methods are called on the correct thread.
 *
 * We use the Canvas' own Matrix (provided in the onDraw method) to perform hardware-accelerated
 * scale and translate operations.
 *
 */
public class FrameBufferView extends View implements Viewer.FramebufferCallback, Viewer.ServerEventCallback {

    private static final String TAG = "FrameBufferView";
    private Bitmap mFbBitmap;
    private TouchEventAdapter mTouchEventAdapter;
    private float mScaleFactor = 1.0f;
    private float mOffsetx = 0.0f;
    private float mOffsety = 0.0f;
    private int mW = 0;
    private int mH = 0;

    /**
     * The method which actually renders to the screen.
     *
     * Called on the UI thread when the view has been invalidated (by {@link #viewerFbUpdated}.
     * @param canvas
     */
    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);

        canvas.drawColor(Color.BLACK);

        // Clamp scale and offset
        canvas.scale(mScaleFactor, mScaleFactor);
        canvas.translate(mOffsetx, mOffsety);

        if (mFbBitmap != null) {
            canvas.drawBitmap(mFbBitmap, 0f, 0f, null);
        }
    }

    // region constructors and init
    public FrameBufferView(Context context) {
        super(context);

        init();
    }

    public FrameBufferView(Context context, AttributeSet attrs) {
        super(context, attrs);

        init();
    }

    public FrameBufferView(Context context, AttributeSet attrs, int defStyle) {
        super(context, attrs, defStyle);

        init();
    }

    private void init() {
        setWillNotDraw(false);
    }
    // endregion

    /**
     * Capture touch events and send equivalent pointer events.
     *
     * Called by the Android runtime on the UI thread.
     *
     * @param event The MotionEvent.
     * @return The value returned by {@link TouchEventAdapter#onTouchEvent(MotionEvent)}
     */
    @Override
    public boolean onTouchEvent(@NonNull MotionEvent event) {
        if (mTouchEventAdapter == null) {
            return false;
        }

        return mTouchEventAdapter.onTouchEvent(event);
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        clampScaleAndOffset();
        invalidate();
    }


    // region Viewer.FrameBufferCallback members. These methods are called in the SDK's thread.

    /**
     * Called when the server's framebuffer size has changed. Here we initialise the viewer
     * framebuffer.
     *
     * Called in the SDK thread.
     * @param viewer The SDK Viewer object
     * @param w The width of the server framebuffer
     * @param h The height of the server framebuffer
     */
    @Override
    public void serverFbSizeChanged(Viewer viewer, int w, int h) {
        Log.d(TAG, "desktopSizeChanged");
        mW = w;
        mH = h;

        initFbBitmap();

        try {
            viewer.setViewerFb(null, PixelFormat.bgr888(), w, h, 0);
        } catch (Library.VncException e) {
            Log.e(TAG, "desktopSizeChanged", e);
        }
    }


    /**
     * Called when a region of the server's framebuffer has been updated. Here we copy the RGB data
     * into the {@link #mFbBitmap} member, which is then copied to the Canvas in the
     * {@link #onDraw(Canvas)} method after the View has been invalidated.
     *
     * <p>
     * Note: This sample will fail if the framebuffer is larger than the maximum supported size for
     * a Bitmap, as a single Bitmap is used to contain the entire framebuffer. The maximum Bitmap
     * size will vary depending on the Android device. One way to support a framebuffer larger than
     * the maximum Bitmap size is to divide the framebuffer into multiple tiles, where each tile is
     * less than the maximum Bitmap size. Bitmaps can then be used to copy data from tiles in the
     * framebuffer onto the canvas.
     * </p>
     *
     * Called in the SDK thread.
     * @param viewer The SDK Viewer object.
     * @param x The horizontal component of the updated region's root coordinate
     * @param y The vertical component of the updated region's root coordinate
     * @param w The width of the updated region
     * @param h The height of the updated region
     */
    @Override
    public void viewerFbUpdated(Viewer viewer, int x, int y, int w, int h) {
        try {
            viewer.getViewerFbData(x, y, w, h, mFbBitmap, x, y);
            // postInvalidate ensures the draw methods are called on the correct (UI) thread.
            postInvalidate();
        } catch (Exception e) {
            Log.e(TAG, "viewerFbUpdated", e);
        }
    }

    /**
     * Called when some text has been placed in the server's clipboard.
     *
     * Called in the SDK thread.
     * @param viewer The SDK Viewer object
     * @param s The text in the clipboard
     */
    @Override
    public void serverClipboardTextChanged(Viewer viewer, String s) {

    }

    /**
     * Called when the server's 'friendly' name has been updated.
     * @param viewer The SDK Viewer object
     * @param s The server's 'friendly' name
     */
    @Override
    public void serverFriendlyNameChanged(Viewer viewer, String s) {

    }
    // endregion

    // region helper methods

    /**
     * Initialises the mFbBitmap Bitmap.
     *
     * Called on the SDK thread.
     */
    private void initFbBitmap() {
        synchronized (this) {
            mFbBitmap = Bitmap.createBitmap(mW, mH, Bitmap.Config.ARGB_8888);
            mFbBitmap.setHasAlpha(false);
        }
    }

    public void setTouchEventAdapter(TouchEventAdapter touchEventAdapter) {
        this.mTouchEventAdapter = touchEventAdapter;
    }

    public void setScaleFactor(float scaleFactor) {
        mScaleFactor *= scaleFactor;
        clampScaleAndOffset();
        postInvalidate();
    }

    public void setOffset(float x, float y) {
        mOffsetx -= x;
        mOffsety -= y;
        clampScaleAndOffset();
        invalidate();
    }

    private float clamp(float x, float min, float max) {
        return Math.min(Math.max(x, min), max);
    }

    private void clampScaleAndOffset() {
        mScaleFactor = clamp(mScaleFactor, 0.25f, 4);
        mOffsetx = clamp(mOffsetx, getMeasuredWidth() / mScaleFactor - mW, 0);
        mOffsety = clamp(mOffsety, getMeasuredHeight() / mScaleFactor - mH, 0);
    }

    public void sendPointerEvent(final Viewer viewer,
                                 final int x, final int y,
                                 final EnumSet<Viewer.MouseButton> mouseButtons,
                                 final boolean b) {
        SdkThread.getInstance().post(new Runnable() {
            @Override
            public void run() {
                try {
                    viewer.sendPointerEvent((int) (x / mScaleFactor - mOffsetx),
                            (int) (y / mScaleFactor - mOffsety),
                            mouseButtons, b);
                } catch (Library.VncException e) {
                    Log.w(TAG, "onPointerEvent", e);
                }
            }
        });
    }
    // endregion
}

