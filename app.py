from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os

app = Flask(__name__)
CORS(app)  # ✅ Habilita CORS para todos os domínios

@app.route('/')
def home():
    return {"mensagem": "API Bolsa está online!"}

@app.route('/analise/<ticker>', methods=['GET'])
def analisar_acao(ticker):
    try:
        # 🔐 Token do Brapi
        token = os.getenv("BRAPI_TOKEN")
        brapi_url = f"https://brapi.dev/api/quote/{ticker}?token={token}"
        brapi_resp = requests.get(brapi_url)
        brapi_data = brapi_resp.json()['results'][0]

        preco = brapi_data.get('regularMarketPrice')
        empresa = brapi_data.get('longName')
        pl = brapi_data.get('priceEarnings')
        crescimento_receita = brapi_data.get('earningsGrowth')

        # 🌐 Scraping Fundamentus
        url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker.upper()}"
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).content.decode("ISO-8859-1")
        soup = BeautifulSoup(html, 'html.parser')

        def buscar(label):
            for td in soup.find_all("td"):
                if label.lower() in td.get_text(strip=True).lower():
                    valor = td.find_next_sibling("td").text.strip().replace('%', '').replace('.', '').replace(',', '.')
                    try:
                        return float(valor)
                    except:
                        return None
            return None

        # 📊 Indicadores
        indicadores = {
            "ticker": ticker.upper(),
            "empresa": empresa,
            "preco": preco,
            "P/L": pl,
            "Dividend Yield": buscar("Div. Yield"),
            "ROE": buscar("ROE"),
            "ROIC": buscar("ROIC"),
            "EV/EBITDA": buscar("EV / EBITDA"),
            "Margem Líquida": buscar("Marg. Líquida"),
            "Dívida/Patrimônio": buscar("Div Br/ Patrim"),
            "Crescimento de Receita": crescimento_receita,
            "Setor": buscar("Setor"),
            "Valor de Mercado": brapi_data.get("marketCap"),
            "IPCA": 4.2,
            "Taxa Selic": 10.5,
            "PIB": 2.3,
            "Câmbio": 5.10,
        }

        # 🧠 Sistema de Pontuação
        pontos = 0
        if pl and pl < 10: pontos += 1
        if indicadores['ROE'] and indicadores['ROE'] > 15: pontos += 1
        if indicadores['Dividend Yield'] and indicadores['Dividend Yield'] > 6: pontos += 1
        if indicadores['EV/EBITDA'] and indicadores['EV/EBITDA'] < 8: pontos += 1
        if indicadores['Margem Líquida'] and indicadores['Margem Líquida'] > 20: pontos += 1
        if indicadores['Dívida/Patrimônio'] and indicadores['Dívida/Patrimônio'] < 1: pontos += 1
        if indicadores['ROIC'] and indicadores['ROIC'] > 10: pontos += 1
        if indicadores['Crescimento de Receita']:
            crescimento = indicadores['Crescimento de Receita']
            if crescimento > 10:
                pontos += 1
            elif crescimento > 3:
                pontos += 0.5

        if pontos >= 8:
            recomendacao = "COMPRAR"
        elif pontos >= 5:
            recomendacao = "MANTER"
        else:
            recomendacao = "VENDER"

        indicadores["Pontuacao"] = f"{pontos}/8"
        indicadores["Recomendacao"] = recomendacao

        return jsonify(indicadores)

    except Exception as e:
        return jsonify({"erro": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
