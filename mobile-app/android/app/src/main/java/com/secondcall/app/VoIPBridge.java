package com.secondcall.app;

import android.content.Context;
import android.media.AudioManager;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.util.UUID;

/**
 * Native VoIP bridge between WebView JavaScript and Telnyx Android Voice SDK v3.5.
 * Uses reflection to avoid compile-time Kotlin dependency issues.
 *
 * SDK API (Kotlin):
 *   TelnyxClient(context) → connect(credentialConfig) → newInvite(...)
 *   acceptCall(callId, destNumber) / endCall(callId)
 */
public class VoIPBridge {
    private static final String TAG = "VoIPBridge";

    private final Context context;
    private final WebView webView;
    private Object telnyxClient;
    private boolean isLoggedIn = false;
    private boolean isMuted = false;
    private UUID activeCallId = null;

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
                Class<?> clientClass = Class.forName("com.telnyx.webrtc.sdk.TelnyxClient");
                telnyxClient = clientClass.getConstructor(Context.class).newInstance(context);

                // 2. Build CredentialConfig
                Object config = buildCredentialConfig(username, password);
                if (config == null) {
                    sendEvent("error", "Failed to create CredentialConfig");
                    return;
                }

                // 3. connect(credentialConfig) — this connects AND logs in
                Class<?> configClass = config.getClass();
                boolean connected = false;

                // Try connect(TxServerConfiguration, CredentialConfig, String, boolean)
                for (Method m : clientClass.getMethods()) {
                    if (m.getName().equals("connect")) {
                        Class<?>[] pt = m.getParameterTypes();
                        // Look for the overload that takes CredentialConfig
                        if (pt.length >= 2 && pt[1].isAssignableFrom(configClass)) {
                            Object[] args = new Object[pt.length];
                            // First param: TxServerConfiguration — create default
                            try {
                                Class<?> serverConfigClass = Class.forName("com.telnyx.webrtc.sdk.TxServerConfiguration");
                                args[0] = serverConfigClass.getConstructor().newInstance();
                            } catch (Exception e) {
                                args[0] = null;
                            }
                            args[1] = config;
                            // Fill remaining with defaults
                            for (int i = 2; i < pt.length; i++) {
                                if (pt[i] == boolean.class) args[i] = true; // autoLogin
                                else args[i] = null;
                            }
                            m.invoke(telnyxClient, args);
                            connected = true;
                            break;
                        }
                    }
                }

                // Fallback: try credentialLogin(config) separately
                if (!connected) {
                    try {
                        Method loginMethod = clientClass.getMethod("credentialLogin", configClass);
                        loginMethod.invoke(telnyxClient, config);
                        connected = true;
                    } catch (NoSuchMethodException e) {
                        // Try with base class
                        for (Method m : clientClass.getMethods()) {
                            if (m.getName().equals("credentialLogin") && m.getParameterCount() == 1) {
                                m.invoke(telnyxClient, config);
                                connected = true;
                                break;
                            }
                        }
                    }
                }

