package com.shibaclaw.companion

import android.app.Application

class ShibaApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Prefs.init(this)
    }
}
