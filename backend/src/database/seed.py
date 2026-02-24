"""
Database seeding script - generates mock customer data for testing.
Creates 100 customers with accounts and cards, all with PIN=1234.
"""
import asyncio
import random
from faker import Faker
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.connection import async_session
from src.database.models import Customer, Account, Card
from datetime import datetime, timedelta


fake = Faker()


async def seed_customers(session: AsyncSession, count: int = 100):
    """Seed customer data with accounts and cards."""
    
    print(f"🌱 Seeding {count} customers...")
    
    customers = []
    accounts = []
    cards = []
    
    # Hash PIN once (all test customers use PIN=1234)
    pin_hash = bcrypt.hashpw(b"1234", bcrypt.gensalt()).decode()
    
    for i in range(count):
        customer_id = f"CUST{i:05d}"
        
        # Create customer
        customer = Customer(
            customer_id=customer_id,
            name=fake.name(),
            email=fake.email(),
            phone=fake.phone_number()[:20],  # Truncate to max length
            pin_hash=pin_hash,
        )
        customers.append(customer)
        
        # Create 1-2 accounts per customer
        num_accounts = random.randint(1, 2)
        for j in range(num_accounts):
            account_id = f"ACC{i:05d}{j}"
            
            account = Account(
                account_id=account_id,
                customer_id=customer_id,
                account_type=random.choice(["checking", "savings"]),
                balance=round(random.uniform(100.0, 50000.0), 2),
                currency="USD",
            )
            accounts.append(account)
            
            # Create 1 card per account
            card = Card(
                card_id=f"CARD{i:05d}{j}",
                account_id=account_id,
                card_number_last4=str(random.randint(1000, 9999)),
                status="active",
                expiration_date=datetime.now() + timedelta(days=365 * 3),  # 3 years
            )
            cards.append(card)
    
    # Bulk insert
    session.add_all(customers)
    session.add_all(accounts)
    session.add_all(cards)
    await session.commit()
    
    print(f"✅ Seeded {len(customers)} customers, {len(accounts)} accounts, {len(cards)} cards")
    print(f"📝 Test credentials: Customer ID=CUST00001, PIN=1234")


async def seed_configurations(session: AsyncSession):
    """Seed default system configurations."""
    from src.database.models import Configuration
    
    print("🔧 Seeding configurations...")
    
    default_configs = [
        Configuration(
            key="intent_router_system_prompt",
            value={
                "prompt": """You are an intent classification expert for Bank ABC's voice assistant.
Your job is to classify customer banking inquiries into one of these categories:
1. card_atm: Lost/stolen cards, ATM issues, declined payments
2. account_servicing: Statement requests, profile updates, balance inquiries
3. account_opening: New account inquiries
4. digital_support: App/online banking issues
5. transfer_payment: Transfer and bill payment issues
6. account_closure: Account closure requests
7. general_inquiry: General questions, hours, locations"""
            },
            description="System prompt for intent classification",
            updated_by="system_seed",
        ),
        Configuration(
            key="max_auth_attempts",
            value={"value": 3},
            description="Maximum authentication attempts before escalation",
            updated_by="system_seed",
        ),
    ]
    
    session.add_all(default_configs)
    await session.commit()
    
    print("✅ Seeded configurations")


async def main():
    """Main seeding function."""
    async with async_session() as session:
        try:
            await seed_customers(session, count=100)
            await seed_configurations(session)
            print("\n🎉 Database seeding complete!")
        except Exception as e:
            print(f"❌ Seeding failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
