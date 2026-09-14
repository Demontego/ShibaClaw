package com.shibaclaw.companion

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

class PairActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContentView(R.layout.activity_pair)
        val root = findViewById<android.view.View>(R.id.pair_root)
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }
        val url = findViewById<EditText>(R.id.url)
        val username = findViewById<EditText>(R.id.username)
        val password = findViewById<EditText>(R.id.password)
        val status = findViewById<TextView>(R.id.status)
        val face = findViewById<ImageView>(R.id.pair_face)
        url.setText(Prefs.baseUrl(this))
        username.setText(Prefs.username(this))
        password.setText(Prefs.password(this))
        face.setImageResource(Mood.from(Prefs.mood(this)).drawable())

        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
        findViewById<Button>(R.id.connect).setOnClickListener {
            val raw = url.text.toString().trim()
            if (raw.isEmpty()) {
                Toast.makeText(this, R.string.url_hint, Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            Prefs.savePair(this, raw, username.text.toString(), password.text.toString())
            status.setText(R.string.status_connecting)
            ShibaService.start(this)
            startActivity(Intent(this, ChatActivity::class.java))
        }
        findViewById<Button>(R.id.open_chat).setOnClickListener {
            startActivity(Intent(this, ChatActivity::class.java))
        }
        ChatBus.statusListener = { runOnUiThread { status.text = it } }
        ChatBus.moodListener = { runOnUiThread { face.setImageResource(it.drawable()) } }
    }

    override fun onDestroy() {
        ChatBus.statusListener = null
        ChatBus.moodListener = null
        super.onDestroy()
    }
}
