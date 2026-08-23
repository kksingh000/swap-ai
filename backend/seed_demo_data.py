"""Populate the database with realistic demo data.

    python seed_demo_data.py            (from backend/)
    python seed_demo_data.py --reset    (wipe first)

Rather than inserting fake rows, this replays scripted conversations through
the real conversation engine - so the transcripts, scores, score reasons,
WhatsApp messages and callbacks are all genuinely produced by the pipeline.
"""
import argparse
import asyncio
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.services import customer_service  # noqa: E402
from app.services.conversation.engine import ConversationEngine  # noqa: E402

CONVERSATIONS = [
    {
        "name": "Rahul Mehta",
        "phone": "+919812345601",
        "language": "english",
        "lines": [
            "Yeah sure, I have a minute. What is this about?",
            "I need branded jackets and hoodies, my budget is around 1500 and I need them this week.",
            "Size L. Can you send me the catalog on WhatsApp?",
        ],
    },
    {
        "name": "Priya Sharma",
        "phone": "+919812345602",
        "language": "hinglish",
        "lines": [
            "Haan bolo, kya hai?",
            "Idea to achha hai par pehle main apni wardrobe check karungi ki kya swap kar sakti hoon.",
            "Kal shaam 6 baje call kar lena.",
        ],
    },
    {
        "name": "Aman Verma",
        "phone": "+919812345603",
        "language": "english",
        "lines": [
            "Who is this?",
            "Oh, I was just curious what you people do. I'm not looking for anything right now.",
        ],
    },
    {
        "name": "Sneha Kapoor",
        "phone": "+919812345604",
        "language": "hinglish",
        "lines": [
            "Haan ji boliye.",
            "Budget around 1000 hai but mujhe branded jackets chahiye, Zara ya H&M type.",
            "Is hafte chahiye. WhatsApp pe bhej do collection.",
        ],
    },
    {
        "name": "Karan Singh",
        "phone": "+919812345605",
        "language": "hinglish",
        "lines": [
            "Haan sunn raha hoon.",
            "Mere paas kaafi kapde pade hain jo main pehenta nahi. Bech sakta hoon kya?",
            "Levis ki jeans aur kuch shirts hain. Kitna mil jayega?",
            "Theek hai, agle hafte call karna.",
        ],
    },
    {
        "name": "Meera Nair",
        "phone": "+919812345606",
        "language": "english",
        "lines": [
            "How do I know the clothes are clean? Used clothes sound unhygienic to me.",
            "And is this genuine? How do I trust you?",
            "Okay that sounds fair. Show me what you have under 800.",
        ],
    },
    {
        "name": "Vikram Rao",
        "phone": "+919812345607",
        "language": "english",
        "lines": ["Please don't call me again. Remove my number."],
    },
    {
        "name": "Anjali Gupta",
        "phone": "+919812345608",
        "language": "hindi",
        "lines": [
            "Namaste, haan boliye.",
            "मुझे कुर्ती चाहिए, बजट 800 है।",
            "इस महीने ले लूंगी। व्हाट्सएप पर भेज दीजिए।",
        ],
    },
]


async def run(reset: bool) -> None:
    import app.models  # noqa: F401

    if reset:
        Base.metadata.drop_all(bind=engine)
        print("Dropped existing tables.")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        for script in CONVERSATIONS:
            customer = customer_service.get_or_create(
                db, script["phone"], script["name"], script["language"]
            )
            customer.do_not_call = False
            db.commit()

            engine_instance = ConversationEngine(db)
            call, opening = await engine_instance.start_call(customer, mode="demo", provider="seed")
            print(f"\n--- {script['name']} ({script['language']}) ---")
            print(f"  AGENT   : {opening[:88]}…")

            ended = False
            for line in script["lines"]:
                if ended:
                    break
                print(f"  CUSTOMER: {line[:88]}")
                result = await engine_instance.handle_turn(call, line)
                print(f"  AGENT   : {result['reply'][:88]}")
                actions = [a["action_type"] for a in result["actions"]]
                print(
                    f"     -> {result['lead']['score']}/100 {result['lead']['classification']}"
                    + (f"  actions: {actions}" if actions else "")
                )
                ended = result["should_end"]

            if not ended:
                await engine_instance.end_call(call)

        # Let the fire-and-forget WhatsApp tasks finish before we exit.
        await asyncio.sleep(1.2)

        from app.models import Callback, Customer, Lead, WhatsAppMessage

        print("\n" + "=" * 62)
        print(f"  Customers : {db.query(Customer).count()}")
        print(f"  Leads     : {db.query(Lead).count()}")
        print(f"    HOT     : {db.query(Lead).filter(Lead.status == 'HOT').count()}")
        print(f"    WARM    : {db.query(Lead).filter(Lead.status == 'WARM').count()}")
        print(f"    COLD    : {db.query(Lead).filter(Lead.status == 'COLD').count()}")
        print(f"  WhatsApp  : {db.query(WhatsAppMessage).count()}")
        print(f"  Callbacks : {db.query(Callback).count()}")
        print("=" * 62)
        print("\nStart the app and open http://localhost:5173\n")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo data")
    parser.add_argument("--reset", action="store_true", help="drop all tables first")
    args = parser.parse_args()
    asyncio.run(run(args.reset))
