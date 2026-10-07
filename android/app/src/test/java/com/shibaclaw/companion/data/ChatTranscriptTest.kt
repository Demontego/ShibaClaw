package com.shibaclaw.companion.data

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ChatTranscriptTest {
    @Test
    fun deltasAppendOneReplyBesideTheUser() {
        val log = ChatTranscript()
            .addUser("ping", id = "u")
            .delta("hel", id = "s")
            .delta("lo", id = "ignored")

        val messages = log.items.filterIsInstance<ChatItem.Message>()
        assertEquals(listOf("ping", "hello"), messages.map { it.text })
        assertTrue(messages.first().fromUser)
        assertFalse(messages.last().fromUser)
        assertTrue(messages.last().streaming)
        assertEquals("s", log.streamId)
    }

    @Test
    fun doneClosesTheStream() {
        val log = ChatTranscript().delta("hel", id = "s").done("hello!", id = "d")
        val reply = log.items.filterIsInstance<ChatItem.Message>().single()
        assertEquals("hello!", reply.text)
        assertFalse(reply.streaming)
        assertNull(log.streamId)
    }

    @Test
    fun blankDoneKeepsPartialText() {
        val log = ChatTranscript()
            .delta("partial", id = "s")
            .done("hello!", id = "d1")
            .delta("next", id = "s2")
            .done("", id = "d2")

        assertEquals(listOf("hello!", "next"), log.items.filterIsInstance<ChatItem.Message>().map { it.text })
        assertFalse((log.items.last() as ChatItem.Message).streaming)
    }

    @Test
    fun secondDoneDoesNotCloneTheReply() {
        val log = ChatTranscript()
            .addUser("привет", id = "u")
            .delta("факт", id = "s")
            .done("Акулы. Привет!", id = "d1")
            .done("Акулы. Привет!", id = "d2")
        val replies = log.items.filterIsInstance<ChatItem.Message>().filter { !it.fromUser }
        assertEquals(listOf("Акулы. Привет!"), replies.map { it.text })
    }

    @Test
    fun historyDropsFactPromptAndClonedReply() {
        val msgs = historyMessages(
            listOf(
                SessionMessage(role = "user", content = JsonPrimitive(factPrompt("ru"))),
                SessionMessage(role = "user", content = JsonPrimitive("привет")),
                SessionMessage(role = "assistant", content = JsonPrimitive("Акулы. Привет!")),
                SessionMessage(role = "assistant", content = JsonPrimitive("Акулы. Привет!")),
            ),
        ) { n -> "h$n" }
        assertEquals(listOf("привет", "Акулы. Привет!"), msgs.map { it.text })
    }

    @Test
    fun nextDeltaStartsANewReply() {
        val log = ChatTranscript().delta("one", id = "s1").done("one", id = "d").delta("two", id = "s2")
        val replies = log.items.filterIsInstance<ChatItem.Message>()
        assertEquals(listOf("one", "two"), replies.map { it.text })
        assertTrue(replies.last().streaming)
    }

    @Test
    fun sameRequestReplacesTheCard() {
        val log = ChatTranscript()
            .interactive(ChatItem.Interactive(id = "i1", requestId = "r1", prompt = "pick"), systemId = "sys")
            .interactive(ChatItem.Interactive(id = "i2", requestId = "r1", prompt = "pick again"), systemId = "sys")
        assertEquals(listOf("pick again"), log.items.filterIsInstance<ChatItem.Interactive>().map { it.prompt })
    }

    @Test
    fun answerMarksOnlyThatRequest() {
        val log = ChatTranscript()
            .interactive(ChatItem.Interactive(id = "a", requestId = "r1", prompt = "a"), systemId = "s")
            .interactive(ChatItem.Interactive(id = "b", requestId = "r2", prompt = "b"), systemId = "s")
            .answered("r1")
        assertEquals(listOf(true, false), log.items.filterIsInstance<ChatItem.Interactive>().map { it.answered })
    }

    @Test
    fun progressCardIsASystemLine() {
        val log = ChatTranscript().interactive(
            ChatItem.Interactive(id = "p", requestId = "p", prompt = "Working", kind = "progress_card", hint = "files"),
            systemId = "sys",
        )
        assertEquals("Working — files", (log.items.single() as ChatItem.System).text)
    }

    @Test
    fun progressCardDropsBlankHint() {
        val log = ChatTranscript().interactive(
            ChatItem.Interactive(id = "p", requestId = "p", prompt = "Working", kind = "progress_card"),
            systemId = "sys",
        )
        assertEquals("Working", (log.items.single() as ChatItem.System).text)
    }

    @Test
    fun thinkingStartsCollapsed() {
        val log = ChatTranscript().thinking("plan", id = "t")
        assertTrue((log.items.single() as ChatItem.Thinking).collapsed)
        assertFalse((log.toggle("t").items.single() as ChatItem.Thinking).collapsed)
    }

    @Test
    fun historyKeepsSpeechAndDropsMachinery() {
        val msgs = historyMessages(
            listOf(
                SessionMessage(role = "system", content = JsonPrimitive("hidden")),
                SessionMessage(role = "human", content = JsonPrimitive("hi"), timestamp = "2026-10-06T12:34:00Z"),
                SessionMessage(
                    role = "assistant",
                    content = JsonArray(listOf(JsonObject(mapOf("text" to JsonPrimitive("yo"))))),
                ),
                SessionMessage(role = "tool", content = JsonPrimitive("noise")),
                SessionMessage(
                    role = "user",
                    content = JsonPrimitive("  "),
                    metadata = SessionMessageMeta(listOf(ApiAttachment("a.png", "/a", "image/png"))),
                ),
            ),
        ) { n -> "h$n" }
        assertEquals(listOf("hi", "yo", ""), msgs.map { it.text })
        assertEquals(listOf(true, false, true), msgs.map { it.fromUser })
        assertEquals(listOf("h0", "h1", "h2"), msgs.map { it.id })
        assertEquals("12:34", msgs.first().time)
        assertEquals("a.png", msgs.last().attachments.single().name)
    }

    @Test
    fun emptyNotifCountsHaveNoLine() {
        assertNull(notifLine(emptyMap()))
    }

    @Test
    fun notifLineKeepsTopThreeByCount() {
        assertEquals(
            "9 in Chat, 2 in Mail, 1 in News unread",
            notifLine(mapOf("Mail" to 2, "Chat" to 9, "News" to 1)),
        )
    }

    @Test
    fun widgetPrefersNotificationsOverFact() {
        assertEquals(
            listOf("2 in Chat unread", "rain"),
            widgetChoices(mapOf("Chat" to 2), Digest(fact = "rain")),
        )
    }

    @Test
    fun factComesBeforeMoodLine() {
        assertEquals(listOf("rain", "calm"), widgetChoices(emptyMap(), Digest(fact = "rain", moodLine = "calm")))
    }

    @Test
    fun shortSpeechStaysWhole() {
        assertEquals("Акулы древние.", speechLine("Акулы древние."))
    }

    @Test
    fun longSpeechKeepsTheLatestWords() {
        val line = speechLine("начало " + "слово ".repeat(40) + "конец фразы", limit = 72)
        assertTrue(line.startsWith("… "))
        assertTrue(line.endsWith("конец фразы"))
        assertTrue(line.length <= 80)
    }

    @Test
    fun speechShowsOnlyTheCurrentSentence() {
        assertEquals("… Вторая короткая.", speechLine("Первая мысль. Вторая короткая.", limit = 24))
    }

    @Test
    fun factPromptNamesTheLanguage() {
        assertTrue(factPrompt("ru").contains("Russian"))
        assertTrue(factPrompt("en").contains("English"))
    }

    @Test
    fun quietHomeAsksEvenWithoutDigestFact() {
        assertTrue(quietHome(emptyMap(), Digest(moodLine = "woof")))
    }

    @Test
    fun newsKeepsTheBubble() {
        assertFalse(quietHome(emptyMap(), Digest(news = listOf("quake"))))
    }

    @Test
    fun notificationsKeepTheBubble() {
        assertFalse(quietHome(mapOf("Chat" to 1), Digest()))
    }

    @Test
    fun emptyWidgetFallsBackToMoodCopy() {
        assertEquals("Something broke. Check the server.", moodCopy(Mood.ERROR))
    }
}
