import asyncpg
import json
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.pool = None
    
    async def connect(self):
        try:
            self.pool = await asyncpg.create_pool(
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "admin123"),
                database=os.getenv("DB_NAME", "zaplabels"),
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", 5432)
            )
            await self.create_tables()
            print("✅ PostgreSQL connected successfully!")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise
    
    async def create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    order_id VARCHAR(50) UNIQUE,
                    user_id BIGINT,
                    country VARCHAR(50),
                    carrier VARCHAR(50),
                    service VARCHAR(50),
                    amount DECIMAL(10,2),
                    status VARCHAR(20) DEFAULT 'pending',
                    file_path VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS warehouses (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100),
                    address TEXT,
                    postcode VARCHAR(20),
                    country VARCHAR(50),
                    carrier VARCHAR(50),
                    latitude DECIMAL(10,8),
                    longitude DECIMAL(11,8)
                )
            """)
            print("✅ Tables created/verified")
    
    async def save_order(self, data):
        try:
            async with self.pool.acquire() as conn:
                # Generate unique order_id with timestamp
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                order_id = f"ZAP-{timestamp}-{data['user_id']}"
                
                # Debug print
                print(f"📦 Saving order data: {data}")
                
                # Get amount from data
                amount = data.get('amount', data.get('price', 0))
                
                await conn.execute("""
                    INSERT INTO orders (order_id, user_id, country, carrier, service, amount, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, order_id, data['user_id'], data['country'], data['carrier'], data['service'], amount, 'pending')
                print(f"✅ Order saved: {order_id}")
                return order_id
        except Exception as e:
            print(f"❌ Error saving order: {e}")
            return None
    
    async def get_orders(self, limit=10):
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM orders ORDER BY created_at DESC LIMIT $1", limit)
                print(f"✅ Fetched {len(rows)} orders")
                return rows
        except Exception as e:
            print(f"❌ Error fetching orders: {e}")
            return []
    
    async def update_order_status(self, order_id, status):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("UPDATE orders SET status = $1 WHERE order_id = $2", status, order_id)
                print(f"✅ Order {order_id} status updated to {status}")
                return True
        except Exception as e:
            print(f"❌ Error updating order: {e}")
            return False
    
    async def get_order_by_id(self, order_id):
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM orders WHERE order_id = $1", order_id)
                return row
        except Exception as e:
            print(f"❌ Error fetching order: {e}")
            return None

db = Database()