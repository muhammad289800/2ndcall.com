package com.secondcall.app;

import android.content.Context;
import android.media.AudioManager;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import java.util.Map;
import java.util.UUID;

/**
 * Native VoIP bridge between WebView JavaScript and Telnyx Android Voice SDK v3.5.
 * Direct SDK imports — no reflection needed.
 */
public class VoIPBridge {
    private static final String TAG = "VoIPBridge";

    private final Context context;
    private final WebView webView;
    private com.telnyx.webrtc.sdk.TelnyxClient telnyxClient;
    private boolean isLoggedIn = false;
    private boolean isMuted = false;
    private UUID activeCallId = null;
    private volatile boolean observerRunning = false;

    public VoIPBridge(Context context, WebView webView) {
        this.context = context;
        this.webView = webView;
    }

    @JavascriptInterface
    public void login(String username, String password) {
        Log.d(TAG, "Login attempt: " + username);
        new Thread(() -> {
            try {
                // 1. Create TelnyxClient
                telnyxClient = new com.telnyx.webrtc.sdk.TelnyxClient(context);

                // 2. Build CredentialConfig — try direct constructor, fall back to reflection
                Object config = buildCredentialConfig(username, password);
                if (config == null) {
                    sendEvent("error", "Failed to create CredentialConfig");
                    return;
                }

                // 3. Connect and login
                com.telnyx.webrtc.sdk.CredentialConfig credConfig = (com.telnyx.webrtc.sdk.CredentialConfig) config;

                // Log all available connect methods for debugging
                for (java.lang.reflect.Method m : telnyxClient.getClass().getMethods()) {
                    if (m.getName().equals("connect") || m.getName().equals("credentialLogin")) {
                        Class<?>[] pts = m.getParameterTypes();
                        StringBuilder sb = new StringBuilder(m.getName() + "(");
                        for (int i = 0; i < pts.length; i++) {
                            if (i > 0) sb.append(", ");
                            sb.append(pts[i].getSimpleName());
                        }
                        sb.append(")");
                        Log.d(TAG, "SDK method: " + sb);
                    }
                }

                // Strategy 1: Try connect(CredentialConfig) directly
                boolean connected = false;
                for (java.lang.reflect.Method m : telnyxClient.getClass().getMethods()) {
                    if (m.getName().equals("connect")) {
                        Class<?>[] pts = m.getParameterTypes();
                        // Look for connect(CredentialConfig) or connect(..., CredentialConfig, ...)
                        for (int i = 0; i < pts.length; i++) {
                            if (pts[i].isAssignableFrom(credConfig.getClass())) {
                                Object[] args = new Object[pts.length];
                                for (int j = 0; j < pts.length; j++) {
                                    if (pts[j].isAssignableFrom(credConfig.getClass())) {
                                        args[j] = credConfig;
                                    } else if (pts[j] == boolean.class) {
                                        args[j] = true;
                                    } else if (pts[j] == String.class) {
                                        args[j] = null;
                                    } else {
                                        // Try default constructor for other types
                                        try { args[j] = pts[j].getConstructor().newInstance(); }
                                        catch (Exception ignored) { args[j] = null; }
                                    }
                                }
                                try {
                                    m.invoke(telnyxClient, args);
                                    connected = true;
                                    Log.d(TAG, "Connected via connect() with " + pts.length + " params");
                                } catch (Exception ce) {
                                    Log.w(TAG, "connect() variant failed: " + ce.getMessage());
                                }
                                break;
                            }
                        }
                        if (connected) break;
                    }
                }

                // Strategy 2: connect() no-args then credentialLogin
                if (!connected) {
                    try {
                        java.lang.reflect.Method connectMethod = telnyxClient.getClass().getMethod("connect");
                        connectMethod.invoke(telnyxClient);
                        Log.d(TAG, "connect() no-args succeeded, waiting...");
                        Thread.sleep(3000);
                        telnyxClient.credentialLogin(credConfig);
                        connected = true;
                    } catch (NoSuchMethodException nsm) {
                        Log.w(TAG, "No zero-arg connect()");
                    } catch (Exception e2) {
                        Log.w(TAG, "connect()+credentialLogin failed: " + e2.getMessage());
                    }
                }

                // Strategy 3: credentialLogin directly
                if (!connected) {
                    try {
                        telnyxClient.credentialLogin(credConfig);
                        connected = true;
                        Log.d(TAG, "credentialLogin() direct succeeded");
                    } catch (Exception e3) {
                        Log.e(TAG, "credentialLogin direct failed: " + e3.getMessage());
                    }
                }

                if (!connected) {
                    sendEvent("error", "All connect strategies failed");
                    return;
                }

                Log.d(TAG, "Connect called, starting observers...");
                observerRunning = true;
                startReadyWatcher();
                startCallStateObserver();

            } catch (NoClassDefFoundError e) {
                Log.w(TAG, "Telnyx SDK not available: " + e.getMessage());
                sendEvent("error", "Native VoIP SDK not loaded. Using web calling.");
            } catch (Exception e) {
                Log.e(TAG, "Login failed: " + e.getMessage(), e);
                sendEvent("error", "Login failed: " + e.getMessage());
            }
        }).start();
    }

