package com.shibaclaw.companion

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.core.app.NotificationCompat
import com.shibaclaw.companion.data.AttachmentRef
import com.shibaclaw.companion.data.ChatItem
import com.shibaclaw.companion.data.Clip
import com.shibaclaw.companion.data.Digest
import com.shibaclaw.companion.data.Mood
import com.shibaclaw.companion.data.ShibaClient
import com.shibaclaw.companion.data.ShibaRepo
import com.shibaclaw.companion.data.Rest
import com.shibaclaw.companion.data.frameHoldMs
import com.shibaclaw.companion.data.homeFor
import com.shibaclaw.companion.data.restAt
import org.json.JSONArray
import org.json.JSONObject

class ShibaService : Service(), ShibaClient.Listener {
    private lateinit var client: ShibaClient
    private val main = Handler(Looper.getMainLooper())
    private val outbound = ArrayDeque<Outbound>()
    private var running = true
    private var retries = 0
    private var oneShot = false
    private val digestEveryMs = 60 * 60 * 1000L
    private val digestTick = object : Runnable {
        override fun run() {
            if (client.connected) client.requestDigest()
            main.postDelayed(this, digestEveryMs)
        }
    }
    private val reconnect = Runnable {
        if (running && Prefs.isPaired(this) && !client.connected) connect()
    }
    private var factLive = false
    private var factShown = ""
    private var writing = false
    private val wakeMs = 10 * 60 * 1000L
    private val clock = object : Runnable {
        override fun run() {
            if (!oneShot) showRest()
            main.postDelayed(this, 60_000)
        }
    }

