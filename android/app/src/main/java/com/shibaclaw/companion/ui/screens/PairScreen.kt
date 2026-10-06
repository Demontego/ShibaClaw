package com.shibaclaw.companion.ui.screens

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.shibaclaw.companion.Prefs
import com.shibaclaw.companion.R
import com.shibaclaw.companion.ShibaService
import com.shibaclaw.companion.data.ShibaRepo

@Composable
fun PairScreen(onPaired: () -> Unit) {
    val ctx = LocalContext.current
    var url by remember { mutableStateOf(Prefs.baseUrl(ctx)) }
    var username by remember { mutableStateOf(Prefs.username(ctx)) }
    var password by remember { mutableStateOf(Prefs.password(ctx)) }
    val status by ShibaRepo.status.collectAsState()
    val mood by ShibaRepo.mood.collectAsState()
    val permission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { }

    LaunchedEffect(Unit) {
        if (Build.VERSION.SDK_INT >= 33) {
            permission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Image(
            painter = painterResource(mood.drawable()),
            contentDescription = null,
            modifier = Modifier.size(120.dp),
        )
        Spacer(Modifier.height(16.dp))
        Text(stringResource(R.string.pair_title), style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(8.dp))
        Text(status, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(
            value = url,
            onValueChange = { url = it },
            label = { Text(stringResource(R.string.url_hint)) },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = username,
            onValueChange = { username = it },
            label = { Text(stringResource(R.string.username_hint)) },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text(stringResource(R.string.password_hint)) },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Spacer(Modifier.height(20.dp))
        Button(
            shape = MaterialTheme.shapes.medium,
            onClick = {
                if (url.isBlank()) return@Button
                Prefs.savePair(ctx, url, username, password)
                ShibaService.start(ctx)
                onPaired()
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(stringResource(R.string.connect))
        }
        if (Prefs.isPaired(ctx)) {
            TextButton(onClick = onPaired) {
                Text(stringResource(R.string.open_chat))
            }
        }
        Spacer(Modifier.height(12.dp))
        Text(
            stringResource(R.string.add_widget_hint),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
