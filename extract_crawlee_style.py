#!/usr/bin/env python3
"""
EXTRATOR PROFISSIONAL COM CRAWLEE-LIKE PATTERN
==============================================
Implementa padrões do Crawlee (AutoscaledPool, RequestQueue, rate limiting)
mas em Python puro, adaptado para nosso caso.

Vantagens vs código anterior:
- AutoscaledPool: ajusta velocidade automaticamente com base em erros
- RequestQueue: gerencia fila de URLs com retry automático
- Checkpoints: salva progresso a cada N produtos
- Melhor logging e métricas
"""

import asyncio
import httpx
import time
import json
import random
from datetime import datetime
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
import re
from dataclasses import dataclass, asdict
from pathlib import Path


# ================================================================================================
# CONFIGURAÇÃO
# ================================================================================================
@dataclass
class Config:
    """Configuração do scraper."""
    
    # Rate Limiting
    inicial_pps: float = 0.8  # Começa conservador
    max_pps: float = 1.2  # Máximo permitido
    min_pps: float = 0.3  # Mínimo em caso de muitos erros
    jitter_frac: float = 0.20
    
    # AutoScaling
    erro_threshold: float = 0.15  # Se >15% erros, reduz velocidade
    sucesso_threshold: float = 0.95  # Se >95% sucesso, aumenta velocidade
    ajuste_interval: int = 10  # Ajusta a cada 10 requests
    
    # Retry & Timeout
    max_retries: int = 3
    timeout: float = 20.0
    retry_backoff: float = 2.0  # Exponential backoff
    
    # Checkpoints
    checkpoint_interval: int = 50  # Salva a cada 50 produtos
    checkpoint_file: str = "checkpoint_crawlee.json"
    output_file: str = "produtos_crawlee.json"
    
    # HTTP
    max_connections: int = 5
    max_keepalive: int = 3