    override fun onCreate() {
        super.onCreate()
        ensureChannels()
        client = ShibaClient(DeviceTools(this), this)
        ShibaRepo.client = client
        Companion.instance = this
        showRest(kick = true)
        main.postDelayed(clock, 60_000)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        dropRunningNotice()
        when (intent?.action) {
            ACTION_BOOP -> if (!petBusy()) {
                retries = 0
                val ask = boopLocal(streamFact = true)
                if (ask) requestFact()
                else if (!client.connected) connect()
                syncBusy()
            }
            ACTION_HEY -> if (!petBusy()) {
                retries = 0
                boopLocal(streamFact = false)
                sendOrQueue(getString(R.string.boop_prompt), emptyList())
                syncBusy()
            }
            ACTION_CHAT -> {
                val text = intent.getStringExtra(EXTRA_TEXT).orEmpty()
                val atts = parseAttachments(intent.getStringExtra(EXTRA_ATTACHMENTS))
                if (text.isNotBlank() || atts.isNotEmpty()) sendOrQueue(text, atts)
            }
            else -> {
                retries = 0
                connect()
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        main.removeCallbacks(digestTick)
        main.removeCallbacks(reconnect)
        main.removeCallbacks(anim)
        main.removeCallbacks(clock)
        main.removeCallbacks(factWatch)
        client.disconnect()
        busy = false
        if (ShibaRepo.client === client) ShibaRepo.client = null
        if (Companion.instance === this) Companion.instance = null
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun petBusy(): Boolean =
        oneShot || factLive || writing || ShibaRepo.processing.value || outbound.isNotEmpty()

    private fun syncBusy() {
        busy = petBusy()
    }

    private fun sendOrQueue(text: String, atts: List<AttachmentRef>) {
        writing = true
        if (client.connected) {
            client.sendChat(text, atts)
        } else {
            outbound.addLast(Outbound(text, atts))
            connect()
        }
        syncBusy()
    }

    private fun requestFact() {
        factLive = true
        armFactWatch()
        if (client.connected) {
            client.sendFact(Prefs.replyLang(this))
        } else {
            outbound.addLast(Outbound("", emptyList(), fact = true))
            connect()
        }
        syncBusy()
    }

    private fun flushOutbound() {
        while (client.connected && outbound.isNotEmpty()) {
            val item = outbound.removeFirst()
            if (item.fact) client.sendFact(Prefs.replyLang(this))
            else client.sendChat(item.text, item.atts)
        }
    }

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

    private fun boopLocal(streamFact: Boolean): Boolean {
        val now = java.time.LocalTime.now()
        if (restAt(now.hour, now.minute, awake = false) == Rest.SLEEP) {
            Prefs.setAwakeUntil(this, System.currentTimeMillis() + wakeMs)
        }
        val home = homeClip()
        Prefs.setRestClip(this, home.name)
        val last = Clip.entries.firstOrNull { it.name == Prefs.lastGesture(this) }
        val clip = Clip.tapPool(last).random()
        Prefs.setLastGesture(this, clip.name)
        oneShot = true
        Prefs.setClip(this, clip.name)
        Prefs.setFrame(this, 0)
        Prefs.setMood(this, Mood.BOOP)
        ShibaRepo.setMood(Mood.BOOP)
        val ask = streamFact && ShibaRepo.askWorldFact()
        factLive = ask
        factShown = ""
        if (ask) {
            Prefs.setBubble(this, "")
            ShibaRepo.setBubble("")
        } else {
            val line = ShibaRepo.pickLine()
            Prefs.setBubble(this, line)
            ShibaRepo.setBubble(line)
        }
        ShibaWidget.refresh(this)
        arm(clip)
        vibrate()
        syncBusy()
        return ask
    }

    private fun currentClip(): Clip =
        Clip.entries.firstOrNull { it.name == Prefs.clipName(this) }
            ?: Clip.forMood(Mood.from(Prefs.mood(this)))

    private fun homeClip(): Clip {
        val now = java.time.LocalTime.now()
        val awake = System.currentTimeMillis() < Prefs.awakeUntil(this)
        return Clip.homeFor(restAt(now.hour, now.minute, awake))
    }

    private fun played(clip: Clip): List<Int> {
        val home = Clip.entries.firstOrNull { it.name == Prefs.restClip(this) }
            ?: Clip.IDLE
        return clip.playedFrames(home.frameDrawables.first())
    }

    private fun showRest(kick: Boolean = false) {
        val clip = homeClip()
        val mood = if (clip == Clip.SLEEP) Mood.SLEEP else Mood.IDLE
        Prefs.setMood(this, mood)
        ShibaRepo.setMood(mood)
        Prefs.setRestClip(this, clip.name)
        if (Prefs.clipName(this) == clip.name) {
            if (kick) arm(clip)
            return
        }
        Prefs.setClip(this, clip.name)
        Prefs.setFrame(this, 0)
        ShibaWidget.refresh(this)
        arm(clip)
    }

    private fun arm(clip: Clip) {
        main.removeCallbacks(anim)
        val count = played(clip).size
        if (count <= 1) return
        val delay = if (clip.looping) clip.restMs else frameHoldMs(0, count, clip.intervalMs)
        main.postDelayed(anim, delay)
    }

    private val anim = Runnable { stepFrame() }

    private fun stepFrame() {
        val clip = currentClip()
        val count = played(clip).size
        if (count <= 1) return
        val next = Prefs.frameIndex(this) + 1
        if (next >= count) {
            if (!clip.looping) {
                oneShot = false
                showRest()
                syncBusy()
                return
            }
            Prefs.setFrame(this, 0)
            ShibaWidget.refresh(this)
            val pause = if (clip.restMs > 0) clip.restMs else clip.intervalMs.toLong()
            main.postDelayed(anim, pause)
            return
        }
        Prefs.setFrame(this, next)
        ShibaWidget.refresh(this)
        val delay = if (clip.looping) {
            clip.intervalMs.toLong()
        } else {
            frameHoldMs(next, count, clip.intervalMs)
        }
        main.postDelayed(anim, delay)
    }

    private fun vibrate() {
        val vibe = if (Build.VERSION.SDK_INT >= 31) {
            getSystemService(VibratorManager::class.java).defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            getSystemService(Vibrator::class.java)
        }
        vibe.vibrate(VibrationEffect.createOneShot(40, VibrationEffect.DEFAULT_AMPLITUDE))
    }

    override fun onHello(ok: Boolean, error: String?) {
        ShibaRepo.setConnected(ok)
        if (ok) {
            retries = 0
            if (!oneShot) showRest()
            ShibaRepo.setStatus(getString(R.string.status_online))
            val deviceSession = "android:${Prefs.deviceId(this)}"
            val current = ShibaRepo.sessionId.value
            if (current.isNullOrBlank()) {
                ShibaRepo.setSessionIdFromServer(deviceSession)
            } else if (current != deviceSession) {
                client.switchSession(current)
            }
            ShibaRepo.openAuthed()
            flushOutbound()
            client.requestDigest()
            main.removeCallbacks(digestTick)
            main.postDelayed(digestTick, digestEveryMs)
        } else {
            onMood(Mood.ERROR)
            ShibaRepo.setStatus(error ?: getString(R.string.status_offline))
        }
    }

    override fun onToken(token: String) {
        Prefs.setToken(this, token)
    }

    override fun onMood(mood: Mood) {
        Prefs.setMood(this, mood)
        ShibaRepo.setMood(mood)
        if (oneShot && mood != Mood.ERROR) {
            ShibaWidget.refresh(this)
            return
        }
        if (mood == Mood.ERROR) {
            Prefs.setClip(this, Clip.ERROR.name)
            Prefs.setFrame(this, 0)
            ShibaWidget.refresh(this)
            arm(Clip.ERROR)
            return
        }
        if (mood == Mood.THINK && !oneShot) {
            Prefs.setClip(this, Clip.THINK.name)
            Prefs.setFrame(this, 0)
            ShibaWidget.refresh(this)
            return
        }
        showRest()
    }

    override fun onBubble(text: String) {
        ShibaRepo.setBubble(text)
        ShibaWidget.refresh(this)
    }

    override fun onChatDelta(text: String) {
        ShibaRepo.onChatDelta(text)
    }

    override fun onFactDelta(text: String) {
        if (!factLive || text.isEmpty()) return
        factShown += text
        paintBubble(factShown, force = false)
    }

    override fun onFactDone(text: String) {
        factLive = false
        main.removeCallbacks(factWatch)
        val line = text.ifBlank { factShown }
        factShown = line
        if (line.isNotBlank()) paintBubble(line, force = true)
        syncBusy()
    }

    override fun onFactError() {
        factLive = false
        main.removeCallbacks(factWatch)
        syncBusy()
    }

    private fun armFactWatch() {
        main.removeCallbacks(factWatch)
        main.postDelayed(factWatch, 30_000)
    }

    private val factWatch = Runnable {
        factLive = false
        syncBusy()
    }

    private fun paintBubble(text: String, force: Boolean) {
        Prefs.setBubble(this, text)
        ShibaRepo.setBubble(text)
        val now = android.os.SystemClock.uptimeMillis()
        if (!force && now - bubblePaintAt < 280) return
        bubblePaintAt = now
        ShibaWidget.refresh(this)
    }

    override fun onChatDone(text: String) {
        val fromFact = factLive
        factLive = false
        writing = false
        ShibaRepo.onChatDone(text)
        onMood(Mood.ALERT)
        if (!fromFact && !Prefs.chatForeground(this) && text.isNotBlank()) {
            notifyReply(text)
        }
        main.postDelayed({
            if (Prefs.mood(this) == Mood.ALERT.name) onMood(Mood.IDLE)
        }, 2500)
        syncBusy()
    }

    override fun onThinking(text: String) {
        ShibaRepo.onThinking(text)
    }

    override fun onTool(name: String, detail: String) {
        ShibaRepo.onTool(name, detail)
    }

    override fun onInteractive(card: ChatItem.Interactive) {
        ShibaRepo.onInteractive(card)
    }

    override fun onQueued(position: Int) {
        ShibaRepo.onQueued(position)
    }

    override fun onSessionStatus(processing: Boolean) {
        ShibaRepo.setProcessing(processing)
        if (!processing) writing = false
        syncBusy()
    }

    override fun onSessionReset(sessionId: String?) {
        if (sessionId != null) {
            ShibaRepo.setSessionIdFromServer(sessionId)
            ShibaRepo.clearMessages()
        }
        ShibaRepo.refreshSessions()
    }

    override fun onSystemEvent(text: String) {
        ShibaRepo.onSystem(text)
        if (!Prefs.chatForeground(this) && text.isNotBlank()) {
            notifyReply(text)
        }
    }

    override fun onDigest(digest: Digest) {
        ShibaRepo.setDigest(digest)
        ShibaWidget.refresh(this)
    }

    override fun onClosed() {
        factLive = false
        main.removeCallbacks(factWatch)
        writing = false
        showRest()
        syncBusy()
        ShibaRepo.setConnected(false)
        ShibaRepo.setStatus(getString(R.string.status_offline))
        main.removeCallbacks(digestTick)
        if (!running || !Prefs.isPaired(this)) return
        retries += 1
        val delay = (2000L * retries).coerceAtMost(30_000L)
        main.removeCallbacks(reconnect)
        main.postDelayed(reconnect, delay)
    }

    private fun notifyReply(text: String) {
        val open = PendingIntent.getActivity(
            this,
            1,
            Intent(this, MainActivity::class.java).putExtra(
                MainActivity.EXTRA_SESSION,
                ShibaRepo.sessionId.value,
            ),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val n = NotificationCompat.Builder(this, CHANNEL_REPLIES)
            .setSmallIcon(R.drawable.shiba_idle)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(text.take(160))
            .setStyle(NotificationCompat.BigTextStyle().bigText(text.take(800)))
            .setContentIntent(open)
            .setAutoCancel(true)
            .build()
        getSystemService(NotificationManager::class.java).notify(
            (System.currentTimeMillis() % 100000).toInt() + 100,
            n,
        )
    }

    private fun ensureChannels() {
        val mgr = getSystemService(NotificationManager::class.java)
        val quiet = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.notif_channel),
            NotificationManager.IMPORTANCE_MIN,
        )
        quiet.setShowBadge(false)
        quiet.setSound(null, null)
        mgr.createNotificationChannel(quiet)
        mgr.createNotificationChannel(
            NotificationChannel(
                CHANNEL_REPLIES,
                getString(R.string.notif_replies_channel),
                NotificationManager.IMPORTANCE_DEFAULT,
            ),
        )
    }

    private fun buildServiceNotif(text: String): Notification {
        val open = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.shiba_idle)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(text)
            .setContentIntent(open)
            .setSilent(true)
            .setOngoing(true)
            .build()
    }

    private fun dropRunningNotice() {
        if (!needsNotice) return
        val notif = buildServiceNotif(getString(R.string.notif_title))
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIF_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(NOTIF_ID, notif)
        }
        stopForeground(STOP_FOREGROUND_REMOVE)
        getSystemService(NotificationManager::class.java).cancel(NOTIF_ID)
        needsNotice = false
    }

