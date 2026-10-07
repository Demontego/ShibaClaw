package com.shibaclaw.companion.data

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive
import java.time.format.DateTimeFormatter

internal data class ChatTranscript(
    val items: List<ChatItem> = emptyList(),
    val streamId: String? = null,
) {
    fun addUser(text: String, attachments: List<AttachmentRef> = emptyList(), id: String): ChatTranscript =
        copy(items = items + ChatItem.Message(id, true, text, attachments))

    fun delta(text: String, id: String): ChatTranscript {
        val stream = streamId ?: id
        val existing = items.indexOfLast { it is ChatItem.Message && it.id == stream }
        val next = if (existing >= 0) {
            val msg = items[existing] as ChatItem.Message
            items.toMutableList().also { it[existing] = msg.copy(text = msg.text + text, streaming = true) }
        } else {
            items + ChatItem.Message(stream, false, text, streaming = true)
        }
        return copy(items = next, streamId = stream)
    }

    fun done(text: String, id: String): ChatTranscript {
        val next = when {
            streamId == null && text.isBlank() -> items
            streamId == null && sameAssistant(items, text) -> items
            streamId == null -> items + ChatItem.Message(id, false, text)
            else -> {
                val idx = items.indexOfLast { it is ChatItem.Message && it.id == streamId }
                when {
                    idx >= 0 -> {
                        val msg = items[idx] as ChatItem.Message
                        items.toMutableList().also {
                            it[idx] = msg.copy(text = text.ifBlank { msg.text }, streaming = false)
                        }
                    }
                    text.isNotBlank() -> items + ChatItem.Message(id, false, text)
                    else -> items
                }
            }
        }
        return copy(items = next, streamId = null)
    }

    fun thinking(text: String, id: String): ChatTranscript =
        copy(items = items + ChatItem.Thinking(id, text))

    fun tool(name: String, detail: String, id: String): ChatTranscript =
        copy(items = items + ChatItem.Tool(id, name, detail))

    fun interactive(card: ChatItem.Interactive, systemId: String): ChatTranscript {
        if (card.kind == "progress_card") {
            val line = listOf(card.prompt, card.hint).filter { it.isNotBlank() }.joinToString(" — ")
            return copy(items = items + ChatItem.System(systemId, line))
        }
        val rest = items.filterNot { it is ChatItem.Interactive && it.requestId == card.requestId }
        return copy(items = rest + card)
    }

    fun answered(requestId: String): ChatTranscript = copy(
        items = items.map {
            if (it is ChatItem.Interactive && it.requestId == requestId) it.copy(answered = true) else it
        },
    )

    fun toggle(id: String): ChatTranscript = copy(
        items = items.map {
            when {
                it is ChatItem.Thinking && it.id == id -> it.copy(collapsed = !it.collapsed)
                it is ChatItem.Tool && it.id == id -> it.copy(collapsed = !it.collapsed)
                else -> it
            }
        },
    )
}

internal fun historyMessages(messages: List<SessionMessage>, id: (Int) -> String): List<ChatItem.Message> {
    var n = 0
    val out = mutableListOf<ChatItem.Message>()
    for (m in messages) {
        val role = m.role.lowercase()
        val text = messageText(m.content)
        if (text.isBlank() && m.metadata?.attachments.isNullOrEmpty()) continue
        if (role == "system" || role == "tool") continue
        val fromUser = role == "user" || role == "human"
        if (fromUser && isFactPrompt(text)) continue
        if (!fromUser && sameAssistant(out, text)) continue
        out += ChatItem.Message(
            id = id(n++),
            fromUser = fromUser,
            text = text,
            attachments = m.metadata?.attachments?.map { AttachmentRef(it.name, it.url, it.type) } ?: emptyList(),
            time = clockStamp(m.timestamp),
        )
    }
    return out
}

private fun sameAssistant(items: List<ChatItem>, text: String): Boolean {
    val last = items.lastOrNull() as? ChatItem.Message ?: return false
    return !last.fromUser && last.text == text
}

internal fun isFactPrompt(text: String): Boolean =
    text.startsWith("Tell one surprising real-world fact")

internal fun messageText(content: JsonElement?): String {
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

internal fun clockStamp(raw: String): String {
    if (raw.isBlank()) return ""
    val fmt = DateTimeFormatter.ofPattern("HH:mm")
    return runCatching { java.time.OffsetDateTime.parse(raw).format(fmt) }
        .recoverCatching { java.time.LocalDateTime.parse(raw).format(fmt) }
        .getOrDefault("")
}

internal fun speechLine(raw: String, limit: Int = 72): String {
    val text = raw.trim().replace(Regex("\\s+"), " ")
    if (text.isEmpty() || text.length <= limit) return text
    val from = Regex("[.!?…]\\s+").findAll(text).lastOrNull()?.range?.last?.plus(1) ?: 0
    val sentence = text.substring(from).trim()
    val body = if (sentence.length <= limit) {
        sentence
    } else {
        sentence.takeLast(limit).dropWhile { it != ' ' }.trim().ifBlank { sentence.takeLast(limit).trim() }
    }
    return if (from > 0 || sentence.length > limit) "… $body" else body
}

internal fun notifLine(counts: Map<String, Int>): String? {
    if (counts.isEmpty()) return null
    val parts = counts.entries
        .sortedByDescending { it.value }
        .take(3)
        .map { "${it.value} in ${it.key}" }
    return parts.joinToString(", ") + " unread"
}

internal fun factPrompt(lang: String): String {
    val name = if (lang == "ru") "Russian" else "English"
    return "Tell one surprising real-world fact in one or two short sentences. Reply in $name. No tools, no preamble."
}

internal fun quietHome(counts: Map<String, Int>, digest: Digest): Boolean {
    if (notifLine(counts) != null) return false
    return digest.news.none { it.isNotBlank() }
}

internal fun widgetChoices(counts: Map<String, Int>, digest: Digest): List<String> = buildList {
    notifLine(counts)?.let { add(it) }
    digest.news.filter { it.isNotBlank() }.forEach { add(it) }
    if (digest.fact.isNotBlank()) add(digest.fact)
    if (digest.moodLine.isNotBlank()) add(digest.moodLine)
}

internal fun moodCopy(mood: Mood): String = when (mood) {
    Mood.SLEEP -> "Zzz… wake me with a pair."
    Mood.ERROR -> "Something broke. Check the server."
    Mood.THINK -> "Thinking…"
    Mood.ALERT -> "Heads up!"
    Mood.BOOP -> "Boop!"
    Mood.IDLE -> "Woof. Tap me again."
}