# ================================================================================================
# ADAPTIVE RATE LIMITER (LeakyBucket + AutoScaling)
# ================================================================================================
class AdaptiveRateLimiter:
    """
    Rate limiter que ajusta velocidade automaticamente com base em taxa de sucesso.
    Similar ao AutoscaledPool do Crawlee.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.current_pps = config.inicial_pps
        self.base_interval = 1.0 / self.current_pps
        
        self.next_slot = time.monotonic()
        self.lock = asyncio.Lock()
        
        # Métricas para autoscaling
        self.recent_requests = 0
        self.recent_successes = 0
        self.recent_429s = 0
        
    async def acquire(self):
        """Aguarda até poder fazer próxima requisição (com jitter)."""
        async with self.lock:
            now = time.monotonic()
            wait = max(0, self.next_slot - now)
            
            if wait > 0:
                await asyncio.sleep(wait)
            
            # Full Jitter (AWS)
            jitter_range = self.base_interval * self.config.jitter_frac
            jitter = random.uniform(-jitter_range, jitter_range)
            next_interval = self.base_interval + jitter
            
            self.next_slot = time.monotonic() + next_interval
    
    def report_success(self):
        """Registra sucesso para autoscaling."""
        self.recent_requests += 1
        self.recent_successes += 1
        self._maybe_adjust()
    
    def report_429(self):
        """Registra 429 error para autoscaling."""
        self.recent_requests += 1
        self.recent_429s += 1
        self._maybe_adjust()
    
    def report_error(self):
        """Registra erro geral para autoscaling."""
        self.recent_requests += 1
        self._maybe_adjust()
    
    def _maybe_adjust(self):
        """Ajusta velocidade se atingiu intervalo de ajuste."""
        if self.recent_requests >= self.config.ajuste_interval:
            taxa_sucesso = self.recent_successes / self.recent_requests
            taxa_429 = self.recent_429s / self.recent_requests
            
            old_pps = self.current_pps
            
            # Se muitos 429s, reduz velocidade drasticamente
            if taxa_429 > 0.2:
                self.current_pps = max(self.config.min_pps, self.current_pps * 0.5)
                print(f"⚠️  Muitos 429s ({taxa_429:.0%})! Reduzindo para {self.current_pps:.2f} pps")
            
            # Se muitos erros, reduz velocidade
            elif taxa_sucesso < (1 - self.config.erro_threshold):
                self.current_pps = max(self.config.min_pps, self.current_pps * 0.8)
                print(f"⚠️  Taxa de sucesso baixa ({taxa_sucesso:.0%}). Reduzindo para {self.current_pps:.2f} pps")
            
            # Se muito sucesso e sem 429s, aumenta velocidade
            elif taxa_sucesso >= self.config.sucesso_threshold and taxa_429 == 0:
                self.current_pps = min(self.config.max_pps, self.current_pps * 1.1)
                print(f"✅ Alta taxa de sucesso ({taxa_sucesso:.0%})! Aumentando para {self.current_pps:.2f} pps")
            
            # Atualiza base_interval
            self.base_interval = 1.0 / self.current_pps
            
            # Reset métricas
            self.recent_requests = 0
            self.recent_successes = 0
            self.recent_429s = 0


# ================================================================================================
# REQUEST QUEUE (gerencia URLs com retry)
# ================================================================================================
@dataclass
class RequestInfo:
    """Informação sobre uma requisição."""
    url: str
    attempts: int = 0
    last_error: Optional[str] = None


class RequestQueue:
    """
    Gerencia fila de URLs com retry automático.
    Similar ao RequestQueue do Crawlee.
    """
    
    def __init__(self, urls: List[str], max_retries: int = 3):
        self.queue = asyncio.Queue()
        self.max_retries = max_retries
        self.in_progress: Dict[str, RequestInfo] = {}
        self.completed: List[str] = []
        self.failed: List[RequestInfo] = []
        
        # Adiciona todas URLs na fila
        for url in urls:
            self.queue.put_nowait(RequestInfo(url=url))
    
    async def get_next(self) -> Optional[RequestInfo]:
        """Pega próxima URL da fila."""
        if self.queue.empty():
            return None
        
        req = await self.queue.get()
        self.in_progress[req.url] = req
        return req
    
    def mark_success(self, url: str):
        """Marca URL como concluída com sucesso."""
        if url in self.in_progress:
            del self.in_progress[url]
        self.completed.append(url)
    
    def mark_failure(self, url: str, error: str):
        """Marca URL como falha e recoloca na fila se tiver retries."""
        if url not in self.in_progress:
            return
        
        req = self.in_progress[url]
        req.attempts += 1
        req.last_error = error
        
        if req.attempts < self.max_retries:
            # Recoloca na fila com backoff
            self.queue.put_nowait(req)
        else:
            # Falha definitiva
            self.failed.append(req)
        
        del self.in_progress[url]
    
    def is_done(self) -> bool:
        """Verifica se todas URLs foram processadas."""
        return self.queue.empty() and len(self.in_progress) == 0
    
    def get_stats(self) -> Dict[str, int]:
        """Retorna estatísticas."""
        return {
            "pending": self.queue.qsize(),
            "in_progress": len(self.in_progress),
            "completed": len(self.completed),
            "failed": len(self.failed)
        }


# ================================================================================================
# EXTRATOR DE PRODUTO
# ================================================================================================
PRECO_RE = re.compile(r'R\$\s*(?:<!--.*?-->)?\s*([\d.,]+)', re.DOTALL)
SKU_RE = re.compile(r'(?:sku|codigo|SKU)["\']?\s*:?\s*["\']?([A-Z0-9\-]+)', re.IGNORECASE)


async def extrair_produto_html(client: httpx.AsyncClient, url: str, rate_limiter: AdaptiveRateLimiter) -> Dict[str, Any]:
    """
    Extrai dados do produto via HTML.
    Retorna: {sucesso, dados, erro}
    """
    await rate_limiter.acquire()
    
    inicio = time.perf_counter()
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        }
        
        response = await client.get(url, headers=headers)
        tempo = time.perf_counter() - inicio
        
        if response.status_code == 429:
            rate_limiter.report_429()
            return {"sucesso": False, "erro": "429 Too Many Requests", "tempo": tempo}
        
        if response.status_code != 200:
            rate_limiter.report_error()
            return {"sucesso": False, "erro": f"HTTP {response.status_code}", "tempo": tempo}
        
        html = response.text
        
        if len(html) < 10000:
            rate_limiter.report_error()
            return {"sucesso": False, "erro": "HTML muito pequeno", "tempo": tempo}
        
        # Parse HTML
        soup = BeautifulSoup(html, 'lxml')
        
        # Nome (h1)
        h1_tags = soup.find_all('h1')
        nome = None
        if len(h1_tags) >= 2:
            nome = h1_tags[1].get_text(strip=True)
        elif h1_tags:
            nome = h1_tags[0].get_text(strip=True)
        
        # Preço
        precos = PRECO_RE.findall(html)
        preco = precos[0] if precos else None
        
        # SKU
        sku_match = SKU_RE.search(html)
        sku = sku_match.group(1) if sku_match else None
        
        rate_limiter.report_success()
        
        return {
            "sucesso": True,
            "dados": {
                "url": url,
                "nome": nome,
                "preco": preco,
                "sku": sku,
                "timestamp": datetime.now().isoformat()
            },
            "tempo": tempo
        }
    
    except httpx.TimeoutException:
        rate_limiter.report_error()
        return {"sucesso": False, "erro": "Timeout", "tempo": time.perf_counter() - inicio}
    
    except Exception as e:
        rate_limiter.report_error()
        return {"sucesso": False, "erro": str(e)[:100], "tempo": time.perf_counter() - inicio}


# ================================================================================================
# CRAWLER PRINCIPAL
# ================================================================================================
async def crawl(urls: List[str], config: Config):
    """
    Crawler principal com AutoscaledPool e RequestQueue.
    """
    print(f"{'='*100}")
    print(f"CRAWLER PROFISSIONAL (Crawlee-like)")
    print(f"{'='*100}")
    print(f"URLs: {len(urls)}")
    print(f"Taxa inicial: {config.inicial_pps} pps (ajusta automaticamente)")
    print(f"Checkpoint: a cada {config.checkpoint_interval} produtos")
    print(f"{'='*100}\n")
    
    # Inicializar componentes
    rate_limiter = AdaptiveRateLimiter(config)
    request_queue = RequestQueue(urls, max_retries=config.max_retries)
    
    produtos_extraidos = []
    inicio_total = time.time()
    
    # HTTP Client
    async with httpx.AsyncClient(
        timeout=config.timeout,
        follow_redirects=True,
        limits=httpx.Limits(
            max_connections=config.max_connections,
            max_keepalive_connections=config.max_keepalive
        )
    ) as client:
        
        contador = 0
        
        while not request_queue.is_done():
            req = await request_queue.get_next()
            
            if req is None:
                break
            
            contador += 1
            tentativa_str = f" (tentativa {req.attempts + 1})" if req.attempts > 0 else ""
            
            # Extrair produto
            resultado = await extrair_produto_html(client, req.url, rate_limiter)
            
            if resultado["sucesso"]:
                request_queue.mark_success(req.url)
                produtos_extraidos.append(resultado["dados"])
                
                print(f"[{contador:3d}/{len(urls)}] ✅ OK  ({resultado['tempo']:.2f}s){tentativa_str}")
                
                # Checkpoint
                if len(produtos_extraidos) % config.checkpoint_interval == 0:
                    salvar_checkpoint(produtos_extraidos, config.checkpoint_file)
                    print(f"   💾 Checkpoint salvo: {len(produtos_extraidos)} produtos")
            
            else:
                request_queue.mark_failure(req.url, resultado["erro"])
                
                if resultado["erro"] == "429 Too Many Requests":
                    print(f"[{contador:3d}/{len(urls)}] ⚠️  429{tentativa_str}")
                    # Aguarda um pouco antes de continuar
                    await asyncio.sleep(5)
                else:
                    print(f"[{contador:3d}/{len(urls)}] ❌ ERR ({resultado['erro'][:30]}){tentativa_str}")
    
    tempo_total = time.time() - inicio_total
    
    # Estatísticas finais
    stats = request_queue.get_stats()
    
    print(f"\n{'='*100}")
    print("RESULTADOS FINAIS")
    print(f"{'='*100}")
    print(f"✅ Sucesso: {stats['completed']}/{len(urls)} ({stats['completed']/len(urls)*100:.1f}%)")
    print(f"❌ Falhas: {stats['failed']}")
    print(f"⏱️  Tempo total: {tempo_total:.1f}s ({tempo_total/60:.1f} min)")
    print(f"📊 Tempo médio: {tempo_total/len(urls):.2f}s por produto")
    print(f"🚀 Taxa final: {rate_limiter.current_pps:.2f} pps")
    print(f"{'='*100}\n")
    
    # Salvar resultados
    with open(config.output_file, "w", encoding="utf-8") as f:
        json.dump(produtos_extraidos, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Resultados salvos em: {config.output_file}\n")
    
    # Salvar URLs que falharam
    if request_queue.failed:
        with open("urls_falhadas.txt", "w", encoding="utf-8") as f:
            for req in request_queue.failed:
                f.write(f"{req.url} | {req.last_error}\n")
        print(f"⚠️  URLs falhadas salvas em: urls_falhadas.txt\n")


def salvar_checkpoint(produtos: List[Dict], filename: str):
    """Salva checkpoint para recuperação."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "produtos": produtos
        }, f, indent=2, ensure_ascii=False)


# ================================================================================================
# MAIN
# ================================================================================================
async def main():
    # Carregar URLs
    try:
        with open('urls_matcon_100.txt', 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("❌ Arquivo urls_matcon_100.txt não encontrado!")
        return
    
    # Configuração
    config = Config(
        inicial_pps=0.8,  # Começa conservador após o ban
        max_pps=1.0,      # Não ultrapassa 1.0 pps
        min_pps=0.3,      # Mínimo em caso de problemas
        checkpoint_interval=50
    )
    
    # Executar crawler
    await crawl(urls, config)


if __name__ == "__main__":
    asyncio.run(main())