                if (connected) {
                    isLoggedIn = true;
                    sendEvent("ready", "connected");
                    Log.d(TAG, "Login successful");
                    startCallStateObserver();
                } else {
                    sendEvent("error", "Could not find connect or credentialLogin method");
                }
            } catch (ClassNotFoundException e) {
                Log.w(TAG, "Telnyx SDK not available: " + e.getMessage());
                sendEvent("error", "Native VoIP SDK not loaded. Using web calling.");
            } catch (Exception e) {
                Log.e(TAG, "Login failed: " + e.getMessage(), e);
                sendEvent("error", "Login failed: " + e.getMessage());
            }
        }).start();
    }

    private Object buildCredentialConfig(String username, String password) {
        // Try both package paths
        String[] classNames = {
            "com.telnyx.webrtc.sdk.CredentialConfig",
            "com.telnyx.webrtc.sdk.model.CredentialConfig"
        };

        for (String className : classNames) {
            try {
                Class<?> configClass = Class.forName(className);

                // Kotlin data classes with default params generate a constructor with all params
                // CredentialConfig(sipUser, sipPassword, sipCallerIDName?, sipCallerIDNumber?,
                //                  fcmToken?, ringtone?, ringBackTone?, logLevel, customLogger?,
                //                  autoReconnect, debug, reconnectionTimeout, region, fallbackOnRegionFailure)
                for (Constructor<?> ctor : configClass.getConstructors()) {
                    Class<?>[] params = ctor.getParameterTypes();
                    Log.d(TAG, "CredentialConfig constructor found with " + params.length + " params");

                    if (params.length >= 2 && params[0] == String.class && params[1] == String.class) {
                        Object[] args = new Object[params.length];
                        args[0] = username;   // sipUser
                        args[1] = password;   // sipPassword

                        for (int i = 2; i < params.length; i++) {
                            if (params[i] == String.class) {
                                // sipCallerIDName (index 2), sipCallerIDNumber (index 3), fcmToken (index 4)
                                if (i == 2) args[i] = "2ndCall";
                                else args[i] = null;
                            } else if (params[i] == boolean.class) {
                                args[i] = false;
                            } else if (params[i] == long.class) {
                                args[i] = 60000L;
                            } else if (params[i] == int.class) {
                                // Kotlin's Int? compiled as int in some overloads, or Integer
                                args[i] = 0;
                            } else {
                                args[i] = null;
                            }
                        }

                        try {
                            return ctor.newInstance(args);
                        } catch (Exception e) {
                            Log.w(TAG, "Constructor with " + params.length + " params failed: " + e.getMessage());
                        }
                    }
                }

                // Try Kotlin companion object or builder pattern
                for (Method m : configClass.getMethods()) {
                    if (m.getName().equals("copy") || m.getName().equals("invoke")) {
                        Log.d(TAG, "Found method: " + m.getName() + " with " + m.getParameterCount() + " params");
                    }
                }
            } catch (ClassNotFoundException e) {
                Log.d(TAG, className + " not found, trying next...");
            }
        }
        return null;
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
                // newInvite is directly on TelnyxClient
                // Signature: newInvite(callerName, callerNumber, destinationNumber, clientState, ...)
                Method newInvite = null;
                for (Method m : telnyxClient.getClass().getMethods()) {
                    if (m.getName().equals("newInvite")) {
                        newInvite = m;
                        break;
                    }
                }

                if (newInvite == null) {
                    sendEvent("error", "newInvite method not found");
                    return;
                }

                Class<?>[] params = newInvite.getParameterTypes();
                Object[] args = new Object[params.length];
                Log.d(TAG, "newInvite has " + params.length + " params");

                // Fill params: callerName, callerNumber, destinationNumber, clientState, ...
                int strIdx = 0;
                String[] strValues = {"2ndCall", callerNumber, destinationNumber, ""};
                for (int i = 0; i < params.length; i++) {
                    if (params[i] == String.class && strIdx < strValues.length) {
                        args[i] = strValues[strIdx++];
                    } else if (params[i] == boolean.class) {
                        args[i] = false;
                    } else if (params[i] == java.util.Map.class) {
                        args[i] = null;
                    } else if (params[i] == java.util.List.class) {
                        args[i] = null;
                    } else {
                        args[i] = null;
                    }
                }

                Object callObj = newInvite.invoke(telnyxClient, args);

                // Extract call ID from returned Call object
                if (callObj != null) {
                    try {
                        Method getCallId = callObj.getClass().getMethod("getCallId");
                        Object callIdObj = getCallId.invoke(callObj);
                        if (callIdObj instanceof UUID) {
                            activeCallId = (UUID) callIdObj;
                        }
                    } catch (Exception e) {
                        Log.w(TAG, "Could not get callId: " + e.getMessage());
                    }
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
                // acceptCall(callId: UUID, destinationNumber: String, ...)
                Method acceptCall = null;
                for (Method m : telnyxClient.getClass().getMethods()) {
                    if (m.getName().equals("acceptCall")) {
                        acceptCall = m;
                        break;
                    }
                }
                if (acceptCall != null) {
                    Class<?>[] params = acceptCall.getParameterTypes();
                    Object[] args = new Object[params.length];
                    args[0] = activeCallId;
                    if (params.length > 1) args[1] = ""; // destinationNumber
                    for (int i = 2; i < params.length; i++) {
                        if (params[i] == boolean.class) args[i] = false;
                        else args[i] = null;
                    }
                    acceptCall.invoke(telnyxClient, args);
                    sendEvent("answered", "");
                } else {
                    sendEvent("error", "acceptCall method not found");
                }
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
                // endCall(callId: UUID)
                Method endCall = null;
                for (Method m : telnyxClient.getClass().getMethods()) {
                    if (m.getName().equals("endCall") && m.getParameterCount() == 1) {
                        endCall = m;
                        break;
                    }
                }
                if (endCall != null) {
                    endCall.invoke(telnyxClient, activeCallId);
                }
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
        // Mute is on the Call object, not TelnyxClient
        if (telnyxClient != null && activeCallId != null) {
            try {
                // Get active calls map and find ours
                Method getActiveCalls = telnyxClient.getClass().getMethod("getActiveCalls");
                Object callsMap = getActiveCalls.invoke(telnyxClient);
                if (callsMap instanceof java.util.Map) {
                    Object callObj = ((java.util.Map<?, ?>) callsMap).get(activeCallId);
                    if (callObj != null) {
                        for (Method m : callObj.getClass().getMethods()) {
                            if (m.getName().equals("onMuteUnmutePressed") && m.getParameterCount() == 0) {
                                m.invoke(callObj);
                                break;
                            }
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

    /**
     * Observe call state changes via TelnyxClient's socketResponseFlow.
     * Since we can't easily use Kotlin Flows from Java, we poll getActiveCalls() instead.
     */
    private void startCallStateObserver() {
        new Thread(() -> {
            String lastState = "";
            while (isLoggedIn && telnyxClient != null) {
                try {
                    Thread.sleep(1000);
                    Method getActiveCalls = telnyxClient.getClass().getMethod("getActiveCalls");
                    Object callsMap = getActiveCalls.invoke(telnyxClient);
                    if (callsMap instanceof java.util.Map) {
                        java.util.Map<?, ?> calls = (java.util.Map<?, ?>) callsMap;
                        if (!calls.isEmpty()) {
                            Object callObj = calls.values().iterator().next();
                            // Get call ID
                            try {
                                Method getCallId = callObj.getClass().getMethod("getCallId");
                                Object cid = getCallId.invoke(callObj);
                                if (cid instanceof UUID) activeCallId = (UUID) cid;
                            } catch (Exception ignored) {}

                            // Get call state
                            try {
                                Method getState = callObj.getClass().getMethod("getCallState");
                                Object state = getState.invoke(callObj);
                                String stateStr = state != null ? state.toString().toLowerCase() : "";
                                if (!stateStr.equals(lastState)) {
                                    lastState = stateStr;
                                    Log.d(TAG, "Call state: " + stateStr);
                                    if (stateStr.contains("active") || stateStr.contains("answer")) {
                                        sendEvent("active", "");
                                    } else if (stateStr.contains("ring")) {
                                        sendEvent("ringing", "");
                                    } else if (stateStr.contains("done") || stateStr.contains("hangup") || stateStr.contains("bye")) {
                                        sendEvent("hangup", "");
                                        activeCallId = null;
                                        break;
                                    }
                                }
                            } catch (Exception ignored) {}
                        } else if (activeCallId != null) {
                            // Call was active but now gone — hung up
                            sendEvent("hangup", "");
                            activeCallId = null;
                            lastState = "";
                        }
                    }
                } catch (Exception e) {
                    Log.w(TAG, "State observer error: " + e.getMessage());
                    break;
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
        isLoggedIn = false;
        if (telnyxClient != null) {
            try {
                Method onDestroy = telnyxClient.getClass().getMethod("onDestroy");
                onDestroy.invoke(telnyxClient);
            } catch (Exception e) {
                Log.e(TAG, "Destroy error: " + e.getMessage());
            }
            telnyxClient = null;
        }
        activeCallId = null;
    }
}
