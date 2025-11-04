import requests

print("Testando Artistas do Mundo...")
try:
    r = requests.get('https://www.artistasdomundo.com.br', timeout=15)
    print(f"✅ Status: {r.status_code}")
    print(f"📦 Tamanho: {len(r.text)} bytes")
    
    # Detectar plataforma
    text_lower = r.text.lower()
    if 'vtex' in text_lower:
        print("✅ VTEX detectado")
    if 'shopify' in text_lower:
        print("✅ Shopify detectado")
    if 'woocommerce' in text_lower:
        print("✅ WooCommerce detectado")
    
    # Testar sitemap
    print("\nTestando sitemap...")
    r2 = requests.get('https://www.artistasdomundo.com.br/sitemap.xml', timeout=10)
    if r2.status_code == 200:
        print(f"✅ Sitemap encontrado: {len(r2.text)} bytes")
        urls = r2.text.count('<loc>')
        print(f"   URLs: {urls}")
    else:
        print(f"⚠️  Sitemap não encontrado: {r2.status_code}")
        
except Exception as e:
    print(f"❌ Erro: {e}")
