package com.shibaclaw.companion

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class PairActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_pair)
        val host = findViewById<EditText>(R.id.host)
        val port = findViewById<EditText>(R.id.port)
        val token = findViewById<EditText>(R.id.token)
        val status = findViewById<TextView>(R.id.status)
        val face = findViewById<ImageView>(R.id.pair_face)
        host.setText(Prefs.host(this))
        port.setText(Prefs.port(this).toString())
        token.setText(Prefs.token(this))
        face.setImageResource(Mood.from(Prefs.mood(this)).drawable())

        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
        findViewById<Button>(R.id.connect).setOnClickListener {
            val h = host.text.toString().trim()
            val p = port.text.toString().toIntOrNull() ?: 19998
            if (h.isEmpty()) {
                Toast.makeText(this, R.string.host_hint, Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            Prefs.savePair(this, h, p, token.text.toString())
            status.setText(R.string.status_online)
            ShibaService.start(this)
            Toast.makeText(this, R.string.add_widget_hint, Toast.LENGTH_LONG).show()
        }
        findViewById<Button>(R.id.open_chat).setOnClickListener {
            startActivity(android.content.Intent(this, ChatActivity::class.java))
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
