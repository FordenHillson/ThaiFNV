import re
from pathlib import Path

def scan(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        n, th = line.split("\t", 1)
        # flag lowercase latin inside th (except allowed)
        if re.search(r"[a-z]", th):
            # allow common EN tokens
            cleaned = th
            for tok in [
                "RS", "Foxtrot", "Ringo", "Nevada", "Agave", "Prickly", "Pear", "Barrel",
                "Powder", "Ganger", "Reset", "Marker", "Nellis", "Honey", "Mesquite",
                "mm", "Joe", "Cobb", "Vit-o-matic", "Vigor", "Tester", "Sonic", "Emitter",
                "Fiend", "Ballast", "Gun", "Runner", "Hector", "CurtisTowerWarp", "Up",
                "Jas", "Wilkins", "Fade", "Vikki", "Vance", "Reflector", "Sniper",
                "Jeannie", "May", "Harland", "Ranger", "Station", "Charlie", "REPCON",
                "Ghoul", "Kilo", "Bravo", "Laser", "Tripwire", "goo", "Eat'o'tronic",
                "rad", "pack", "bruce", "drifter", "PA", "Mojave", "Music", "Radio",
                "Ultra", "Luxe", "Gomorrah", "Lounge", "Mainframe", "Lucky", "NCR",
                "Lily", "ED-E", "Hanlon", "Tops", "New", "Vegas", "Camp", "Guardian",
                "Black", "Mountain", "House", "Jukebox", "Papa", "November", "Sierra",
                "Victor", "Romeo", "Yankee", "Oscar", "Tango", "Echo", "Alfa", "Lima",
                "President", "Eden", "Zulu", "Deputy", "Weld", "Agatha", "Vault",
                "People's", "Republic", "America", "Recon", "Craft", "Theta", "Enclave",
                "Tenpenny", "Tower", "Galaxy", "News", "Jessup", "Veronica", "Legate",
                "White", "Glove", "Society", "Stealth", "Cass", "Mark", "Raul",
                "General", "Oliver", "Papa", "Khan", "Followers", "Gladiator", "Repconn",
                "Raoul", "Jason", "Bright", "Recon", "DamWar", "Great", "Centurion",
                "Legion", "Power", "Armor", "Caesar", "Aura", "Token", "Kicker", "Tesla",
                "Remnants", "Salvaged", "Gannon", "Family", "Kimball", "Our", "Rich",
                "Solar", "System", "It's", "Got", "Wheels", "The", "Hand", "Handy",
                "Eyebot", "Watch", "Your", "Step", "Green", "Bean", "Big", "Fat",
                "Fiery", "Fred", "Needlenose", "Rockets", "Away", "Ready", "Set",
                "Launch", "Nuclear", "Plas-Ma", "What", "Radioactive", "Waste",
                "Boring", "Old", "Rod", "Or", "overflow", "Suite", "Pod", "Activator",
                "Chinese", "combat", "combat", "1st", "Bottle", "Cap", "Press",
            ]:
                cleaned = cleaned.replace(tok, "")
            if re.search(r"[a-z]", cleaned):
                print(n, th)

base = Path(r"D:\backup\github\ThaiFNV\extracted\sheets\names_packs\out")
for pid in ["u_0012", "u_0013"]:
    print("===", pid)
    scan(base / f"{pid}.tsv")
