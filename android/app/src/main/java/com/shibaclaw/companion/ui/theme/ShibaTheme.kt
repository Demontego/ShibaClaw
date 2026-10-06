package com.shibaclaw.companion.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.shibaclaw.companion.data.ThemeMode

private val DarkColors = darkColorScheme(
    primary = Color(0xFFDBAA79),
    onPrimary = Color(0xFF191918),
    primaryContainer = Color(0xFF352B22),
    onPrimaryContainer = Color(0xFFE5BD96),
    secondary = Color(0xFF9BC3AB),
    onSecondary = Color(0xFF191918),
    background = Color(0xFF191918),
    onBackground = Color(0xFFEEEEE8),
    surface = Color(0xFF222221),
    onSurface = Color(0xFFEEEEE8),
    surfaceVariant = Color(0xFF2B2B29),
    onSurfaceVariant = Color(0xFFAAA99E),
    surfaceContainerLow = Color(0xFF131312),
    surfaceContainerHigh = Color(0xFF30302D),
    error = Color(0xFFF87171),
    outline = Color(0xFF343431),
)

private val LightColors = lightColorScheme(
    primary = Color(0xFF9A5D2B),
    onPrimary = Color(0xFFFCFBF9),
    primaryContainer = Color(0xFFF3E8DC),
    onPrimaryContainer = Color(0xFF875022),
    secondary = Color(0xFF39705A),
    onSecondary = Color(0xFFFCFBF9),
    tertiary = Color(0xFF2D6FB3),
    background = Color(0xFFFCFBF9),
    onBackground = Color(0xFF252620),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF252620),
    surfaceVariant = Color(0xFFE9E8E3),
    onSurfaceVariant = Color(0xFF66695E),
    surfaceContainerLow = Color(0xFFF2F1ED),
    surfaceContainerHigh = Color(0xFFE5E3DC),
    error = Color(0xFFB84040),
    outline = Color(0xFFE5E3DC),
)

private val ShibaShapes = androidx.compose.material3.Shapes(
    extraSmall = RoundedCornerShape(6.dp),
    small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(10.dp),
    large = RoundedCornerShape(16.dp),
    extraLarge = RoundedCornerShape(16.dp),
)

private val ShibaType = Typography(
    titleMedium = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 17.sp, letterSpacing = (-0.4).sp),
    bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 22.sp),
    labelSmall = TextStyle(fontSize = 11.sp, letterSpacing = 0.4.sp),
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
        shapes = ShibaShapes,
        typography = ShibaType,
        content = content,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun shibaBarColors() = TopAppBarDefaults.topAppBarColors(
    containerColor = MaterialTheme.colorScheme.background,
    titleContentColor = MaterialTheme.colorScheme.onBackground,
    navigationIconContentColor = MaterialTheme.colorScheme.onSurfaceVariant,
    actionIconContentColor = MaterialTheme.colorScheme.onSurfaceVariant,
)
