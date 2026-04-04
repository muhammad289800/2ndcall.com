package com.secondcall.app;

import android.content.Context;
import android.media.AudioManager;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import com.telnyx.webrtc.sdk.TelnyxClient;
import com.telnyx.webrtc.sdk.model.CallState;
import com.telnyx.webrtc.sdk.model.CredentialConfig;
import com.telnyx.webrtc.sdk.model.TxServerConfiguration;
import com.telnyx.webrtc.sdk.verto.receive.SocketResponse;

import java.util.UUID;

/**
 * Native VoIP bridge between WebView JavaScript and Telnyx Android SDK.
 *
 * JavaScript calls:
 *   NativeVoIP.login(username, password)
 *   NativeVoIP.call(destinationNumber, callerNumber)
 *   NativeVoIP.answer()
 *   NativeVoIP.hangup()
 *   NativeVoIP.mute()
 *   NativeVoIP.unmute()
 *   NativeVoIP.speaker(on)
 *   NativeVoIP.getState()
 *
 * JavaScript receives callbacks via:
 *   window.onNativeVoIPEvent(event, data)
 */
public class VoIPBridge {
    private static final String TAG = "VoIPBridge";

    private final Context context;
    private final WebView webView;
    private TelnyxClient telnyxClient;
    private com.telnyx.webrtc.sdk.Call activeCall;
    private boolean isLoggedIn = false;
    private boolean isMuted = false;
    private boolean isSpeaker = false;

    public VoIPBridge(Context context, WebView webView) {
        this.context = context;
        this.webView = webView;
    }

    @JavascriptInterface
    public void login(String username, String password) {
        Log.d(TAG, "Login: " + username);
        try {
            telnyxClient = new TelnyxClient(context);

            CredentialConfig config = new CredentialConfig(
                username,
                password,
                null, // callerIdName
                null, // callerIdNumber
                null, // fcmToken
                null, // ringtone
                null, // ringBackTone
                TxServerConfiguration.Dev.PROD
            );

            telnyxClient.credentialLogin(config);

            // Listen for socket events
            telnyxClient.getSocketResponse().observeForever(response -> {
                if (response instanceof SocketResponse.MessageReceived) {
                    // Handle messages
                } else if (response instanceof SocketResponse.Error) {
                    sendEvent("error", ((SocketResponse.Error) response).getMessage());
                }
            });

            // Listen for login state
            telnyxClient.getSessionState().observeForever(state -> {
                Log.d(TAG, "Session state: " + state);
                switch (state) {
                    case LOGIN:
                        isLoggedIn = true;
                        sendEvent("ready", "connected");
                        break;
                    case CLIENT_READY:
                        sendEvent("client_ready", "ready");
                        break;
                    default:
                        sendEvent("session", state.toString());
                }
            });

            // Listen for incoming calls
            telnyxClient.getCall().observeForever(call -> {
                if (call != null) {
                    activeCall = call;
                    observeCall(call);
                    sendEvent("incoming", call.getCallInfo().getCallerIdNumber());
                }
            });

        } catch (Exception e) {
            Log.e(TAG, "Login failed", e);
            sendEvent("error", "Login failed: " + e.getMessage());
        }
    }

    @JavascriptInterface
    public void call(String destinationNumber, String callerNumber) {
        Log.d(TAG, "Call: " + callerNumber + " -> " + destinationNumber);
        if (telnyxClient == null || !isLoggedIn) {
            sendEvent("error", "Not logged in");
            return;
        }
        try {
            UUID callId = telnyxClient.newInvite(
                callerNumber,
                destinationNumber,
                "2ndCall",
                null, // customHeaders
                null  // debugReportId
            );

            activeCall = telnyxClient.getCall().getValue();
            if (activeCall != null) {
                observeCall(activeCall);
            }
            sendEvent("calling", destinationNumber);
        } catch (Exception e) {
            Log.e(TAG, "Call failed", e);
            sendEvent("error", "Call failed: " + e.getMessage());
        }
    }

    @JavascriptInterface
    public void answer() {
        Log.d(TAG, "Answer");
        if (activeCall != null) {
            try {
                activeCall.acceptCall(UUID.fromString(activeCall.getCallInfo().getCallId()), null);
                sendEvent("answered", "");
            } catch (Exception e) {
                sendEvent("error", "Answer failed: " + e.getMessage());
            }
        }
    }

    @JavascriptInterface
    public void hangup() {
        Log.d(TAG, "Hangup");
        if (activeCall != null) {
            try {
                activeCall.endCall(UUID.fromString(activeCall.getCallInfo().getCallId()));
            } catch (Exception e) {
                Log.e(TAG, "Hangup error", e);
            }
            activeCall = null;
        }
        sendEvent("hangup", "");
    }

    @JavascriptInterface
    public void mute() {
        if (activeCall != null) {
            isMuted = !isMuted;
            activeCall.onMuteUnmutePressed(UUID.fromString(activeCall.getCallInfo().getCallId()));
            sendEvent("mute", String.valueOf(isMuted));
        }
    }

    @JavascriptInterface
    public void unmute() {
        mute(); // Toggle
    }

    @JavascriptInterface
    public void speaker(boolean on) {
        AudioManager audioManager = (AudioManager) context.getSystemService(Context.AUDIO_SERVICE);
        if (audioManager != null) {
            audioManager.setSpeakerphoneOn(on);
            isSpeaker = on;
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

    private void observeCall(com.telnyx.webrtc.sdk.Call call) {
        call.getCallState().observeForever(state -> {
            Log.d(TAG, "Call state: " + state);
            switch (state) {
                case NEW:
                    sendEvent("state", "new");
                    break;
                case CONNECTING:
                    sendEvent("state", "connecting");
                    break;
                case RINGING:
                    sendEvent("state", "ringing");
                    break;
                case ACTIVE:
                    sendEvent("state", "active");
                    break;
                case HELD:
                    sendEvent("state", "held");
                    break;
                case DONE:
                    sendEvent("state", "done");
                    activeCall = null;
                    break;
                default:
                    sendEvent("state", state.toString());
            }
        });
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
                telnyxClient.onDestroy();
            } catch (Exception e) {
                Log.e(TAG, "Destroy error", e);
            }
        }
    }
}
