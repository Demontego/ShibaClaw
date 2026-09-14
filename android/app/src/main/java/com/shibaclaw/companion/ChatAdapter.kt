package com.shibaclaw.companion

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

class ChatAdapter : RecyclerView.Adapter<ChatAdapter.Holder>() {
    private val items = mutableListOf<ChatLine>()

    fun add(line: ChatLine) {
        items.add(line)
        notifyItemInserted(items.lastIndex)
    }

    fun appendToLast(delta: String) {
        if (items.isEmpty() || items.last().fromUser) {
            add(ChatLine(fromUser = false, text = delta))
            return
        }
        val last = items.last()
        items[items.lastIndex] = last.copy(text = last.text + delta)
        notifyItemChanged(items.lastIndex)
    }

    fun lastPosition(): Int = items.lastIndex

    override fun getItemViewType(position: Int): Int = if (items[position].fromUser) 1 else 0

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder {
        val layout = if (viewType == 1) R.layout.item_msg_user else R.layout.item_msg_shiba
        val view = LayoutInflater.from(parent.context).inflate(layout, parent, false)
        return Holder(view)
    }

    override fun onBindViewHolder(holder: Holder, position: Int) {
        holder.bubble.text = items[position].text
    }

    override fun getItemCount(): Int = items.size

    class Holder(view: View) : RecyclerView.ViewHolder(view) {
        val bubble: TextView = view.findViewById(R.id.bubble)
    }
}

data class ChatLine(val fromUser: Boolean, val text: String)
