package com.shibaclaw.companion.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.shibaclaw.companion.ui.theme.shibaBarColors
import com.shibaclaw.companion.data.ShibaRepo

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AutomationScreen(onBack: () -> Unit) {
    val jobs by ShibaRepo.jobs.collectAsState()
    val error by ShibaRepo.jobsError.collectAsState()
    var creating by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) { ShibaRepo.refreshJobs() }

    Scaffold(
        topBar = {
            TopAppBar(
                colors = shibaBarColors(),
                title = { Text("Automation") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { creating = true }) {
                        Icon(Icons.Default.Add, contentDescription = "New job")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            if (error.isNotBlank()) {
                Text(
                    error,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                )
            }
            if (jobs.isEmpty() && error.isBlank()) {
                Text(
                    "No jobs yet. A job sends a message to the current agent on a schedule.",
                    modifier = Modifier.padding(16.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            LazyColumn(Modifier.weight(1f)) {
                items(jobs, key = { it.id }) { job ->
                    Column(Modifier.padding(horizontal = 16.dp, vertical = 10.dp)) {
                        Row(
                            Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(job.name, style = MaterialTheme.typography.titleSmall)
                                Text(
                                    job.schedule,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            Switch(
                                checked = job.enabled,
                                onCheckedChange = { ShibaRepo.setJobEnabled(job.id, it) },
                            )
                        }
                        if (job.message.isNotBlank()) {
                            Text(
                                job.message,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis,
                                style = MaterialTheme.typography.bodyMedium,
                            )
                        }
                        if (job.lastStatus.isNotBlank()) {
                            Text(
                                job.lastStatus,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Row {
                            TextButton(onClick = { ShibaRepo.triggerJob(job.id) }) {
                                Icon(Icons.Default.PlayArrow, contentDescription = null)
                                Text("Run")
                            }
                            TextButton(onClick = { ShibaRepo.deleteJob(job.id) }) {
                                Icon(Icons.Default.Delete, contentDescription = null)
                                Text("Delete")
                            }
                        }
                    }
                }
            }
        }
    }

    if (creating) {
        NewJobDialog(onDismiss = { creating = false })
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun NewJobDialog(onDismiss: () -> Unit) {
    var name by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("") }
    var kind by remember { mutableStateOf("every") }
    var everyMin by remember { mutableIntStateOf(30) }
    var cron by remember { mutableStateOf("0 9 * * *") }
    var inMin by remember { mutableLongStateOf(60L) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("New job") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Name") },
                    singleLine = true,
                )
                OutlinedTextField(
                    value = message,
                    onValueChange = { message = it },
                    label = { Text("Message to the agent") },
                    minLines = 2,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(selected = kind == "every", onClick = { kind = "every" }, label = { Text("Every") })
                    FilterChip(selected = kind == "cron", onClick = { kind = "cron" }, label = { Text("Cron") })
                    FilterChip(selected = kind == "at", onClick = { kind = "at" }, label = { Text("Once") })
                }
                when (kind) {
                    "every" -> OutlinedTextField(
                        value = everyMin.toString(),
                        onValueChange = { everyMin = it.toIntOrNull() ?: everyMin },
                        label = { Text("Minutes") },
                        singleLine = true,
                    )
                    "cron" -> OutlinedTextField(
                        value = cron,
                        onValueChange = { cron = it },
                        label = { Text("Cron") },
                        singleLine = true,
                    )
                    else -> OutlinedTextField(
                        value = inMin.toString(),
                        onValueChange = { inMin = it.toLongOrNull() ?: inMin },
                        label = { Text("Minutes from now") },
                        singleLine = true,
                    )
                }
                Text(
                    "Runs as the agent of the open chat.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val atMs = System.currentTimeMillis() + inMin.coerceAtLeast(1) * 60_000L
                    ShibaRepo.createJob(name, message, kind, everyMin, cron, atMs)
                    onDismiss()
                },
                enabled = message.isNotBlank() && (kind != "cron" || cron.isNotBlank()),
            ) { Text("Save") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}
