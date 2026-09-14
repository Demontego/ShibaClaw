package com.shibaclaw.companion

import android.net.Uri

object Endpoints {
    fun baseUrl(raw: String): String {
        val trimmed = raw.trim().trimEnd('/')
        val withScheme = if (trimmed.contains("://")) trimmed else "https://$trimmed"
        val uri = Uri.parse(withScheme)
        val host = uri.host ?: return withScheme
        val port = if (uri.port != -1) ":${uri.port}" else ""
        return "${uri.scheme}://$host$port"
    }

    fun wsUrl(base: String): String {
        val root = baseUrl(base)
        return when {
            root.startsWith("https://") -> "wss://" + root.removePrefix("https://") + "/ws"
            root.startsWith("http://") -> "ws://" + root.removePrefix("http://") + "/ws"
            else -> "$root/ws"
        }
    }
}
