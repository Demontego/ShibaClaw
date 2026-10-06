package com.shibaclaw.companion.data

import org.junit.Assert.assertEquals
import org.junit.Test

class CompanionModelsTest {
    @Test
    fun unknownMoodSleeps() {
        assertEquals(Mood.SLEEP, Mood.from(null))
        assertEquals(Mood.SLEEP, Mood.from("nope"))
    }

    @Test
    fun moodIgnoresCase() {
        assertEquals(Mood.ALERT, Mood.from("alert"))
    }

    @Test
    fun boopUsesIdleClip() {
        assertEquals(Clip.IDLE, Clip.forMood(Mood.BOOP))
        assertEquals(Clip.THINK, Clip.forMood(Mood.THINK))
        assertEquals(Clip.ERROR, Clip.forMood(Mood.ERROR))
    }

    @Test
    fun profileTitlePrefersLabelThenNameThenId() {
        assertEquals("label", ProfileEntry(id = "a", name = "n", label = "label").title())
        assertEquals("n", ProfileEntry(id = "a", name = "n").title())
        assertEquals("a", ProfileEntry(id = "a").title())
    }

    @Test
    fun sessionIdPrefersKeyAndLinePrefersPreview() {
        val entry = SessionEntry(key = "k", session_key = "s", preview = "seen", last_message = "older")
        assertEquals("k", entry.id())
        assertEquals("seen", entry.line())
    }

    @Test
    fun sessionFallsBackWhenPrimaryFieldsBlank() {
        val entry = SessionEntry(session_key = "s1", last_message = "hi")
        assertEquals("s1", entry.id())
        assertEquals("hi", entry.line())
    }
}
