from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
import os
import re

app = Flask(__name__)

@app.route('/')
def home():
    return {"mensagem": "API de Análise de Ações está online!"}

@app.route('/analise/<ticker>', methods=['GET'])
def analisar_acao(ticker):
    token = os.getenv("BRAPI_TOKEN")
    brapi_url = f"https://brapi.dev/api/quote/{ticker}?token={token}"

    try:
        # Busca dados do Brapi
        brapi_resp = requests.get(brapi_url)
        brapi_data = brapi_resp.json()['results'][0]

        preco = brapi_data.get('regularMarketPrice')
        empresa = brapi_data.get('longName')
        setor = brapi_data.get('sector') or 'N/A'
        valor_mercado = brapi_data.get('marketCap')

        # Busca dados do Fundamentus
        url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker.upper()}"
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).content.decode("ISO-8859-1")
        soup = BeautifulSoup(html, 'html.parser')

        # Função para buscar valores com precisão
        def get_valor(label):
            for tr in soup.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) >= 2:
                    titulo = tds[0].get_text(strip=True).lower()
                    if label.lower() in titulo:
                        bruto = tds[1].get_text(strip=True)
                        numero = re.sub(r'[^\d,.-]', '', bruto).replace('.', '').replace(',', '.')
                        try:
                            return float(numero)
                        except:
                            return None
            return None

        # Indicadores
        pl = get_valor("P/L")
        dy = get_valor("Div. Yield")
        roe = get_valor("ROE")
        roic = get_valor("ROIC")
        ev_ebitda = get_valor("EV / EBITDA")
        margem_liquida = get_valor("Marg. Líquida")
        divida_patrimonio = get_valor("Div Br/ Patrim")
        crescimento = get_valor("Cres. Rec (5a)")

        # Dados macro fixos
        ipca = 4.2
        selic = 10.5
        pib = 2.3
        cambio = 5.10

        # Pontuação e recomendação
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
            "Setor": setor,
            "Valor de Mercado": valor_mercado,
            "IPCA": ipca,
            "Taxa Selic": selic,
            "PIB": pib,
            "Câmbio": cambio,
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
