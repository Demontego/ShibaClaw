package com.shibaclaw.companion.data

import android.content.Context
import com.shibaclaw.companion.Prefs
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

object ShibaRepo {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private lateinit var app: Context

    private val _connected = MutableStateFlow(false)
    val connected: StateFlow<Boolean> = _connected.asStateFlow()

    private val _status = MutableStateFlow("Sleeping — not connected")
    val status: StateFlow<String> = _status.asStateFlow()

    private val _mood = MutableStateFlow(Mood.SLEEP)
    val mood: StateFlow<Mood> = _mood.asStateFlow()

    private val _sessionId = MutableStateFlow<String?>(null)
    val sessionId: StateFlow<String?> = _sessionId.asStateFlow()

    private val _messages = MutableStateFlow<List<ChatItem>>(emptyList())
    val messages: StateFlow<List<ChatItem>> = _messages.asStateFlow()

    private val _processing = MutableStateFlow(false)
    val processing: StateFlow<Boolean> = _processing.asStateFlow()

    private val _queued = MutableStateFlow(0)
    val queued: StateFlow<Int> = _queued.asStateFlow()

    private val _sessions = MutableStateFlow<List<SessionSummary>>(emptyList())
    val sessions: StateFlow<List<SessionSummary>> = _sessions.asStateFlow()

    private val _models = MutableStateFlow<List<ModelEntry>>(emptyList())
    val models: StateFlow<List<ModelEntry>> = _models.asStateFlow()

    private val _profiles = MutableStateFlow<List<ProfileEntry>>(emptyList())
    val profiles: StateFlow<List<ProfileEntry>> = _profiles.asStateFlow()

    private val _sessionModel = MutableStateFlow("")
    val sessionModel: StateFlow<String> = _sessionModel.asStateFlow()

    private val _sessionProfile = MutableStateFlow("default")
    val sessionProfile: StateFlow<String> = _sessionProfile.asStateFlow()

    private val _sessionNick = MutableStateFlow("")
    val sessionNick: StateFlow<String> = _sessionNick.asStateFlow()

    private val _jobs = MutableStateFlow<List<AutoJob>>(emptyList())
    val jobs: StateFlow<List<AutoJob>> = _jobs.asStateFlow()

    private val _jobsError = MutableStateFlow("")
    val jobsError: StateFlow<String> = _jobsError.asStateFlow()

    private val _notifications = MutableStateFlow<List<AgentNotification>>(emptyList())
    val notifications: StateFlow<List<AgentNotification>> = _notifications.asStateFlow()

    private val _bubble = MutableStateFlow("")
    val bubble: StateFlow<String> = _bubble.asStateFlow()

    private val _digest = MutableStateFlow(Digest())
    val digest: StateFlow<Digest> = _digest.asStateFlow()

    private val _theme = MutableStateFlow(ThemeMode.SYSTEM)
    val theme: StateFlow<ThemeMode> = _theme.asStateFlow()

    private val _events = MutableSharedFlow<String>(extraBufferCapacity = 32)
    val events: SharedFlow<String> = _events.asSharedFlow()

    private val phoneNotifCounts = ConcurrentHashMap<String, Int>()
    private var streamId: String? = null

    @Volatile var client: ShibaClient? = null

    fun init(ctx: Context) {
        app = ctx.applicationContext
        _mood.value = Mood.from(Prefs.mood(app))
        _bubble.value = Prefs.lastBubble(app)
        _digest.value = Prefs.digest(app)
        _theme.value = Prefs.themeMode(app)
        _sessionId.value = "android:${Prefs.deviceId(app)}"
    }

    fun setStatus(text: String) {
        _status.value = text
    }

    fun setConnected(ok: Boolean) {
        _connected.value = ok
    }

    fun setMood(mood: Mood) {
        _mood.value = mood
        if (::app.isInitialized) Prefs.setMood(app, mood)
    }

    fun setBubble(text: String) {
        val line = text.trim().replace("\n", " ").take(160)
        _bubble.value = line
        if (::app.isInitialized) Prefs.setBubble(app, line)
    }

