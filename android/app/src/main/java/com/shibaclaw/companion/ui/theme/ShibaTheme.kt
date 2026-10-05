package com.shibaclaw.companion.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import com.shibaclaw.companion.data.ThemeMode

val ShibaGold = Color(0xFFE8A317)
val ShibaGoldLight = Color(0xFFF5C94A)

private val DarkColors = darkColorScheme(
    primary = ShibaGold,
    onPrimary = Color(0xFF1A1400),
    secondary = Color(0xFF4A9EFF),
    tertiary = Color(0xFF4ADE80),
    background = Color(0xFF0D0D0D),
    onBackground = Color(0xFFE8E8E8),
    surface = Color(0xFF191919),
    onSurface = Color(0xFFE8E8E8),
    surfaceVariant = Color(0xFF242424),
    onSurfaceVariant = Color(0xFF9A9A9A),
    error = Color(0xFFF87171),
    outline = Color(0x1AFFFFFF),
)

private val LightColors = lightColorScheme(
    primary = ShibaGold,
    onPrimary = Color(0xFF1A1400),
    secondary = Color(0xFF2D6FB3),
    tertiary = Color(0xFF39705A),
    background = Color(0xFFFCFBF9),
    onBackground = Color(0xFF252620),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF252620),
    surfaceVariant = Color(0xFFE5E3DC),
    onSurfaceVariant = Color(0xFF66695E),
    error = Color(0xFFB84040),
    outline = Color(0x1A000000),
)

@Composable
fun ShibaTheme(mode: ThemeMode, content: @Composable () -> Unit) {
    val dark = when (mode) {
        ThemeMode.SYSTEM -> isSystemInDarkTheme()
        ThemeMode.DARK -> true
        ThemeMode.LIGHT -> false
    }
    MaterialTheme(
        colorScheme = if (dark) DarkColors else LightColors,
        content = content,
    )
}
