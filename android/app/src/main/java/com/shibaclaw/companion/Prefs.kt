package com.shibaclaw.companion

import android.content.Context
import android.content.SharedPreferences
import android.os.Build
import androidx.security.crypto.EncryptedSharedPreferences
import com.shibaclaw.companion.data.Digest
import com.shibaclaw.companion.data.Mood
import com.shibaclaw.companion.data.ThemeMode
import java.util.UUID
import org.json.JSONArray
import org.json.JSONObject

object Prefs {
    private const val NAME = "shiba"
    private lateinit var p: SharedPreferences

    fun init(ctx: Context) {
        val app = ctx.applicationContext
        p = app.getSharedPreferences(NAME, Context.MODE_PRIVATE)
        secrets(app)
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
    fun password(ctx: Context? = null): String = secret(ctx, "password")
    fun token(ctx: Context? = null): String = secret(ctx, "token")
    fun deviceId(ctx: Context? = null): String = prefs(ctx).getString("device_id", "") ?: ""
    fun label(ctx: Context? = null): String =
        prefs(ctx).getString("label", Build.MODEL) ?: "Android"
    fun lastBubble(ctx: Context? = null): String = prefs(ctx).getString("bubble", "") ?: ""
    fun mood(ctx: Context? = null): String =
        prefs(ctx).getString("mood", Mood.SLEEP.name) ?: Mood.SLEEP.name
    fun lastTapAt(ctx: Context? = null): Long = prefs(ctx).getLong("last_tap", 0L)
    fun isPaired(ctx: Context? = null): Boolean = baseUrl(ctx).isNotBlank()
    fun themeMode(ctx: Context? = null): ThemeMode =
        ThemeMode.entries.firstOrNull {
            it.name == prefs(ctx).getString("theme", ThemeMode.SYSTEM.name)
        } ?: ThemeMode.SYSTEM
    fun clipName(ctx: Context? = null): String =
        prefs(ctx).getString("clip", "IDLE") ?: "IDLE"
    fun frameIndex(ctx: Context? = null): Int = prefs(ctx).getInt("frame", 0)
    fun pickIndex(ctx: Context? = null): Int = prefs(ctx).getInt("pick_index", 0)
    fun chatForeground(ctx: Context? = null): Boolean =
        prefs(ctx).getBoolean("chat_foreground", false)
    fun replyLang(ctx: Context? = null): String =
        prefs(ctx).getString("reply_lang", "ru") ?: "ru"

    fun digest(ctx: Context? = null): Digest {
        val raw = prefs(ctx).getString("digest", "") ?: ""
        if (raw.isBlank()) return Digest()
        return try {
            val o = JSONObject(raw)
            val news = mutableListOf<String>()
            val arr = o.optJSONArray("news") ?: JSONArray()
            for (i in 0 until arr.length()) news.add(arr.optString(i))
            Digest(
                mood = o.optString("mood", "IDLE"),
                moodLine = o.optString("mood_line", ""),
                fact = o.optString("fact", ""),
                news = news,
            )
        } catch (_: Exception) {
            Digest()
        }
    }

    fun savePair(ctx: Context, baseUrl: String, username: String, password: String) {
        prefs(ctx).edit()
            .putString("base_url", Endpoints.baseUrl(baseUrl))
            .putString("username", username.trim())
            .remove("password")
            .apply()
        putSecret(ctx, "password", password)
    }

    fun setToken(ctx: Context, token: String) {
        prefs(ctx).edit().remove("token").apply()
        putSecret(ctx, "token", token)
    }

    fun setMood(ctx: Context, mood: Mood) {
        prefs(ctx).edit().putString("mood", mood.name).apply()
    }

    fun setBubble(ctx: Context, text: String) {
        prefs(ctx).edit().putString("bubble", text.take(4000)).apply()
    }

    fun setLastTap(ctx: Context, at: Long) {
        prefs(ctx).edit().putLong("last_tap", at).apply()
    }

    fun setThemeMode(ctx: Context, mode: ThemeMode) {
        prefs(ctx).edit().putString("theme", mode.name).apply()
    }

    fun setClip(ctx: Context, clip: String) {
        prefs(ctx).edit().putString("clip", clip).apply()
    }

    fun restClip(ctx: Context? = null): String = prefs(ctx).getString("rest_clip", "IDLE") ?: "IDLE"

    fun setRestClip(ctx: Context, name: String) {
        prefs(ctx).edit().putString("rest_clip", name).apply()
    }

    fun lastGesture(ctx: Context? = null): String = prefs(ctx).getString("last_gesture", "") ?: ""

    fun setLastGesture(ctx: Context, name: String) {
        prefs(ctx).edit().putString("last_gesture", name).apply()
    }

    fun awakeUntil(ctx: Context? = null): Long = prefs(ctx).getLong("awake_until", 0L)

    fun setAwakeUntil(ctx: Context, at: Long) {
        prefs(ctx).edit().putLong("awake_until", at).apply()
    }

    fun setFrame(ctx: Context, index: Int) {
        prefs(ctx).edit().putInt("frame", index).apply()
    }

    fun setPickIndex(ctx: Context, index: Int) {
        prefs(ctx).edit().putInt("pick_index", index).apply()
    }

    fun setChatForeground(ctx: Context, on: Boolean) {
        prefs(ctx).edit().putBoolean("chat_foreground", on).apply()
    }

    fun setReplyLang(ctx: Context, lang: String) {
        prefs(ctx).edit().putString("reply_lang", lang).apply()
    }

    fun setDigest(ctx: Context, digest: Digest) {
        val arr = JSONArray()
        digest.news.forEach { arr.put(it) }
        val o = JSONObject()
            .put("mood", digest.mood)
            .put("mood_line", digest.moodLine)
            .put("fact", digest.fact)
            .put("news", arr)
        prefs(ctx).edit().putString("digest", o.toString()).apply()
    }

    fun clearPair(ctx: Context) {
        prefs(ctx).edit()
            .remove("base_url")
            .remove("username")
            .remove("password")
            .remove("token")
            .apply()
        putSecret(ctx, "password", "")
        putSecret(ctx, "token", "")
    }

    private fun secret(ctx: Context?, key: String): String {
        val box = secrets(ctx)
        val stored = box?.getString(key, null)
        if (!stored.isNullOrEmpty()) return stored
        val plain = prefs(ctx).getString(key, "") ?: ""
        if (plain.isNotEmpty() && box != null) {
            box.edit().putString(key, plain).apply()
            prefs(ctx).edit().remove(key).apply()
        }
        return plain
    }

    private fun putSecret(ctx: Context?, key: String, value: String) {
        val box = secrets(ctx)
        if (box != null) {
            box.edit().putString(key, value).commit()
        } else {
            prefs(ctx).edit().putString(key, value).commit()
        }
    }

    private var secretBox: SharedPreferences? = null

    private fun secrets(ctx: Context?): SharedPreferences? {
        secretBox?.let { return it }
        val context = ctx?.applicationContext ?: return null
        return try {
            EncryptedSharedPreferences.create(
                "shiba_secret",
                "shiba_master_key",
                context,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            ).also { secretBox = it }
        } catch (_: Exception) {
            null
        }
    }
}
