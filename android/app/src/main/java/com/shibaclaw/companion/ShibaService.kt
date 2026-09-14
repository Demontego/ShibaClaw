package com.shibaclaw.companion

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.pm.ServiceInfo
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.core.app.NotificationCompat

class ShibaService : Service(), ShibaClient.Listener {
    private lateinit var client: ShibaClient

    override fun onCreate() {
        super.onCreate()
        ensureChannel()
        client = ShibaClient(DeviceTools(this), this)
        Companion.instance = this
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notif = buildNotif(getString(R.string.notif_title))
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(
                NOTIF_ID,
                notif,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
            )
        } else {
            startForeground(NOTIF_ID, notif)
        }
        when (intent?.action) {
            ACTION_BOOP -> {
                boopLocal()
            }
            ACTION_HEY -> {
                boopLocal()
                if (client.connected) {
                    client.sendChat(getString(R.string.boop_prompt))
                } else {
                    connect()
                }
            }
            ACTION_CHAT -> {
                val text = intent.getStringExtra(EXTRA_TEXT).orEmpty()
                if (text.isNotBlank() && client.connected) {
                    client.sendChat(text)
                }
            }
            else -> connect()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        client.disconnect()
        if (Companion.instance === this) Companion.instance = null
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun connect() {
        if (!Prefs.isPaired(this)) {
            onMood(Mood.SLEEP)
            return
        }
        client.connect(
            Prefs.baseUrl(this),
            Prefs.username(this),
            Prefs.password(this),
            Prefs.token(this),
            Prefs.deviceId(this),
            Prefs.label(this),
        )
    }

    private fun boopLocal() {
        Prefs.setMood(this, Mood.BOOP)
        ShibaWidget.refresh(this)
        vibrate()
        ChatBus.emitMood(Mood.BOOP)
        android.os.Handler(mainLooper).postDelayed({
            if (Prefs.mood(this) == Mood.BOOP.name) {
                val next = if (client.connected) Mood.IDLE else Mood.SLEEP
                onMood(next)
            }
        }, 450)
    }

    private fun vibrate() {
        val vibe = if (Build.VERSION.SDK_INT >= 31) {
            (getSystemService(VibratorManager::class.java)).defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            getSystemService(Vibrator::class.java)
        }
        vibe.vibrate(VibrationEffect.createOneShot(40, VibrationEffect.DEFAULT_AMPLITUDE))
    }

    override fun onHello(ok: Boolean, error: String?) {
        if (ok) {
            onMood(Mood.IDLE)
            ChatBus.emitStatus(getString(R.string.status_online))
        } else {
            onMood(Mood.ERROR)
            ChatBus.emitStatus(error ?: getString(R.string.status_offline))
        }
    }

    override fun onToken(token: String) {
        Prefs.setToken(this, token)
    }

    override fun onMood(mood: Mood) {
        Prefs.setMood(this, mood)
        ShibaWidget.refresh(this)
        ChatBus.emitMood(mood)
    }

    override fun onBubble(text: String) {
        val line = text.trim().replace("\n", " ")
        Prefs.setBubble(this, line)
        ShibaWidget.refresh(this)
        ChatBus.emitBubble(line)
    }

    override fun onChatDelta(text: String) {
        ChatBus.emitDelta(text)
    }

    override fun onChatDone(text: String) {
        ChatBus.emitDone(text)
        onMood(Mood.ALERT)
        android.os.Handler(mainLooper).postDelayed({
            if (Prefs.mood(this) == Mood.ALERT.name) onMood(Mood.IDLE)
        }, 2500)
    }

    override fun onClosed() {
        onMood(Mood.SLEEP)
        ChatBus.emitStatus(getString(R.string.status_offline))
    }

    private fun ensureChannel() {
        val mgr = getSystemService(NotificationManager::class.java)
        mgr.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                getString(R.string.notif_channel),
                NotificationManager.IMPORTANCE_LOW,
            ),
        )
    }

    private fun buildNotif(text: String): Notification {
        val open = PendingIntent.getActivity(
            this,
            0,
            Intent(this, ChatActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.shiba_idle)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(text)
            .setContentIntent(open)
            .setOngoing(true)
            .build()
    }

    companion object {
        const val CHANNEL_ID = "shiba"
        const val NOTIF_ID = 7
        const val ACTION_BOOP = "com.shibaclaw.companion.BOOP"
        const val ACTION_HEY = "com.shibaclaw.companion.HEY"
        const val ACTION_CHAT = "com.shibaclaw.companion.CHAT"
        const val EXTRA_TEXT = "text"

        @Volatile
        var instance: ShibaService? = null

        fun start(ctx: Context, action: String? = null, text: String? = null) {
            val i = Intent(ctx, ShibaService::class.java)
            if (action != null) i.action = action
            if (text != null) i.putExtra(EXTRA_TEXT, text)
            if (Build.VERSION.SDK_INT >= 26) {
                ctx.startForegroundService(i)
            } else {
                ctx.startService(i)
            }
        }
    }
}

object ChatBus {
    @Volatile var moodListener: ((Mood) -> Unit)? = null
    @Volatile var statusListener: ((String) -> Unit)? = null
    @Volatile var deltaListener: ((String) -> Unit)? = null
    @Volatile var doneListener: ((String) -> Unit)? = null
    @Volatile var bubbleListener: ((String) -> Unit)? = null

    fun emitMood(m: Mood) { moodListener?.invoke(m) }
    fun emitStatus(s: String) { statusListener?.invoke(s) }
    fun emitDelta(s: String) { deltaListener?.invoke(s) }
    fun emitDone(s: String) { doneListener?.invoke(s) }
    fun emitBubble(s: String) { bubbleListener?.invoke(s) }
}
