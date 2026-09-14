package com.shibaclaw.companion

import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView

class ChatActivity : AppCompatActivity() {
    private val adapter = ChatAdapter()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContentView(R.layout.activity_chat)
        val root = findViewById<android.view.View>(R.id.chat_root)
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, insets ->
            val bars = insets.getInsets(
                WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime(),
            )
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }
        val face = findViewById<ImageView>(R.id.chat_face)
        val status = findViewById<TextView>(R.id.chat_status)
        val list = findViewById<RecyclerView>(R.id.messages)
        val input = findViewById<EditText>(R.id.input)
        face.setImageResource(Mood.from(Prefs.mood(this)).drawable())
        list.layoutManager = LinearLayoutManager(this).apply { stackFromEnd = true }
        list.adapter = adapter
        if (Prefs.lastBubble(this).isNotBlank()) {
            adapter.add(ChatLine(fromUser = false, text = Prefs.lastBubble(this)))
        }
        ShibaService.start(this)
        findViewById<Button>(R.id.send).setOnClickListener {
            val text = input.text.toString().trim()
            if (text.isEmpty()) return@setOnClickListener
            adapter.add(ChatLine(fromUser = true, text = text))
            list.scrollToPosition(adapter.lastPosition())
            input.setText("")
            ShibaService.start(this, ShibaService.ACTION_CHAT, text)
        }
        ChatBus.moodListener = { runOnUiThread { face.setImageResource(it.drawable()) } }
        ChatBus.statusListener = { runOnUiThread { status.text = it } }
        ChatBus.doneListener = { text ->
            runOnUiThread {
                if (text.isNotBlank()) {
                    adapter.add(ChatLine(fromUser = false, text = text))
                    list.scrollToPosition(adapter.lastPosition())
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
