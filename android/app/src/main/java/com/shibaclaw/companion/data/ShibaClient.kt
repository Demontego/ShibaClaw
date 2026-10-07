package com.shibaclaw.companion.data

import android.os.Build
import android.os.Handler
import android.os.Looper
import com.shibaclaw.companion.DeviceTools
import com.shibaclaw.companion.Endpoints
import java.util.UUID
import java.util.concurrent.TimeUnit
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONArray
import org.json.JSONObject

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
        fun onThinking(text: String)
        fun onTool(name: String, detail: String)
        fun onInteractive(card: ChatItem.Interactive)
        fun onQueued(position: Int)
        fun onSessionStatus(processing: Boolean)
        fun onSessionReset(sessionId: String?)
        fun onSystemEvent(text: String)
        fun onDigest(digest: Digest)
        fun onFactDelta(text: String)
        fun onFactDone(text: String)
        fun onFactError()
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

    fun connect(
        baseUrl: String,
        username: String,
        password: String,
        savedToken: String,
        deviceId: String,
        label: String,
    ) {
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
        val old = socket
        socket = null
        old?.close(1000, "bye")
    }

    fun sendChat(content: String, attachments: List<AttachmentRef> = emptyList()): String {
        val id = "c" + UUID.randomUUID().toString().take(8)
        val msg = JSONObject()
            .put("type", "message")
            .put("id", id)
            .put("content", content)
        if (attachments.isNotEmpty()) {
            val arr = JSONArray()
            attachments.forEach { a ->
                arr.put(
                    JSONObject()
                        .put("name", a.name)
                        .put("url", a.url)
                        .put("type", a.type),
                )
            }
            msg.put("attachments", arr)
        }
        socket?.send(msg.toString())
        listener.onMood(Mood.THINK)
        return id
    }

    fun stop() {
        socket?.send(JSONObject().put("type", "stop").toString())
    }

    fun newSession(profileId: String = "default") {
        socket?.send(
            JSONObject()
                .put("type", "new_session")
                .put("profile_id", profileId)
                .toString(),
        )
    }

    fun switchSession(sessionId: String) {
        socket?.send(
            JSONObject()
                .put("type", "switch_session")
                .put("session_id", sessionId)
                .toString(),
        )
    }

    fun interactiveReply(requestId: String, response: JSONObject) {
        socket?.send(
            JSONObject()
                .put("type", "interactive_reply")
                .put("request_id", requestId)
                .put("response", response)
                .toString(),
        )
    }

    fun requestDigest() {
        socket?.send(JSONObject().put("type", "digest_request").toString())
    }

    fun sendFact(lang: String) {
        socket?.send(
            JSONObject()
                .put("type", "fact_request")
                .put("lang", lang)
                .toString(),
        )
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
                if (webSocket !== socket) return
                connected = false
                socket = null
                main.post {
                    listener.onMood(Mood.SLEEP)
                    listener.onClosed()
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                if (webSocket !== socket) return
                connected = false
                socket = null
                main.post {
                    listener.onHello(false, t.message)
                    listener.onMood(Mood.ERROR)
                    listener.onClosed()
                }
            }
        })
    }

    private fun handle(ws: WebSocket, msg: JSONObject, token: String) {
        when (msg.optString("type")) {
            "connected" -> {
                connected = true
                main.post {
                    listener.onToken(token)
                    listener.onHello(true, null)
                    listener.onMood(Mood.IDLE)
                }
            }
            "device_ready" -> main.post { listener.onMood(Mood.IDLE) }
            "error" -> main.post {
                listener.onHello(false, msg.optString("message"))
                listener.onMood(Mood.ERROR)
            }
            "pong" -> Unit
            "thinking", "agent_thinking" -> main.post {
                listener.onMood(Mood.THINK)
                listener.onThinking(msg.optString("content").ifBlank { "Thinking…" })
                listener.onSessionStatus(true)
            }
            "tool", "agent_tool" -> main.post {
                val content = msg.optString("content").ifBlank { msg.optString("detail") }
                val name = msg.optString("name").ifBlank {
                    content.lineSequence().firstOrNull()?.take(48)?.ifBlank { null } ?: "tool"
                }
                listener.onMood(Mood.ALERT)
                listener.onTool(name, content)
                listener.onSessionStatus(true)
            }
            "interactive", "agent_interactive" -> main.post {
                val payload = msg.optJSONObject("payload") ?: msg
                val kind = payload.optString("kind").ifBlank { "ask" }
                val options = buildList {
                    val arr = payload.optJSONArray("options") ?: return@buildList
                    for (i in 0 until arr.length()) {
                        val o = arr.optJSONObject(i) ?: continue
                        val id = o.optString("id").ifBlank { o.optString("label") }
                        if (id.isBlank()) continue
                        add(ChatItem.AskOption(id, o.optString("label").ifBlank { id }))
                    }
                }
                val prompt = when (kind) {
                    "credential" -> payload.optString("title").ifBlank { "Credential" }
                    "progress_card" -> payload.optString("title").ifBlank { payload.optString("detail") }
                    else -> payload.optString("prompt").ifBlank { payload.optString("content") }
                }
                listener.onInteractive(
                    ChatItem.Interactive(
                        id = "i" + payload.optString("request_id").ifBlank { msg.optString("id") },
                        requestId = payload.optString("request_id").ifBlank { msg.optString("id") },
                        prompt = prompt,
                        kind = kind,
                        options = options,
                        hint = payload.optString("hint"),
                        allowFree = payload.optBoolean("allow_free_text", true),
                        allowSkip = payload.optBoolean("allow_skip", true),
                    ),
                )
            }
            "response_chunk", "agent_response_chunk" -> main.post {
                listener.onChatDelta(msg.optString("content"))
                listener.onSessionStatus(true)
            }
            "response", "agent_response" -> {
                val content = msg.optString("content")
                main.post {
                    listener.onChatDone(content)
                    listener.onBubble(content)
                    listener.onMood(Mood.ALERT)
                    listener.onSessionStatus(false)
                }
            }
            "message_ack" -> Unit
            "message_queued" -> main.post {
                listener.onQueued(msg.optInt("position", 1))
            }
            "session_status" -> main.post {
                listener.onSessionStatus(msg.optBoolean("processing", false))
            }
            "session_reset" -> main.post {
                val key = msg.optString("session_key").ifBlank { msg.optString("session_id") }
                listener.onSessionReset(key.takeIf { it.isNotBlank() })
            }
            "subagent_status" -> main.post {
                val label = msg.optString("name").ifBlank { "subagent" }
                val st = msg.optString("status")
                listener.onSystemEvent("$label: $st")
            }
            "system_event" -> main.post {
                listener.onSystemEvent(msg.optString("content").ifBlank { msg.optString("message") })
            }
            "fact_chunk" -> main.post { listener.onFactDelta(msg.optString("content")) }
            "fact" -> main.post { listener.onFactDone(msg.optString("content")) }
            "fact_error" -> main.post { listener.onFactError() }
            "digest" -> main.post {
                val news = mutableListOf<String>()
                val arr = msg.optJSONArray("news")
                if (arr != null) {
                    for (i in 0 until arr.length()) news.add(arr.optString(i))
                }
                listener.onDigest(
                    Digest(
                        mood = msg.optString("mood", "IDLE"),
                        moodLine = msg.optString("mood_line", ""),
                        fact = msg.optString("fact", ""),
                        news = news,
                    ),
                )
            }
            "new_session" -> main.post {
                val key = msg.optString("session_key").ifBlank { msg.optString("session_id") }
                if (key.isNotBlank()) listener.onSessionReset(key)
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
