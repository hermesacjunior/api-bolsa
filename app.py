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

# Cache simples em memória (5 minutos)
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

@app.route('/')
def home():
    return {"mensagem": "API Bolsa está online!"}


@app.route('/analise/fii/<ticker>', methods=['GET'])
def analisar_fii(ticker):
    cache_key = f"fii_{ticker.upper()}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)

    try:
        url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker.upper()}"
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).content.decode("ISO-8859-1")
        soup = BeautifulSoup(html, 'html.parser')

        def buscar(label_esperado):
            for td in soup.find_all("td"):
                if td.get_text(strip=True) == label_esperado:
                    td_valor = td.find_next_sibling("td")
                    if td_valor:
                        valor_str = td_valor.text.strip().replace('%', '').replace('.', '').replace(',', '.')
                        try:
                            return float(valor_str)
                        except:
                            logging.warning(f"⚠️ Erro ao converter valor de '{label_esperado}': {valor_str}")
                            return None
            logging.warning(f"⚠️ Indicador não encontrado: {label_esperado}")
            return None

        # Indicadores com nomes exatos do HTML do Fundamentus
        dy = buscar("Div. yield")
        pvp = buscar("P/VP")
        vacancia = buscar("Vacância média")
        caprate = buscar("Cap rate")
        liquidez = buscar("Liq. média diária")
        hist = buscar("Últ. rendimento")
        preco = buscar("Cotação")

        pontos = 0
        if dy and dy > 7: pontos += 1
        if pvp and pvp < 1.05: pontos += 1
        if vacancia and vacancia < 10: pontos += 1
        if caprate and caprate > 8: pontos += 1
        if liquidez and liquidez > 500: pontos += 1
        if hist and hist > 0.9: pontos += 1  # Simula "bom histórico"

        if pontos >= 5:
            recomendacao = "COMPRAR"
        elif pontos >= 3:
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
            "Pontuacao": f"{pontos}/6",
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
