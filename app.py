from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime, timedelta
import logging

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

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

def buscar_statusinvest(soup, label_esperado):
    try:
        cards = soup.find_all("div", class_="top-info")
        for card in cards:
            label = card.find("h3")
            valor = card.find("strong")
            if label and valor and label_esperado.lower() in label.text.strip().lower():
                texto = valor.text.strip().replace('%', '').replace('.', '').replace(',', '.')
                return float(texto)
    except Exception as e:
        logging.warning(f"❌ Erro ao buscar '{label_esperado}': {e}")
    return None

def ajustar_por_perfil(recomendacao, pontos, perfil):
    if perfil == "conservador":
        if pontos >= 7.5:
            return "COMPRAR"
        elif pontos >= 5:
            return "MANTER"
        else:
            return "VENDER"
    elif perfil == "agressivo":
        if pontos >= 6:
            return "COMPRAR"
        elif pontos >= 3.5:
            return "MANTER"
        else:
            return "VENDER"
    return recomendacao  # padrão moderado

@app.route('/')
def home():
    return {"mensagem": "API Bolsa está online!"}

@app.route('/analise/acao/<ticker>', methods=['GET'])
def analisar_acao(ticker):
    if ticker.upper().endswith("11"):
        return jsonify({"erro": "Este código termina com '11'. Use /analise/fii/."}), 400

    perfil = request.args.get("perfil", "moderado")
    cache_key = f"acao_{ticker.upper()}_{perfil}"
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

        url = f"https://statusinvest.com.br/acoes/{ticker.lower()}"
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).text
        soup = BeautifulSoup(html, 'html.parser')

        indicadores = {
            "ticker": ticker.upper(),
            "empresa": empresa,
            "preco": preco,
            "P/L": buscar_statusinvest(soup, "P/L"),
            "Dividend Yield": buscar_statusinvest(soup, "Dividendo"),
            "ROE": buscar_statusinvest(soup, "ROE"),
            "ROIC": buscar_statusinvest(soup, "ROIC"),
            "EV/EBITDA": buscar_statusinvest(soup, "EV/EBITDA"),
            "Margem Líquida": buscar_statusinvest(soup, "M. Líquida"),
            "Crescimento de Receita": buscar_statusinvest(soup, "CAGR Receitas")
        }

        pontos = 0
        explicacoes = []

        pl = indicadores["P/L"]
        if pl and 5 <= pl <= 15:
            pontos += 1.5
            explicacoes.append("✅ P/L ideal entre 5 e 15")
        else:
            explicacoes.append("⚠️ P/L fora da faixa ideal")

        if indicadores['ROE'] and indicadores['ROE'] > 10:
            pontos += 1
            explicacoes.append("✅ ROE acima de 10%")
        if indicadores['Dividend Yield'] and indicadores['Dividend Yield'] > 4:
            pontos += 1
            explicacoes.append("✅ Dividend Yield acima de 4%")
        if indicadores['EV/EBITDA'] and 0 < indicadores['EV/EBITDA'] < 8:
            pontos += 1
            explicacoes.append("✅ EV/EBITDA saudável")
        if indicadores['Margem Líquida'] and indicadores['Margem Líquida'] > 10:
            pontos += 1
            explicacoes.append("✅ Margem Líquida maior que 10%")
        if indicadores['ROIC'] and indicadores['ROIC'] > 8:
            pontos += 1
            explicacoes.append("✅ ROIC acima de 8%")
        if indicadores['Crescimento de Receita'] and indicadores['Crescimento de Receita'] > 10:
            pontos += 0.5
            explicacoes.append("✅ Crescimento de Receita > 10%")

        if pl and pl > 60:
            recomendacao = "VENDER"
        elif pontos >= 6.5:
            recomendacao = "COMPRAR"
        elif pontos >= 4:
            recomendacao = "MANTER"
        else:
            recomendacao = "VENDER"

        recomendacao = ajustar_por_perfil(recomendacao, pontos, perfil)

        indicadores["Pontuacao"] = f"{round(pontos, 2)}/7"
        indicadores["Recomendacao"] = recomendacao
        indicadores["Explicacao"] = explicacoes
        indicadores["Perfil"] = perfil

        set_cache(cache_key, indicadores)
        return jsonify(indicadores)

    except Exception as e:
        import traceback
        logging.error(f"Erro na análise da ação {ticker}: {e}")
        return jsonify({"erro": str(e), "trace": traceback.format_exc()}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
