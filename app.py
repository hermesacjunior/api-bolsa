from flask_cors import CORS
from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
import os

app = Flask(__name__)
CORS(app, origins=["https://bolsabrasilinsights.lovable.app"])

@app.route('/')
def home():
    return {"mensagem": "API está online!"}

@app.route('/analise/<ticker>', methods=['GET'])
def analisar_acao(ticker):
    token = os.getenv("BRAPI_TOKEN")
    brapi_url = f"https://brapi.dev/api/quote/{ticker}?token={token}"

    try:
        # Requisição à Brapi
        brapi_resp = requests.get(brapi_url)
        brapi_data = brapi_resp.json()['results'][0]

        pl = brapi_data.get('priceEarnings')
        preco = brapi_data.get('regularMarketPrice')
        empresa = brapi_data.get('longName')
        valor_mercado = brapi_data.get('marketCap')

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
            return None

        roe = get_valor("ROE")
        roic = get_valor("ROIC")
        ev_ebitda = get_valor("EV / EBITDA")
        margem_liquida = get_valor("Marg. Líquida")
        divida_patrimonio = get_valor("Div Br/ Patrim")
        crescimento = get_valor("Cres. Rec (5a)")
        setor = get_valor("Setor")

        # Indicadores fixos
        ipca = 4.2
        selic = 10.5
        pib = 2.3
        cambio = 5.10

        # Cálculo de pontuação
        pontos = 0
        if pl and pl < 10: pontos += 1
        if roe and roe > 15: pontos += 1
        if roic and roic > 10: pontos += 1
        if ev_ebitda and ev_ebitda < 8: pontos += 1
        if margem_liquida and margem_liquida > 20: pontos += 1
        if divida_patrimonio and divida_patrimonio < 1: pontos += 1
        if crescimento and crescimento > 10: pontos += 1

        if pontos >= 6:
            recomendacao = "COMPRA"
        elif 4 <= pontos < 6:
            recomendacao = "MANTER"
        else:
            recomendacao = "VENDER"

        return jsonify({
            "ticker": ticker.upper(),
            "empresa": empresa,
            "preco": preco,
            "P/L": pl,
            "ROE": roe,
            "ROIC": roic,
            "EV/EBITDA": ev_ebitda,
            "Margem Líquida": margem_liquida,
            "Dívida/Patrimônio": divida_patrimonio,
            "Crescimento de Receita": crescimento,
            "Valor de Mercado": valor_mercado,
            "Setor": setor if setor else "N/A",
            "IPCA": ipca,
            "Taxa Selic": selic,
            "PIB": pib,
            "Câmbio": cambio,
            "Pontuacao": f"{pontos}/7",
            "Recomendacao": recomendacao
        })

    except Exception as e:
        import traceback
        return jsonify({"erro": str(e), "detalhes": traceback.format_exc()}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
