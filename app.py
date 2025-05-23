from flask import Flask, jsonify
import requests
import os

app = Flask(__name__)

@app.route('/')
def home():
    return {"mensagem": "API de Análise de Ações está online!"}

@app.route('/analise/<ticker>', methods=['GET'])
def analisar_acao(ticker):
    token = os.getenv("BRAPI_TOKEN")
    brapi_url = f"https://brapi.dev/api/quote/{ticker}?modules=summaryProfile,financialData&token={token}"

    try:
        # Consome a API da Brapi
        response = requests.get(brapi_url)
        data = response.json()['results'][0]

        # Indicadores disponíveis
        preco = data.get('regularMarketPrice')
        empresa = data.get('longName')
        setor = data.get('sector') or 'N/A'
        valor_mercado = data.get('marketCap')
        pl = data.get('priceEarningsRatio')
        dy = data.get('dividendYield')
        roe = data.get('returnOnEquity')
        roic = data.get('returnOnInvestedCapital')
        crescimento = data.get('earningsGrowth') or data.get('revenueGrowth')

        # Indicadores macroeconômicos fixos
        ipca = 4.2
        selic = 10.5
        pib = 2.3
        cambio = 5.10

        # Pontuação
        pontos = 0
        if pl and pl < 15: pontos += 1
        if dy and dy > 0.05: pontos += 1
        if roe and roe > 0.12: pontos += 1
        if roic and roic > 0.10: pontos += 1
        if crescimento and crescimento > 0: pontos += 1

        if pontos >= 4:
            recomendacao = "COMPRAR"
        elif pontos >= 2:
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
            "Crescimento de Receita": crescimento,
            "Setor": setor,
            "Valor de Mercado": valor_mercado,
            "IPCA": ipca,
            "Taxa Selic": selic,
            "PIB": pib,
            "Câmbio": cambio,
            "Pontuacao": f"{pontos}/5",
            "Recomendacao": recomendacao
        })

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
