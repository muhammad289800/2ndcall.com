package com.secondcall.app;

import android.content.Context;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.util.Log;

/**
 * Native VoIP bridge placeholder.
 * Currently reports not ready — will be enabled when VoIP SDK is integrated.
 *
 * JavaScript interface:
 *   NativeVoIP.isReady() — returns false until SDK is added
 *   NativeVoIP.getState() — returns current state
 */
public class VoIPBridge {
    private static final String TAG = "VoIPBridge";
    private final Context context;
    private final WebView webView;

    public VoIPBridge(Context context, WebView webView) {
        this.context = context;
        this.webView = webView;
    }

    @JavascriptInterface
    public boolean isReady() {
        return false; // Will return true when VoIP SDK is integrated
    }

    @JavascriptInterface
    public String getState() {
        return "sdk_not_available";
    }

    @JavascriptInterface
    public void login(String username, String password) {
        Log.d(TAG, "VoIP SDK not yet integrated");
        sendEvent("error", "Native VoIP not available yet. Using web calling.");
    }

    @JavascriptInterface
    public void call(String destinationNumber, String callerNumber) {
        sendEvent("error", "Native VoIP not available. Call placed via web.");
    }

    @JavascriptInterface
    public void answer() {}

    @JavascriptInterface
    public void hangup() {}

    @JavascriptInterface
    public void mute() {}

    @JavascriptInterface
    public void speaker(boolean on) {}

    private void sendEvent(String event, String data) {
        String js = String.format(
            "javascript:if(window.onNativeVoIPEvent)window.onNativeVoIPEvent('%s','%s')",
            event.replace("'", "\\'"),
            data != null ? data.replace("'", "\\'") : ""
        );
        webView.post(() -> webView.evaluateJavascript(js, null));
    }

    public void destroy() {}
}
