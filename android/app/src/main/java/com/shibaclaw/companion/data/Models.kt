package com.shibaclaw.companion.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

enum class Mood {
    IDLE, THINK, SLEEP, ALERT, ERROR, BOOP;

    fun drawable(): Int = when (this) {
        IDLE -> com.shibaclaw.companion.R.drawable.shiba_idle
        THINK -> com.shibaclaw.companion.R.drawable.shiba_think
        SLEEP -> com.shibaclaw.companion.R.drawable.shiba_sleep
        ALERT -> com.shibaclaw.companion.R.drawable.shiba_alert
        ERROR -> com.shibaclaw.companion.R.drawable.shiba_error
        BOOP -> com.shibaclaw.companion.R.drawable.shiba_boop
    }

    companion object {
        fun from(raw: String?): Mood =
            entries.firstOrNull { it.name.equals(raw, ignoreCase = true) } ?: SLEEP
    }
}

enum class Clip(
    val frameDrawables: List<Int>,
    val intervalMs: Int,
    val restMs: Long,
    val looping: Boolean = true,
) {
    IDLE(
        listOf(
            com.shibaclaw.companion.R.drawable.clip_idle_0,
            com.shibaclaw.companion.R.drawable.clip_idle_1,
            com.shibaclaw.companion.R.drawable.clip_idle_2,
            com.shibaclaw.companion.R.drawable.clip_idle_3,
        ),
        60,
        2400,
        true,
    ),
    BOOP(
        listOf(
            com.shibaclaw.companion.R.drawable.clip_boop_0,
            com.shibaclaw.companion.R.drawable.clip_boop_1,
            com.shibaclaw.companion.R.drawable.clip_boop_2,
            com.shibaclaw.companion.R.drawable.clip_boop_3,
            com.shibaclaw.companion.R.drawable.clip_boop_4,
            com.shibaclaw.companion.R.drawable.clip_boop_5,
            com.shibaclaw.companion.R.drawable.clip_boop_6,
            com.shibaclaw.companion.R.drawable.clip_boop_7,
        ),
        70,
        0,
        false,
    ),
    WAG(
        listOf(
            com.shibaclaw.companion.R.drawable.clip_wag_0,
            com.shibaclaw.companion.R.drawable.clip_wag_1,
            com.shibaclaw.companion.R.drawable.clip_wag_2,
            com.shibaclaw.companion.R.drawable.clip_wag_3,
            com.shibaclaw.companion.R.drawable.clip_wag_4,
            com.shibaclaw.companion.R.drawable.clip_wag_5,
            com.shibaclaw.companion.R.drawable.clip_wag_6,
            com.shibaclaw.companion.R.drawable.clip_wag_7,
            com.shibaclaw.companion.R.drawable.clip_wag_8,
            com.shibaclaw.companion.R.drawable.clip_wag_9,
        ),
        72,
        0,
        false,
    ),
    JUMP(
        listOf(
            com.shibaclaw.companion.R.drawable.clip_jump_0,
            com.shibaclaw.companion.R.drawable.clip_jump_1,
            com.shibaclaw.companion.R.drawable.clip_jump_2,
            com.shibaclaw.companion.R.drawable.clip_jump_3,
            com.shibaclaw.companion.R.drawable.clip_jump_4,
            com.shibaclaw.companion.R.drawable.clip_jump_5,
            com.shibaclaw.companion.R.drawable.clip_jump_6,
            com.shibaclaw.companion.R.drawable.clip_jump_7,
            com.shibaclaw.companion.R.drawable.clip_jump_8,
            com.shibaclaw.companion.R.drawable.clip_jump_9,
        ),
        64,
        0,
        false,
    ),
    THINK(
        listOf(com.shibaclaw.companion.R.drawable.clip_think_0),
        1000,
        0,
        true,
    ),
    SLEEP(
        listOf(com.shibaclaw.companion.R.drawable.clip_sleep_0),
        1000,
        0,
        true,
    ),
    ALERT(
        listOf(com.shibaclaw.companion.R.drawable.clip_alert_0),
        1000,
        0,
        true,
    ),
    ERROR(
        listOf(com.shibaclaw.companion.R.drawable.clip_error_0),
        1000,
        0,
        true,
    );

    companion object {
        fun forMood(mood: Mood): Clip = when (mood) {
            Mood.IDLE, Mood.BOOP -> IDLE
            Mood.THINK -> THINK
            Mood.SLEEP -> SLEEP
            Mood.ALERT -> ALERT
            Mood.ERROR -> ERROR
        }

        fun randomTap(): Clip = listOf(BOOP, WAG, JUMP).random()
    }
}

