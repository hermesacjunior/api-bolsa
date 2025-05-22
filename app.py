from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
import os

app = Flask(__name__)

@app.route('/')
def home():
    return {"mensagem": "API está online!"}

@app.route('/analise/<ticker>', methods=['GET'])
def analisar_acao(ticker):
    token = os.getenv("BRAPI_TOKEN")
    brapi_url = f"https://brapi.dev/api/quote/{ticker}?token={token}"

    try:
        brapi_resp = requests.get(brapi_url)
        brapi_data = brapi_resp.json()['results'][0]

        pl = brapi_data.get('priceEarningsRatio')
        dy = brapi_data.get('dividendYield')
        preco = brapi_data.get('regularMarketPrice')
        empresa = brapi_data.get('longName')

        # Scraping do Fundamentus
        fundamentus_url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker.upper()}"
        html = requests.get(fundamentus_url, headers={"User-Agent": "Mozilla/5.0"}).content.decode("ISO-8859-1")
        soup = BeautifulSoup(html, 'html.parser')

        def get_valor(label):
            for td in soup.find_all("td"):
                texto = td.get_text(strip=True)
                if label.lower() in texto.lower():
                    valor_td = td.find_next_sibling("td")
                    if valor_td:
                        valor = valor_td.text.strip().replace('%', '').replace('.', '').replace(',', '.')
                        try:
                            return float(valor)
                        except:
                            return None
            return None  # <- agora está corretamente DENTRO da função

        # Buscar os dados do Fundamentus
        pl = get_valor("P/L")
        dy = get_valor("Div. Yield")
        roe = get_valor("ROE")
        roic = get_valor("ROIC")
        ev_ebitda = get_valor("EV / EBITDA")
        margem_liquida = get_valor("Marg. Líquida")
        divida_patrimonio = get_valor("Div Br/ Patrim")
        crescimento = get_valor("Cres. Rec (5a)")

        # Lógica de pontuação
        pontos = 0
        if pl and pl < 15: pontos += 1
        if dy and dy > 5: pontos += 1
        if roe and roe > 12: pontos += 1
        if roic and roic > 10: pontos += 1
        if ev_ebitda and ev_ebitda < 10: pontos += 1
        if margem_liquida and margem_liquida > 10: pontos += 1
        if crescimento and crescimento > 0: pontos += 1
        if divida_patrimonio and divida_patrimonio < 1: pontos += 1

        if pontos >= 7:
            recomendacao = "COMPRAR"
        elif 4 <= pontos < 7:
            recomendacao = "MANTER"
        else:
            recomendacao = "VENDER"

        return jsonify({
            "ticker": ticker.upper(),
            "empresa": empresa,
            "preco": preco,
            "P/L": pl,
            "Dividend Yield": dy,
            "ROE": roe,
            "ROIC": roic,
            "EV/EBITDA": ev_ebitda,
            "Margem Líquida": margem_liquida,
            "Dívida/Patrimônio": divida_patrimonio,
            "Crescimento de Lucro": crescimento,
            "Pontuacao": f"{pontos}/8",
            "Recomendacao": recomendacao
        })

    except Exception as e:
        import traceback
        erro = traceback.format_exc()
        return jsonify({"erro": str(e), "detalhes": erro}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
