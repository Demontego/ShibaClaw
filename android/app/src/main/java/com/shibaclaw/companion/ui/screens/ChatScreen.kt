package com.shibaclaw.companion.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AddPhotoAlternate
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberDrawerState
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import coil.compose.AsyncImage
import com.mikepenz.markdown.compose.components.markdownComponents
import com.mikepenz.markdown.compose.elements.highlightedCodeBlock
import com.mikepenz.markdown.compose.elements.highlightedCodeFence
import com.mikepenz.markdown.m3.Markdown
import com.shibaclaw.companion.Prefs
import com.shibaclaw.companion.ShibaService
import com.shibaclaw.companion.data.AttachmentRef
import com.shibaclaw.companion.data.ChatItem
import com.shibaclaw.companion.data.ShibaApi
import com.shibaclaw.companion.data.ShibaRepo
import com.shibaclaw.companion.ui.theme.shibaBarColors
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    onOpenSettings: () -> Unit,
    onOpenNotifications: () -> Unit,
    onOpenAutomation: () -> Unit,
) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val messages by ShibaRepo.messages.collectAsState()
    val mood by ShibaRepo.mood.collectAsState()
    val status by ShibaRepo.status.collectAsState()
    val processing by ShibaRepo.processing.collectAsState()
    val queued by ShibaRepo.queued.collectAsState()
    val sessionModel by ShibaRepo.sessionModel.collectAsState()
    val sessionProfile by ShibaRepo.sessionProfile.collectAsState()
    val sessionNick by ShibaRepo.sessionNick.collectAsState()
    val models by ShibaRepo.models.collectAsState()
    val profiles by ShibaRepo.profiles.collectAsState()
    val snackbar = remember { SnackbarHostState() }
    var input by remember { mutableStateOf("") }
    val pending = remember { mutableStateListOf<AttachmentRef>() }
    var uploading by remember { mutableStateOf(false) }
    var showPicker by remember { mutableStateOf(false) }
    var cameraUri by remember { mutableStateOf<Uri?>(null) }
    val listState = rememberLazyListState()

    DisposableEffect(Unit) {
        Prefs.setChatForeground(ctx, true)
        ShibaService.start(ctx)
        ShibaRepo.refreshSessions()
        ShibaRepo.ensureHistory()
        ShibaRepo.refreshModelsAndProfiles()
        onDispose { Prefs.setChatForeground(ctx, false) }
    }

    val tailLen = (messages.lastOrNull() as? ChatItem.Message)?.text?.length ?: 0
    LaunchedEffect(messages.size, tailLen) {
        val atTail = listState.firstVisibleItemIndex == 0 && listState.firstVisibleItemScrollOffset == 0
        if (messages.isNotEmpty() && atTail) {
            listState.scrollToItem(0)
        }
    }
    LaunchedEffect(Unit) {
        ShibaRepo.events.collect { snackbar.showSnackbar(it) }
    }

    fun uploadUri(uri: Uri, mime: String, name: String) {
        scope.launch {
            uploading = true
            runCatching {
                withContext(Dispatchers.IO) {
                    val tmp = File(ctx.cacheDir, name)
                    ctx.contentResolver.openInputStream(uri)?.use { inputStream ->
                        FileOutputStream(tmp).use { output -> inputStream.copyTo(output) }
                    }
                    ShibaApi.upload(tmp, mime, name)
                }
            }.onSuccess { pending.add(it) }
            uploading = false
        }
    }

    val photoPicker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia(),
    ) { uri ->
        if (uri != null) {
            uploadUri(uri, "image/jpeg", "photo_${System.currentTimeMillis()}.jpg")
        }
    }
    val filePicker = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent(),
    ) { uri ->
        if (uri != null) {
            val mime = ctx.contentResolver.getType(uri) ?: "application/octet-stream"
            val name = uri.lastPathSegment?.substringAfterLast('/')
                ?: "file_${System.currentTimeMillis()}"
            uploadUri(uri, mime, name)
        }
    }
    val cameraLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.TakePicture(),
    ) { ok ->
        val uri = cameraUri
        if (ok && uri != null) {
            uploadUri(uri, "image/jpeg", "camera_${System.currentTimeMillis()}.jpg")
        }
    }

    fun launchCamera() {
        val file = File(ctx.cacheDir, "camera_${System.currentTimeMillis()}.jpg")
        val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.files", file)
        cameraUri = uri
        cameraLauncher.launch(uri)
    }

    val cameraPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) launchCamera()
    }

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            SessionsDrawer(
                onClose = { scope.launch { drawerState.close() } },
            )
        },
    ) {
        Scaffold(
            snackbarHost = { SnackbarHost(snackbar) },
            topBar = {
                TopAppBar(
                    colors = shibaBarColors(),
                    title = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Image(
                                painter = painterResource(mood.drawable()),
                                contentDescription = null,
                                modifier = Modifier.size(36.dp),
                            )
                            Spacer(Modifier.width(10.dp))
                            Column {
                                Text(
                                    sessionNick.ifBlank { "ShibaClaw" },
                                    style = MaterialTheme.typography.titleMedium,
                                    maxLines = 1,
                                )
                                Text(
                                    status,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    },
                    navigationIcon = {
                        IconButton(onClick = { scope.launch { drawerState.open() } }) {
                            Icon(Icons.Default.Menu, contentDescription = "Sessions")
                        }
                    },
                    actions = {
                        IconButton(onClick = onOpenAutomation) {
                            Icon(Icons.Default.Schedule, contentDescription = "Automation")
                        }
                        IconButton(onClick = onOpenNotifications) {
                            Icon(Icons.Default.Notifications, contentDescription = "Notifications")
                        }
                        IconButton(onClick = onOpenSettings) {
                            Icon(Icons.Default.Settings, contentDescription = "Settings")
                        }
                    },
                )
            },
        ) { padding ->
            Column(
                Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .imePadding(),
            ) {
                Row(
                    Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState())
                        .padding(horizontal = 12.dp, vertical = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    val agent = profiles.firstOrNull { it.id == sessionProfile }?.title()
                        ?: sessionProfile.ifBlank { "agent" }
                    val modelLabel = sessionModel.substringAfterLast('/').ifBlank { "model" }
                    AssistChip(onClick = { showPicker = true }, label = { Text(agent, maxLines = 1) })
                    AssistChip(onClick = { showPicker = true }, label = { Text(modelLabel, maxLines = 1) })
                    if (processing) {
                        AssistChip(
                            onClick = { ShibaRepo.client?.stop() },
                            label = { Text("Stop") },
                            leadingIcon = {
                                Icon(Icons.Default.Stop, contentDescription = null, Modifier.size(16.dp))
                            },
                        )
                    }
                    if (queued > 0) {
                        AssistChip(onClick = {}, label = { Text("Queued #$queued") })
                    }
                }
                LazyColumn(
                    state = listState,
                    reverseLayout = true,
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(messages.asReversed(), key = { it.id }) { item ->
                        ChatBubble(
                            item = item,
                            onToggle = { ShibaRepo.toggleCollapse(item.id) },
                            onReply = { requestId, body ->
                                ShibaRepo.client?.interactiveReply(requestId, body)
                                ShibaRepo.markInteractiveAnswered(requestId)
                            },
                        )
                    }
                }
                if (pending.isNotEmpty()) {
                    Row(
                        Modifier.padding(horizontal = 12.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        pending.forEach { att ->
                            AsyncImage(
                                model = att.url,
                                contentDescription = att.name,
                                modifier = Modifier
                                    .size(56.dp)
                                    .clip(RoundedCornerShape(8.dp))
                                    .clickable { pending.remove(att) },
                                contentScale = ContentScale.Crop,
                            )
                        }
                    }
                }
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    IconButton(onClick = {
                        photoPicker.launch(
                            PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly),
                        )
                    }) {
                        Icon(Icons.Default.AddPhotoAlternate, contentDescription = "Photo")
                    }
                    IconButton(onClick = {
                        val granted = ctx.checkSelfPermission(Manifest.permission.CAMERA) ==
                            PackageManager.PERMISSION_GRANTED
                        if (granted) launchCamera() else cameraPermission.launch(Manifest.permission.CAMERA)
                    }) {
                        Icon(Icons.Default.PhotoCamera, contentDescription = "Camera")
                    }
                    IconButton(onClick = { filePicker.launch("*/*") }) {
                        Icon(Icons.Default.AttachFile, contentDescription = "File")
                    }
                    OutlinedTextField(
                        value = input,
                        onValueChange = { input = it },
                        modifier = Modifier.weight(1f),
                        shape = MaterialTheme.shapes.medium,
                        placeholder = { Text("Tell Shiba…") },
                        maxLines = 5,
                    )
                    if (uploading) {
                        CircularProgressIndicator(Modifier.size(28.dp).padding(start = 8.dp))
                    } else {
                        IconButton(
                            onClick = {
                                val text = input.trim()
                                if (text.isEmpty() && pending.isEmpty()) return@IconButton
                                val atts = pending.toList()
                                pending.clear()
                                input = ""
                                ShibaRepo.appendUser(text.ifBlank { "(attachment)" }, atts)
                                ShibaService.start(
                                    ctx,
                                    ShibaService.ACTION_CHAT,
                                    text.ifBlank { " " },
                                    atts,
                                )
                            },
                        ) {
                            Icon(
                                Icons.AutoMirrored.Filled.Send,
                                contentDescription = "Send",
                                tint = MaterialTheme.colorScheme.primary,
                            )
                        }
                    }
                }
            }
        }
    }

    if (showPicker) {
        ModalBottomSheet(
            onDismissRequest = { showPicker = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        ) {
            ModelProfileSheet(
                models = models,
                profiles = profiles,
                currentModel = sessionModel,
                currentProfile = sessionProfile,
                onSelectModel = { ShibaRepo.patchSession(mapOf("model" to it)) },
                onSelectProfile = { ShibaRepo.patchSession(mapOf("profile_id" to it)) },
            )
        }
    }
}