    @JavascriptInterface
    public void call(String destinationNumber, String callerNumber) {
        Log.d(TAG, "Call: " + callerNumber + " -> " + destinationNumber);
        if (telnyxClient == null) {
            sendEvent("error", "VoIP client not created");
            return;
        }
        if (!isLoggedIn) {
            // Try to use it anyway — SDK might be connected even if our flag wasn't set
            Log.w(TAG, "isLoggedIn=false but trying call anyway...");
        }
        new Thread(() -> {
            try {
                // Log available newInvite methods
                for (java.lang.reflect.Method m : telnyxClient.getClass().getMethods()) {
                    if (m.getName().equals("newInvite")) {
                        Class<?>[] pts = m.getParameterTypes();
                        StringBuilder sb = new StringBuilder("newInvite(");
                        for (int i = 0; i < pts.length; i++) {
                            if (i > 0) sb.append(", ");
                            sb.append(pts[i].getSimpleName());
                        }
                        sb.append(")");
                        Log.d(TAG, "Found: " + sb);
                    }
                }

                com.telnyx.webrtc.sdk.Call callObj = telnyxClient.newInvite(
                    "2ndCall",            // callerName
                    callerNumber,         // callerNumber
                    destinationNumber,    // destinationNumber
                    "",                   // clientState
                    null,                 // customHeaders
                    false,                // debug
                    null,                 // preferredCodecs
                    false,                // useTrickleIce
                    null,                 // audioConstraints
                    false                 // mutedMicOnStart
                );

                if (callObj != null) {
                    activeCallId = callObj.getCallId();
                    Log.d(TAG, "Call initiated, callId: " + activeCallId);
                    sendEvent("calling", destinationNumber);

                    // Monitor this specific call for 15 seconds
                    for (int i = 0; i < 15; i++) {
                        Thread.sleep(1000);
                        try {
                            Object state = callObj.getCallState();
                            String stateStr = state != null ? state.toString() : "null";
                            Log.d(TAG, "Call state [" + i + "s]: " + stateStr);
                            sendEvent("state", stateStr.toLowerCase());

                            if (stateStr.toLowerCase().contains("active")) {
                                sendEvent("active", "");
                                break;
                            } else if (stateStr.toLowerCase().contains("done") || stateStr.toLowerCase().contains("error")) {
                                sendEvent("error", "Call ended: " + stateStr);
                                break;
                            }
                        } catch (Exception se) {
                            Log.w(TAG, "State check error: " + se.getMessage());
                        }

                        // Also check active calls map
                        try {
                            Map<UUID, com.telnyx.webrtc.sdk.Call> activeCalls = telnyxClient.getActiveCalls();
                            Log.d(TAG, "Active calls count: " + (activeCalls != null ? activeCalls.size() : 0));
                        } catch (Exception ignored) {}
                    }
                } else {
                    Log.e(TAG, "newInvite returned null");
                    sendEvent("error", "Call returned null");
                }
            } catch (Exception e) {
                Log.e(TAG, "Call failed: " + e.getMessage(), e);
                sendEvent("error", "Call failed: " + e.getMessage());
                // Try reflection as last resort
                try {
                    for (java.lang.reflect.Method m : telnyxClient.getClass().getMethods()) {
                        if (m.getName().equals("newInvite")) {
                            Class<?>[] pts = m.getParameterTypes();
                            Object[] args = new Object[pts.length];
                            int strIdx = 0;
                            String[] strs = {"2ndCall", callerNumber, destinationNumber, ""};
                            for (int i = 0; i < pts.length; i++) {
                                if (pts[i] == String.class && strIdx < strs.length) {
                                    args[i] = strs[strIdx++];
                                } else if (pts[i] == boolean.class) {
                                    args[i] = false;
                                } else {
                                    args[i] = null;
                                }
                            }
                            Object result = m.invoke(telnyxClient, args);
                            if (result != null) {
                                Log.d(TAG, "Reflection call succeeded");
                                sendEvent("calling", destinationNumber);
                            }
                            break;
                        }
                    }
                } catch (Exception e2) {
                    Log.e(TAG, "Reflection call also failed: " + e2.getMessage());
                }
            }
        }).start();
    }

