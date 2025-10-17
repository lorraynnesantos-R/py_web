
import sys
from pathlib import Path
import asyncio
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.auto_uploader.health_checker import APIHealthChecker

async def main():
    checker = APIHealthChecker(data_dir=Path("data"))
    url = "https://httpbin.org/status/200"  # URL de teste
    result = await checker.check_health(url, use_cache=False)
    print(f"Status: {result.status.value}")
    print(f"Tempo de resposta: {result.response_time_ms:.1f} ms")
    print(f"Saudável: {result.is_healthy}")
    print(f"Métricas: {checker.get_metrics(url)}")
    print(f"Resumo uptime: {checker.get_uptime_summary(url, hours=1)}")

if __name__ == "__main__":
    asyncio.run(main())
