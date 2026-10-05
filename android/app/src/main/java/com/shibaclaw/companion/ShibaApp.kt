package com.shibaclaw.companion

import android.app.Application
import com.shibaclaw.companion.data.ShibaRepo

class ShibaApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Prefs.init(this)
        ShibaRepo.init(this)
    }
}
