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
        listOf(
            com.shibaclaw.companion.R.drawable.clip_sleep_0,
            com.shibaclaw.companion.R.drawable.clip_sleep_1,
            com.shibaclaw.companion.R.drawable.clip_sleep_2,
            com.shibaclaw.companion.R.drawable.clip_sleep_3,
            com.shibaclaw.companion.R.drawable.clip_sleep_4,
            com.shibaclaw.companion.R.drawable.clip_sleep_5,
            com.shibaclaw.companion.R.drawable.clip_sleep_6,
            com.shibaclaw.companion.R.drawable.clip_sleep_7,
            com.shibaclaw.companion.R.drawable.clip_sleep_8,
            com.shibaclaw.companion.R.drawable.clip_sleep_9,
            com.shibaclaw.companion.R.drawable.clip_sleep_10,
            com.shibaclaw.companion.R.drawable.clip_sleep_11,
        ),
        140,
        0,
        true,
    ),
    WALK(
        listOf(
            com.shibaclaw.companion.R.drawable.clip_walk_0,
            com.shibaclaw.companion.R.drawable.clip_walk_1,
            com.shibaclaw.companion.R.drawable.clip_walk_2,
            com.shibaclaw.companion.R.drawable.clip_walk_3,
            com.shibaclaw.companion.R.drawable.clip_walk_4,
            com.shibaclaw.companion.R.drawable.clip_walk_5,
            com.shibaclaw.companion.R.drawable.clip_walk_6,
            com.shibaclaw.companion.R.drawable.clip_walk_7,
            com.shibaclaw.companion.R.drawable.clip_walk_8,
            com.shibaclaw.companion.R.drawable.clip_walk_9,
            com.shibaclaw.companion.R.drawable.clip_walk_10,
            com.shibaclaw.companion.R.drawable.clip_walk_11,
            com.shibaclaw.companion.R.drawable.clip_walk_12,
            com.shibaclaw.companion.R.drawable.clip_walk_13,
            com.shibaclaw.companion.R.drawable.clip_walk_14,
            com.shibaclaw.companion.R.drawable.clip_walk_15,
        ),
        90,
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
    ),
    SWAY(
        listOf(
            com.shibaclaw.companion.R.drawable.clip_sway_0,
            com.shibaclaw.companion.R.drawable.clip_sway_1,
            com.shibaclaw.companion.R.drawable.clip_sway_2,
            com.shibaclaw.companion.R.drawable.clip_sway_3,
            com.shibaclaw.companion.R.drawable.clip_sway_4,
            com.shibaclaw.companion.R.drawable.clip_sway_5,
            com.shibaclaw.companion.R.drawable.clip_sway_6,
            com.shibaclaw.companion.R.drawable.clip_sway_7,
            com.shibaclaw.companion.R.drawable.clip_sway_8,
            com.shibaclaw.companion.R.drawable.clip_sway_9,
            com.shibaclaw.companion.R.drawable.clip_sway_10,
            com.shibaclaw.companion.R.drawable.clip_sway_11,
            com.shibaclaw.companion.R.drawable.clip_sway_12,
            com.shibaclaw.companion.R.drawable.clip_sway_13,
            com.shibaclaw.companion.R.drawable.clip_sway_14,
            com.shibaclaw.companion.R.drawable.clip_sway_15,
        ),
        42,
        0,
        false,
    ),
    BOW(
        listOf(
            com.shibaclaw.companion.R.drawable.clip_bow_0,
            com.shibaclaw.companion.R.drawable.clip_bow_1,
            com.shibaclaw.companion.R.drawable.clip_bow_2,
            com.shibaclaw.companion.R.drawable.clip_bow_3,
            com.shibaclaw.companion.R.drawable.clip_bow_4,
            com.shibaclaw.companion.R.drawable.clip_bow_5,
            com.shibaclaw.companion.R.drawable.clip_bow_6,
            com.shibaclaw.companion.R.drawable.clip_bow_7,
            com.shibaclaw.companion.R.drawable.clip_bow_8,
            com.shibaclaw.companion.R.drawable.clip_bow_9,
            com.shibaclaw.companion.R.drawable.clip_bow_10,
            com.shibaclaw.companion.R.drawable.clip_bow_11,
            com.shibaclaw.companion.R.drawable.clip_bow_12,
            com.shibaclaw.companion.R.drawable.clip_bow_13,
        ),
        46,
        0,
        false,
    ),
    HOP(
        listOf(
            com.shibaclaw.companion.R.drawable.clip_hop_0,
            com.shibaclaw.companion.R.drawable.clip_hop_1,
            com.shibaclaw.companion.R.drawable.clip_hop_2,
            com.shibaclaw.companion.R.drawable.clip_hop_3,
            com.shibaclaw.companion.R.drawable.clip_hop_4,
            com.shibaclaw.companion.R.drawable.clip_hop_5,
            com.shibaclaw.companion.R.drawable.clip_hop_6,
            com.shibaclaw.companion.R.drawable.clip_hop_7,
            com.shibaclaw.companion.R.drawable.clip_hop_8,
            com.shibaclaw.companion.R.drawable.clip_hop_9,
            com.shibaclaw.companion.R.drawable.clip_hop_10,
            com.shibaclaw.companion.R.drawable.clip_hop_11,
            com.shibaclaw.companion.R.drawable.clip_hop_12,
            com.shibaclaw.companion.R.drawable.clip_hop_13,
            com.shibaclaw.companion.R.drawable.clip_hop_14,
            com.shibaclaw.companion.R.drawable.clip_hop_15,
        ),
        40,
        0,
        false,
    ),
    BREATHE(
        listOf(
            com.shibaclaw.companion.R.drawable.clip_breathe_0,
            com.shibaclaw.companion.R.drawable.clip_breathe_1,
            com.shibaclaw.companion.R.drawable.clip_breathe_2,
            com.shibaclaw.companion.R.drawable.clip_breathe_3,
            com.shibaclaw.companion.R.drawable.clip_breathe_4,
            com.shibaclaw.companion.R.drawable.clip_breathe_5,
            com.shibaclaw.companion.R.drawable.clip_breathe_6,
            com.shibaclaw.companion.R.drawable.clip_breathe_7,
            com.shibaclaw.companion.R.drawable.clip_breathe_8,
            com.shibaclaw.companion.R.drawable.clip_breathe_9,
            com.shibaclaw.companion.R.drawable.clip_breathe_10,
            com.shibaclaw.companion.R.drawable.clip_breathe_11,
            com.shibaclaw.companion.R.drawable.clip_breathe_12,
            com.shibaclaw.companion.R.drawable.clip_breathe_13,
        ),
        48,
        0,
        false,
    );

    fun playedFrames(home: Int = IDLE.frameDrawables.first()): List<Int> {
        if (looping) return frameDrawables
        return listOf(home) + frameDrawables + listOf(home)
    }

    companion object {
        fun forMood(mood: Mood): Clip = when (mood) {
            Mood.IDLE, Mood.BOOP -> IDLE
            Mood.THINK -> THINK
            Mood.SLEEP -> SLEEP
            Mood.ALERT -> ALERT
            Mood.ERROR -> ERROR
        }

        fun tapPool(last: Clip?): List<Clip> {
            val all = listOf(BOOP, WAG, JUMP, SWAY, BOW, HOP, BREATHE)
            return all.filter { it != last }.ifEmpty { all }
        }
    }
}

internal enum class Rest { SIT, SLEEP, WALK }

internal fun restAt(hour: Int, minute: Int, awake: Boolean): Rest {
    if (awake) return Rest.SIT
    val mins = hour * 60 + minute
    if (mins >= 22 * 60 || mins < 7 * 60) return Rest.SLEEP
    if (mins in 8 * 60 until 9 * 60) return Rest.WALK
    if (mins in 13 * 60 until 14 * 60) return Rest.WALK
    if (mins in 19 * 60 until 20 * 60) return Rest.WALK
    return Rest.SIT
}

internal fun Clip.Companion.homeFor(rest: Rest): Clip = when (rest) {
    Rest.SIT -> Clip.IDLE
    Rest.SLEEP -> Clip.SLEEP
    Rest.WALK -> Clip.WALK
}

fun frameHoldMs(index: Int, count: Int, baseMs: Int): Long {
    if (count <= 2) return baseMs.toLong()
    val fromEdge = minOf(index, count - 1 - index)
    val extra = (2 - fromEdge).coerceAtLeast(0) * baseMs / 2
    return (baseMs + extra).toLong()
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
