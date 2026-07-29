import subprocess
import shlex

# Authorized users
ALLOWED_USERS = [346930679, 167429176]

# Dangerous commands blacklist
BLACKLIST = ["rm -rf", "shutdown", "reboot", "dd", "mkfs"]

def is_authorized(user_id):
    return user_id in ALLOWED_USERS

def execute_command(user_id, command):
    if not is_authorized(user_id):
        return "🚫 Доступ запрещен. Только Ринат и Николай могут использовать этот плагин."
    
    # Check blacklist
    if any(bad in command for bad in BLACKLIST):
        return "⚠️ Эта команда заблокирована в целях безопасности!"
    
    try:
        # Execute command
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        output = result.stdout if result.stdout else result.stderr
        return f"🖥️ Результат:\n```\n{output[:1000]}\n```"
    except Exception as e:
        return f"❌ Ошибка выполнения: {str(e)}"

def setup():
    print("Shell Exec Plugin Loaded! Access restricted to Rinat and Nikolay.")