    fun setDigest(d: Digest) {
        _digest.value = d
        if (::app.isInitialized) Prefs.setDigest(app, d)
        if (d.moodLine.isNotBlank()) setBubble(d.moodLine)
    }

    fun setTheme(mode: ThemeMode) {
        _theme.value = mode
        if (::app.isInitialized) Prefs.setThemeMode(app, mode)
    }

    fun setProcessing(on: Boolean) {
        _processing.value = on
        if (!on) _queued.value = 0
    }

    fun setPhoneNotifCounts(counts: Map<String, Int>) {
        phoneNotifCounts.clear()
        phoneNotifCounts.putAll(counts)
    }

    fun phoneNotifLine(): String? {
        if (phoneNotifCounts.isEmpty()) return null
        val parts = phoneNotifCounts.entries
            .sortedByDescending { it.value }
            .take(3)
            .map { "${it.value} in ${it.key}" }
        return parts.joinToString(", ").let { "$it unread" }
    }

    fun pickLine(): String {
        val d = _digest.value
        val options = buildList {
            phoneNotifLine()?.let { add(it) }
            d.news.filter { it.isNotBlank() }.forEach { add(it) }
            if (d.fact.isNotBlank()) add(d.fact)
            if (d.moodLine.isNotBlank()) add(d.moodLine)
        }
        if (options.isEmpty()) {
            return when (_mood.value) {
                Mood.SLEEP -> "Zzz… wake me with a pair."
                Mood.ERROR -> "Something broke. Check the server."
                Mood.THINK -> "Thinking…"
                Mood.ALERT -> "Heads up!"
                Mood.BOOP -> "Boop!"
                Mood.IDLE -> "Woof. Tap me again."
            }
        }
        val idx = if (::app.isInitialized) Prefs.pickIndex(app) else 0
        val next = (idx + 1) % options.size
        if (::app.isInitialized) Prefs.setPickIndex(app, next)
        return options[idx % options.size]
    }

    fun appendUser(text: String, attachments: List<AttachmentRef> = emptyList()) {
        val id = "u" + UUID.randomUUID().toString().take(8)
        _messages.update { it + ChatItem.Message(id, true, text, attachments) }
    }

    fun onChatDelta(text: String) {
        val id = streamId ?: ("s" + UUID.randomUUID().toString().take(8)).also { streamId = it }
        _messages.update { list ->
            val existing = list.indexOfLast { it is ChatItem.Message && it.id == id }
            if (existing >= 0) {
                val msg = list[existing] as ChatItem.Message
                list.toMutableList().also {
                    it[existing] = msg.copy(text = msg.text + text, streaming = true)
                }
            } else {
                list + ChatItem.Message(id, false, text, streaming = true)
            }
        }
        setProcessing(true)
    }

    fun onChatDone(text: String) {
        val id = streamId
        streamId = null
        _messages.update { list ->
            if (id != null) {
                val idx = list.indexOfLast { it is ChatItem.Message && it.id == id }
                if (idx >= 0) {
                    val msg = list[idx] as ChatItem.Message
                    list.toMutableList().also {
                        it[idx] = msg.copy(text = text.ifBlank { msg.text }, streaming = false)
                    }
                } else if (text.isNotBlank()) {
                    list + ChatItem.Message("d" + UUID.randomUUID().toString().take(8), false, text)
                } else {
                    list
                }
            } else if (text.isNotBlank()) {
                list + ChatItem.Message("d" + UUID.randomUUID().toString().take(8), false, text)
            } else {
                list
            }
        }
        setProcessing(false)
        if (text.isNotBlank()) setBubble(text)
    }

    fun onThinking(text: String) {
        val id = "t" + UUID.randomUUID().toString().take(8)
        _messages.update { it + ChatItem.Thinking(id, text) }
        setMood(Mood.THINK)
        setProcessing(true)
    }

    fun onTool(name: String, detail: String = "") {
        val id = "tool" + UUID.randomUUID().toString().take(8)
        _messages.update { it + ChatItem.Tool(id, name, detail) }
        setMood(Mood.ALERT)
        setProcessing(true)
    }

