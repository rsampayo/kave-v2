import asyncio

import asyncpg


async def test_connection():
    try:
        conn = await asyncpg.connect(
            "postgresql://ramonsampayo:postgres@localhost:5432/kave_dev"
        )
        print("Connection successful")
        await conn.close()
    except Exception as e:
        print(f"Connection error: {e}")


if __name__ == "__main__":
    asyncio.run(test_connection())
