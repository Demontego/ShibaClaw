package com.shibaclaw.companion

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.view.View
import android.widget.RemoteViews
import com.shibaclaw.companion.data.Clip
import com.shibaclaw.companion.data.Mood
import com.shibaclaw.companion.data.speechLine

class ShibaWidget : AppWidgetProvider() {
    override fun onUpdate(context: Context, mgr: AppWidgetManager, ids: IntArray) {
        ids.forEach { render(context, mgr, it) }
    }

    override fun onEnabled(context: Context) {
        ShibaService.start(context)
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        if (intent.action == ACTION_TAP) {
            val now = System.currentTimeMillis()
            val last = Prefs.lastTapAt(context)
            Prefs.setLastTap(context, now)
            val double = now - last in 1..DOUBLE_TAP_MS
            if (ShibaService.busy) return
            ShibaService.busy = true
            if (double) {
                ShibaService.start(context, ShibaService.ACTION_HEY)
                openChat(context)
            } else {
                ShibaService.start(context, ShibaService.ACTION_BOOP)
            }
        }
    }

    companion object {
        const val ACTION_TAP = "com.shibaclaw.companion.TAP"
        private const val DOUBLE_TAP_MS = 420L

        fun refresh(context: Context) {
            val mgr = AppWidgetManager.getInstance(context)
            val ids = mgr.getAppWidgetIds(ComponentName(context, ShibaWidget::class.java))
            ids.forEach { render(context, mgr, it) }
        }

        private fun render(context: Context, mgr: AppWidgetManager, id: Int) {
            val views = RemoteViews(context.packageName, R.layout.shiba_widget)
            val clip = Clip.entries.firstOrNull { it.name == Prefs.clipName(context) }
                ?: Clip.forMood(Mood.from(Prefs.mood(context)))
            val restName = Prefs.restClip(context)
            val home = Clip.entries.firstOrNull { it.name == restName }?.frameDrawables?.first()
                ?: Clip.IDLE.frameDrawables.first()
            val frames = clip.playedFrames(home)
            val index = Prefs.frameIndex(context).coerceIn(0, frames.lastIndex)
            views.setImageViewResource(R.id.shiba_face, frames[index])
            val bubble = Prefs.lastBubble(context)
            if (bubble.isBlank()) {
                views.setViewVisibility(R.id.shiba_bubble, View.GONE)
            } else {
                views.setViewVisibility(R.id.shiba_bubble, View.VISIBLE)
                val width = mgr.getAppWidgetOptions(id)
                    .getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_WIDTH, 0)
                val limit = if (width <= 0) 72 else (width / 9 * 3).coerceIn(48, 180)
                views.setTextViewText(R.id.shiba_bubble, speechLine(bubble, limit))
            }
            val tap = Intent(context, ShibaWidget::class.java).setAction(ACTION_TAP)
            val pi = PendingIntent.getBroadcast(
                context,
                0,
                tap,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
            views.setOnClickPendingIntent(R.id.widget_root, pi)
            mgr.updateAppWidget(id, views)
        }

        private fun openChat(context: Context) {
            val open = Intent(context, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(open)
        }
    }
}