    fun onInteractive(card: ChatItem.Interactive) {
        if (card.kind == "progress_card") {
            onSystem(listOf(card.prompt, card.hint).filter { it.isNotBlank() }.joinToString(" — "))
            return
        }
        _messages.update {
            it.filterNot { item -> item is ChatItem.Interactive && item.requestId == card.requestId } + card
        }
    }

    fun markInteractiveAnswered(requestId: String) {
        _messages.update { list ->
            list.map {
                if (it is ChatItem.Interactive && it.requestId == requestId) {
                    it.copy(answered = true)
                } else {
                    it
                }
            }
        }
    }

    fun onQueued(position: Int) {
        _queued.value = position
    }

    fun onSystem(text: String) {
        _messages.update {
            it + ChatItem.System("sys" + UUID.randomUUID().toString().take(8), text)
        }
    }

    fun toggleCollapse(id: String) {
        _messages.update { list ->
            list.map {
                when {
                    it is ChatItem.Thinking && it.id == id -> it.copy(collapsed = !it.collapsed)
                    it is ChatItem.Tool && it.id == id -> it.copy(collapsed = !it.collapsed)
                    else -> it
                }
            }
        }
    }

    fun clearMessages() {
        _messages.value = emptyList()
        streamId = null
    }

    fun ensureHistory() = scope.launch(Dispatchers.IO) {
        if (_messages.value.isNotEmpty()) return@launch
        val id = _sessionId.value ?: return@launch
        val detail = runCatching { ShibaApi.getSession(id) }.getOrNull() ?: return@launch
        if (_messages.value.isNotEmpty() || _sessionId.value != id) return@launch
        loadSessionHistory(detail)
    }

    fun loadSessionHistory(detail: SessionDetail) {
        _sessionModel.value = detail.model
        _sessionProfile.value = detail.profile_id
        _sessionNick.value = detail.nickname.orEmpty()
        val items = detail.messages.mapNotNull { m ->
            val role = m.role.lowercase()
            val text = contentToText(m.content)
            if (text.isBlank() && m.metadata?.attachments.isNullOrEmpty()) return@mapNotNull null
            val fromUser = role == "user" || role == "human"
            if (role == "system" || role == "tool") return@mapNotNull null
            ChatItem.Message(
                id = "h" + UUID.randomUUID().toString().take(8),
                fromUser = fromUser,
                text = text,
                attachments = m.metadata?.attachments?.map {
                    AttachmentRef(it.name, it.url, it.type)
                } ?: emptyList(),
                time = shortStamp(m.timestamp),
            )
        }
        _messages.value = items
    }

    private fun shortStamp(raw: String): String {
        if (raw.isBlank()) return ""
        val fmt = java.time.format.DateTimeFormatter.ofPattern("HH:mm")
        return runCatching { java.time.OffsetDateTime.parse(raw).format(fmt) }
            .recoverCatching { java.time.LocalDateTime.parse(raw).format(fmt) }
            .getOrDefault("")
    }

    private fun contentToText(content: JsonElement?): String {
        if (content == null) return ""
        return when (content) {
            is JsonPrimitive -> content.contentOrNull ?: content.toString()
            is JsonArray -> content.joinToString("\n") { el ->
                when (el) {
                    is JsonObject -> {
                        val t = el["text"]?.jsonPrimitive?.contentOrNull
                        t ?: el["content"]?.jsonPrimitive?.contentOrNull ?: ""
                    }
                    is JsonPrimitive -> el.contentOrNull ?: ""
                    else -> ""
                }
            }
            is JsonObject -> content["text"]?.jsonPrimitive?.contentOrNull
                ?: content["content"]?.jsonPrimitive?.contentOrNull
                ?: content.toString()
            else -> content.toString()
        }.trim()
    }

    fun refreshSessions() = scope.launch(Dispatchers.IO) {
        runCatching { ShibaApi.listSessions() }
            .onSuccess { _sessions.value = it }
            .onFailure { _events.emit(it.message ?: "sessions failed") }
    }

    fun searchSessions(q: String) = scope.launch(Dispatchers.IO) {
        runCatching { ShibaApi.searchSessions(q) }
            .onSuccess { _sessions.value = it }
    }

