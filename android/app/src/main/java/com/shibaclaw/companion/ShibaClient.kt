package com.shibaclaw.companion

import android.os.Build
import android.os.Handler
import android.os.Looper
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.TimeUnit

class ShibaClient(
    private val tools: DeviceTools,
    private val listener: Listener,
) {
    interface Listener {
        fun onHello(ok: Boolean, error: String?)
        fun onToken(token: String)
        fun onMood(mood: Mood)
        fun onBubble(text: String)
        fun onChatDelta(text: String)
        fun onChatDone(text: String)
        fun onClosed()
    }

    private val http = OkHttpClient.Builder()
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(25, TimeUnit.SECONDS)
        .build()

    private val jsonType = "application/json; charset=utf-8".toMediaType()
    private val main = Handler(Looper.getMainLooper())

    private var socket: WebSocket? = null
    @Volatile var connected: Boolean = false
        private set

    fun connect(baseUrl: String, username: String, password: String, savedToken: String, deviceId: String, label: String) {
        disconnect()
        Thread {
            try {
                val root = Endpoints.baseUrl(baseUrl)
                val token = login(root, username, password, savedToken)
                openSocket(root, token, deviceId, label)
            } catch (e: Exception) {
                main.post {
                    listener.onHello(false, e.message)
                    listener.onMood(Mood.ERROR)
                }
            }
        }.start()
    }

    fun disconnect() {
        connected = false
        socket?.close(1000, "bye")
        socket = null
    }

    fun sendChat(content: String): String {
        val id = "c" + UUID.randomUUID().toString().take(8)
        val msg = JSONObject()
            .put("type", "message")
            .put("id", id)
            .put("content", content)
        socket?.send(msg.toString())
        listener.onMood(Mood.THINK)
        return id
    }

    private fun login(root: String, username: String, password: String, savedToken: String): String {
        val statusReq = Request.Builder().url("$root/api/auth/status").get().build()
        http.newCall(statusReq).execute().use { resp ->
            val body = resp.body?.string().orEmpty()
            val status = if (body.isBlank()) JSONObject() else JSONObject(body)
            if (!status.optBoolean("auth_required", true)) {
                return savedToken
            }
        }
        if (savedToken.isNotBlank() && verify(root, savedToken)) {
            return savedToken
        }
        if (username.isBlank() || password.isBlank()) {
            throw IllegalStateException("Need username and password")
        }
        val payload = JSONObject()
            .put("username", username)
            .put("password", password)
            .toString()
            .toRequestBody(jsonType)
        val req = Request.Builder()
            .url("$root/api/auth/login")
            .post(payload)
            .build()
        http.newCall(req).execute().use { resp ->
            val body = resp.body?.string().orEmpty()
            val json = if (body.isBlank()) JSONObject() else JSONObject(body)
            if (!resp.isSuccessful) {
                throw IllegalStateException(json.optString("error", "login failed ${resp.code}"))
            }
            val token = json.optString("session_token")
            if (token.isBlank()) throw IllegalStateException("login returned no token")
            return token
        }
    }

    private fun verify(root: String, token: String): Boolean {
        val payload = JSONObject().put("token", token).toString().toRequestBody(jsonType)
        val req = Request.Builder().url("$root/api/auth/verify").post(payload).build()
        return http.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) return@use false
            val json = JSONObject(resp.body?.string().orEmpty().ifBlank { "{}" })
            json.optBoolean("valid", false)
        }
    }

    private fun openSocket(root: String, token: String, deviceId: String, label: String) {
        val wsUrl = Endpoints.wsUrl(root)
        val req = Request.Builder().url(wsUrl).build()
        socket = http.newWebSocket(req, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                val auth = JSONObject()
                    .put("type", "auth")
                    .put("token", token)
                    .put("role", "device")
                    .put("device_id", deviceId)
                    .put("label", label.ifBlank { Build.MODEL })
                webSocket.send(auth.toString())
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                handle(webSocket, JSONObject(text), token)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                connected = false
                main.post {
                    listener.onMood(Mood.SLEEP)
                    listener.onClosed()
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                connected = false
                main.post {
                    listener.onHello(false, t.message)
                    listener.onMood(Mood.ERROR)
                    listener.onClosed()
                }
            }
        })
    }

    private fun handle(ws: WebSocket, msg: JSONObject, token: String) {
        when (val type = msg.optString("type")) {
            "connected" -> {
                connected = true
                main.post {
                    listener.onHello(true, null)
                    listener.onToken(token)
                    listener.onMood(Mood.IDLE)
                }
            }
            "device_ready" -> main.post { listener.onMood(Mood.IDLE) }
            "error" -> main.post {
                listener.onHello(false, msg.optString("message"))
                listener.onMood(Mood.ERROR)
            }
            "pong" -> Unit
            "thinking" -> main.post { listener.onMood(Mood.THINK) }
            "tool" -> main.post { listener.onMood(Mood.ALERT) }
            "response_chunk" -> main.post { listener.onChatDelta(msg.optString("content")) }
            "response" -> {
                val content = msg.optString("content")
                main.post {
                    listener.onChatDone(content)
                    listener.onBubble(content)
                    listener.onMood(Mood.ALERT)
                }
            }
            "device_invoke" -> {
                main.post { listener.onMood(Mood.ALERT) }
                val outcome = tools.execute(
                    msg.optString("name"),
                    msg.optJSONObject("arguments") ?: JSONObject(),
                )
                val result = JSONObject()
                    .put("type", "device_result")
                    .put("id", msg.optString("id"))
                    .put("ok", outcome.ok)
                    .put("result", outcome.result)
                    .put("error", outcome.error)
                ws.send(result.toString())
                main.post { listener.onMood(Mood.IDLE) }
            }
            else -> Unit
        }
    }
}

