package com.secondcall.app;

import android.content.Context;
import android.media.AudioManager;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;

/**
 * Native VoIP bridge between WebView JavaScript and Telnyx Android Voice SDK.
 * Uses com.github.team-telnyx:telnyx-webrtc-android (JitPack)
 */
public class VoIPBridge {
    private static final String TAG = "VoIPBridge";

    private final Context context;
    private final WebView webView;
    private Object telnyxClient;
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
            // Initialize TelnyxClient
            Class<?> clientClass = Class.forName("com.telnyx.webrtc.sdk.TelnyxClient");
            telnyxClient = clientClass.getConstructor(Context.class).newInstance(context);

            // Connect the client first
            try {
                Method connectMethod = clientClass.getMethod("connect");
                connectMethod.invoke(telnyxClient);
            } catch (NoSuchMethodException e) {
                Log.w(TAG, "connect() method not found, SDK may auto-connect on login");
            }

            // Build CredentialConfig — find constructor with String params
            Class<?> configClass = Class.forName("com.telnyx.webrtc.sdk.CredentialConfig");
            Object config = null;

            // Try constructors, looking for one that takes Strings
            for (Constructor<?> ctor : configClass.getConstructors()) {
                Class<?>[] params = ctor.getParameterTypes();
                if (params.length >= 2 && params[0] == String.class && params[1] == String.class) {
                    Object[] args = new Object[params.length];
                    args[0] = username;  // sipUser
                    args[1] = password;  // sipPassword
                    if (params.length > 2 && params[2] == String.class) args[2] = "2ndCall";  // callerIdName
                    if (params.length > 3 && params[3] == String.class) args[3] = "";  // callerIdNumber
                    // remaining args stay null (fcmToken, ringtone, etc.)
                    config = ctor.newInstance(args);
                    break;
                }
            }

            if (config == null) {
                // Try model.CredentialConfig path
                try {
                    configClass = Class.forName("com.telnyx.webrtc.sdk.model.CredentialConfig");
                    for (Constructor<?> ctor : configClass.getConstructors()) {
                        Class<?>[] params = ctor.getParameterTypes();
                        if (params.length >= 2 && params[0] == String.class && params[1] == String.class) {
                            Object[] args = new Object[params.length];
                            args[0] = username;
                            args[1] = password;
                            if (params.length > 2 && params[2] == String.class) args[2] = "2ndCall";
                            if (params.length > 3 && params[3] == String.class) args[3] = "";
                            config = ctor.newInstance(args);
                            break;
                        }
                    }
                } catch (ClassNotFoundException ignored) {}
            }

            if (config == null) {
                sendEvent("error", "CredentialConfig constructor not found. SDK version may be incompatible.");
                return;
            }

            // Login with credentials
            Method loginMethod = clientClass.getMethod("credentialLogin", configClass);
            loginMethod.invoke(telnyxClient, config);
            isLoggedIn = true;
            sendEvent("ready", "connected");
            Log.d(TAG, "Login successful");
        } catch (ClassNotFoundException e) {
            Log.w(TAG, "Telnyx SDK not available: " + e.getMessage());
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
            // Try telnyxClient.call.newInvite() — SDK v3 uses a call manager
            Object callManager = null;
            try {
                Method getCall = telnyxClient.getClass().getMethod("getCall");
                callManager = getCall.invoke(telnyxClient);
            } catch (NoSuchMethodException e) {
                // Try direct method
                callManager = telnyxClient;
            }

            if (callManager != null) {
                // Find newInvite method — signature varies by version
                Method newInvite = null;
                for (Method m : callManager.getClass().getMethods()) {
                    if (m.getName().equals("newInvite")) {
                        newInvite = m;
                        break;
                    }
                }
                if (newInvite != null) {
                    Class<?>[] params = newInvite.getParameterTypes();
                    Object[] args = new Object[params.length];
                    // Fill in known parameters by position
                    if (params.length >= 3) {
                        args[0] = callerNumber;       // callerName or callerNumber
                        args[1] = destinationNumber;  // callerNumber or destinationNumber
                        args[2] = destinationNumber;  // destinationNumber
                    } else if (params.length == 2) {
                        args[0] = callerNumber;
                        args[1] = destinationNumber;
                    }
                    // remaining args stay null
                    newInvite.invoke(callManager, args);
                    sendEvent("calling", destinationNumber);
                } else {
                    sendEvent("error", "newInvite method not found in SDK");
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Call failed: " + e.getMessage(), e);
            sendEvent("error", "Call failed: " + e.getMessage());
        }
    }

    @JavascriptInterface
    public void answer() {
        Log.d(TAG, "Answer");
        if (telnyxClient != null) {
            try {
                Object callManager = telnyxClient.getClass().getMethod("getCall").invoke(telnyxClient);
                if (callManager != null) {
                    for (Method m : callManager.getClass().getMethods()) {
                        if (m.getName().equals("acceptCall")) {
                            m.invoke(callManager, new Object[m.getParameterCount()]);
                            break;
                        }
                    }
                }
            } catch (Exception e) {
                Log.e(TAG, "Answer failed: " + e.getMessage());
            }
        }
        sendEvent("answered", "");
    }

    @JavascriptInterface
    public void hangup() {
        Log.d(TAG, "Hangup");
        if (telnyxClient != null) {
            try {
                Object callManager = telnyxClient.getClass().getMethod("getCall").invoke(telnyxClient);
                if (callManager != null) {
                    for (Method m : callManager.getClass().getMethods()) {
                        if (m.getName().equals("endCall") || m.getName().equals("hangup")) {
                            m.invoke(callManager, new Object[m.getParameterCount()]);
                            break;
                        }
                    }
                }
            } catch (Exception e) {
                Log.e(TAG, "Hangup error: " + e.getMessage());
            }
            // Also try destroying client
            try {
                telnyxClient.getClass().getMethod("onDestroy").invoke(telnyxClient);
            } catch (Exception ignored) {}
        }
        isLoggedIn = false;
        sendEvent("hangup", "");
    }

    @JavascriptInterface
    public void mute() {
        isMuted = !isMuted;
        if (telnyxClient != null) {
            try {
                Object callManager = telnyxClient.getClass().getMethod("getCall").invoke(telnyxClient);
                if (callManager != null) {
                    for (Method m : callManager.getClass().getMethods()) {
                        if (m.getName().equals("onMuteUnmutePressed")) {
                            m.invoke(callManager);
                            break;
                        }
                    }
                }
            } catch (Exception e) {
                Log.e(TAG, "Mute error: " + e.getMessage());
            }
        }
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
                Log.e(TAG, "Destroy error: " + e.getMessage());
            }
            telnyxClient = null;
        }
        isLoggedIn = false;
    }
}