    fun refreshModelsAndProfiles() = scope.launch(Dispatchers.IO) {
        runCatching { ShibaApi.listModels() }.onSuccess { _models.value = it }
        runCatching { ShibaApi.listProfiles() }.onSuccess { _profiles.value = it }
    }

    fun refreshNotifications() = scope.launch(Dispatchers.IO) {
        runCatching { ShibaApi.listNotifications() }
            .onSuccess { _notifications.value = it }
    }

    fun switchSession(id: String, after: (() -> Unit)? = null) = scope.launch(Dispatchers.IO) {
        _sessionId.value = id
        client?.switchSession(id)
        runCatching { ShibaApi.getSession(id) }
            .onSuccess {
                loadSessionHistory(it)
                after?.let { cb -> scope.launch { cb() } }
            }
            .onFailure {
                clearMessages()
                _events.emit(it.message ?: "load failed")
            }
        refreshSessions()
    }

    fun newSession(profileId: String = "default") {
        client?.newSession(profileId)
        clearMessages()
        _sessionProfile.value = profileId
        _sessionNick.value = ""
        refreshSessions()
    }

    fun patchSession(fields: Map<String, Any?>, sessionId: String? = null) = scope.launch(Dispatchers.IO) {
        val id = sessionId ?: _sessionId.value ?: return@launch
        runCatching { ShibaApi.patchSession(id, fields) }
            .onSuccess {
                if (id == _sessionId.value) {
                    fields["model"]?.let { _sessionModel.value = it.toString() }
                    fields["profile_id"]?.let { _sessionProfile.value = it.toString() }
                    fields["nickname"]?.let { _sessionNick.value = it.toString() }
                }
                refreshSessions()
            }
            .onFailure { _events.emit(it.message ?: "patch failed") }
    }

    fun deleteSession(id: String) = scope.launch(Dispatchers.IO) {
        runCatching { ShibaApi.deleteSession(id) }
            .onSuccess {
                if (_sessionId.value == id) newSession()
                refreshSessions()
            }
    }

    fun archiveSession(id: String) = scope.launch(Dispatchers.IO) {
        runCatching { ShibaApi.archiveSession(id) }
            .onSuccess { refreshSessions() }
    }

    fun refreshJobs() = scope.launch(Dispatchers.IO) {
        runCatching { ShibaApi.listJobs() }
            .onSuccess {
                _jobs.value = it
                _jobsError.value = ""
            }
            .onFailure { _jobsError.value = it.message ?: "jobs failed" }
    }

    fun createJob(
        name: String,
        message: String,
        kind: String,
        everyMin: Int,
        cron: String,
        atMs: Long,
    ) = scope.launch(Dispatchers.IO) {
        runCatching {
            ShibaApi.createJob(
                name,
                message,
                kind,
                everyMin,
                cron,
                atMs,
                _sessionProfile.value,
                _sessionId.value.orEmpty(),
            )
        }.onSuccess { refreshJobs() }
            .onFailure { _jobsError.value = it.message ?: "create failed" }
    }

    fun setJobEnabled(id: String, enabled: Boolean) = scope.launch(Dispatchers.IO) {
        runCatching { ShibaApi.setJobEnabled(id, enabled) }
            .onSuccess { refreshJobs() }
            .onFailure { _jobsError.value = it.message ?: "update failed" }
    }

    fun triggerJob(id: String) = scope.launch(Dispatchers.IO) {
        runCatching { ShibaApi.triggerJob(id) }
            .onSuccess { refreshJobs() }
            .onFailure { _jobsError.value = it.message ?: "trigger failed" }
    }

    fun deleteJob(id: String) = scope.launch(Dispatchers.IO) {
        runCatching { ShibaApi.deleteJob(id) }
            .onSuccess { refreshJobs() }
            .onFailure { _jobsError.value = it.message ?: "delete failed" }
    }

    fun clearNotifications() = scope.launch(Dispatchers.IO) {
        runCatching { ShibaApi.clearNotifications() }
            .onSuccess { _notifications.value = emptyList() }
    }

    fun setSessionIdFromServer(id: String) {
        _sessionId.value = id
    }
}
