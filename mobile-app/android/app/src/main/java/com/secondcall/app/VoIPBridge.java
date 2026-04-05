package com.secondcall.app;

import android.content.Context;
import android.media.AudioManager;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

/**
 * Native VoIP bridge between WebView JavaScript and Telnyx Android SDK.
 * Uses com.telnyx.webrtc.lib (Maven Central)
 */
public class VoIPBridge {
    private static final String TAG = "VoIPBridge";

    private final Context context;
    private final WebView webView;
    private Object telnyxClient; // Will be TelnyxClient when SDK loads
    private boolean isLoggedIn = false;
    private boolean isMuted = false;

    public VoIPBridge(Context context, WebView webView) {
        this.context = context;
        this.webView = webView;
    }

    @JavascriptInterface
    public void login(String username, String password) {
        Log.d(TAG, "Login attempt: " + username);
        try {
            // Use reflection to avoid compile-time dependency issues
            Class<?> clientClass = Class.forName("com.telnyx.webrtc.sdk.TelnyxClient");
            telnyxClient = clientClass.getConstructor(Context.class).newInstance(context);

            // Create credential config
            Class<?> configClass = Class.forName("com.telnyx.webrtc.sdk.model.CredentialConfig");
            Object config = configClass.getConstructors()[0].newInstance(
                username, password, null, null, null, null, null, null
            );

            // Login
            clientClass.getMethod("credentialLogin", configClass).invoke(telnyxClient, config);
            isLoggedIn = true;
            sendEvent("ready", "connected");
            Log.d(TAG, "Login successful");
        } catch (ClassNotFoundException e) {
            Log.w(TAG, "Telnyx SDK not available, using web fallback");
            sendEvent("error", "Native VoIP SDK not loaded. Using web calling.");
        } catch (Exception e) {
            Log.e(TAG, "Login failed: " + e.getMessage(), e);
            sendEvent("error", "Login failed: " + e.getMessage());
        }
    }

    @JavascriptInterface
    public void call(String destinationNumber, String callerNumber) {
        Log.d(TAG, "Call: " + callerNumber + " -> " + destinationNumber);
        if (telnyxClient == null) {
            sendEvent("error", "Not logged in");
            return;
        }
        try {
            java.lang.reflect.Method newInvite = telnyxClient.getClass().getMethod(
                "newInvite", String.class, String.class, String.class, java.util.Map.class, String.class
            );
            newInvite.invoke(telnyxClient, callerNumber, destinationNumber, "2ndCall", null, null);
            sendEvent("calling", destinationNumber);
        } catch (Exception e) {
            Log.e(TAG, "Call failed: " + e.getMessage(), e);
            sendEvent("error", "Call failed: " + e.getMessage());
        }
    }

    @JavascriptInterface
    public void answer() {
        Log.d(TAG, "Answer");
        sendEvent("answered", "");
    }

    @JavascriptInterface
    public void hangup() {
        Log.d(TAG, "Hangup");
        if (telnyxClient != null) {
            try {
                telnyxClient.getClass().getMethod("onDestroy").invoke(telnyxClient);
            } catch (Exception e) {
                Log.e(TAG, "Hangup error", e);
            }
        }
        sendEvent("hangup", "");
    }

    @JavascriptInterface
    public void mute() {
        isMuted = !isMuted;
        sendEvent("mute", String.valueOf(isMuted));
    }

    @JavascriptInterface
    public void speaker(boolean on) {
        AudioManager audioManager = (AudioManager) context.getSystemService(Context.AUDIO_SERVICE);
        if (audioManager != null) {
            audioManager.setSpeakerphoneOn(on);
            sendEvent("speaker", String.valueOf(on));
        }
    }

    @JavascriptInterface
    public String getState() {
        return isLoggedIn ? "logged_in" : "not_logged_in";
    }

    @JavascriptInterface
    public boolean isReady() {
        return isLoggedIn;
    }

    private void sendEvent(String event, String data) {
        String js = String.format(
            "javascript:if(window.onNativeVoIPEvent)window.onNativeVoIPEvent('%s','%s')",
            event.replace("'", "\\'"),
            data != null ? data.replace("'", "\\'") : ""
        );
        webView.post(() -> webView.evaluateJavascript(js, null));
    }

    public void destroy() {
        if (telnyxClient != null) {
            try {
                telnyxClient.getClass().getMethod("onDestroy").invoke(telnyxClient);
            } catch (Exception e) {
                Log.e(TAG, "Destroy error", e);
            }
        }
    }
}
