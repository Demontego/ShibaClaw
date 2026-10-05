package com.shibaclaw.companion.data

import com.shibaclaw.companion.Endpoints
import com.shibaclaw.companion.Prefs
import java.io.File
import java.time.Instant
import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

object ShibaApi {
    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
    }
    private val http = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()
    private val jsonType = "application/json; charset=utf-8".toMediaType()

    private fun root(): String = Endpoints.baseUrl(Prefs.baseUrl())
    private fun token(): String = Prefs.token()

    private fun auth(builder: Request.Builder): Request.Builder {
        val t = token()
        if (t.isNotBlank()) builder.header("Authorization", "Bearer $t")
        return builder
    }

    private fun get(path: String): String {
        val req = auth(Request.Builder().url("${root()}$path").get()).build()
        http.newCall(req).execute().use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) {
                throw IllegalStateException(errorMessage(body, resp.code))
            }
            return body
        }
    }

    private fun send(method: String, path: String, payload: String? = null): String {
        val body = payload?.toRequestBody(jsonType)
        val builder = Request.Builder().url("${root()}$path")
        when (method) {
            "POST" -> builder.post(body ?: ByteArray(0).toRequestBody(null))
            "PATCH" -> builder.patch(body ?: ByteArray(0).toRequestBody(null))
            "DELETE" -> if (body != null) builder.delete(body) else builder.delete()
            else -> builder.get()
        }
        val req = auth(builder).build()
        http.newCall(req).execute().use { resp ->
            val text = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) {
                throw IllegalStateException(errorMessage(text, resp.code))
            }
            return text
        }
    }

    private fun errorMessage(body: String, code: Int): String {
        return try {
            JSONObject(body).optString("error", "HTTP $code")
        } catch (_: Exception) {
            "HTTP $code"
        }
    }

    fun listSessions(): List<SessionSummary> = parseSessionArray(get("/api/sessions"), "sessions")

    fun searchSessions(q: String): List<SessionSummary> {
        if (q.isBlank()) return listSessions()
        val raw = get("/api/sessions/search?q=${java.net.URLEncoder.encode(q, "UTF-8")}&limit=40")
        return try {
            val o = JSONObject(raw)
            when {
                o.has("sessions") -> parseSessionArray(raw, "sessions")
                o.has("hits") -> parseSessionArray(raw, "hits")
                else -> emptyList()
            }.ifEmpty {
                listSessions().filter {
                    it.key.contains(q, true) ||
                        (it.nickname?.contains(q, true) == true) ||
                        it.preview.contains(q, true)
                }
            }
        } catch (_: Exception) {
            listSessions().filter {
                it.key.contains(q, true) ||
                    (it.nickname?.contains(q, true) == true) ||
                    it.preview.contains(q, true)
            }
        }
    }

    fun getSession(id: String): SessionDetail =
        json.decodeFromString(get("/api/sessions/${java.net.URLEncoder.encode(id, "UTF-8")}"))

    fun patchSession(id: String, fields: Map<String, Any?>) {
        val o = JSONObject()
        fields.forEach { (k, v) -> o.put(k, v) }
        send("PATCH", "/api/sessions/${java.net.URLEncoder.encode(id, "UTF-8")}", o.toString())
    }

    fun deleteSession(id: String) {
        send("DELETE", "/api/sessions/${java.net.URLEncoder.encode(id, "UTF-8")}")
    }

    fun archiveSession(id: String) {
        send("POST", "/api/sessions/${java.net.URLEncoder.encode(id, "UTF-8")}/archive")
    }

    fun listModels(): List<ModelEntry> {
        val raw = get("/api/models")
        return try {
            json.decodeFromString<ModelsResponse>(raw).models
        } catch (_: Exception) {
            val o = JSONObject(raw)
            val arr = o.optJSONArray("models") ?: return emptyList()
            buildList {
                for (i in 0 until arr.length()) {
                    val m = arr.optJSONObject(i) ?: continue
                    add(
                        ModelEntry(
                            id = m.optString("id"),
                            name = m.optString("name", m.optString("id")),
                            provider = m.optString("provider"),
                        ),
                    )
                }
            }
        }
    }

    fun listProfiles(): List<ProfileEntry> {
        val raw = get("/api/profiles")
        return try {
            json.decodeFromString<ProfilesResponse>(raw).profiles
        } catch (_: Exception) {
            val o = JSONObject(raw)
            val arr = o.optJSONArray("profiles") ?: return emptyList()
            buildList {
                for (i in 0 until arr.length()) {
                    val m = arr.optJSONObject(i) ?: continue
                    add(
                        ProfileEntry(
                            id = m.optString("id"),
                            name = m.optString("name"),
                            label = m.optString("label"),
                        ),
                    )
                }
            }
        }
    }

    fun upload(file: File, mime: String, name: String): AttachmentRef {
        val part = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart(
                "file",
                name,
                file.asRequestBody(mime.toMediaType()),
            )
            .build()
        val req = auth(
            Request.Builder().url("${root()}/api/upload").post(part),
        ).build()
        http.newCall(req).execute().use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw IllegalStateException(errorMessage(body, resp.code))
            val o = JSONObject(body)
            val file = o.optJSONArray("files")?.optJSONObject(0)
            val url = file?.optString("url").orEmpty().ifBlank { o.optString("url") }
            val filename = file?.optString("filename").orEmpty().ifBlank { name }
            if (url.isBlank()) throw IllegalStateException("upload returned no url")
            return AttachmentRef(
                name = filename,
                url = if (url.startsWith("http")) url else "${root()}$url",
                type = mime,
            )
        }
    }

    private fun parseSessionArray(raw: String, field: String): List<SessionSummary> {
        val arr = JSONObject(raw).optJSONArray(field) ?: return emptyList()
        return buildList {
            for (i in 0 until arr.length()) {
                val o = arr.optJSONObject(i) ?: continue
                val key = o.optString("key").ifBlank { o.optString("session_key") }
                if (key.isBlank() || key.endsWith(":digest")) continue
                val nick = o.optString("nickname").ifBlank { null }
                add(
                    SessionSummary(
                        key = key,
                        nickname = nick,
                        updatedAt = stampOf(o.opt("updated_at") ?: o.opt("updatedAt")),
                        preview = o.optString("preview")
                            .ifBlank { o.optString("snippet") }
                            .ifBlank { o.optString("last_message") },
                    ),
                )
            }
        }.sortedByDescending { it.updatedAt }
    }

    private fun stampOf(value: Any?): Long {
        return when (value) {
            is Number -> {
                val n = value.toDouble()
                if (n < 1e11) (n * 1000).toLong() else n.toLong()
            }
            is String -> runCatching { Instant.parse(value).toEpochMilli() }.getOrDefault(0L)
            else -> 0L
        }
    }

    fun listNotifications(): List<AgentNotification> {
        val raw = get("/api/v1/notifications")
        return try {
            json.decodeFromString<NotificationsResponse>(raw).notifications
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun clearNotifications() {
        send("DELETE", "/api/v1/notifications")
    }
}
