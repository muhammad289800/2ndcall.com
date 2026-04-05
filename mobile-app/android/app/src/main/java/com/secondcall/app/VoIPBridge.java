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

                // 3. Connect with credential config
                try {
                    telnyxClient.connect(
                        new com.telnyx.webrtc.sdk.TxServerConfiguration(),
                        (com.telnyx.webrtc.sdk.CredentialConfig) config,
                        null,   // txPushMetaData
                        true    // autoLogin
                    );
                } catch (ClassCastException e) {
                    // Config might be from a different class path — try credentialLogin
                    Log.w(TAG, "connect() cast failed, trying credentialLogin...");
                    telnyxClient.credentialLogin((com.telnyx.webrtc.sdk.CredentialConfig) config);
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
        if (telnyxClient == null || !isLoggedIn) {
            sendEvent("error", "Not logged in");
            return;
        }
        new Thread(() -> {
            try {
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
                }
                sendEvent("calling", destinationNumber);
            } catch (Exception e) {
                Log.e(TAG, "Call failed: " + e.getMessage(), e);
                sendEvent("error", "Call failed: " + e.getMessage());
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
            try {
                telnyxClient.onDestroy();
            } catch (Exception e) {
                Log.e(TAG, "Destroy error: " + e.getMessage());
            }
            telnyxClient = null;
        }
        activeCallId = null;
    }
}
