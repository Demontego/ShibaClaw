package com.shibaclaw.companion.ui.screens

import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.shibaclaw.companion.Prefs
import com.shibaclaw.companion.R
import com.shibaclaw.companion.data.ShibaRepo
import com.shibaclaw.companion.data.ThemeMode

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(onBack: () -> Unit, onRePair: () -> Unit) {
    val ctx = LocalContext.current
    val theme by ShibaRepo.theme.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
        ) {
            Text("Server", style = MaterialTheme.typography.titleMedium)
            Text(Prefs.baseUrl(ctx).ifBlank { "—" })
            Text(Prefs.username(ctx))
            Spacer(Modifier.height(8.dp))
            Button(onClick = onRePair, modifier = Modifier.fillMaxWidth()) {
                Text("Re-pair account")
            }
            OutlinedButton(
                onClick = {
                    Prefs.clearPair(ctx)
                    onRePair()
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Sign out")
            }
            Spacer(Modifier.height(24.dp))
            Text("Theme", style = MaterialTheme.typography.titleMedium)
            ThemeMode.entries.forEach { mode ->
                OutlinedButton(
                    onClick = { ShibaRepo.setTheme(mode) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text((if (theme == mode) "✓ " else "") + mode.name.lowercase().replaceFirstChar { it.uppercase() })
                }
            }
            Spacer(Modifier.height(24.dp))
            Text("Widget", style = MaterialTheme.typography.titleMedium)
            Text(stringResource(R.string.add_widget_hint))
            Spacer(Modifier.height(8.dp))
            Button(
                onClick = {
                    ctx.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.notif_listener_button))
            }
            Text(
                stringResource(R.string.notif_listener_hint),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