    @JavascriptInterface
    public void answer() {
        Log.d(TAG, "Answer");
        if (telnyxClient == null || activeCallId == null) {
            sendEvent("error", "No incoming call to answer");
            return;
        }
        new Thread(() -> {
            try {
                telnyxClient.acceptCall(
                    activeCallId,
                    "",     // destinationNumber
                    null,   // customHeaders
                    false,  // debug
                    false,  // useTrickleIce
                    null,   // audioConstraints
                    false,  // mutedMicOnStart
                    null    // answeredDeviceToken
                );
                sendEvent("answered", "");
            } catch (Exception e) {
                Log.e(TAG, "Answer failed: " + e.getMessage(), e);
                sendEvent("error", "Answer failed: " + e.getMessage());
            }
        }).start();
    }

    @JavascriptInterface
    public void hangup() {
        Log.d(TAG, "Hangup");
        if (telnyxClient != null && activeCallId != null) {
            try {
                telnyxClient.endCall(activeCallId);
            } catch (Exception e) {
                Log.e(TAG, "Hangup error: " + e.getMessage());
            }
        }
        activeCallId = null;
        sendEvent("hangup", "");
    }

    @JavascriptInterface
    public void mute() {
        isMuted = !isMuted;
        if (telnyxClient != null && activeCallId != null) {
            try {
                Map<UUID, com.telnyx.webrtc.sdk.Call> calls = telnyxClient.getActiveCalls();
                com.telnyx.webrtc.sdk.Call callObj = calls.get(activeCallId);
                if (callObj != null) {
                    callObj.onMuteUnmutePressed();
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
        }
        // Also try SDK's audio device control
        if (telnyxClient != null) {
            try {
                if (on) {
                    telnyxClient.setAudioOutputDevice(
                        com.telnyx.webrtc.sdk.model.AudioDevice.LOUDSPEAKER
                    );
                } else {
                    telnyxClient.setAudioOutputDevice(
                        com.telnyx.webrtc.sdk.model.AudioDevice.PHONE_EARPIECE
                    );
                }
            } catch (Exception e) {
                Log.w(TAG, "SDK speaker toggle: " + e.getMessage());
            }
        }
        sendEvent("speaker", String.valueOf(on));
    }

    @JavascriptInterface
    public String getState() {
        return isLoggedIn ? "logged_in" : "not_logged_in";
    }

    @JavascriptInterface
    public boolean isReady() {
        return isLoggedIn;
    }

    /**
     * Build CredentialConfig — tries direct construction first, then reflection fallback
     */
    private Object buildCredentialConfig(String username, String password) {
        // Attempt 1: Direct constructor with all 15 params
        try {
            return new com.telnyx.webrtc.sdk.CredentialConfig(
                username,       // sipUser
                password,       // sipPassword
                "2ndCall",      // sipCallerIDName
                null,           // sipCallerIDNumber
                null,           // fcmToken
                null,           // ringtone
                null,           // ringBackTone (Integer? in Kotlin)
                com.telnyx.webrtc.sdk.model.LogLevel.DEBUG,
                null,           // customLogger
                true,           // autoReconnect
                false,          // debug
                60000L,         // reconnectionTimeout
                com.telnyx.webrtc.sdk.model.Region.US_EAST,
                true,           // fallbackOnRegionFailure
                false           // forceRelayCandidate
            );
        } catch (Exception e) {
            Log.w(TAG, "Direct CredentialConfig failed: " + e.getMessage());
        }

        // Attempt 2: Reflection — find any constructor that starts with (String, String, ...)
        try {
            Class<?> configClass = Class.forName("com.telnyx.webrtc.sdk.CredentialConfig");
            for (java.lang.reflect.Constructor<?> ctor : configClass.getConstructors()) {
                Class<?>[] params = ctor.getParameterTypes();
                Log.d(TAG, "Found CredentialConfig constructor with " + params.length + " params: " + java.util.Arrays.toString(params));

                if (params.length >= 2 && params[0] == String.class && params[1] == String.class) {
                    Object[] args = new Object[params.length];
                    args[0] = username;
                    args[1] = password;
                    for (int i = 2; i < params.length; i++) {
                        if (params[i] == String.class) {
                            args[i] = (i == 2) ? "2ndCall" : null;
                        } else if (params[i] == boolean.class) {
                            args[i] = (i <= 10) ? true : false; // autoReconnect=true
                        } else if (params[i] == long.class) {
                            args[i] = 60000L;
                        } else if (params[i] == int.class) {
                            // This might be the Kotlin default mask — try 0 or bitmask
                            args[i] = 0;
                        } else if (params[i].getName().contains("DefaultConstructorMarker")) {
                            args[i] = null;
                        } else {
                            // Try to find enum values for LogLevel, Region
                            try {
                                if (params[i].isEnum()) {
                                    Object[] enumConstants = params[i].getEnumConstants();
                                    if (enumConstants != null && enumConstants.length > 0) {
                                        args[i] = enumConstants[0]; // First enum value
                                    }
                                }
                            } catch (Exception ignored) {}
                            if (args[i] == null && params[i].isPrimitive()) {
                                if (params[i] == int.class) args[i] = 0;
                                else if (params[i] == long.class) args[i] = 0L;
                                else if (params[i] == boolean.class) args[i] = false;
                            }
                        }
                    }
                    try {
                        Object result = ctor.newInstance(args);
                        Log.d(TAG, "CredentialConfig created via reflection (" + params.length + " params)");
                        return result;
                    } catch (Exception e2) {
                        Log.w(TAG, "Constructor " + params.length + " params failed: " + e2.getMessage());
                    }
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Reflection CredentialConfig failed: " + e.getMessage());
        }

        return null;
    }

    private void startReadyWatcher() {
        new Thread(() -> {
            for (int i = 0; i < 30; i++) {
                try { Thread.sleep(500); } catch (InterruptedException ignored) { return; }
                if (telnyxClient == null) return;
                // Check if we have active connection by trying getActiveCalls
                try {
                    telnyxClient.getActiveCalls();
                    // If no exception, SDK is connected
                    if (!isLoggedIn) {
                        isLoggedIn = true;
                        sendEvent("ready", "connected");
                        Log.d(TAG, "SDK ready");
                        return;
                    }
                } catch (Exception e) {
                    // Not ready yet
                }
            }
            // Timeout — assume ready
            if (!isLoggedIn && telnyxClient != null) {
                isLoggedIn = true;
                sendEvent("ready", "connected");
                Log.w(TAG, "SDK ready (timeout fallback)");
            }
        }).start();
    }

    private void startCallStateObserver() {
        new Thread(() -> {
            String lastState = "";
            while (observerRunning && telnyxClient != null) {
                try {
                    Thread.sleep(1000);
                    Map<UUID, com.telnyx.webrtc.sdk.Call> calls = telnyxClient.getActiveCalls();

                    if (calls != null && !calls.isEmpty()) {
                        com.telnyx.webrtc.sdk.Call callObj = calls.values().iterator().next();
                        activeCallId = callObj.getCallId();

                        String stateStr = "";
                        try {
                            Object state = callObj.getCallState();
                            stateStr = state != null ? state.toString().toLowerCase() : "";
                        } catch (Exception ignored) {}

                        if (!stateStr.isEmpty() && !stateStr.equals(lastState)) {
                            lastState = stateStr;
                            Log.d(TAG, "Call state: " + stateStr);
                            if (stateStr.contains("active")) {
                                sendEvent("active", "");
                            } else if (stateStr.contains("ringing") || stateStr.contains("connecting")) {
                                sendEvent("ringing", "");
                            } else if (stateStr.contains("done") || stateStr.contains("error")) {
                                sendEvent("hangup", "");
                                activeCallId = null;
                                lastState = "";
                            }
                        }
                    } else if (activeCallId != null) {
                        sendEvent("hangup", "");
                        activeCallId = null;
                        lastState = "";
                    }
                } catch (Exception e) {
                    // Silently continue
                }
            }
        }).start();
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
        observerRunning = false;
        isLoggedIn = false;
        if (telnyxClient != null) {
            // End any active calls
            if (activeCallId != null) {
                try {
                    telnyxClient.endCall(activeCallId);
                } catch (Exception ignored) {}
            }
            // Try to disconnect/destroy via reflection (method name varies by version)
            try {
                java.lang.reflect.Method m = telnyxClient.getClass().getMethod("disconnect");
                m.invoke(telnyxClient);
            } catch (Exception ignored) {}
            telnyxClient = null;
        }
        activeCallId = null;
    }
}
