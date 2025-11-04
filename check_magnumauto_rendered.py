from bs4 import BeautifulSoup

soup = BeautifulSoup(open('magnumauto_rendered.html', encoding='utf-8'), 'html.parser')
rs = soup.find_all(string=lambda t: t and 'R$' in str(t))
print(f'Elementos com R$: {len(rs)}')
for r in rs[:10]:
    print(f'  {r.strip()[:150]}')

# Buscar classes com price
prices = soup.find_all(class_=lambda x: x and 'price' in str(x).lower())
print(f'\nClasses com price: {len(prices)}')
for p in prices[:5]:
    classes = ' '.join(p.get('class', []))
    print(f'  {classes}: {p.get_text(strip=True)[:100]}')
