package com.shibaclaw.companion

import android.content.Context
import android.content.SharedPreferences
import android.os.Build
import java.util.UUID

object Prefs {
    private const val NAME = "shiba"
    private lateinit var p: SharedPreferences

    fun init(ctx: Context) {
        p = ctx.applicationContext.getSharedPreferences(NAME, Context.MODE_PRIVATE)
        if (deviceId().isEmpty()) {
            p.edit().putString("device_id", "android." + UUID.randomUUID().toString().take(8)).apply()
        }
    }

    private fun prefs(ctx: Context? = null): SharedPreferences {
        if (this::p.isInitialized) return p
        p = ctx!!.applicationContext.getSharedPreferences(NAME, Context.MODE_PRIVATE)
        return p
    }

    fun baseUrl(ctx: Context? = null): String = prefs(ctx).getString("base_url", "") ?: ""
    fun username(ctx: Context? = null): String = prefs(ctx).getString("username", "") ?: ""
    fun password(ctx: Context? = null): String = prefs(ctx).getString("password", "") ?: ""
    fun token(ctx: Context? = null): String = prefs(ctx).getString("token", "") ?: ""
    fun deviceId(ctx: Context? = null): String = prefs(ctx).getString("device_id", "") ?: ""
    fun label(ctx: Context? = null): String =
        prefs(ctx).getString("label", Build.MODEL) ?: "Android"
    fun lastBubble(ctx: Context? = null): String = prefs(ctx).getString("bubble", "") ?: ""
    fun mood(ctx: Context? = null): String = prefs(ctx).getString("mood", Mood.SLEEP.name) ?: Mood.SLEEP.name
    fun lastTapAt(ctx: Context? = null): Long = prefs(ctx).getLong("last_tap", 0L)
    fun isPaired(ctx: Context? = null): Boolean = baseUrl(ctx).isNotBlank()

    fun savePair(ctx: Context, baseUrl: String, username: String, password: String) {
        prefs(ctx).edit()
            .putString("base_url", Endpoints.baseUrl(baseUrl))
            .putString("username", username.trim())
            .putString("password", password)
            .apply()
    }

    fun setToken(ctx: Context, token: String) {
        prefs(ctx).edit().putString("token", token).apply()
    }

    fun setMood(ctx: Context, mood: Mood) {
        prefs(ctx).edit().putString("mood", mood.name).apply()
    }

    fun setBubble(ctx: Context, text: String) {
        prefs(ctx).edit().putString("bubble", text.take(160)).apply()
    }

    fun setLastTap(ctx: Context, at: Long) {
        prefs(ctx).edit().putLong("last_tap", at).apply()
    }
}

enum class Mood {
    IDLE, THINK, SLEEP, ALERT, ERROR, BOOP;

    fun drawable(): Int = when (this) {
        IDLE -> R.drawable.shiba_idle
        THINK -> R.drawable.shiba_think
        SLEEP -> R.drawable.shiba_sleep
        ALERT -> R.drawable.shiba_alert
        ERROR -> R.drawable.shiba_error
        BOOP -> R.drawable.shiba_boop
    }

    companion object {
        fun from(raw: String?): Mood =
            entries.firstOrNull { it.name == raw } ?: SLEEP
    }
}