enum class ThemeMode { SYSTEM, DARK, LIGHT }

sealed class ChatItem {
    abstract val id: String

    data class Message(
        override val id: String,
        val fromUser: Boolean,
        val text: String,
        val attachments: List<AttachmentRef> = emptyList(),
        val streaming: Boolean = false,
        val time: String = "",
    ) : ChatItem()

    data class Thinking(
        override val id: String,
        val text: String,
        val collapsed: Boolean = true,
    ) : ChatItem()

    data class Tool(
        override val id: String,
        val name: String,
        val detail: String = "",
        val collapsed: Boolean = true,
    ) : ChatItem()

    data class AskOption(val id: String, val label: String)

    data class Interactive(
        override val id: String,
        val requestId: String,
        val prompt: String,
        val kind: String = "ask",
        val options: List<AskOption> = emptyList(),
        val hint: String = "",
        val allowFree: Boolean = true,
        val allowSkip: Boolean = true,
        val answered: Boolean = false,
    ) : ChatItem()

    data class System(
        override val id: String,
        val text: String,
    ) : ChatItem()
}

data class AttachmentRef(
    val name: String,
    val url: String,
    val type: String,
)

data class SessionSummary(
    val key: String,
    val nickname: String?,
    val updatedAt: Long = 0L,
    val preview: String = "",
    val profileId: String = "default",
    val model: String = "",
)

data class Digest(
    val mood: String = "IDLE",
    val moodLine: String = "",
    val fact: String = "",
    val news: List<String> = emptyList(),
)

@Serializable
data class SessionsListResponse(
    val sessions: List<SessionEntry> = emptyList(),
)

@Serializable
data class SessionEntry(
    val key: String = "",
    val session_key: String = "",
    val nickname: String? = null,
    val preview: String? = null,
    val last_message: String? = null,
) {
    fun id(): String = key.ifBlank { session_key }
    fun line(): String = preview ?: last_message ?: ""
}

@Serializable
data class SessionDetail(
    val messages: List<SessionMessage> = emptyList(),
    val nickname: String? = null,
    val profile_id: String = "default",
    val model: String = "",
)

@Serializable
data class SessionMessage(
    val role: String = "",
    val content: JsonElement? = null,
    val metadata: SessionMessageMeta? = null,
    val timestamp: String = "",
)

@Serializable
data class SessionMessageMeta(
    val attachments: List<ApiAttachment>? = null,
)

@Serializable
data class ApiAttachment(
    val name: String = "",
    val url: String = "",
    val type: String = "",
)

@Serializable
data class ModelsResponse(
    val models: List<ModelEntry> = emptyList(),
)

@Serializable
data class ModelEntry(
    val id: String = "",
    val name: String = "",
    val provider: String = "",
)

@Serializable
data class ProfilesResponse(
    val profiles: List<ProfileEntry> = emptyList(),
)

@Serializable
data class ProfileEntry(
    val id: String = "",
    val name: String = "",
    val label: String = "",
    val description: String = "",
) {
    fun title(): String = label.ifBlank { name }.ifBlank { id }
}

data class AutoJob(
    val id: String,
    val name: String,
    val enabled: Boolean,
    val schedule: String,
    val message: String,
    val lastStatus: String,
    val profileId: String,
)

@Serializable
data class UploadResponse(
    val url: String = "",
    val path: String = "",
    val name: String = "",
    val type: String = "",
)

@Serializable
data class NotificationsResponse(
    val notifications: List<AgentNotification> = emptyList(),
)

@Serializable
data class AgentNotification(
    val id: String = "",
    val title: String = "",
    val body: String = "",
    val message: String = "",
    val created_at: Double? = null,
    val session_key: String? = null,
)

@Serializable
data class DigestPayload(
    val mood: String = "IDLE",
    @SerialName("mood_line") val moodLine: String = "",
    val fact: String = "",
    val news: List<String> = emptyList(),
)
