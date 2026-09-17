import os

FIXTURES_DIR = "tests/fixtures/eval"
os.makedirs(FIXTURES_DIR, exist_ok=True)

docs = {
    "feed_policy.md": """# Feeding Policy

Adult shrimp should be fed three times a day using high-protein pellets (40% protein). 
Feeding times are strictly 06:00, 12:00, and 18:00.

During the molting phase, feed rations must be reduced by 20% to prevent water fouling, as shrimp appetite decreases significantly.

The automatic shrimp feeder requires an override code if it jams. The emergency code is FEED-1234.
""",
    
    "disease_control.md": """# Disease Control

White Spot Syndrome Virus (WSSV) is highly contagious. If WSSV is detected, the affected pond must be isolated immediately. 
Do not drain the water into the main canal. Treat the pond with chlorine at 30 ppm and leave it for 7 days before discharging.

Early signs of WSSV include lethargy, sudden high mortality, and white spots on the carapace.
""",

    "water_quality.md": """# Advanced Water Quality

Optimal pH for Litopenaeus vannamei is between 7.5 and 8.5. 
If pH fluctuates by more than 0.5 units within 24 hours, it indicates poor buffering capacity (low alkalinity). 
To increase alkalinity, agricultural lime (CaCO3) should be applied at 100 kg per hectare.

Dissolved oxygen (DO) must never drop below 4.0 mg/L. Aerators should run continuously during the night from 22:00 to 06:00.
""",
    
    "equipment.md": """# Farm Equipment

The primary paddlewheel aerator is the AquaMaster 2000. It requires maintenance every 500 hours of operation. 
Maintenance includes lubricating the gear box and checking the motor seals.

Backup generators (DieselGen V8) must be tested weekly on Mondays at 10:00 AM.
""",

    "conflict_policy_a.md": """# Quarantine Procedures (Version A)

In the event of a suspected bacterial infection, the quarantine period is mandatory for exactly 14 days. 
No harvesting is allowed during this time.
""",

    "conflict_policy_b.md": """# Quarantine Procedures (Version B)

If a bacterial infection is suspected, farmers must enforce a quarantine period of 21 days to ensure complete eradication.
Harvesting is permitted after day 15 if samples test negative.
"""
}

for filename, content in docs.items():
    with open(os.path.join(FIXTURES_DIR, filename), "w", encoding="utf-8") as f:
        f.write(content)

print(f"Created {len(docs)} test fixtures in {FIXTURES_DIR}")
