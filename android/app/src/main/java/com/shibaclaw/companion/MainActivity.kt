package com.shibaclaw.companion

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.shibaclaw.companion.data.ShibaRepo
import com.shibaclaw.companion.ui.screens.ChatScreen
import com.shibaclaw.companion.ui.screens.NotificationsScreen
import com.shibaclaw.companion.ui.screens.PairScreen
import com.shibaclaw.companion.ui.screens.SettingsScreen
import com.shibaclaw.companion.ui.theme.ShibaTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val start = if (Prefs.isPaired(this)) "chat" else "pair"
        val openSession = intent?.getStringExtra(EXTRA_SESSION)
        setContent {
            val theme by ShibaRepo.theme.collectAsState()
            ShibaTheme(theme) {
                Surface(Modifier.fillMaxSize()) {
                    val nav = rememberNavController()
                    LaunchedEffect(openSession) {
                        if (!openSession.isNullOrBlank()) ShibaRepo.switchSession(openSession)
                    }
                    NavHost(navController = nav, startDestination = start) {
                        composable("pair") {
                            PairScreen(onPaired = {
                                nav.navigate("chat") {
                                    popUpTo("pair") { inclusive = true }
                                }
                            })
                        }
                        composable("chat") {
                            ChatScreen(
                                onOpenSettings = { nav.navigate("settings") },
                                onOpenNotifications = { nav.navigate("notifications") },
                            )
                        }
                        composable("settings") {
                            SettingsScreen(
                                onBack = { nav.popBackStack() },
                                onRePair = {
                                    nav.navigate("pair") {
                                        popUpTo("chat") { inclusive = true }
                                    }
                                },
                            )
                        }
                        composable("notifications") {
                            NotificationsScreen(onBack = { nav.popBackStack() })
                        }
                    }
                }
            }
        }
    }

    companion object {
        const val EXTRA_SESSION = "session_key"
    }
}
