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
    if not token:
        return jsonify({"erro": "Token BRAPI não encontrado."}), 500

    url = f"https://brapi.dev/api/quote/{ticker}?token={token}"

    try:
        response = requests.get(url)
        data = response.json()

        if "results" not in data or not data["results"]:
            return jsonify({"erro": "Ticker não encontrado."}), 400

        info = data["results"][0]

        preco = info.get("regularMarketPrice")
        empresa = info.get("longName")
        setor = info.get("sector")
        valor_mercado = info.get("marketCap")

        pl = info.get("priceEarningsRatio")
        dy = info.get("dividendYield")
        roe = info.get("returnOnEquity")
        roic = info.get("returnOnInvestedCapital")
        crescimento = info.get("revenueGrowth") or info.get("earningsGrowth")

        ipca = 4.2
        selic = 10.5
        pib = 2.3
        cambio = 5.10

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
            "Setor": setor,
            "Valor de Mercado": valor_mercado,
            "P/L": pl,
            "Dividend Yield": dy,
            "ROE": roe,
            "ROIC": roic,
            "Crescimento de Receita": crescimento,
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
