import random

# Dungeon State
players = {} # user_id: {"hp": 100, "name": name}
markets = {} # market_id: {"question": question, "bets": {user_id: outcome}}

def is_protected(user_id):
    # Nikolay (167429176) is untouchable
    return user_id == 167429176

def roast(target_name, target_id):
    if is_protected(target_id):
        return f"Николай — легенда, его не трогаем! Он наш бро."
    
    roasts = [
        f"{target_name}, ты сегодня выглядишь как баг в продакшене.",
        f"У {target_name} интеллект как у Internet Explorer.",
        f"{target_name}, даже мой поводок умнее тебя.",
        f"{target_name}, твой код — это спагетти, которые даже собака есть не станет.",
        f"{target_name}, ты как `git push --force` — только всё портишь.",
        f"{target_name}, у тебя в голове `404 Not Found`."
    ]
    return random.choice(roasts)

def fight(attacker_name, attacker_id, defender_name, defender_id):
    if is_protected(defender_id):
        return f"Ты что, {attacker_name}? Николая атаковать нельзя! Он наш бро!"
    
    damage = random.randint(10, 30)
    return f"⚔️ {attacker_name} атакует {defender_name}! Урон: {damage} HP. {defender_name} в шоке!"

def create_market(question):
    market_id = len(markets) + 1
    markets[market_id] = {"question": question, "bets": {}}
    return f"📊 Рынок #{market_id} открыт: '{question}'! Делайте ставки (да/нет)!"

def place_bet(user_id, market_id, outcome):
    if market_id not in markets:
        return "Рынок не найден!"
    markets[market_id]["bets"][user_id] = outcome
    return f"✅ Ставка принята: {outcome}."

def setup():
    print("Dungeon Chaos Plugin Loaded! Ready to cause some trouble.")