    private var bubblePaintAt = 0L

    private data class Outbound(
        val text: String,
        val atts: List<AttachmentRef>,
        val fact: Boolean = false,
    )

    companion object {
        const val CHANNEL_ID = "shiba_quiet"
        const val CHANNEL_REPLIES = "replies"
        const val NOTIF_ID = 7
        const val ACTION_BOOP = "com.shibaclaw.companion.BOOP"
        const val ACTION_HEY = "com.shibaclaw.companion.HEY"
        const val ACTION_CHAT = "com.shibaclaw.companion.CHAT"
        const val EXTRA_TEXT = "text"
        const val EXTRA_ATTACHMENTS = "attachments"

        @Volatile
        var instance: ShibaService? = null

        @Volatile
        var needsNotice = true

        @Volatile
        var busy = false

        fun start(
            ctx: Context,
            action: String? = null,
            text: String? = null,
            attachments: List<AttachmentRef> = emptyList(),
        ) {
            val i = Intent(ctx, ShibaService::class.java)
            if (action != null) i.action = action
            if (text != null) i.putExtra(EXTRA_TEXT, text)
            if (attachments.isNotEmpty()) {
                val arr = JSONArray()
                attachments.forEach { a ->
                    arr.put(
                        JSONObject()
                            .put("name", a.name)
                            .put("url", a.url)
                            .put("type", a.type),
                    )
                }
                i.putExtra(EXTRA_ATTACHMENTS, arr.toString())
            }
            if (instance == null) {
                needsNotice = true
                ctx.startForegroundService(i)
            } else {
                try {
                    ctx.startService(i)
                } catch (_: IllegalStateException) {
                    needsNotice = true
                    ctx.startForegroundService(i)
                }
            }
        }

        fun parseAttachments(raw: String?): List<AttachmentRef> {
            if (raw.isNullOrBlank()) return emptyList()
            return try {
                val arr = JSONArray(raw)
                buildList {
                    for (i in 0 until arr.length()) {
                        val o = arr.getJSONObject(i)
                        add(
                            AttachmentRef(
                                o.optString("name"),
                                o.optString("url"),
                                o.optString("type"),
                            ),
                        )
                    }
                }
            } catch (_: Exception) {
                emptyList()
            }
        }
    }
}
