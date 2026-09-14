package com.shibaclaw.companion

import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class ChatActivity : AppCompatActivity() {
    private val buf = StringBuilder()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_chat)
        val face = findViewById<ImageView>(R.id.chat_face)
        val status = findViewById<TextView>(R.id.chat_status)
        val transcript = findViewById<TextView>(R.id.transcript)
        val scroll = findViewById<ScrollView>(R.id.transcript_scroll)
        val input = findViewById<EditText>(R.id.input)
        face.setImageResource(Mood.from(Prefs.mood(this)).drawable())
        if (Prefs.lastBubble(this).isNotBlank()) {
            buf.append("Shiba: ").append(Prefs.lastBubble(this)).append("\n")
            transcript.text = buf
        }
        ShibaService.start(this)
        findViewById<Button>(R.id.send).setOnClickListener {
            val text = input.text.toString().trim()
            if (text.isEmpty()) return@setOnClickListener
            buf.append("You: ").append(text).append("\n")
            transcript.text = buf
            input.setText("")
            ShibaService.start(this, ShibaService.ACTION_CHAT, text)
        }
        ChatBus.moodListener = { runOnUiThread { face.setImageResource(it.drawable()) } }
        ChatBus.statusListener = { runOnUiThread { status.text = it } }
        ChatBus.doneListener = { text ->
            runOnUiThread {
                if (text.isNotBlank()) {
                    buf.append("Shiba: ").append(text).append("\n\n")
                    transcript.text = buf
                    scroll.post { scroll.fullScroll(ScrollView.FOCUS_DOWN) }
                }
            }
        }
    }

    override fun onDestroy() {
        ChatBus.moodListener = null
        ChatBus.statusListener = null
        ChatBus.deltaListener = null
        ChatBus.doneListener = null
        super.onDestroy()
    }
}
