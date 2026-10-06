package com.shibaclaw.companion.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Archive
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.shibaclaw.companion.data.ShibaRepo

@Composable
fun SessionsDrawer(onClose: () -> Unit) {
    val sessions by ShibaRepo.sessions.collectAsState()
    val current by ShibaRepo.sessionId.collectAsState()
    val profiles by ShibaRepo.profiles.collectAsState()
    val currentProfile by ShibaRepo.sessionProfile.collectAsState()
    var query by remember { mutableStateOf("") }
    var renameKey by remember { mutableStateOf<String?>(null) }
    var renameText by remember { mutableStateOf("") }

    ModalDrawerSheet(modifier = Modifier.width(320.dp)) {
        Column(
            Modifier
                .fillMaxHeight()
                .padding(16.dp),
        ) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Chats", style = MaterialTheme.typography.titleLarge)
                IconButton(
                    onClick = {
                        ShibaRepo.newSession(currentProfile)
                        onClose()
                    },
                ) {
                    Icon(Icons.Default.Add, contentDescription = "New")
                }
            }
            OutlinedTextField(
                value = query,
                onValueChange = {
                    query = it
                    ShibaRepo.searchSessions(it)
                },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("Search") },
                singleLine = true,
            )
            Spacer(Modifier.height(8.dp))
            HorizontalDivider()
            LazyColumn(Modifier.weight(1f)) {
                items(sessions, key = { it.key }) { s ->
                    val selected = s.key == current
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .clickable {
                                ShibaRepo.switchSession(s.key)
                                onClose()
                            }
                            .padding(vertical = 10.dp),
                    ) {
                        val agent = profiles.firstOrNull { it.id == s.profileId }?.title()
                            ?: s.profileId
                        Text(
                            s.nickname?.takeIf { it.isNotBlank() }
                                ?: "Chat " + s.key.substringAfterLast(':').take(8),
                            style = MaterialTheme.typography.titleSmall,
                            color = if (selected) {
                                MaterialTheme.colorScheme.primary
                            } else {
                                MaterialTheme.colorScheme.onSurface
                            },
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        if (s.preview.isNotBlank()) {
                            Text(
                                s.preview,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                        Text(
                            listOf(agent, ago(s.updatedAt)).filter { it.isNotBlank() }.joinToString(" · "),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Row {
                            TextButton(
                                onClick = {
                                    renameKey = s.key
                                    renameText = s.nickname.orEmpty()
                                },
                            ) { Text("Rename") }
                            IconButton(onClick = { ShibaRepo.archiveSession(s.key) }) {
                                Icon(Icons.Default.Archive, contentDescription = "Archive")
                            }
                            IconButton(onClick = { ShibaRepo.deleteSession(s.key) }) {
                                Icon(Icons.Default.Delete, contentDescription = "Delete")
                            }
                        }
                    }
                    HorizontalDivider()
                }
            }
        }
    }

    renameKey?.let { key ->
        androidx.compose.material3.AlertDialog(
            onDismissRequest = { renameKey = null },
            title = { Text("Rename") },
            text = {
                OutlinedTextField(
                    value = renameText,
                    onValueChange = { renameText = it },
                    singleLine = true,
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        ShibaRepo.patchSession(mapOf("nickname" to renameText), sessionId = key)
                        renameKey = null
                    },
                ) { Text("Save") }
            },
            dismissButton = {
                TextButton(onClick = { renameKey = null }) { Text("Cancel") }
            },
        )
    }
}

private fun ago(ms: Long): String {
    if (ms <= 0L) return ""
    val min = (System.currentTimeMillis() - ms) / 60_000L
    return when {
        min < 1 -> "now"
        min < 60 -> "${min}m"
        min < 60 * 24 -> "${min / 60}h"
        else -> "${min / (60 * 24)}d"
    }
}
