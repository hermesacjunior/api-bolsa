from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return {"mensagem": "API Bolsa está online!"}


@app.route('/analise/acao/<ticker>', methods=['GET'])
def analisar_acao(ticker):
    try:
        token = os.getenv("BRAPI_TOKEN")
        brapi_url = f"https://brapi.dev/api/quote/{ticker}?token={token}"
        brapi_resp = requests.get(brapi_url)
        brapi_data = brapi_resp.json()['results'][0]

        preco = brapi_data.get('regularMarketPrice')
        empresa = brapi_data.get('longName')
        pl = brapi_data.get('priceEarnings')
        crescimento_receita = brapi_data.get('earningsGrowth')
        valor_mercado = brapi_data.get("marketCap")

        url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker.upper()}"
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).content.decode("ISO-8859-1")
        soup = BeautifulSoup(html, 'html.parser')

        def buscar(label):
            for td in soup.find_all("td"):
                if label.lower() in td.text.lower():
                    next_td = td.find_next_sibling("td")
                    if next_td:
                        valor = next_td.text.strip().replace('%', '').replace('.', '').replace(',', '.')
                        try:
                            return float(valor)
                        except:
                            return None
            return None

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
            "Crescimento de Receita": buscar("Cres. Rec (5a)"),
        }

        pontos = 0
        if pl and pl < 10: pontos += 1
        if indicadores['ROE'] and indicadores['ROE'] > 15: pontos += 1
        if indicadores['Dividend Yield'] and indicadores['Dividend Yield'] > 6: pontos += 1
        if indicadores['EV/EBITDA'] and indicadores['EV/EBITDA'] < 8: pontos += 1
        if indicadores['Margem Líquida'] and indicadores['Margem Líquida'] > 20: pontos += 1
        if indicadores['Dívida/Patrimônio'] and indicadores['Dívida/Patrimônio'] < 1: pontos += 1
        if indicadores['ROIC'] and indicadores['ROIC'] > 10: pontos += 1
        if crescimento_receita:
            if crescimento_receita > 0.10: pontos += 1
            elif crescimento_receita > 0.03: pontos += 0.5

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
        import traceback
        return jsonify({"erro": str(e), "trace": traceback.format_exc()}), 500


@app.route('/analise/fii/<ticker>', methods=['GET'])
def analisar_fii(ticker):
    try:
        url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker.upper()}"
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).content.decode("ISO-8859-1")
        soup = BeautifulSoup(html, 'html.parser')

        def buscar(label):
            for td in soup.find_all("td"):
                if label.lower() in td.text.lower():
                    next_td = td.find_next_sibling("td")
                    if next_td:
                        valor = next_td.text.strip().replace('%', '').replace('.', '').replace(',', '.')
                        try:
                            return float(valor)
                        except:
                            return None
            return None

        dy = buscar("Div. Yield")
        pvp = buscar("P/VP")
        vacancia = buscar("Vacância Média")
        caprate = buscar("Cap Rate")
        liquidez = buscar("Liq. Média Diária")
        hist = buscar("Últ Rendimento")  # Pode ser nota de 1 a 5 manual, aqui simulado

        pontos = 0
        if dy and dy > 7: pontos += 1
        if pvp and pvp < 1.05: pontos += 1
        if vacancia and vacancia < 10: pontos += 1
        if caprate and caprate > 8: pontos += 1
        if liquidez and liquidez > 500: pontos += 1
        if hist and hist > 0.9: pontos += 1  # Simulando histórico bom

        if pontos >= 5:
            recomendacao = "COMPRAR"
        elif pontos >= 3:
            recomendacao = "MANTER"
        else:
            recomendacao = "VENDER"

        return jsonify({
            "ticker": ticker.upper(),
            "empresa": f"FII {ticker.upper()}",
            "preco": buscar("Cotação"),
            "Dividend Yield": dy,
            "P/VP": pvp,
            "Vacância": vacancia,
            "Cap Rate": caprate,
            "Liquidez Média": liquidez,
            "Histórico de Dividendos": hist,
            "Pontuacao": f"{pontos}/6",
            "Recomendacao": recomendacao
        })

    except Exception as e:
        import traceback
        return jsonify({"erro": str(e), "trace": traceback.format_exc()}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
