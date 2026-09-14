package com.shibaclaw.companion

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import org.json.JSONArray
import org.json.JSONObject

class DeviceTools(private val ctx: Context) {
    fun execute(name: String, args: JSONObject): ToolOutcome {
        return try {
            when (name) {
                "list_apps" -> listApps(args.optString("query"))
                "launch_app" -> launchApp(args.optString("package"))
                "open_setting" -> openSetting(args.optString("which"))
                else -> ToolOutcome(false, error = "unknown tool $name")
            }
        } catch (e: Exception) {
            ToolOutcome(false, error = e.message ?: "tool failed")
        }
    }

    private fun listApps(query: String): ToolOutcome {
        val pm = ctx.packageManager
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val found = pm.queryIntentActivities(intent, 0)
            .mapNotNull { info ->
                val label = info.loadLabel(pm).toString()
                val pkg = info.activityInfo.packageName
                label to pkg
            }
            .distinctBy { it.second }
            .sortedBy { it.first.lowercase() }
            .filter {
                query.isBlank() ||
                    it.first.contains(query, ignoreCase = true) ||
                    it.second.contains(query, ignoreCase = true)
            }
        val arr = JSONArray()
        for ((label, pkg) in found) {
            arr.put(JSONObject().put("label", label).put("package", pkg))
        }
        return ToolOutcome(true, result = arr.toString())
    }

    private fun launchApp(pkg: String): ToolOutcome {
        if (pkg.isBlank()) return ToolOutcome(false, error = "package required")
        val launch = ctx.packageManager.getLaunchIntentForPackage(pkg)
            ?: return ToolOutcome(false, error = "no launcher for $pkg")
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        ctx.startActivity(launch)
        return ToolOutcome(true, result = "launched $pkg")
    }

    private fun openSetting(which: String): ToolOutcome {
        val action = when (which.lowercase()) {
            "wifi", "wireless" -> Settings.ACTION_WIFI_SETTINGS
            "bluetooth" -> Settings.ACTION_BLUETOOTH_SETTINGS
            "display" -> Settings.ACTION_DISPLAY_SETTINGS
            "sound" -> Settings.ACTION_SOUND_SETTINGS
            "apps" -> Settings.ACTION_APPLICATION_SETTINGS
            "battery" -> Settings.ACTION_BATTERY_SAVER_SETTINGS
            "notifications" -> Settings.ACTION_APP_NOTIFICATION_SETTINGS
            "nfc" -> Settings.ACTION_NFC_SETTINGS
            "location" -> Settings.ACTION_LOCATION_SOURCE_SETTINGS
            "accessibility" -> Settings.ACTION_ACCESSIBILITY_SETTINGS
            "development" -> Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS
            "date" -> Settings.ACTION_DATE_SETTINGS
            "locale" -> Settings.ACTION_LOCALE_SETTINGS
            "app_detail" -> Settings.ACTION_APPLICATION_DETAILS_SETTINGS
            else -> Settings.ACTION_SETTINGS
        }
        val intent = Intent(action).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (action == Settings.ACTION_APP_NOTIFICATION_SETTINGS ||
            action == Settings.ACTION_APPLICATION_DETAILS_SETTINGS
        ) {
            intent.data = Uri.fromParts("package", ctx.packageName, null)
            intent.putExtra(Settings.EXTRA_APP_PACKAGE, ctx.packageName)
        }
        ctx.startActivity(intent)
        return ToolOutcome(true, result = "opened $which")
    }
}

data class ToolOutcome(val ok: Boolean, val result: String = "", val error: String = "")
