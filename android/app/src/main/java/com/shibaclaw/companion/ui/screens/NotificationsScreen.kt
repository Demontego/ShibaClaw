package com.shibaclaw.companion.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.shibaclaw.companion.data.ShibaRepo
import com.shibaclaw.companion.ui.theme.shibaBarColors

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotificationsScreen(onBack: () -> Unit) {
    val items by ShibaRepo.notifications.collectAsState()
    LaunchedEffect(Unit) { ShibaRepo.refreshNotifications() }

    Scaffold(
        topBar = {
            TopAppBar(
                colors = shibaBarColors(),
                title = { Text("Notifications") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    TextButton(onClick = { ShibaRepo.clearNotifications() }) {
                        Text("Clear")
                    }
                },
            )
        },
    ) { padding ->
        if (items.isEmpty()) {
            Text(
                "No notifications",
                modifier = Modifier
                    .padding(padding)
                    .padding(24.dp),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            LazyColumn(
                Modifier
                    .fillMaxSize()
                    .padding(padding),
            ) {
                items(items, key = { it.id.ifBlank { it.hashCode().toString() } }) { n ->
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                    ) {
                        Text(
                            n.title.ifBlank { "Shiba" },
                            style = MaterialTheme.typography.titleSmall,
                        )
                        Text(
                            n.body.ifBlank { n.message },
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        n.session_key?.let {
                            Text(
                                it,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    HorizontalDivider()
                }
            }
        }
    }
}