@Composable
private fun ChatBubble(
    item: ChatItem,
    onToggle: () -> Unit,
    onReply: (String, JSONObject) -> Unit,
) {
    when (item) {
        is ChatItem.Message -> {
            val align = if (item.fromUser) Alignment.CenterEnd else Alignment.CenterStart
            Box(Modifier.fillMaxWidth(), contentAlignment = align) {
                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = if (item.fromUser) {
                        MaterialTheme.colorScheme.primaryContainer
                    } else {
                        MaterialTheme.colorScheme.surfaceVariant
                    },
                    modifier = if (item.fromUser) {
                        Modifier.widthIn(max = 300.dp)
                    } else {
                        Modifier.fillMaxWidth()
                    },
                ) {
                    Column(Modifier.padding(horizontal = 14.dp, vertical = 12.dp)) {
                        item.attachments.forEach { att ->
                            if (att.type.startsWith("image/")) {
                                AsyncImage(
                                    model = att.url,
                                    contentDescription = att.name,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(160.dp)
                                        .clip(RoundedCornerShape(8.dp)),
                                    contentScale = ContentScale.Crop,
                                )
                                Spacer(Modifier.height(6.dp))
                            } else {
                                Text(att.name, style = MaterialTheme.typography.labelMedium)
                            }
                        }
                        if (item.fromUser || !item.text.contains("```")) {
                            Text(
                                item.text.ifBlank { if (item.streaming) "…" else "" },
                                style = MaterialTheme.typography.bodyMedium,
                            )
                        } else {
                            Markdown(
                                content = item.text,
                                modifier = Modifier.fillMaxWidth(),
                                components = markdownComponents(
                                    codeBlock = highlightedCodeBlock,
                                    codeFence = highlightedCodeFence,
                                ),
                            )
                        }
                        if (item.time.isNotBlank()) {
                            Text(
                                item.time,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        }
        is ChatItem.Thinking -> {
            TextButton(onClick = onToggle) {
                Text(if (item.collapsed) "Thinking ▸" else "Thinking ▾ ${item.text.take(120)}")
            }
        }
        is ChatItem.Tool -> {
            TextButton(onClick = onToggle) {
                Text(
                    if (item.collapsed) {
                        "Tool ${item.name} ▸"
                    } else {
                        "Tool ${item.name} ▾ ${item.detail.take(120)}"
                    },
                )
            }
        }
        is ChatItem.Interactive -> {
            var draft by remember(item.requestId) { mutableStateOf("") }
            val secret = item.kind == "credential"
            Surface(
                shape = MaterialTheme.shapes.large,
                color = MaterialTheme.colorScheme.secondaryContainer,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text(item.prompt.ifBlank { if (secret) "Credential" else "Question" })
                    if (item.hint.isNotBlank()) {
                        Text(
                            item.hint,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (!item.answered) {
                        item.options.forEach { option ->
                            TextButton(
                                onClick = {
                                    onReply(
                                        item.requestId,
                                        JSONObject()
                                            .put("ok", true)
                                            .put("option_id", option.id)
                                            .put("label", option.label),
                                    )
                                },
                            ) { Text(option.label) }
                        }
                        if (secret || item.allowFree) {
                            OutlinedTextField(
                                value = draft,
                                onValueChange = { draft = it },
                                modifier = Modifier.fillMaxWidth(),
                                visualTransformation = if (secret) {
                                    PasswordVisualTransformation()
                                } else {
                                    androidx.compose.ui.text.input.VisualTransformation.None
                                },
                                keyboardOptions = KeyboardOptions(
                                    keyboardType = if (secret) {
                                        androidx.compose.ui.text.input.KeyboardType.Password
                                    } else {
                                        androidx.compose.ui.text.input.KeyboardType.Text
                                    },
                                ),
                                placeholder = { Text(if (secret) "Secret" else "Reply") },
                                singleLine = true,
                            )
                            Button(
                                shape = MaterialTheme.shapes.medium,
                                onClick = {
                                    if (draft.isBlank()) return@Button
                                    val body = JSONObject().put("ok", true)
                                    if (secret) body.put("secret", draft) else body.put("text", draft)
                                    onReply(item.requestId, body)
                                },
                            ) { Text(if (secret) "Store" else "Send") }
                        }
                        if (item.allowSkip) {
                            TextButton(
                                onClick = {
                                    onReply(
                                        item.requestId,
                                        JSONObject()
                                            .put("ok", true)
                                            .put("action", "skip")
                                            .put("skipped", true),
                                    )
                                },
                            ) { Text("Skip") }
                        }
                    }
                }
            }
        }
        is ChatItem.System -> {
            Text(
                item.text,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp),
            )
        }
    }
}

@Composable
fun ModelProfileSheet(
    models: List<com.shibaclaw.companion.data.ModelEntry>,
    profiles: List<com.shibaclaw.companion.data.ProfileEntry>,
    currentModel: String,
    currentProfile: String,
    onSelectModel: (String) -> Unit,
    onSelectProfile: (String) -> Unit,
) {
    var query by remember { mutableStateOf("") }
    val needle = query.trim()
    val shownProfiles = profiles.filter {
        needle.isBlank() || it.title().contains(needle, true) || it.description.contains(needle, true)
    }
    val shownModels = models.filter {
        needle.isBlank() || it.name.contains(needle, true) || it.id.contains(needle, true) ||
            it.provider.contains(needle, true)
    }
    Column(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
    ) {
        Text("Agent and model", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("Search") },
            singleLine = true,
        )
        LazyColumn(Modifier.height(420.dp)) {
            item { Text("Agents", style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(top = 8.dp)) }
            items(shownProfiles, key = { "p-" + it.id }) { p ->
                TextButton(onClick = { onSelectProfile(p.id) }, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.fillMaxWidth()) {
                        Text((if (p.id == currentProfile) "✓ " else "") + p.title())
                        if (p.description.isNotBlank()) {
                            Text(
                                p.description,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 2,
                            )
                        }
                    }
                }
            }
            item { Text("Models", style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(top = 8.dp)) }
            items(shownModels, key = { "m-" + it.id }) { m ->
                TextButton(onClick = { onSelectModel(m.id) }, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.fillMaxWidth()) {
                        Text((if (m.id == currentModel) "✓ " else "") + m.name.ifBlank { m.id.substringAfterLast('/') })
                        if (m.provider.isNotBlank() || m.id.contains('/')) {
                            Text(
                                m.provider.ifBlank { m.id.substringBefore('/') },
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
            item { Spacer(Modifier.height(24.dp)) }
        }
    }
}
