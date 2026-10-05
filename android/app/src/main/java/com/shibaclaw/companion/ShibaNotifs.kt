package com.shibaclaw.companion

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import com.shibaclaw.companion.data.ShibaRepo

class ShibaNotifs : NotificationListenerService() {
    override fun onListenerConnected() {
        super.onListenerConnected()
        publish()
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        publish()
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
        publish()
    }

    private fun publish() {
        val counts = linkedMapOf<String, Int>()
        val active = try {
            activeNotifications
        } catch (_: Exception) {
            null
        } ?: return
        for (sbn in active) {
            if (sbn.isOngoing || sbn.packageName == packageName) continue
            val label = try {
                val info = packageManager.getApplicationInfo(sbn.packageName, 0)
                packageManager.getApplicationLabel(info).toString()
            } catch (_: Exception) {
                sbn.packageName
            }
            counts[label] = (counts[label] ?: 0) + 1
        }
        ShibaRepo.setPhoneNotifCounts(counts)
    }
}
