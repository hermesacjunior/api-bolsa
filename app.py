from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime, timedelta
import logging

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)

# Cache simples
cache = {}
TEMPO_CACHE = timedelta(minutes=5)

def get_cache(key):
    if key in cache:
        valor, expiracao = cache[key]
        if datetime.now() < expiracao:
            logging.info(f"✅ Cache HIT: {key}")
            return valor
    return None

def set_cache(key, valor):
    cache[key] = (valor, datetime.now() + TEMPO_CACHE)
    logging.info(f"🆕 Cache SET: {key}")

def buscar(soup, label_esperado):
    label_esperado = label_esperado.lower()
    for td in soup.find_all("td"):
        texto = td.get_text(strip=True).lower()
        if label_esperado in texto:
            td_valor = td.find_next_sibling("td")
            if td_valor:
                valor_str = td_valor.text.strip().replace('%', '').replace('.', '').replace(',', '.')
                try:
                    return float(valor_str)
                except:
                    logging.warning(f"⚠️ Erro ao converter '{td_valor.text.strip()}'")
                    return None
    logging.warning(f"❌ Indicador não encontrado: {label_esperado}")
    return None

@app.route('/')
def home():
    return {"mensagem": "API Bolsa está online!"}

# ✅ Proteção: se terminar com 11, bloqueia como ação
@app.route('/analise/acao/<ticker>', methods=['GET'])
def analisar_acao(ticker):
    if ticker.upper().endswith("11"):
        return jsonify({"erro": "Este código termina com '11' e provavelmente é um Fundo Imobiliário. Use /analise/fii/."}), 400

    cache_key = f"acao_{ticker.upper()}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)

    try:
        token = os.getenv("BRAPI_TOKEN")
        brapi_url = f"https://brapi.dev/api/quote/{ticker.upper()}"
        if token:
            brapi_url += f"?token={token}"

        brapi_resp = requests.get(brapi_url)
        brapi_data = brapi_resp.json()
        if 'results' not in brapi_data or not brapi_data['results']:
            return jsonify({"erro": "Ticker não encontrado na Brapi."}), 404

        brapi_data = brapi_data['results'][0]

        preco = brapi_data.get('regularMarketPrice')
        empresa = brapi_data.get('longName')
        pl = brapi_data.get('priceEarnings')
        crescimento_receita = brapi_data.get('earningsGrowth')
        valor_mercado = brapi_data.get("marketCap")

        url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker.upper()}"
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).content.decode("ISO-8859-1")
        soup = BeautifulSoup(html, 'html.parser')

        indicadores = {
            "ticker": ticker.upper(),
            "empresa": empresa,
            "preco": preco,
            "P/L": pl,
            "Dividend Yield": buscar(soup, "Div. yield"),
            "ROE": buscar(soup, "ROE"),
            "ROIC": buscar(soup, "ROIC"),
            "EV/EBITDA": buscar(soup, "EV / EBITDA"),
            "Margem Líquida": buscar(soup, "Marg. líquida"),
            "Dívida/Patrimônio": buscar(soup, "Div br/ patrim"),
            "Crescimento de Receita": buscar(soup, "Cres. rec (5a)"),
            "Valor de Mercado": valor_mercado
        }

        pontos = 0
        if pl and pl < 10: pontos += 1.5
        if indicadores['ROE'] and indicadores['ROE'] > 15: pontos += 1
        if indicadores['Dividend Yield'] and indicadores['Dividend Yield'] > 6: pontos += 1
        if indicadores['EV/EBITDA'] and indicadores['EV/EBITDA'] < 8: pontos += 1
        if indicadores['Margem Líquida'] and indicadores['Margem Líquida'] > 20: pontos += 1
        if indicadores['Dívida/Patrimônio'] and indicadores['Dívida/Patrimônio'] < 1: pontos += 1
        if indicadores['ROIC'] and indicadores['ROIC'] > 10: pontos += 1
        if crescimento_receita:
            if crescimento_receita > 0.10:
                pontos += 0.5
            elif crescimento_receita > 0.03:
                pontos += 0.25

        if pl and pl > 60:
            recomendacao = "VENDER"
        elif pontos >= 7:
            recomendacao = "COMPRAR"
        elif pontos >= 4.5:
            recomendacao = "MANTER"
        else:
            recomendacao = "VENDER"

        indicadores["Pontuacao"] = f"{round(pontos, 2)}/8"
        indicadores["Recomendacao"] = recomendacao

        set_cache(cache_key, indicadores)
        return jsonify(indicadores)

    except Exception as e:
        import traceback
        logging.error(f"Erro na análise da ação {ticker}: {e}")
        return jsonify({"erro": str(e), "trace": traceback.format_exc()}), 500

# ✅ Proteção: se NÃO terminar com 11, bloqueia como FII
@app.route('/analise/fii/<ticker>', methods=['GET'])
def analisar_fii(ticker):
    if not ticker.upper().endswith("11"):
        return jsonify({"erro": "Este código não termina com '11'. Provavelmente é uma ação. Use /analise/acao/."}), 400

    cache_key = f"fii_{ticker.upper()}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)

    try:
        url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker.upper()}"
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).content.decode("ISO-8859-1")
        soup = BeautifulSoup(html, 'html.parser')

        preco = buscar(soup, "Cotação")
        dy = buscar(soup, "Div. yield")
        pvp = buscar(soup, "P/VP")
        caprate = buscar(soup, "Cap rate")
        vacancia = buscar(soup, "Vacância média")
        liquidez = buscar(soup, "Vol $ méd")
        hist = buscar(soup, "Dividendo/cota")

        pontos = 0
        if dy and dy > 7: pontos += 1.5
        if pvp and pvp < 1.05: pontos += 1
        if caprate and caprate > 8: pontos += 1
        if vacancia is not None and vacancia < 10: pontos += 1
        if liquidez and liquidez > 500: pontos += 0.75
        if hist and hist > 0.9: pontos += 0.75

        if dy and dy < 5:
            recomendacao = "VENDER"
        elif vacancia and vacancia > 25:
            recomendacao = "VENDER"
        elif caprate == 0:
            recomendacao = "VENDER"
        elif pontos >= 5:
            recomendacao = "COMPRAR"
        elif pontos >= 3.5:
            recomendacao = "MANTER"
        else:
            recomendacao = "VENDER"

        resultado = {
            "ticker": ticker.upper(),
            "empresa": f"FII {ticker.upper()}",
            "preco": preco,
            "Dividend Yield": dy,
            "P/VP": pvp,
            "Vacância": vacancia,
            "Cap Rate": caprate,
            "Liquidez Média": liquidez,
            "Histórico de Dividendos": hist,
            "Pontuacao": f"{round(pontos, 2)}/6",
            "Recomendacao": recomendacao
        }

        set_cache(cache_key, resultado)
        return jsonify(resultado)

    except Exception as e:
        import traceback
        logging.error(f"Erro na análise do FII {ticker}: {e}")
        return jsonify({"erro": str(e), "trace": traceback.format_exc()}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
