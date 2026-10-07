package com.shibaclaw.companion.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
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
    fun sitGesturePlaysItsOwnFrames() {
        assertEquals(Clip.BOOP.frameDrawables, Clip.BOOP.playedFrames())
        assertEquals(Clip.IDLE.frameDrawables, Clip.IDLE.playedFrames())
    }

    @Test
    fun actionFramesHoldTheMiddle() {
        assertTrue(frameHoldMs(4, 10, 70) > frameHoldMs(0, 10, 70))
    }

    @Test
    fun gestureDoesNotRepeat() {
        val pool = Clip.tapPool(Clip.BOOP)
        assertTrue(Clip.BOOP !in pool)
        assertEquals(6, pool.size)
        assertEquals(7, Clip.tapPool(null).size)
    }

    @Test
    fun gestureReturnsToTheCurrentPose() {
        val home = Clip.SLEEP.frameDrawables.first()
        val played = Clip.HOP.playedFrames(home)
        assertEquals(home, played.first())
        assertEquals(Clip.IDLE.frameDrawables.first(), played.last())
    }

    @Test
    fun nightSleepsUntilMorning() {
        assertEquals(Rest.SLEEP, restAt(23, 0, awake = false))
        assertEquals(Rest.SLEEP, restAt(6, 59, awake = false))
        assertEquals(Rest.SIT, restAt(7, 0, awake = false))
        assertEquals(Rest.SIT, restAt(23, 30, awake = true))
    }

    @Test
    fun walksAtMorningLunchAndEvening() {
        assertEquals(Rest.WALK, restAt(8, 15, awake = false))
        assertEquals(Rest.WALK, restAt(13, 0, awake = false))
        assertEquals(Rest.WALK, restAt(19, 40, awake = false))
        assertEquals(Rest.SIT, restAt(9, 0, awake = false))
        assertEquals(Rest.SIT, restAt(12, 0, awake = false))
        assertEquals(Clip.WALK, Clip.homeFor(Rest.WALK))
        assertEquals(Clip.IDLE, Clip.homeFor(Rest.SIT))
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
