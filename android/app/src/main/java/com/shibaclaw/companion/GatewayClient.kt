package com.shibaclaw.companion

import android.os.Build
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.util.concurrent.TimeUnit

class GatewayClient(
    private val tools: DeviceTools,
    private val listener: Listener,
) {
    interface Listener {
        fun onHello(ok: Boolean, error: String?)
        fun onMood(mood: Mood)
        fun onBubble(text: String)
        fun onChatDelta(text: String)
        fun onChatDone(text: String)
        fun onClosed()
    }

    private val http = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()

    private var socket: WebSocket? = null
    @Volatile var connected: Boolean = false
        private set

    private val pendingChat = ConcurrentHashMap<String, StringBuilder>()

    fun connect(host: String, port: Int, token: String, deviceId: String, label: String) {
        disconnect()
        val url = "ws://$host:$port"
        val req = Request.Builder().url(url).build()
        socket = http.newWebSocket(req, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                val hello = JSONObject()
                    .put("type", "hello")
                    .put("role", "device")
                    .put("token", token)
                    .put("device_id", deviceId)
                    .put("label", label.ifBlank { Build.MODEL })
                webSocket.send(hello.toString())
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                handle(webSocket, JSONObject(text))
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                connected = false
                listener.onMood(Mood.SLEEP)
                listener.onClosed()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                connected = false
                listener.onMood(Mood.ERROR)
                listener.onHello(false, t.message)
                listener.onClosed()
            }
        })
    }

    fun disconnect() {
        connected = false
        socket?.close(1000, "bye")
        socket = null
    }

    fun sendChat(content: String): String {
        val id = "c" + UUID.randomUUID().toString().take(8)
        pendingChat[id] = StringBuilder()
        val msg = JSONObject()
            .put("type", "request")
            .put("id", id)
            .put("action", "chat")
            .put(
                "payload",
                JSONObject().put("content", content),
            )
        socket?.send(msg.toString())
        listener.onMood(Mood.THINK)
        return id
    }

    fun ping() {
        socket?.send(JSONObject().put("type", "ping").toString())
    }

    private fun handle(ws: WebSocket, msg: JSONObject) {
        when (msg.optString("type")) {
            "hello_ok" -> {
                connected = true
                listener.onHello(true, null)
                listener.onMood(Mood.IDLE)
            }
            "error" -> {
                listener.onHello(false, msg.optString("error"))
                listener.onMood(Mood.ERROR)
            }
            "pong" -> Unit
            "event" -> handleEvent(ws, msg)
            "response" -> handleResponse(msg)
        }
    }

    private fun handleEvent(ws: WebSocket, msg: JSONObject) {
        val name = msg.optString("name")
        val payload = msg.optJSONObject("payload") ?: JSONObject()
        when (name) {
            "device.tools.invoke" -> {
                listener.onMood(Mood.ALERT)
                val id = payload.optString("id")
                val tool = payload.optString("name")
                val args = payload.optJSONObject("arguments") ?: JSONObject()
                val outcome = tools.execute(tool, args)
                val resultMsg = JSONObject()
                    .put("type", "request")
                    .put("id", "r" + UUID.randomUUID().toString().take(8))
                    .put("action", "device.tools.result")
                    .put(
                        "payload",
                        JSONObject()
                            .put("id", id)
                            .put("ok", outcome.ok)
                            .put("result", outcome.result)
                            .put("error", outcome.error),
                    )
                ws.send(resultMsg.toString())
                listener.onMood(Mood.IDLE)
            }
            "chat.progress" -> {
                listener.onMood(if (payload.optBoolean("h")) Mood.ALERT else Mood.THINK)
            }
            "chat.response_token" -> {
                val chunk = payload.optString("c")
                listener.onChatDelta(chunk)
            }
        }
    }

    private fun handleResponse(msg: JSONObject) {
        val id = msg.optString("id")
        if (!msg.optBoolean("ok", false)) {
            listener.onMood(Mood.ERROR)
            listener.onChatDone("Error: " + msg.optString("error"))
            pendingChat.remove(id)
            return
        }
        val payload = msg.optJSONObject("payload") ?: JSONObject()
        if (payload.has("connected") || payload.has("device_id")) {
            return
        }
        val content = payload.optString("content")
        if (content.isNotEmpty() || pendingChat.containsKey(id)) {
            pendingChat.remove(id)
            listener.onChatDone(content)
            listener.onBubble(content)
            listener.onMood(Mood.ALERT)
        }
    }
}

data class ToolOutcome(val ok: Boolean, val result: String = "", val error: String = "")
